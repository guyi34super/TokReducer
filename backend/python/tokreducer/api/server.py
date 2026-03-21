"""FastAPI REST API for TokReducer.

Provides:
- Original endpoints: /compress, /decompress, /chat, /health
- OpenAI-compatible proxy: POST /v1/chat/completions
- Dashboard API: GET/POST /api/config, GET /api/logs, GET /api/usage
- Auth: Firebase ID token verification on all routes except /health
- Agreement: GET/POST /api/agreement
- Stripe: POST /api/stripe/create-checkout, POST /api/stripe/webhook, GET /api/subscription
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import unquote

import httpx
import firebase_admin
from firebase_admin import auth as fb_auth, credentials, firestore
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware

from tokreducer.compressor import TokReducer, Level
from tokreducer.rust_compressor import RustCompressor

logger = logging.getLogger("tokreducer")

_RUST_COMPRESSOR_URL = os.environ.get("RUST_COMPRESSOR_URL", "").strip()


def _get_compressor(level: Level | int, bidirectional: bool = False):
    """Return RustCompressor if RUST_COMPRESSOR_URL is set, else TokReducer."""
    if _RUST_COMPRESSOR_URL:
        return RustCompressor(level=level, bidirectional=bidirectional, base_url=_RUST_COMPRESSOR_URL)
    return TokReducer(level=level, bidirectional=bidirectional)

# ---------------------------------------------------------------------------
# Firebase init (optional when no credentials, e.g. in Docker without ADC)
# Supports: GOOGLE_APPLICATION_CREDENTIALS (file path) or
#           GOOGLE_APPLICATION_CREDENTIALS_JSON (JSON string, e.g. from secrets manager)
# ---------------------------------------------------------------------------

_FIREBASE_CRED_PATH = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
_FIREBASE_CRED_JSON = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()

_db: firestore.Client | None = None
if not firebase_admin._apps:
    if _FIREBASE_CRED_JSON:
        try:
            cred_dict = json.loads(_FIREBASE_CRED_JSON)
            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)
            _db = firestore.client()
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("Invalid GOOGLE_APPLICATION_CREDENTIALS_JSON: %s. Firebase disabled.", e)
    elif _FIREBASE_CRED_PATH and os.path.isfile(_FIREBASE_CRED_PATH):
        cred = credentials.Certificate(_FIREBASE_CRED_PATH)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
    else:
        logger.warning(
            "Firebase credentials not found (GOOGLE_APPLICATION_CREDENTIALS or GOOGLE_APPLICATION_CREDENTIALS_JSON). "
            "Auth and Firestore features disabled."
        )

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="TokReducer API",
    version="1.0.0",
    description="Token Compression Protocol for Large Language Models",
)

_FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")
_ALLOWED_ORIGINS = [
    _FRONTEND_URL,
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Security middleware: secure headers
# ---------------------------------------------------------------------------


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https://*.firebaseapp.com https://*.googleapis.com; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response


app.add_middleware(SecureHeadersMiddleware)


# ---------------------------------------------------------------------------
# Security middleware: WAF-like request filtering
# ---------------------------------------------------------------------------

_PATH_TRAVERSAL_RE = re.compile(r"(\.\./|\.\.%2[fF]|%00)")
_SQL_INJECTION_RE = re.compile(
    r"(union\s+select|or\s+1\s*=\s*1|drop\s+table|;\s*--)",
    re.IGNORECASE,
)
_MAX_URL_LENGTH = 2048


class RequestFilterMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        raw_path = request.url.path
        decoded_path = unquote(raw_path)
        query = request.url.query or ""
        full_url = f"{raw_path}?{query}" if query else raw_path

        if len(full_url) > _MAX_URL_LENGTH:
            logger.warning("WAF: URL too long (%d chars) from %s", len(full_url), _get_client_ip(request))
            return JSONResponse(status_code=400, content={"detail": "URL too long"})

        if _PATH_TRAVERSAL_RE.search(decoded_path) or _PATH_TRAVERSAL_RE.search(query):
            logger.warning("WAF: path traversal attempt from %s: %s", _get_client_ip(request), decoded_path)
            return JSONResponse(status_code=400, content={"detail": "Suspicious request blocked"})

        if _SQL_INJECTION_RE.search(query):
            logger.warning("WAF: SQL injection attempt from %s: %s", _get_client_ip(request), query)
            return JSONResponse(status_code=400, content={"detail": "Suspicious request blocked"})

        return await call_next(request)


app.add_middleware(RequestFilterMiddleware)


# ---------------------------------------------------------------------------
# Security middleware: CSRF protection (Origin/Referer validation)
# ---------------------------------------------------------------------------

_CSRF_EXEMPT_PATHS = {"/api/stripe/webhook"}
_STATE_CHANGING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        if request.method not in _STATE_CHANGING_METHODS:
            return await call_next(request)

        if request.url.path in _CSRF_EXEMPT_PATHS:
            return await call_next(request)

        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")

        if origin:
            if not any(origin == allowed for allowed in _ALLOWED_ORIGINS):
                logger.warning("CSRF: rejected origin %s from %s", origin, _get_client_ip(request))
                return JSONResponse(status_code=403, content={"detail": "Origin not allowed"})
        elif referer:
            if not any(referer.startswith(allowed) for allowed in _ALLOWED_ORIGINS):
                logger.warning("CSRF: rejected referer %s from %s", referer, _get_client_ip(request))
                return JSONResponse(status_code=403, content={"detail": "Referer not allowed"})

        return await call_next(request)


app.add_middleware(CSRFMiddleware)


# ---------------------------------------------------------------------------
# Security middleware: IP rate limiter (token bucket, 60 req/min per IP)
# ---------------------------------------------------------------------------

_RATE_LIMIT = 60
_RATE_WINDOW = 60.0
_rate_buckets: dict[str, list[float]] = defaultdict(lambda: [_RATE_LIMIT, time.monotonic()])


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        ip = _get_client_ip(request)
        now = time.monotonic()
        bucket = _rate_buckets[ip]
        elapsed = now - bucket[1]
        bucket[0] = min(_RATE_LIMIT, bucket[0] + elapsed * (_RATE_LIMIT / _RATE_WINDOW))
        bucket[1] = now
        if bucket[0] < 1.0:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again shortly."},
            )
        bucket[0] -= 1.0
        return await call_next(request)


app.add_middleware(RateLimitMiddleware)


# ---------------------------------------------------------------------------
# Security middleware: request body size limit (1 MB)
# ---------------------------------------------------------------------------

_MAX_BODY_BYTES = 1_048_576


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": "Request body too large (max 1 MB)."},
            )
        return await call_next(request)


app.add_middleware(BodySizeLimitMiddleware)

# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

_PUBLIC_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}


async def _get_uid(request: Request) -> str:
    """Extract and verify Firebase ID token, return uid."""
    if request.url.path in _PUBLIC_PATHS:
        return ""

    if _db is None:
        raise HTTPException(
            status_code=503,
            detail="Firebase not configured. Set GOOGLE_APPLICATION_CREDENTIALS to enable auth.",
        )

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[7:]
    try:
        decoded = fb_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


# ---------------------------------------------------------------------------
# Firestore helpers
# ---------------------------------------------------------------------------

_DEFAULT_CONFIG: dict[str, Any] = {
    "provider": "openai",
    "api_key": "",
    "model": "gpt-4o",
    "level": 2,
    "upstream_url": "https://api.openai.com",
}

_CONFIG_DATA_DOC = "data"  # users/{uid}/config/data: { configs: [...], selected_id: str | None }

_PROVIDER_DEFAULTS: dict[str, str] = {
    "openai": "https://api.openai.com",
    "anthropic": "https://api.anthropic.com",
    "ollama": "http://localhost:11434",
}

FREE_TIER_LIMIT = 2
PRO_DAILY_LIMIT = 10


def _user_ref(uid: str):
    if _db is None:
        raise HTTPException(
            status_code=503,
            detail="Firebase not configured. Set GOOGLE_APPLICATION_CREDENTIALS.",
        )
    return _db.collection("users").document(uid)


_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[a-zA-Z]{2,}$")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _strip_control_chars(s: str) -> str:
    return _CONTROL_CHAR_RE.sub("", s)


def _ensure_user_doc(uid: str, email: str = "") -> dict[str, Any]:
    """Get or create the user document."""
    ref = _user_ref(uid)
    doc = ref.get()
    if doc.exists:
        return doc.to_dict()  # type: ignore[return-value]
    if email and not _EMAIL_RE.match(email):
        email = ""
    data = {
        "email": email,
        "requests_used": 0,
        "agreement_accepted_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tier": "free",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "daily_requests": 0,
        "daily_reset_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    ref.set(data)
    return data


def _config_data_ref(uid: str):
    return _user_ref(uid).collection("config").document(_CONFIG_DATA_DOC)


def _config_current_ref(uid: str):
    return _user_ref(uid).collection("config").document("current")


def _load_config(uid: str) -> dict[str, Any]:
    """Return the selected config for the proxy (full api_key)."""
    data_ref = _config_data_ref(uid)
    doc = data_ref.get()
    if doc.exists:
        data = doc.to_dict() or {}
        configs = data.get("configs") or []
        selected_id = data.get("selected_id")
        if selected_id and configs:
            for c in configs:
                if c.get("id") == selected_id:
                    return {**_DEFAULT_CONFIG, **c}
    # Legacy: single config at config/current
    current_ref = _config_current_ref(uid)
    leg = current_ref.get()
    if leg.exists:
        return {**_DEFAULT_CONFIG, **leg.to_dict()}  # type: ignore[arg-type]
    return dict(_DEFAULT_CONFIG)


def _get_config_list(uid: str) -> tuple[list[dict[str, Any]], str | None]:
    """Return (configs with masked api_key, selected_id)."""
    data_ref = _config_data_ref(uid)
    doc = data_ref.get()
    if doc.exists:
        data = doc.to_dict() or {}
        configs = list(data.get("configs") or [])
        selected_id = data.get("selected_id")
        out = []
        for c in configs:
            masked = dict(c)
            key = masked.get("api_key", "")
            if key and len(key) > 8:
                masked["api_key"] = key[:4] + "..." + key[-4:]
            out.append(masked)
        return (out, selected_id)
    # Legacy: build one entry from config/current
    current_ref = _config_current_ref(uid)
    leg = current_ref.get()
    if leg.exists:
        d = leg.to_dict() or {}
        cid = d.get("id") or str(uuid.uuid4())
        masked = dict(d)
        key = masked.get("api_key", "")
        if key and len(key) > 8:
            masked["api_key"] = key[:4] + "..." + key[-4:]
        masked["id"] = cid
        masked.setdefault("name", "Default")
        return ([masked], cid)
    return ([], None)


def _save_config_list(uid: str, configs: list[dict[str, Any]], selected_id: str | None) -> None:
    _config_data_ref(uid).set({"configs": configs, "selected_id": selected_id})


def _get_full_config_list(uid: str) -> list[dict[str, Any]]:
    """Return configs with real api_key (for internal update). Migrate from legacy if needed."""
    data_ref = _config_data_ref(uid)
    doc = data_ref.get()
    if doc.exists:
        return list((doc.to_dict() or {}).get("configs") or [])
    current_ref = _config_current_ref(uid)
    leg = current_ref.get()
    if leg.exists:
        d = leg.to_dict() or {}
        d["id"] = d.get("id") or str(uuid.uuid4())
        d.setdefault("name", "Default")
        return [d]
    return []


def _add_log_entry(
    uid: str,
    *,
    model: str,
    original_tokens: int,
    compressed_tokens: int,
    reduction_pct: float,
    output_tokens: int,
    latency_ms: int,
    status: str,
    ip: str = "",
    user_agent: str = "",
    endpoint: str = "",
) -> None:
    _user_ref(uid).collection("logs").add({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "original_tokens": original_tokens,
        "compressed_tokens": compressed_tokens,
        "reduction_pct": round(reduction_pct, 1),
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
        "status": status,
        "ip": ip,
        "user_agent": user_agent,
        "endpoint": endpoint,
    })


def _get_logs(uid: str, limit: int = 200) -> list[dict[str, Any]]:
    docs = (
        _user_ref(uid)
        .collection("logs")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]


def _add_audit_log(
    uid: str,
    *,
    action: str,
    ip: str = "",
    user_agent: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    sanitized_details = {}
    for k, v in (details or {}).items():
        sanitized_details[k] = _strip_control_chars(str(v)) if isinstance(v, str) else v
    _user_ref(uid).collection("audit_logs").add({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "action": _strip_control_chars(action),
        "ip": ip,
        "user_agent": _strip_control_chars(user_agent),
        "details": sanitized_details,
    })


def _get_audit_logs(uid: str, limit: int = 200) -> list[dict[str, Any]]:
    docs = (
        _user_ref(uid)
        .collection("audit_logs")
        .order_by("timestamp", direction=firestore.Query.DESCENDING)
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]


def _req_meta(request: Request) -> tuple[str, str]:
    """Extract IP and user-agent from a request."""
    return _get_client_ip(request), request.headers.get("user-agent", "")


def _check_and_increment_usage(uid: str) -> dict[str, Any]:
    """Check usage limits and increment. Returns usage info or raises 403."""
    ref = _user_ref(uid)
    doc = ref.get()
    if not doc.exists:
        _ensure_user_doc(uid)
        doc = ref.get()

    data = doc.to_dict()  # type: ignore[union-attr]
    tier = data.get("tier", "free")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if tier == "pro":
        daily_reset = data.get("daily_reset_date", "")
        daily_used = data.get("daily_requests", 0)
        if daily_reset != today:
            daily_used = 0
            ref.update({"daily_requests": 0, "daily_reset_date": today})
        if daily_used >= PRO_DAILY_LIMIT:
            raise HTTPException(
                status_code=429,
                detail=f"Daily limit reached ({PRO_DAILY_LIMIT} requests/day). Resets at midnight UTC.",
            )
        ref.update({
            "daily_requests": firestore.Increment(1),
            "daily_reset_date": today,
        })
        return {"tier": "pro", "daily_used": daily_used + 1, "daily_limit": PRO_DAILY_LIMIT}

    used = data.get("requests_used", 0)
    if used >= FREE_TIER_LIMIT:
        raise HTTPException(
            status_code=403,
            detail="Free tier limit reached (2 lifetime requests). Upgrade to Pro for $5/month.",
        )
    ref.update({"requests_used": firestore.Increment(1)})
    return {"tier": "free", "used": used + 1, "limit": FREE_TIER_LIMIT}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CompressRequest(BaseModel):
    prompt: str = Field(max_length=100_000)
    level: int = Field(default=2, ge=0, le=3)


class CompressResponse(BaseModel):
    compressed: str
    original_tokens: int
    compressed_tokens: int
    reduction_pct: float


class DecompressRequest(BaseModel):
    text: str = Field(max_length=100_000)


class DecompressResponse(BaseModel):
    decompressed: str


class ChatRequest(BaseModel):
    prompt: str = Field(max_length=100_000)
    level: int = Field(default=2, ge=0, le=3)
    provider: str = Field(default="openai", max_length=64)
    model: str = Field(default="gpt-4o", max_length=128)
    api_key: str | None = Field(default=None, max_length=256)


class ChatResponse(BaseModel):
    response: str
    original_tokens: int
    compressed_tokens: int
    reduction_pct: float
    output_tokens: int


class ConfigPayload(BaseModel):
    provider: str = Field(default="openai", max_length=64)
    api_key: str = Field(default="", max_length=256)
    model: str = Field(default="gpt-4o", max_length=128)
    level: int = Field(default=2, ge=0, le=3)
    upstream_url: str = Field(default="https://api.openai.com", max_length=512)


class ConfigEntryPayload(BaseModel):
    """Create or update a single config entry."""
    id: str | None = Field(default=None, max_length=64)
    name: str = Field(default="", max_length=128)
    provider: str = Field(default="openai", max_length=64)
    api_key: str = Field(default="", max_length=256)
    model: str = Field(default="gpt-4o", max_length=128)
    level: int = Field(default=2, ge=0, le=3)
    upstream_url: str = Field(default="https://api.openai.com", max_length=512)


class SelectedConfigPayload(BaseModel):
    selected_id: str = Field(max_length=64)


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Authenticated endpoints
# ---------------------------------------------------------------------------


@app.post("/compress", response_model=CompressResponse)
def compress_endpoint(request: Request, req: CompressRequest, uid: str = Depends(_get_uid)) -> CompressResponse:
    ip, ua = _req_meta(request)
    tok = _get_compressor(req.level)
    compressed = tok.compress(req.prompt)
    _add_audit_log(uid, action="compress", ip=ip, user_agent=ua, details={"level": req.level})
    return CompressResponse(
        compressed=compressed,
        original_tokens=tok.count(req.prompt),
        compressed_tokens=tok.count(compressed),
        reduction_pct=tok.reduction_pct(req.prompt, compressed),
    )


@app.post("/decompress", response_model=DecompressResponse)
def decompress_endpoint(request: Request, req: DecompressRequest, uid: str = Depends(_get_uid)) -> DecompressResponse:
    ip, ua = _req_meta(request)
    tok = _get_compressor(Level.MEDIUM, bidirectional=True)
    _add_audit_log(uid, action="decompress", ip=ip, user_agent=ua)
    return DecompressResponse(decompressed=tok.decompress(req.text))


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: Request, req: ChatRequest, uid: str = Depends(_get_uid)) -> ChatResponse:
    """Full pipeline: compress -> call LLM -> return response."""
    ip, ua = _req_meta(request)
    _add_audit_log(uid, action="chat", ip=ip, user_agent=ua, details={"provider": req.provider, "model": req.model})
    tok = _get_compressor(req.level)
    compressed = await asyncio.to_thread(tok.compress, req.prompt)
    system = tok.system_prompt()

    api_key = req.api_key or os.environ.get(_ENV_KEY_MAP.get(req.provider, ""), "")
    if not api_key:
        raise HTTPException(
            status_code=400,
            detail=f"No API key provided for {req.provider}. "
            f"Set {_ENV_KEY_MAP.get(req.provider, 'API_KEY')} or pass api_key.",
        )

    response_text = await _call_provider(
        provider=req.provider,
        model=req.model,
        system_prompt=system,
        user_prompt=compressed,
        api_key=api_key,
    )

    orig_tok = await asyncio.to_thread(tok.count, req.prompt)
    comp_tok = await asyncio.to_thread(tok.count, compressed)
    red_pct = await asyncio.to_thread(tok.reduction_pct, req.prompt, compressed)
    out_tok = await asyncio.to_thread(tok.count, response_text)

    return ChatResponse(
        response=response_text,
        original_tokens=orig_tok,
        compressed_tokens=comp_tok,
        reduction_pct=red_pct,
        output_tokens=out_tok,
    )


# ---------------------------------------------------------------------------
# Dashboard API: config (multiple configs + selected)
# ---------------------------------------------------------------------------


@app.get("/api/config")
def get_config(request: Request, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    ip, ua = _req_meta(request)
    _ensure_user_doc(uid)
    configs, selected_id = _get_config_list(uid)
    _add_audit_log(uid, action="config.view", ip=ip, user_agent=ua)
    return {"configs": configs, "selected_id": selected_id}


@app.post("/api/config")
def set_config(request: Request, payload: ConfigEntryPayload, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    ip, ua = _req_meta(request)
    _ensure_user_doc(uid)
    _, selected_id = _get_config_list(uid)
    full_list = _get_full_config_list(uid)
    new = payload.model_dump()
    if new.get("api_key") and "..." in new["api_key"]:
        for c in full_list:
            if c.get("id") == (payload.id or ""):
                new["api_key"] = c.get("api_key", "")
                break
    entry_id = new.pop("id", None) or str(uuid.uuid4())
    new["id"] = entry_id
    if not new.get("name"):
        new["name"] = f"Connection {len(full_list) + 1}"
    found = False
    for i, c in enumerate(full_list):
        if c.get("id") == entry_id or c.get("id") == payload.id:
            full_list[i] = {**c, **new}
            found = True
            break
    if not found:
        full_list.append(new)
        if selected_id is None:
            selected_id = entry_id
    if selected_id is None and full_list:
        selected_id = full_list[0].get("id")
    _save_config_list(uid, full_list, selected_id)
    _add_audit_log(uid, action="config.save", ip=ip, user_agent=ua, details={"id": entry_id})
    configs_out, _ = _get_config_list(uid)
    return {"status": "saved", "configs": configs_out, "selected_id": selected_id}


@app.post("/api/config/selected")
def set_selected_config(request: Request, payload: SelectedConfigPayload, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    ip, ua = _req_meta(request)
    _ensure_user_doc(uid)
    configs, _ = _get_config_list(uid)
    ids = {c.get("id") for c in configs if c.get("id")}
    if payload.selected_id not in ids:
        raise HTTPException(status_code=400, detail="Invalid selected_id")
    full_list = _get_full_config_list(uid)
    _save_config_list(uid, full_list, payload.selected_id)
    _add_audit_log(uid, action="config.select", ip=ip, user_agent=ua, details={"selected_id": payload.selected_id})
    return {"status": "ok", "selected_id": payload.selected_id}


@app.delete("/api/config/{config_id}")
def delete_config(request: Request, config_id: str, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    ip, ua = _req_meta(request)
    _ensure_user_doc(uid)
    data_ref = _config_data_ref(uid)
    doc = data_ref.get()
    data = doc.to_dict() or {} if doc.exists else {}
    full_list = list(data.get("configs") or [])
    selected_id = data.get("selected_id")
    full_list = [c for c in full_list if c.get("id") != config_id]
    if selected_id == config_id:
        selected_id = full_list[0].get("id") if full_list else None
    _save_config_list(uid, full_list, selected_id)
    _add_audit_log(uid, action="config.delete", ip=ip, user_agent=ua, details={"id": config_id})
    configs_out, sel_out = _get_config_list(uid)
    return {"status": "deleted", "configs": configs_out, "selected_id": sel_out}


# ---------------------------------------------------------------------------
# Dashboard API: logs
# ---------------------------------------------------------------------------


@app.get("/api/logs")
def get_logs(request: Request, limit: int = 100, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    ip, ua = _req_meta(request)
    _ensure_user_doc(uid)
    _add_audit_log(uid, action="logs.view", ip=ip, user_agent=ua)
    entries = _get_logs(uid, limit)
    total_requests = len(entries)
    total_saved = sum(e.get("original_tokens", 0) - e.get("compressed_tokens", 0) for e in entries)
    avg_reduction = 0.0
    if entries:
        avg_reduction = sum(e.get("reduction_pct", 0) for e in entries) / len(entries)
    return {
        "entries": entries,
        "summary": {
            "total_requests": total_requests,
            "total_tokens_saved": total_saved,
            "avg_reduction_pct": round(avg_reduction, 1),
        },
    }


# ---------------------------------------------------------------------------
# Dashboard API: audit logs
# ---------------------------------------------------------------------------


@app.get("/api/audit-logs")
def get_audit_logs(request: Request, limit: int = 200, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    _ensure_user_doc(uid)
    entries = _get_audit_logs(uid, limit)
    return {"entries": entries}


# ---------------------------------------------------------------------------
# Dashboard API: usage
# ---------------------------------------------------------------------------


@app.get("/api/usage")
def get_usage(request: Request, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    ip, ua = _req_meta(request)
    _add_audit_log(uid, action="usage.view", ip=ip, user_agent=ua)
    data = _ensure_user_doc(uid)
    tier = data.get("tier", "free")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if tier == "pro":
        daily_reset = data.get("daily_reset_date", "")
        daily_used = data.get("daily_requests", 0) if daily_reset == today else 0
        return {
            "tier": "pro",
            "daily_used": daily_used,
            "daily_limit": PRO_DAILY_LIMIT,
            "daily_remaining": max(0, PRO_DAILY_LIMIT - daily_used),
        }

    used = data.get("requests_used", 0)
    return {
        "tier": "free",
        "used": used,
        "limit": FREE_TIER_LIMIT,
        "remaining": max(0, FREE_TIER_LIMIT - used),
    }


# ---------------------------------------------------------------------------
# Dashboard API: agreement
# ---------------------------------------------------------------------------


@app.get("/api/agreement")
def get_agreement(request: Request, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    ip, ua = _req_meta(request)
    data = _ensure_user_doc(uid)
    _add_audit_log(uid, action="agreement.view", ip=ip, user_agent=ua)
    accepted = data.get("agreement_accepted_at")
    return {"accepted": accepted is not None, "accepted_at": accepted}


@app.post("/api/agreement")
def accept_agreement(request: Request, uid: str = Depends(_get_uid)) -> dict[str, str]:
    ip, ua = _req_meta(request)
    _user_ref(uid).update({
        "agreement_accepted_at": datetime.now(timezone.utc).isoformat(),
    })
    _add_audit_log(uid, action="agreement.accept", ip=ip, user_agent=ua)
    return {"status": "accepted"}


# ---------------------------------------------------------------------------
# Stripe integration
# ---------------------------------------------------------------------------

_STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
_STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
_STRIPE_PRICE_ID = os.environ.get("STRIPE_PRICE_ID", "")


@app.post("/api/stripe/create-checkout")
async def create_checkout(request: Request, uid: str = Depends(_get_uid)) -> dict[str, str]:
    """Create a Stripe Checkout Session for the Pro plan ($5/month)."""
    ip, ua = _req_meta(request)
    if not _STRIPE_SECRET_KEY or not _STRIPE_PRICE_ID:
        raise HTTPException(status_code=500, detail="Stripe not configured")

    user_data = _ensure_user_doc(uid)
    if user_data.get("tier") == "pro":
        raise HTTPException(status_code=400, detail="Already on Pro plan")
    _add_audit_log(uid, action="stripe.checkout", ip=ip, user_agent=ua)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers={"Authorization": f"Bearer {_STRIPE_SECRET_KEY}"},
            data={
                "mode": "subscription",
                "payment_method_types[]": "card",
                "line_items[0][price]": _STRIPE_PRICE_ID,
                "line_items[0][quantity]": "1",
                "success_url": f"{_FRONTEND_URL}/?session_id={{CHECKOUT_SESSION_ID}}",
                "cancel_url": f"{_FRONTEND_URL}/",
                "client_reference_id": uid,
                "metadata[uid]": uid,
            },
            timeout=30,
        )
        resp.raise_for_status()
        session = resp.json()
        return {"url": session["url"]}


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request) -> dict[str, str]:
    """Handle Stripe webhook events for subscription lifecycle."""
    if _db is None:
        logger.warning("Stripe webhook received but Firestore not configured; skipping processing")
        return {"status": "ok"}

    body = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if _STRIPE_WEBHOOK_SECRET:
        parts = dict(item.split("=", 1) for item in sig_header.split(",") if "=" in item)
        timestamp = parts.get("t", "")
        v1_sig = parts.get("v1", "")
        signed_payload = f"{timestamp}.{body.decode()}"
        expected = hmac.HMAC(
            _STRIPE_WEBHOOK_SECRET.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, v1_sig):
            raise HTTPException(status_code=400, detail="Invalid signature")

    event = json.loads(body)
    event_type = event.get("type", "")

    if event_type == "checkout.session.completed":
        session = event["data"]["object"]
        uid = session.get("client_reference_id") or session.get("metadata", {}).get("uid")
        if uid:
            subscription_id = session.get("subscription", "")
            customer_id = session.get("customer", "")
            _user_ref(uid).update({
                "tier": "pro",
                "stripe_customer_id": customer_id,
                "stripe_subscription_id": subscription_id,
            })
            _add_audit_log(uid, action="stripe.upgrade", details={"event": event_type, "subscription_id": subscription_id})
            logger.info("User %s upgraded to pro", uid)

    elif event_type in ("customer.subscription.deleted", "customer.subscription.updated"):
        sub = event["data"]["object"]
        sub_status = sub.get("status", "")
        customer_id = sub.get("customer", "")

        if sub_status in ("canceled", "unpaid", "past_due"):
            users = _db.collection("users").where("stripe_customer_id", "==", customer_id).stream()
            for user_doc in users:
                user_doc.reference.update({"tier": "free"})
                _add_audit_log(user_doc.id, action="stripe.downgrade", details={"event": event_type, "status": sub_status})
                logger.info("User %s downgraded to free (sub %s)", user_doc.id, sub_status)

    return {"status": "ok"}


@app.get("/api/subscription")
def get_subscription(request: Request, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    ip, ua = _req_meta(request)
    data = _ensure_user_doc(uid)
    _add_audit_log(uid, action="subscription.view", ip=ip, user_agent=ua)
    return {
        "tier": data.get("tier", "free"),
        "stripe_subscription_id": data.get("stripe_subscription_id"),
    }


# ---------------------------------------------------------------------------
# OpenAI-compatible proxy: POST /v1/chat/completions
# ---------------------------------------------------------------------------


@app.post("/v1/chat/completions")
async def proxy_chat_completions(request: Request, uid: str = Depends(_get_uid)) -> dict[str, Any]:
    """Accept an OpenAI-shaped request, compress user messages, forward
    to the configured upstream provider, and return an OpenAI-shaped response."""

    _ensure_user_doc(uid)
    _check_and_increment_usage(uid)

    req_ip = _get_client_ip(request)
    req_ua = request.headers.get("user-agent", "")

    body: dict[str, Any] = await request.json()
    cfg = _load_config(uid)

    provider = cfg.get("provider", "openai")
    api_key = cfg.get("api_key", "")
    upstream_url = cfg.get("upstream_url", _PROVIDER_DEFAULTS.get(provider, ""))
    level = cfg.get("level", 2)
    model = body.get("model") or cfg.get("model", "gpt-4o")

    if not api_key and provider != "ollama":
        raise HTTPException(status_code=400, detail="No API key configured. Set one via the dashboard.")

    tok = _get_compressor(level)
    system_prompt = tok.system_prompt()

    messages: list[dict[str, Any]] = body.get("messages", [])
    original_text_parts: list[str] = []
    compressed_messages: list[dict[str, Any]] = []

    has_system = any(m.get("role") == "system" for m in messages)
    if not has_system:
        compressed_messages.append({"role": "system", "content": system_prompt})

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "user" and isinstance(content, str):
            original_text_parts.append(content)
            compressed_messages.append({"role": role, "content": await asyncio.to_thread(tok.compress, content)})
        elif role == "system":
            compressed_messages.append({"role": role, "content": content + "\n\n" + system_prompt})
        else:
            compressed_messages.append(msg)

    original_tokens = sum([await asyncio.to_thread(tok.count, t) for t in original_text_parts])
    compressed_tokens = sum([
        await asyncio.to_thread(tok.count, m["content"])
        for m in compressed_messages if m.get("role") == "user"
    ])

    t0 = time.monotonic()
    status = "ok"
    response_text = ""

    try:
        if provider == "openai":
            response_text, raw_response = await _proxy_openai(
                upstream_url, api_key, model, compressed_messages, body,
            )
        elif provider == "anthropic":
            response_text, raw_response = await _proxy_anthropic(
                upstream_url, api_key, model, compressed_messages, body,
            )
        elif provider == "ollama":
            response_text, raw_response = await _proxy_ollama(
                upstream_url, model, compressed_messages,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")
    except HTTPException:
        raise
    except Exception as exc:
        status = "error"
        latency_ms = int((time.monotonic() - t0) * 1000)
        reduction_for_log = await asyncio.to_thread(
            tok.reduction_pct,
            " ".join(original_text_parts),
            " ".join(m["content"] for m in compressed_messages if m.get("role") == "user"),
        ) if original_text_parts else 0.0
        _add_log_entry(
            uid,
            model=model,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            reduction_pct=reduction_for_log,
            output_tokens=0,
            latency_ms=latency_ms,
            status=status,
            ip=req_ip,
            user_agent=req_ua,
            endpoint="/v1/chat/completions",
        )
        _add_audit_log(uid, action="proxy.error", ip=req_ip, user_agent=req_ua, details={"model": model, "error": str(exc)})
        raise HTTPException(status_code=502, detail=str(exc))

    latency_ms = int((time.monotonic() - t0) * 1000)
    output_tokens = await asyncio.to_thread(tok.count, response_text)
    reduction = 0.0
    if original_tokens > 0:
        reduction = (1 - compressed_tokens / original_tokens) * 100

    _add_log_entry(
        uid,
        model=model,
        original_tokens=original_tokens,
        compressed_tokens=compressed_tokens,
        reduction_pct=reduction,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        status=status,
        ip=req_ip,
        user_agent=req_ua,
        endpoint="/v1/chat/completions",
    )
    _add_audit_log(uid, action="proxy.success", ip=req_ip, user_agent=req_ua, details={
        "model": model, "original_tokens": original_tokens, "compressed_tokens": compressed_tokens,
    })

    return raw_response


# ---------------------------------------------------------------------------
# Proxy provider helpers
# ---------------------------------------------------------------------------


async def _proxy_openai(
    upstream_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    original_body: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    forward_body = {**original_body, "model": model, "messages": messages, "stream": False}
    forward_body.pop("stream", None)
    forward_body["stream"] = False

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{upstream_url.rstrip('/')}/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=forward_body,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        return text, data


async def _proxy_anthropic(
    upstream_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, Any]],
    original_body: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    non_system = [m for m in messages if m["role"] != "system"]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{upstream_url.rstrip('/')}/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": original_body.get("max_tokens", 4096),
                "system": "\n\n".join(system_parts),
                "messages": non_system,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["content"][0]["text"]

    openai_response = _to_openai_shape(model, text)
    return text, openai_response


async def _proxy_ollama(
    upstream_url: str,
    model: str,
    messages: list[dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{upstream_url.rstrip('/')}/api/chat",
            json={"model": model, "stream": False, "messages": messages},
            timeout=300,
        )
        resp.raise_for_status()
        data = resp.json()
        text = data["message"]["content"]

    openai_response = _to_openai_shape(model, text)
    return text, openai_response


def _to_openai_shape(model: str, content: str) -> dict[str, Any]:
    """Wrap a plain text response in the OpenAI chat completions shape."""
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


# ---------------------------------------------------------------------------
# Legacy provider dispatch (used by /chat endpoint)
# ---------------------------------------------------------------------------

_ENV_KEY_MAP: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


async def _call_provider(
    provider: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    api_key: str,
) -> str:
    if provider == "openai":
        return await _call_openai(model, system_prompt, user_prompt, api_key)
    if provider == "anthropic":
        return await _call_anthropic(model, system_prompt, user_prompt, api_key)
    if provider == "ollama":
        return await _call_ollama(model, system_prompt, user_prompt)
    raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")


async def _call_openai(
    model: str, system_prompt: str, user_prompt: str, api_key: str
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=120,
        )
        resp.raise_for_status()
        return _extract_openai(resp.json())


async def _call_anthropic(
    model: str, system_prompt: str, user_prompt: str, api_key: str
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


async def _call_ollama(
    model: str, system_prompt: str, user_prompt: str
) -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "http://localhost:11434/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            timeout=300,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


def _extract_openai(data: dict[str, Any]) -> str:
    return data["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def cli_main() -> None:
    parser = argparse.ArgumentParser(prog="tokreducer", description="TokReducer CLI")
    sub = parser.add_subparsers(dest="command")

    serve_parser = sub.add_parser("serve", help="Start the REST API server")
    serve_parser.add_argument("--port", type=int, default=8080)
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--level", type=int, default=2)

    compress_parser = sub.add_parser("compress", help="Compress a prompt")
    compress_parser.add_argument("prompt", help="The prompt to compress")
    compress_parser.add_argument("--level", type=int, default=2)

    args = parser.parse_args()

    if args.command == "serve":
        import uvicorn

        uvicorn.run(app, host=args.host, port=args.port)
    elif args.command == "compress":
        tok = TokReducer(level=args.level)
        compressed = tok.compress(args.prompt)
        orig = tok.count(args.prompt)
        comp = tok.count(compressed)
        pct = tok.reduction_pct(args.prompt, compressed)
        print(f"Original:   {args.prompt}")
        print(f"Compressed: {compressed}")
        print(f"Tokens:     {orig} \u2192 {comp} ({pct:.1f}% reduction)")
    else:
        parser.print_help()
