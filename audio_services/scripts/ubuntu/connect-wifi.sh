#!/bin/bash
# Connect to a WiFi network using Netplan on Ubuntu 22.04 Server.
# Creates a persistent Netplan config that survives reboots.

if [ $# -lt 2 ]; then
    echo "Usage: $0 <SSID> <PASSWORD>"
    exit 1
fi

SSID="$1"
PASSWORD="$2"
NETPLAN_FILE="/etc/netplan/60-wifi.yaml"

# Detect the wireless interface
WIFI_DEV=$(ip -o link show | grep -oP 'wl\w+' | head -n1)

if [ -z "$WIFI_DEV" ]; then
    echo "No WiFi device found."
    exit 1
fi

echo "Using WiFi device: $WIFI_DEV"

# Ensure rfkill isn't blocking wifi
if command -v rfkill &>/dev/null; then
    rfkill unblock wifi 2>/dev/null
fi

# Write Netplan config
cat > "$NETPLAN_FILE" <<EOF
network:
  version: 2
  wifis:
    $WIFI_DEV:
      dhcp4: true
      access-points:
        "$SSID":
          password: "$PASSWORD"
EOF

# Secure the file (contains password)
chmod 600 "$NETPLAN_FILE"

echo "Applying Netplan configuration..."
netplan apply

if [ $? -eq 0 ]; then
    echo "Connected to '$SSID' on $WIFI_DEV. Connection saved and will auto-connect on reboot."
else
    echo "Failed to apply Netplan config. Check: sudo netplan generate"
    exit 1
fi
