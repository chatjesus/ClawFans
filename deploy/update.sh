#!/bin/bash
# ============================================================
# ClawFans Update Script  
# Run on VPS to pull latest code and restart services
# Usage: bash /opt/clawfans/deploy/update.sh
# ============================================================
set -e

APP_DIR="/opt/clawfans"
APP_USER="clawfans"

echo "[update] Pulling latest code..."
cd "$APP_DIR"
git pull

echo "[update] Updating backend dependencies..."
cd "$APP_DIR/backend"
sudo -u "$APP_USER" ./venv/bin/pip install -q -r requirements.txt

echo "[update] Rebuilding frontend..."
cd "$APP_DIR/frontend"
sudo -u "$APP_USER" npm ci --silent
sudo -u "$APP_USER" npm run build

echo "[update] Restarting services..."
systemctl restart clawfans-backend
sleep 2
systemctl restart clawfans-frontend

echo "[update] Done! Checking status..."
systemctl is-active clawfans-backend && echo "  ✅ backend running"
systemctl is-active clawfans-frontend && echo "  ✅ frontend running"
