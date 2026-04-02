#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/restatify-booking-api"
SERVICE_USER="restatify"
SERVICE_GROUP="restatify"
SERVICE_NAME="restatify-booking-api"
ENV_FILE="${PROJECT_DIR}/.env"

echo "[1/10] Installing OS packages"
sudo apt update
sudo apt install -y caddy postgresql redis-server python3-venv python3-pip curl jq ufw fail2ban unattended-upgrades rsync

echo "[2/10] Creating service user"
if ! id -u "${SERVICE_USER}" >/dev/null 2>&1; then
  sudo useradd --system --shell /usr/sbin/nologin --home "${PROJECT_DIR}" "${SERVICE_USER}"
fi

echo "[3/10] Preparing project directory"
sudo mkdir -p "${PROJECT_DIR}"
sudo rsync -a --delete ./ "${PROJECT_DIR}/"
sudo chown -R "${SERVICE_USER}:${SERVICE_GROUP}" "${PROJECT_DIR}"

echo "[4/10] Python virtualenv and dependencies"
sudo -u "${SERVICE_USER}" python3 -m venv "${PROJECT_DIR}/.venv"
sudo -u "${SERVICE_USER}" "${PROJECT_DIR}/.venv/bin/pip" install --upgrade pip
sudo -u "${SERVICE_USER}" "${PROJECT_DIR}/.venv/bin/pip" install -r "${PROJECT_DIR}/requirements.txt"

echo "[5/10] Creating .env from example (if missing)"
if [[ ! -f "${ENV_FILE}" ]]; then
  sudo cp "${PROJECT_DIR}/.env.example" "${ENV_FILE}"
  sudo chown "${SERVICE_USER}:${SERVICE_GROUP}" "${ENV_FILE}"
  echo "Please edit ${ENV_FILE} and set API_KEY + DATABASE_URL before go-live."
fi

echo "[6/10] Installing systemd unit"
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" >/dev/null <<'UNIT'
[Unit]
Description=Restatify Booking API
After=network.target

[Service]
User=restatify
Group=restatify
WorkingDirectory=/opt/restatify-booking-api
EnvironmentFile=/opt/restatify-booking-api/.env
ExecStart=/opt/restatify-booking-api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8088
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
UNIT

echo "[7/10] Installing Caddy site"
sudo mkdir -p /etc/caddy/sites-available /etc/caddy/sites-enabled
sudo tee /etc/caddy/sites-available/restatify-booking-api.caddy >/dev/null <<'CADDY'
booking-api.example.com {
    encode zstd gzip
    reverse_proxy 127.0.0.1:8088
}
CADDY

if [[ ! -e /etc/caddy/sites-enabled/restatify-booking-api.caddy ]]; then
  sudo ln -s /etc/caddy/sites-available/restatify-booking-api.caddy /etc/caddy/sites-enabled/restatify-booking-api.caddy
fi

if ! sudo grep -q "import /etc/caddy/sites-enabled/\*" /etc/caddy/Caddyfile; then
  echo "import /etc/caddy/sites-enabled/*" | sudo tee -a /etc/caddy/Caddyfile >/dev/null
fi

echo "[8/9] Reloading services"
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"
sudo systemctl reload caddy

echo "[9/9] Firewall baseline"
sudo ufw allow OpenSSH || true
sudo ufw allow 'WWW Full' || true

cat <<EOF
Installation finished.
Next:
1) Edit ${ENV_FILE}
2) Replace booking-api.example.com in /etc/caddy/sites-available/restatify-booking-api.caddy
3) Set GOOGLE_CREDENTIALS_JSON + GOOGLE_CALENDAR_IDS in ${ENV_FILE}
4) sudo systemctl restart ${SERVICE_NAME} caddy
5) sudo -u ${SERVICE_USER} ${PROJECT_DIR}/.venv/bin/python -m app.sync_google_freebusy
6) curl http://127.0.0.1:8088/health
EOF
