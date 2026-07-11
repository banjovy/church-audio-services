#!/bin/bash
# Connect to a WiFi network using nmcli on Fedora 41.
# Connection is saved to /etc/NetworkManager/system-connections/ and persists across reboots.

if [ $# -lt 2 ]; then
    echo "Usage: $0 <SSID> <PASSWORD>"
    exit 1
fi

SSID="$1"
PASSWORD="$2"

# Detect the wireless interface (Fedora 41 commonly uses wlp* naming)
WIFI_DEV=$(nmcli -t -f DEVICE,TYPE device | grep ':wifi$' | cut -d: -f1 | head -n1)

if [ -z "$WIFI_DEV" ]; then
    echo "No WiFi device found."
    exit 1
fi

echo "Using WiFi device: $WIFI_DEV"

# Ensure WiFi radio is enabled
nmcli radio wifi on

# Delete any existing connection with the same SSID to avoid duplicates
nmcli connection delete "$SSID" 2>/dev/null

# Connect and save (nmcli saves by default, making it persistent across reboots)
nmcli device wifi connect "$SSID" password "$PASSWORD" ifname "$WIFI_DEV"

if [ $? -eq 0 ]; then
    # Set connection to auto-connect on boot
    nmcli connection modify "$SSID" connection.autoconnect yes
    echo "Connected to '$SSID' on $WIFI_DEV. Connection saved and will auto-connect on reboot."
else
    echo "Failed to connect to '$SSID'."
    exit 1
fi
