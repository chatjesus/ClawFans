#!/bin/bash
# ============================================================
# ClawFans VPS Setup Script
# Run as root on a fresh Ubuntu 24.04 server
# Usage: bash setup-vps.sh
# ============================================================
set -e

DOMAIN="clawfans.tinyclaw.dev"
APP_USER="clawfans"
APP_DIR="/opt/clawfans"
REPO_URL="https://github.com/YOUR_USERNAME/synclub-local.git"  # update this
OLLAMA_MODEL="qwen2.5:14b"

echo "======================================================"
echo "  ClawFans VPS Setup for $DOMAIN"
echo "======================================================"

# ── 1. System updates ──────────────────────────────────────
echo "[1/9] Updating system..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Install dependencies ────────────────────────────────
echo "[2/9] Installing dependencies..."
apt-get install -y -qq \
    git curl wget nginx certbot python3-certbot-nginx \
    python3 python3-pip python3-venv \
    build-essential libssl-dev

# Install Node.js 20 LTS
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt-get install -y -qq nodejs

echo "  Node: $(node --version), npm: $(npm --version)"
echo "  Python: $(python3 --version)"

# ── 3. Create app user ─────────────────────────────────────
echo "[3/9] Creating app user '$APP_USER'..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$APP_USER"
    echo "  Created user $APP_USER"
fi

# ── 4. Install Ollama ──────────────────────────────────────
echo "[4/9] Installing Ollama..."
if ! command -v ollama &>/dev/null; then
    curl -fsSL https://ollama.ai/install.sh | sh
fi
systemctl enable ollama
systemctl start ollama
echo "  Ollama installed. Pulling model $OLLAMA_MODEL (this takes ~10 min)..."
sudo -u "$APP_USER" ollama pull "$OLLAMA_MODEL" &
OLLAMA_PID=$!
echo "  Model pull started in background (PID $OLLAMA_PID)"

# ── 5. Clone / update code ─────────────────────────────────
echo "[5/9] Setting up application code..."
mkdir -p "$APP_DIR"
if [ -d "$APP_DIR/.git" ]; then
    echo "  Updating existing repo..."
    cd "$APP_DIR" && git pull
else
    echo "  Cloning repo..."
    git clone "$REPO_URL" "$APP_DIR"
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

# ── 6. Backend setup ───────────────────────────────────────
echo "[6/9] Setting up backend..."
cd "$APP_DIR/backend"
sudo -u "$APP_USER" python3 -m venv venv
sudo -u "$APP_USER" ./venv/bin/pip install -q --upgrade pip
sudo -u "$APP_USER" ./venv/bin/pip install -q -r requirements.txt

# Copy env file if not already present
if [ ! -f "$APP_DIR/backend/.env.production" ]; then
    cp "$APP_DIR/deploy/backend.env.production" "$APP_DIR/backend/.env.production"
    chmod 600 "$APP_DIR/backend/.env.production"
    echo "  ⚠️  Edit $APP_DIR/backend/.env.production with your real keys!"
fi

# ── 7. Frontend setup ──────────────────────────────────────
echo "[7/9] Setting up frontend..."
cd "$APP_DIR/frontend"
sudo -u "$APP_USER" npm ci --silent

if [ ! -f "$APP_DIR/frontend/.env.production" ]; then
    cp "$APP_DIR/deploy/frontend.env.production" "$APP_DIR/frontend/.env.production"
    chmod 600 "$APP_DIR/frontend/.env.production"
    echo "  ⚠️  Edit $APP_DIR/frontend/.env.production with your Clerk LIVE keys!"
fi

sudo -u "$APP_USER" npm run build

# ── 8. Nginx + SSL ─────────────────────────────────────────
echo "[8/9] Configuring Nginx..."
cp "$APP_DIR/deploy/nginx.conf" "/etc/nginx/sites-available/clawfans"

# Enable site
ln -sf /etc/nginx/sites-available/clawfans /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test config
nginx -t

# SSL certificate (comment out if DNS not ready yet)
echo "  Obtaining SSL certificate for $DOMAIN..."
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
    --email admin@tinyclaw.dev --redirect || \
    echo "  ⚠️  SSL failed - make sure DNS A record points to this server first"

systemctl reload nginx

# ── 9. Install systemd services ────────────────────────────
echo "[9/9] Installing systemd services..."
cp "$APP_DIR/deploy/clawfans-backend.service" /etc/systemd/system/
cp "$APP_DIR/deploy/clawfans-frontend.service" /etc/systemd/system/

# Fix ExecStart path in frontend service (use local node_modules)
sed -i "s|/usr/bin/node_modules/.bin/next|$APP_DIR/frontend/node_modules/.bin/next|g" \
    /etc/systemd/system/clawfans-frontend.service

systemctl daemon-reload
systemctl enable clawfans-backend clawfans-frontend
systemctl start clawfans-backend clawfans-frontend

# ── Wait for ollama model pull ─────────────────────────────
echo ""
echo "Waiting for Ollama model pull to complete..."
wait $OLLAMA_PID 2>/dev/null || true

# ── Done ───────────────────────────────────────────────────
echo ""
echo "======================================================"
echo "  ✅ Setup complete!"
echo "======================================================"
echo ""
echo "  Services:"
echo "    systemctl status clawfans-backend"
echo "    systemctl status clawfans-frontend"
echo "    journalctl -u clawfans-backend -f"
echo ""
echo "  ⚠️  Before it works, make sure to:"
echo "  1. Edit /opt/clawfans/backend/.env.production (Clerk secret key)"
echo "  2. Edit /opt/clawfans/frontend/.env.production (Clerk LIVE keys)"
echo "  3. Add DNS A record: $DOMAIN → $(curl -s ifconfig.me)"
echo "  4. Add $DOMAIN to Clerk dashboard → Domains"
echo "  5. systemctl restart clawfans-backend clawfans-frontend"
echo ""
