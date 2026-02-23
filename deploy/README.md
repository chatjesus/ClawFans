# ClawFans VPS Deployment Guide

Target: `clawfans.tinyclaw.dev` on Hetzner CAX31 (Ubuntu 24.04)

## Step-by-Step

### Step 1 — Create Hetzner Server

In Hetzner Console → TinyClaw project → **Create Server**:
- Location: Nuremberg (or nearest to your users)
- Image: **Ubuntu 24.04**
- Type: **CAX31** (8 vCPU ARM, 16 GB RAM, ~€8.21/mo)
- SSH Key: add your public key
- Name: `clawfans-prod`

### Step 2 — Add DNS Record

In your DNS provider (or Hetzner DNS):
```
A   clawfans.tinyclaw.dev   →   <VPS IP>
TTL: 300
```

Wait for DNS to propagate (usually 1–5 min with Hetzner DNS).

### Step 3 — Push Code to Git

If not already on GitHub:
```bash
cd C:\Users\PRO\Desktop\CUDA\synclub-local
git init
git add .
git commit -m "initial deploy"
git remote add origin https://github.com/YOUR_USERNAME/synclub-local.git
git push -u origin main
```

Update `REPO_URL` in `deploy/setup-vps.sh` with your actual repo URL.

### Step 4 — Run Setup Script on VPS

```bash
ssh root@<VPS_IP>
curl -O https://raw.githubusercontent.com/YOUR_USERNAME/synclub-local/main/deploy/setup-vps.sh
bash setup-vps.sh
```

Or copy the script directly:
```bash
scp deploy/setup-vps.sh root@<VPS_IP>:/root/
ssh root@<VPS_IP> "bash setup-vps.sh"
```

### Step 5 — Configure Production Env Files

On the VPS, edit the env files with real keys:

```bash
# Backend
nano /opt/clawfans/backend/.env.production

# Frontend  
nano /opt/clawfans/frontend/.env.production
```

For Clerk **production keys**:
1. Go to [clerk.com](https://clerk.com) → Your App
2. Switch instance to **Production**
3. Add domain: `clawfans.tinyclaw.dev`
4. Copy `pk_live_...` and `sk_live_...` keys
5. Paste into `/opt/clawfans/frontend/.env.production`

Rebuild frontend after updating env:
```bash
cd /opt/clawfans/frontend && npm run build
systemctl restart clawfans-frontend
```

### Step 6 — Verify

```bash
# Check services
systemctl status clawfans-backend
systemctl status clawfans-frontend

# Check logs
journalctl -u clawfans-backend -f
journalctl -u clawfans-frontend -f

# Test API
curl https://clawfans.tinyclaw.dev/api/health
```

---

## Ongoing Updates

After any code change, on the VPS:
```bash
bash /opt/clawfans/deploy/update.sh
```

---

## File Locations on VPS

| Path | Contents |
|------|----------|
| `/opt/clawfans/` | All app code |
| `/opt/clawfans/backend/.env.production` | Backend secrets |
| `/opt/clawfans/frontend/.env.production` | Frontend secrets + Clerk keys |
| `/opt/clawfans/backend/synclub.db` | SQLite database |
| `/opt/clawfans/backend/uploads/` | Avatar images |
| `/etc/nginx/sites-available/clawfans` | Nginx config |
| `/etc/systemd/system/clawfans-*.service` | systemd services |
| `/etc/letsencrypt/` | SSL certificates (auto-renewed) |

---

## Database Migration (existing data)

If you want to copy local data to VPS:
```bash
# Upload local DB to VPS
scp backend/synclub.db root@<VPS_IP>:/opt/clawfans/backend/synclub.db
scp -r backend/uploads/ root@<VPS_IP>:/opt/clawfans/backend/

# Fix permissions
ssh root@<VPS_IP> "chown -R clawfans:clawfans /opt/clawfans/backend/synclub.db /opt/clawfans/backend/uploads"
```
