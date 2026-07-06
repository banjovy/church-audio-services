# HTTPS Options for LAN Audio Server

## Current Decision: Stay on HTTP

Plain HTTP on `audio.local:8080` works for our use case. The features we rely on
(WebSocket text captions, Web Audio playback) do not require a secure context in current
browsers. There's no client-side setup friction — scan the QR code and go.

What we'd gain from HTTPS eventually:
- Service Workers / PWA install prompt
- Future browser APIs that may gate on secure context
- Encrypted traffic (low priority on a trusted LAN)

---

## Options Summary

| Approach | Client Setup | Complexity | Best For |
|----------|-------------|------------|----------|
| HTTP (current) | None | None | LAN appliance, random phones |
| Reverse proxy + real domain | None | Medium | Production-ready HTTPS |
| mkcert (local CA) | Install CA on each device | Low-Medium | Controlled/managed devices |
| Self-signed cert | Accept browser warning | Low | Dev/testing only |

---

## Future Plan: Reverse Proxy with Real Domain + Let's Encrypt

This is the recommended upgrade path. A real certificate from Let's Encrypt is trusted
by every device automatically — no client-side setup, no warnings.

### Prerequisites

- A domain you control (e.g., `audio.yourchurch.org`)
- Access to DNS settings for that domain
- The server on a static LAN IP (e.g., `192.168.1.50`)

### Overview

```
Phone/Tablet
    |
    | HTTPS (port 443, trusted cert)
    v
[caddy or nginx on audio server]
    |
    | HTTP localhost:8080
    v
[audio server (aiohttp)]
```

The reverse proxy terminates TLS and forwards traffic to the app unchanged.
The app itself stays on HTTP — no code changes needed.

### Step 1: Get a Domain

Any registrar works. You only need one A record pointing to the server's LAN IP.
A subdomain of something you already own is fine:

```
audio.yourchurch.org  A  192.168.1.50
```

This is a "split-horizon" setup — the DNS record points to a private IP, so it only
resolves usefully from inside the LAN. That's fine for our purposes.

### Step 2: Install Caddy (recommended) or Nginx

Caddy is the simplest option — it handles Let's Encrypt certificates automatically
with zero configuration for renewal.

```bash
# Fedora
sudo dnf install caddy
```

Alternatively, nginx + certbot:

```bash
sudo dnf install nginx certbot python3-certbot-nginx
```

### Step 3: DNS-01 Certificate Challenge

Since the server isn't publicly reachable, you can't use the default HTTP-01 challenge.
Use DNS-01 instead — it proves domain ownership by creating a TXT record.

#### Option A: Caddy with DNS plugin

Caddy supports DNS-01 natively with provider plugins. You'll need a build of Caddy
that includes your DNS provider's plugin (Cloudflare, Route53, etc.).

```bash
# Download custom Caddy build with your DNS provider plugin
# See: https://caddyserver.com/download

# Example Caddyfile
audio.yourchurch.org {
    reverse_proxy localhost:8080
    tls {
        dns cloudflare {env.CF_API_TOKEN}
    }
}
```

```bash
# Set your DNS API token
echo 'CF_API_TOKEN=your-token-here' | sudo tee /etc/caddy/env

# Start Caddy
sudo systemctl enable --now caddy
```

Caddy will obtain and auto-renew the cert via DNS-01. Done.

#### Option B: certbot with DNS plugin

```bash
# Install DNS plugin for your registrar (example: Cloudflare)
sudo dnf install python3-certbot-dns-cloudflare

# Create credentials file
sudo mkdir -p /etc/letsencrypt
cat <<EOF | sudo tee /etc/letsencrypt/cloudflare.ini
dns_cloudflare_api_token = your-token-here
EOF
sudo chmod 600 /etc/letsencrypt/cloudflare.ini

# Request certificate
sudo certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  -d audio.yourchurch.org

# Certs land in /etc/letsencrypt/live/audio.yourchurch.org/
```

Then configure nginx:

```nginx
server {
    listen 443 ssl;
    server_name audio.yourchurch.org;

    ssl_certificate /etc/letsencrypt/live/audio.yourchurch.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/audio.yourchurch.org/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

server {
    listen 80;
    server_name audio.yourchurch.org;
    return 301 https://$host$request_uri;
}
```

The `Upgrade` and `Connection` headers are critical — they allow WebSocket
connections to pass through the proxy.

```bash
sudo systemctl enable --now nginx

# Auto-renewal (certbot sets up a timer, but verify):
sudo systemctl list-timers | grep certbot
```

### Step 4: Firewall

```bash
# Allow HTTPS traffic (replace or supplement existing port 8080 rule)
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-service=http   # for redirect
sudo firewall-cmd --reload
```

You can optionally remove the direct 8080 rule once the proxy is in place,
or keep it for local/fallback access.

### Step 5: Update QR Codes

Update the QR code generation to use the domain name with HTTPS:

```python
url = f"https://audio.yourchurch.org/"
```

This could be a config.json field (e.g., `"public_url"`) so the app doesn't
need to auto-detect anything.

### Step 6: Verify WebSocket + Audio Streaming

After setup, test:
- Caption display page loads over HTTPS
- WebSocket connection upgrades successfully (wss://)
- Audio streaming via /ws/audio works through the proxy
- QR code scan on a phone works with no warnings

---

## Notes

- **Cert renewal is automatic** with both Caddy and certbot. No manual intervention.
- **No code changes to the app** — it stays on HTTP internally.
- **mDNS still works** — `audio.local` continues resolving for direct HTTP access
  on the LAN as a fallback.
- **DNS provider plugins** — most registrars/DNS hosts are supported. Common ones:
  Cloudflare (free tier works), Route53, DigitalOcean, Namecheap, Google Domains.
- **If you don't want a public DNS record** pointing to a private IP, some DNS
  providers let you create records that only resolve internally. Alternatively,
  run a local DNS server (like dnsmasq) but that adds complexity.
