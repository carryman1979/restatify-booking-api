# Restatify Booking API - Docker Compose mit VPN + HTTPS (Ubuntu 24.04)

Diese Anleitung beschreibt einen produktionsnahen Betrieb mit Docker Compose, WireGuard (Host-Level) und HTTPS via Caddy.

## 1) Zielarchitektur

- Server A: WordPress
- Server B: Booking API (Docker Compose)
- Zwischen A und B: WireGuard Tunnel
- HTTPS Terminierung: Caddy auf Server B
- API Container ist nicht direkt ans Internet exposed (nur intern im Docker-Netz)

## 2) Voraussetzungen

- Ubuntu 24.04 auf beiden Servern
- Docker Engine + Docker Compose Plugin auf API-Server
- DNS A-Record: booking-api.deine-domain.tld -> oeffentliche IP von Server B
- Offene Ports auf Server B:
  - 22/tcp (SSH)
  - 80/tcp (ACME HTTP Challenge)
  - 443/tcp (HTTPS)
  - 51820/udp (WireGuard)

### 2.1) Docker Engine + Docker Compose auf Ubuntu 24.04 installieren

1. Alte Docker Pakete entfernen (falls vorhanden):

sudo apt remove -y docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc

2. Docker apt Repository einrichten:

sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

3. Docker Engine und Compose Plugin installieren:

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

4. Dienst aktivieren und Testen:

sudo systemctl enable --now docker
sudo docker version
sudo docker compose version

5. Optional (bequemer Betrieb ohne sudo fuer aktuellen User):

sudo usermod -aG docker $USER

Danach neu einloggen (oder neue SSH Session oeffnen), damit die Gruppenmitgliedschaft greift.

## 3) Verzeichnisstruktur auf API-Server

Beispiel:

/opt/restatify-booking-api/
  app/
  requirements.txt
  Dockerfile
  docker-compose.yml
  .env.local
  Caddyfile

## 4) Produktions-Docker-Compose

Hinweis: Diese Compose-Datei ist fuer Produktion gedacht, nicht fuer lokale Entwicklung.

Beispiel docker-compose.prod.yml:

services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: restatify_booking
      POSTGRES_USER: restatify_booking
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U restatify_booking -d restatify_booking"]
      interval: 10s
      timeout: 5s
      retries: 10

  api:
    build:
      context: .
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file:
      - .env.local
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - booking_data:/app/data
    expose:
      - "8088"
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://127.0.0.1:8088/health"]
      interval: 20s
      timeout: 5s
      retries: 5

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      api:
        condition: service_started

volumes:
  pgdata:
  booking_data:
  caddy_data:
  caddy_config:

## 5) Caddy HTTPS Konfiguration

Beispiel Caddyfile:

booking-api.deine-domain.tld {
    encode zstd gzip
    reverse_proxy api:8088
}

Das Zertifikat wird automatisch via Let's Encrypt bezogen.

## 6) .env.local fuer Produktion

Beispiel (anpassen):

APP_ENV=production
HOST=0.0.0.0
PORT=8088
API_KEY=SEHR_LANGER_ZUFAELLIGER_API_KEY
DATABASE_URL=postgresql+psycopg://restatify_booking:${POSTGRES_PASSWORD}@db:5432/restatify_booking
DEFAULT_TIMEZONE=Europe/Berlin
WORKDAY_START_HOUR=9
WORKDAY_END_HOUR=17
SLOT_STEP_MINUTES=30
MAX_WINDOW_DAYS=30
SYNC_WINDOW_DAYS=30
GOOGLE_CREDENTIALS_JSON={...}
GOOGLE_CALENDAR_IDS=
GOOGLE_WRITE_EVENTS_ENABLED=true
GOOGLE_WRITE_CALENDAR_ID=
CONFLICT_NOTIFY_ENABLED=false
CONFLICT_NOTIFY_EMAIL=
CONFLICT_NOTIFY_FROM=restatify-booking-api@your-domain.tld
SMTP_HOST=
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_STARTTLS=true
SMTP_USE_SSL=false

Wichtig:
- API_KEY stark und eindeutig setzen
- Secrets nicht in Git committen
- .env.local Rechte einschranken (z. B. chmod 600)

## 7) WireGuard auf Host-Ebene (nicht im Compose)

Empfehlung: WireGuard direkt auf beiden Ubuntu Hosts betreiben.

Beispiel API-Server /etc/wireguard/wg0.conf:

[Interface]
Address = 10.44.0.1/24
ListenPort = 51820
PrivateKey = API_SERVER_PRIVATE_KEY

[Peer]
PublicKey = WP_SERVER_PUBLIC_KEY
AllowedIPs = 10.44.0.2/32
PersistentKeepalive = 25

Beispiel WP-Server /etc/wireguard/wg0.conf:

[Interface]
Address = 10.44.0.2/24
PrivateKey = WP_SERVER_PRIVATE_KEY

[Peer]
PublicKey = API_SERVER_PUBLIC_KEY
Endpoint = API_PUBLIC_IP:51820
AllowedIPs = 10.44.0.1/32
PersistentKeepalive = 25

Starten:

sudo systemctl enable --now wg-quick@wg0
sudo wg show

## 8) HTTPS + VPN zusammen nutzen

Variante A (einfach):
- Plugin nutzt https://booking-api.deine-domain.tld
- Verkehr ist HTTPS, Route geht ggf. ueber das oeffentliche Netz

Variante B (bevorzugt fuer Server-zu-Server):
- Plugin nutzt weiterhin https://booking-api.deine-domain.tld
- Auf dem WP-Server wird booking-api.deine-domain.tld per /etc/hosts oder internem DNS auf 10.44.0.1 gemappt
- Ergebnis: gleiche TLS-Domain, aber Transport ueber WireGuard-Tunnel

Beispiel /etc/hosts auf WP-Server:

10.44.0.1 booking-api.deine-domain.tld

## 9) Deployment Schritte

1. Dateien auf API-Server nach /opt/restatify-booking-api kopieren
2. Caddyfile und .env.local anpassen
3. Compose starten:

   docker compose -f docker-compose.prod.yml up -d --build

4. Health pruefen:

   curl https://booking-api.deine-domain.tld/health

5. Plugin in WordPress konfigurieren:
   - API Basis URL: https://booking-api.deine-domain.tld
   - API Key: derselbe Wert wie API_KEY

6. End-to-End Test mit echter Reservierung

## 10) Sync Job per Cron

Da Sync im aktuellen Compose als separates Profil vorgesehen ist, kann auf dem API-Host ein Cronjob verwendet werden:

*/5 * * * * cd /opt/restatify-booking-api && docker compose -f docker-compose.prod.yml run --rm api python -m app.sync_google_freebusy >/var/log/restatify-sync.log 2>&1

## 11) Firewall Empfehlungen

API-Server UFW Baseline:

sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 51820/udp
sudo ufw enable

Optional haerter (nach erfolgreichem Setup):
- 443 nur fuer benoetigte Quellnetze erlauben (wenn kein oeffentlicher Zugriff benoetigt wird)

## 12) Betrieb und Monitoring

- Logs API:
  docker compose -f docker-compose.prod.yml logs -f api
- Logs Caddy:
  docker compose -f docker-compose.prod.yml logs -f caddy
- Status:
  docker compose -f docker-compose.prod.yml ps

## 13) Bekannte Security-Nacharbeiten

- API-Key Rotation ohne Downtime (parallel gueltige Keys) als geplanter Folge-Schritt
- Regelmaessige Secret-Rotation und Backup-Tests
