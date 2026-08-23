#!/usr/bin/env bash
# =============================================================================
# Mitacs Scraper API - Oracle Cloud Always Free VM setup (Ubuntu 22.04/24.04)
#
# Usage (on the VM):
#   sudo bash setup_server.sh [REPO_URL] [BRANCH]
# Defaults:
#   REPO_URL = https://github.com/Rahim36712/mitacs_projects_scraper.git
#   BRANCH   = main
#
# Safe to re-run: it updates the code and restarts the service.
# After it finishes, also open TCP port 8000 in the OCI Console
# (VCN -> Security List -> Add Ingress Rule) - see README.
# =============================================================================
set -euo pipefail

REPO_URL="${1:-https://github.com/Rahim36712/mitacs_projects_scraper.git}"
BRANCH="${2:-main}"
APP_DIR="/opt/mitacs-scraper"
SERVICE_NAME="mitacs-scraper"
PORT=8000

if [ "$EUID" -ne 0 ]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

echo "==> [1/6] Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip git curl ca-certificates \
                   iptables-persistent netfilter-persistent

echo "==> [2/6] Fetching application code (${BRANCH})..."
if [ -d "${APP_DIR}/.git" ]; then
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/${BRANCH}"
else
  rm -rf "$APP_DIR"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi

echo "==> [3/6] Creating Python virtual environment..."
python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/mitacs_scraper/requirements.txt"

echo "==> [4/6] Installing Playwright Chromium browser (+ OS deps)..."
"${APP_DIR}/.venv/bin/python" -m playwright install --with-deps chromium

echo "==> [5/6] Installing systemd service..."
sed -e "s|__APP_DIR__|${APP_DIR}|g" \
    -e "s|__PORT__|${PORT}|g" \
    "${APP_DIR}/deploy/oracle/mitacs-scraper.service" > "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "==> [6/6] Opening TCP ${PORT} in local firewall..."
if ! iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null; then
  iptables -I INPUT 1 -p tcp --dport "$PORT" -j ACCEPT
fi
netfilter-persistent save

sleep 2
PUBLIC_IP=$(curl -s --max-time 5 https://checkip.amazonaws.com || echo "<VM_PUBLIC_IP>")
echo
echo "============================================================"
echo " Setup complete!"
echo " Backend URL : http://${PUBLIC_IP}:${PORT}"
echo " Health check: curl http://127.0.0.1:${PORT}/api/health"
echo
echo " IMPORTANT - one manual step remains:"
echo " Open port ${PORT} in Oracle Cloud console:"
echo "   Networking -> Virtual Cloud Networks -> your VCN"
echo "   -> Security Lists -> Default Security List -> Add Ingress Rule"
echo "      Source CIDR: 0.0.0.0/0 | IP Protocol: TCP"
echo "      Destination Port Range: ${PORT}"
echo
echo " Service logs : journalctl -u ${SERVICE_NAME} -f"
echo " Update later : cd ${APP_DIR} && git pull && \\
                 .venv/bin/pip install -r mitacs_scraper/requirements.txt && \\
                 systemctl restart ${SERVICE_NAME}"
echo "============================================================"
