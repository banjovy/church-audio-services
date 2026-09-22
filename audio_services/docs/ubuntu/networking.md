# Ubuntu 22.04 Network Setup with Netplan

Ubuntu 22.04 Server uses Netplan for network configuration, backed by systemd-networkd.

## View Current State

```bash
# Show IP addresses
ip addr show

# Show active routes
ip route show

# Show Netplan config
cat /etc/netplan/*.yaml

# Apply changes after editing
sudo netplan apply

# Test changes (auto-reverts after 120s if not confirmed)
sudo netplan try
```

## Wired (Ethernet)

Netplan configs live in `/etc/netplan/`. The default file is usually `00-installer-config.yaml` or `01-netcfg.yaml`.

### DHCP (typical)

```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  ethernets:
    enp0s31f6:
      dhcp4: true
```

```bash
sudo netplan apply
```

### Static IP

```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  ethernets:
    enp0s31f6:
      dhcp4: false
      addresses:
        - 192.168.0.50/24
      routes:
        - to: default
          via: 192.168.0.1
      nameservers:
        addresses:
          - 192.168.0.1
          - 8.8.8.8
```

```bash
sudo netplan apply
```

### Switch back to DHCP

Change `dhcp4: true`, remove `addresses`, `routes`, and `nameservers` blocks, then:

```bash
sudo netplan apply
```

## Wireless (Wi-Fi)

### Install required packages

```bash
sudo apt install -y wpasupplicant
```

### Connect to a network

```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  wifis:
    wlp2s0:
      dhcp4: true
      access-points:
        "NetworkName":
          password: "yourpassword"
```

```bash
sudo netplan apply
```

### Connect to a hidden network

```yaml
network:
  version: 2
  wifis:
    wlp2s0:
      dhcp4: true
      access-points:
        "NetworkName":
          password: "yourpassword"
          hidden: true
```

### Static IP on Wi-Fi

```yaml
network:
  version: 2
  wifis:
    wlp2s0:
      dhcp4: false
      addresses:
        - 192.168.0.60/24
      routes:
        - to: default
          via: 192.168.0.1
      nameservers:
        addresses:
          - 192.168.0.1
      access-points:
        "NetworkName":
          password: "yourpassword"
```

## Common Operations

```bash
# Find your interface names
ip link show

# Bring an interface down/up
sudo ip link set enp0s31f6 down
sudo ip link set enp0s31f6 up

# Check if networkd is managing things
networkctl status

# Restart networking
sudo netplan apply
# or
sudo systemctl restart systemd-networkd
```

## Using NetworkManager Instead (optional)

If you prefer nmcli (same as Fedora), install NetworkManager and set it as the Netplan renderer:

```bash
sudo apt install -y network-manager
```

```yaml
# /etc/netplan/01-netcfg.yaml
network:
  version: 2
  renderer: NetworkManager
```

```bash
sudo netplan apply
```

Then use `nmcli` commands as documented in the Fedora networking guide.

## Troubleshooting

### No IP assigned (DHCP not working)

```bash
# Check device status
networkctl status enp0s31f6

# Check for DHCP client activity
journalctl -u systemd-networkd --since "5 minutes ago" | grep -i dhcp

# Force renewal
sudo networkctl renew enp0s31f6

# Validate netplan config (catches YAML errors)
sudo netplan generate
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

# If ping works but names don't resolve
resolvectl status
cat /etc/resolv.conf
```

### Wi-Fi won't connect

```bash
# Check if radio is blocked
rfkill list

# Unblock if needed
sudo rfkill unblock wifi

# Check if driver is loaded
lspci | grep -i wireless
lsmod | grep -i wifi

# Check wpa_supplicant logs
journalctl -u wpa_supplicant --since "2 minutes ago"

# Check networkd logs
journalctl -u systemd-networkd --since "2 minutes ago" | grep -i wifi
```

### Device not showing up

```bash
# List hardware
ip link show

# Check kernel messages
dmesg | grep -i eth
dmesg | grep -i wifi

# For USB adapters
lsusb
```

### Connection drops or unstable

```bash
# Check for Wi-Fi power management
iwconfig 2>/dev/null | grep "Power Management"

# Disable Wi-Fi power saving
sudo iwconfig wlp2s0 power off

# Make it permanent via Netplan (not directly supported),
# use a networkd override or /etc/rc.local

# Check system logs for disconnect events
journalctl -u systemd-networkd --since "30 minutes ago" | grep -i "carrier\|lost\|removed"
```

### Firewall blocking traffic

```bash
# Check if ufw is active
sudo ufw status

# List rules
sudo ufw status numbered

# Temporarily disable to test
sudo ufw disable
# (re-enable after testing)
sudo ufw enable
```

### Netplan YAML syntax errors

```bash
# Validate without applying
sudo netplan generate

# Common mistakes:
# - Tabs instead of spaces (YAML requires spaces)
# - Wrong indentation level
# - Missing quotes around SSID or password with special chars
```
