# Production Deployment Guide

## Prerequisites

- VPS running Ubuntu 22.04+ with Docker & Docker Compose v2 installed
- Domain pointing to VPS IP
- GitHub repository with this code

---

## 1. VPS Initialization

```bash
# Install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Docker Compose plugin (if not bundled)
sudo apt-get install docker-compose-plugin

# Clone the repo
sudo mkdir -p /opt/taiwan-stock-radar
sudo chown $USER:$USER /opt/taiwan-stock-radar
git clone https://github.com/<your-org>/taiwan-stock-radar.git /opt/taiwan-stock-radar
cd /opt/taiwan-stock-radar

# Create prod env file
cp .env.prod.example .env.prod
nano .env.prod   # fill in all values
```

---

## 2. Initial HTTP-only Startup (for Certbot)

Before enabling HTTPS, start with HTTP only so Certbot can verify the domain.

```bash
# Temporarily bring up nginx on port 80 only
docker compose -f docker-compose.prod.yml up -d nginx
```

---

## 3. Obtain SSL Certificate (Let's Encrypt / Certbot)

```bash
# Install certbot on the host
sudo apt-get install certbot

# Obtain certificate using webroot
sudo certbot certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  -d yourdomain.com \
  --email your@email.com \
  --agree-tos \
  --non-interactive

# Verify cert files exist
ls /etc/letsencrypt/live/yourdomain.com/
```

### Auto-renewal cron

```bash
echo "0 3 * * * root certbot renew --quiet && docker compose -f /opt/taiwan-stock-radar/docker-compose.prod.yml exec nginx nginx -s reload" \
  | sudo tee /etc/cron.d/certbot-renew
```

---

## 4. Full Stack Startup

```bash
cd /opt/taiwan-stock-radar
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps   # all should be healthy
curl -f https://yourdomain.com/api/health
```

---

## 5. GitHub Secrets Setup

Go to **Settings → Secrets and variables → Actions** in your GitHub repo and add:

| Secret | Description |
|---|---|
| `VPS_HOST` | VPS IP address or hostname |
| `VPS_USER` | SSH user (e.g. `ubuntu`) |
| `VPS_SSH_KEY` | Private SSH key (generate with `ssh-keygen -t ed25519`) |
| `DOMAIN` | Your domain (e.g. `yourdomain.com`) |

The workflow uses `GITHUB_TOKEN` (auto-provided) to push images to GHCR.

### Add SSH public key to VPS

```bash
# On VPS
echo "<your-public-key>" >> ~/.ssh/authorized_keys
```

---

## 6. Rollback

### Option A — Git revert + push (triggers CI/CD)

```bash
git revert HEAD
git push origin main
```

### Option B — Direct VPS rollback to specific image tag

```bash
ssh user@vps
cd /opt/taiwan-stock-radar

# Find previous image tag from GHCR or CI logs
export IMAGE_TAG=<previous-sha>
docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d
curl -f https://yourdomain.com/api/health
```

### Option C — Direct git checkout on VPS (no CI/CD)

```bash
ssh user@vps
cd /opt/taiwan-stock-radar
git log --oneline -10        # find target commit
git checkout <commit-sha>
docker compose -f docker-compose.prod.yml up -d --build
```

---

## 7. Manual DB Backup

```bash
docker compose -f docker-compose.prod.yml exec backup /backup-db.sh
ls /var/lib/docker/volumes/taiwan-stock-radar_backup_data/_data/
```

---

## 8. Monitoring

```bash
# Service status
docker compose -f docker-compose.prod.yml ps

# Logs
docker compose -f docker-compose.prod.yml logs -f fastapi
docker compose -f docker-compose.prod.yml logs -f nginx

# Health
curl https://yourdomain.com/api/health
```
