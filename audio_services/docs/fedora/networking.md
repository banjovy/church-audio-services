# Fedora Network Setup with nmcli

## View Current State

```bash
# List all connections
nmcli connection show

# Show active connections
nmcli connection show --active

# Show device status
nmcli device status

# Show detailed info for a device
nmcli device show enp0s31f6
```

## Wired (Ethernet)

### DHCP (typical)

```bash
# Usually auto-configured. If not, create a connection:
nmcli connection add type ethernet con-name "Wired" ifname enp0s31f6

# Activate it
nmcli connection up "Wired"
```

### Static IP

```bash
nmcli connection modify "Wired" \
  ipv4.method manual \
  ipv4.addresses 192.168.0.50/24 \
  ipv4.gateway 192.168.0.1 \
  ipv4.dns "192.168.0.1 8.8.8.8"

nmcli connection up "Wired"
```

### Switch back to DHCP

```bash
nmcli connection modify "Wired" ipv4.method auto
nmcli connection up "Wired"
```

## Wireless (Wi-Fi)

### Scan for networks

```bash
nmcli device wifi list
```

### Connect to a network

```bash
nmcli device wifi connect "NetworkName" password "yourpassword"
```

### Connect to a hidden network

```bash
nmcli device wifi connect "NetworkName" password "yourpassword" hidden yes
```

### Create a saved Wi-Fi connection

```bash
nmcli connection add type wifi con-name "ChurchWifi" \
  ssid "NetworkName" \
  wifi-sec.key-mgmt wpa-psk \
  wifi-sec.psk "yourpassword"

nmcli connection up "ChurchWifi"
```

### Static IP on Wi-Fi

```bash
nmcli connection modify "ChurchWifi" \
  ipv4.method manual \
  ipv4.addresses 192.168.0.60/24 \
  ipv4.gateway 192.168.0.1 \
  ipv4.dns "192.168.0.1"

nmcli connection up "ChurchWifi"
```

## Common Operations

```bash
# Disconnect
nmcli connection down "Wired"

# Delete a connection
nmcli connection delete "Wired"

# Restart NetworkManager
sudo systemctl restart NetworkManager

# Enable/disable Wi-Fi radio
nmcli radio wifi off
nmcli radio wifi on
```

## Troubleshooting

### No IP assigned (DHCP not working)

```bash
# Check if the device is managed by NetworkManager
nmcli device status

# If "unmanaged", check /etc/NetworkManager/NetworkManager.conf
# Make sure the device isn't excluded

# Force a DHCP renewal
nmcli connection down "Wired"
nmcli connection up "Wired"

# Check DHCP client logs
journalctl -u NetworkManager --since "5 minutes ago" | grep -i dhcp
```

### Can't reach the network

```bash
# Check IP assignment
ip addr show

# Check default route
ip route show

# Ping gateway
ping -c 3 192.168.0.1

# Ping external (DNS bypass)
ping -c 3 8.8.8.8

# If ping works but names don't resolve, check DNS
cat /etc/resolv.conf
nmcli device show | grep DNS
```

### Wi-Fi won't connect

```bash
# Check if radio is enabled
nmcli radio wifi

# Check if driver is loaded
lspci | grep -i wireless
lsmod | grep -i wifi

# Check for WPA supplicant errors
journalctl -u NetworkManager --since "2 minutes ago" | grep -i wifi

# Forget and reconnect
nmcli connection delete "ChurchWifi"
nmcli device wifi connect "NetworkName" password "yourpassword"
```

### Device not showing up

```bash
# List hardware
nmcli device
ip link show

# Check if driver is loaded
dmesg | grep -i eth
dmesg | grep -i wifi

# For USB adapters
lsusb
```

### Connection drops or unstable

```bash
# Check for power management issues (Wi-Fi)
iwconfig 2>/dev/null | grep "Power Management"

# Disable Wi-Fi power saving
nmcli connection modify "ChurchWifi" 802-11-wireless.powersave 2

# Check system logs for disconnect events
journalctl -u NetworkManager --since "30 minutes ago" | grep -i "disconn\|deactivat"
```

### Firewall blocking traffic

```bash
# Check if firewall is active
sudo firewall-cmd --state

# List open ports
sudo firewall-cmd --list-all

# Temporarily disable to test
sudo systemctl stop firewalld
# (re-enable after testing)
sudo systemctl start firewalld
```
