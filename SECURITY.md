# Security Architecture

## Authentication

- **Firebase Authentication** handles all user identity management (email/password).
- Every protected API endpoint verifies a Firebase **ID token** (JWT) via the `Authorization: Bearer <token>` header.
- Tokens are verified server-side using the Firebase Admin SDK (`firebase_admin.auth.verify_id_token`).
- The frontend stores tokens **in-memory only** (React state), never in localStorage or cookies. Tokens are refreshed every 10 minutes.

## Authorization

- **Firestore Security Rules** block all client-side writes (`allow write: if false`). Only the backend (Admin SDK) can mutate data.
- Read access is scoped to the authenticated user's own documents (`users/{userId}/**`).
- Usage limits (free tier: 2 lifetime requests; pro tier: 10/day) are enforced server-side before processing.

## Data Protection

- **TLS**: Nginx terminates HTTPS in the Docker deployment. HSTS headers (`max-age=31536000; includeSubDomains; preload`) enforce HTTPS on all subsequent requests.
- **Encryption at rest**: Firestore encrypts all data at rest by default (Google-managed keys).
- **API keys**: Stored in Firestore per-user, masked in API responses (first 4 + last 4 characters only).
- **Secrets**: All credentials (`STRIPE_SECRET_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, etc.) are loaded from environment variables, never committed to source.

## Transport Security Headers

All API responses include:

| Header | Value |
|---|---|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self' https://*.firebaseapp.com https://*.googleapis.com; img-src 'self' data:; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'` |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=()` |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |

Nginx applies the same headers to static assets.

## Rate Limiting & Abuse Prevention

- **IP-based token bucket**: 60 requests/minute per IP address (backend middleware).
- **Request body size limit**: 1 MB maximum.
- **URL length limit**: 2048 characters maximum.
- **WAF-like filtering**: Blocks path traversal (`../`, `%00`), SQL injection patterns (`UNION SELECT`, `OR 1=1`, `DROP TABLE`), and logs blocked attempts.

## CSRF Protection

- State-changing requests (`POST`, `PUT`, `DELETE`, `PATCH`) must include an `Origin` or `Referer` header matching the allowed origins list.
- The Stripe webhook endpoint is exempt (validated via HMAC signature instead).

## CORS

- Origins are restricted to the configured `FRONTEND_URL` plus `localhost:3000` and `127.0.0.1:3000`.
- Credentials are allowed; all methods and headers are permitted for authenticated requests.

## Input Validation

- **Backend**: All Pydantic request models enforce `max_length` on string fields and `ge`/`le` on numeric fields.
- **Frontend**: User-controlled text is sanitized with DOMPurify before rendering.
- **Audit logs**: Control characters are stripped from all stored strings.

## Audit Logging

Every significant action is recorded in `users/{uid}/audit_logs` with:
- Timestamp (UTC ISO 8601)
- Action name
- Client IP address
- User-Agent string
- Action-specific details

Logged actions include: login, config changes, compression requests, proxy calls, Stripe events, agreement acceptance, and all data views.

## Dependency Scanning

- **GitHub Actions** runs `npm audit --audit-level=high` (frontend) and `pip-audit --strict` (backend) on every push, PR, and weekly schedule.
- Builds fail on high or critical vulnerabilities.

## Infrastructure

- **Docker Compose** orchestrates 3 backend replicas behind an Nginx load balancer.
- Nginx handles upstream failover (`proxy_next_upstream error timeout http_502 http_503`) with 2 retry attempts.
- Backend containers expose port 8080 only internally; only Nginx port 80/443 is publicly accessible.

## Responsible Disclosure

If you discover a security vulnerability, please report it responsibly:

1. **Email**: security@tokreducer.com
2. **Do not** open a public GitHub issue for security vulnerabilities.
3. Include a description of the vulnerability, steps to reproduce, and potential impact.
4. We will acknowledge receipt within 48 hours and aim to provide a fix within 7 days for critical issues.
