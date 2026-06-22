#!/bin/bash
# Install (or update) the captioning systemd service.
# Usage: sudo ./install-service.sh [username]
#   username defaults to 'lscoc'
# Idempotent — safe to re-run at any time.

set -e

SERVICE_USER="${1:-lscoc}"
INSTALL_DIR="/home/$SERVICE_USER/church-av"
SERVICE_NAME="captioning"
UNIT_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Validate user exists
if ! id "$SERVICE_USER" &>/dev/null; then
    echo "ERROR: User '$SERVICE_USER' does not exist."
    echo "Create it first: sudo useradd -m $SERVICE_USER"
    exit 1
fi

# Validate install directory
if [ ! -d "$INSTALL_DIR" ]; then
    echo "ERROR: Install directory not found: $INSTALL_DIR"
    exit 1
fi

if [ ! -f "$INSTALL_DIR/.venv/bin/python" ]; then
    echo "ERROR: Python venv not found at $INSTALL_DIR/.venv"
    exit 1
fi

echo "Installing systemd service for user: $SERVICE_USER"
echo "Install directory: $INSTALL_DIR"

# Set SELinux contexts so systemd can read .env and exec the venv python
if command -v semanage &>/dev/null; then
    echo "Configuring SELinux file contexts..."
    semanage fcontext -a -t etc_t "$INSTALL_DIR/\.env" 2>/dev/null || \
        semanage fcontext -m -t etc_t "$INSTALL_DIR/\.env"
    semanage fcontext -a -t bin_t "$INSTALL_DIR/\.venv/bin(/.*)?" 2>/dev/null || \
        semanage fcontext -m -t bin_t "$INSTALL_DIR/\.venv/bin(/.*)?"
    restorecon -v "$INSTALL_DIR/.env"
    restorecon -Rv "$INSTALL_DIR/.venv/bin/"
fi

# Generate unit file (overwrites if already present)
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Live Captioning Service
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/.venv/bin/python -m captioning.main
Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Hardening
NoNewPrivileges=true
ProtectSystem=full
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo ""
echo "=== Service installed ==="
echo ""
echo "Commands:"
echo "  sudo systemctl start captioning    # Start"
echo "  sudo systemctl stop captioning     # Stop"
echo "  sudo systemctl restart captioning  # Restart"
echo "  sudo systemctl status captioning   # Check status"
echo "  journalctl -u captioning -f        # View logs"
echo ""
echo "The service will auto-start on boot."
echo "To start now: sudo systemctl start captioning"
