#!/bin/bash
# Install (or update) the audio-services systemd service on Ubuntu 22.04.
# Usage: sudo ./install-service.sh [username]
#   username defaults to 'audio'
# Idempotent — safe to re-run at any time.

set -e

SERVICE_USER="${1:-audio}"
INSTALL_DIR="/home/$SERVICE_USER/church-audio-services"
SERVICE_NAME="audio-services"
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

# Generate unit file (overwrites if already present)
cat > "$UNIT_FILE" <<EOF
[Unit]
Description=Church Audio Services
After=network.target sound.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
EnvironmentFile=$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/.venv/bin/python -m audio_services.main
Environment="LD_LIBRARY_PATH=$INSTALL_DIR/.venv/lib/python3.12/site-packages/nvidia/cudnn/lib"
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
echo "  sudo systemctl start audio-services    # Start"
echo "  sudo systemctl stop audio-services     # Stop"
echo "  sudo systemctl restart audio-services  # Restart"
echo "  sudo systemctl status audio-services   # Check status"
echo "  journalctl -u audio-services -f        # View logs"
echo ""
echo "The service will auto-start on boot."
echo "To start now: sudo systemctl start audio-services"
