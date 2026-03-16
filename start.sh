#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "=== TokReducer ==="
echo ""

# Load .env if present
if [ -f "$ROOT/.env" ]; then
    set -a
    source "$ROOT/.env"
    set +a
    echo "Loaded environment from .env"
fi

# --- Backend ---
echo "[1/3] Installing Python backend..."
cd "$ROOT/backend/python"
pip install -e ".[api]" --quiet 2>/dev/null || pip install --user -e ".[api]"

# --- Frontend ---
echo "[2/3] Installing frontend dependencies..."
cd "$ROOT/web"
npm install --silent 2>/dev/null || npm install

# --- Rust compressor (optional) ---
RUST_PID=""
if command -v cargo &>/dev/null; then
    echo "[2.5/3] Building Rust compressor..."
    cd "$ROOT/backend/rust"
    if cargo build --release --features cli 2>/dev/null; then
        ./target/release/tokreducer-cli serve --port 8081 &
        RUST_PID=$!
        export RUST_COMPRESSOR_URL=http://localhost:8081
        echo "  Rust compressor -> http://localhost:8081"
        sleep 1
    else
        echo "  Rust build skipped (Python compressor will be used)"
    fi
    cd "$ROOT"
else
    echo "  Rust not installed (Python compressor will be used)"
fi

# --- Start both ---
echo "[3/3] Starting services..."
echo ""
echo "  Backend   -> http://localhost:8080"
echo "  Dashboard -> http://localhost:3000"
echo "  Proxy     -> http://localhost:8080/v1/chat/completions"
echo ""

cd "$ROOT/backend/python"
uvicorn tokreducer.api.server:app --host 0.0.0.0 --port 8080 --log-level info &
BACKEND_PID=$!

cd "$ROOT/web"
npx vite --port 3000 --host &
FRONTEND_PID=$!

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    [ -n "$RUST_PID" ] && kill $RUST_PID 2>/dev/null
    exit 0
}

trap cleanup INT TERM

wait
