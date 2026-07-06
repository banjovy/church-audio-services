# Display & Streaming Guide

How mobile devices and TVs consume the captioning and audio streaming services.

## Dedicated Caption TV

### What It Is

A TV or monitor mounted in the auditorium specifically for displaying captions in large, high-contrast text. Always visible, no interaction required — like subtitles at a movie theater.

### How It Connects

The TV runs a full-screen web browser pointing at the server's TV display URL:

```
http://<server-ip>:8080/display?mode=tv
```

### Setup Options (Pick One)

1. **HDMI direct from the server** — simplest. Plug an HDMI cable from the mini PC to the TV. Open Chromium in full-screen kiosk mode on that display. Zero network dependency for the TV itself.

2. **Chromecast / Fire TV Stick** — if the TV isn't physically near the server. Plug the stick into the TV, open its built-in browser, navigate to the display URL. The stick connects via WiFi to reach the server.

3. **Raspberry Pi (dedicated)** — mount a Pi behind the TV running Chromium in kiosk mode pointing at the URL. Most reliable for a permanent install since it boots straight into the caption display.

### What the Viewer Sees

- Black background, white text, enormous font (scales with viewport — readable from ~15 feet)
- Only the most recent caption is shown, replacing the previous one as new text arrives
- A small green/orange/red dot in the corner shows connection status

### Behavior

- On load: shows "Waiting for speech..."
- When captions arrive: displays current text, centered
- If connection drops: shows "Reconnecting..." in orange, auto-retries every 5 seconds
- No scrolling, no history — just the current phrase, big and clear

---

## Personal Devices (Phones/Tablets)

### What It Is

Any attendee's phone or tablet, accessing captions through their mobile browser. No app install needed.

### How They Connect

Two entry points:

1. **QR code** — posted on a printed card in the lobby, in the bulletin, or briefly shown on the main screen. The QR encodes the home page URL. Attendee scans with their phone camera and it opens in Safari/Chrome automatically, where they can choose their preferred display mode.

2. **Direct URL** — for regulars who bookmark it. The mDNS name (e.g., `http://audio.local:8080`) works on iPhones natively; Android may need the IP directly (see `/qr-ip` page).

### Prerequisite

The phone must be on the church WiFi network (same subnet as the server). A guest network that isolates clients from the LAN won't work — the phone needs to reach the server's IP on port 8080.

### Display Modes Available

#### Scrolling Mode (`?mode=scroll`)

- Captions accumulate like a chat transcript
- New lines appear at the bottom, page auto-scrolls
- Attendee can scroll up to re-read something they missed
- Font size is comfortable for handheld reading
- Good for: people who want full context, or want to review what was said

#### TV Mode (`?mode=tv`)

- Large centered text, best for big screens
- Shows a rolling window of recent lines with fade effect
- Previous lines dim as new ones arrive

#### Current-Only Mode (`?mode=current`)

- Shows only the single most recent caption, centered on screen
- Previous text disappears when new text arrives
- Simpler, less distracting — just glance down and see what's being said now
- Good for: people who want a quick assist, not a full transcript

### What the Viewer Sees

- Dark background (saves battery on OLED phones, easy on eyes in a dim auditorium)
- Connection indicator in the corner
- No controls to fiddle with — it just works

### Behavior

- On connect: receives the last 10 captions as history (so you're not starting from blank if you join mid-sermon)
- Live: new captions push instantly via WebSocket (sub-50ms delivery once transcribed)
- If WiFi drops or phone sleeps: shows "Reconnecting...", auto-retries every 5 seconds. On reconnect, gets recent history so you catch up.
- No login, no pairing, no cookies — completely stateless. Close the tab, open it again, works immediately.

---

## Audio Streaming (Hearing Assist)

### What It Is

Live audio from the mixer board streamed to mobile devices over WiFi. Users connect at `/listen`, tap play, and hear the service through earphones or hearing devices with under one second of delay.

### How They Connect

From the home page (`/`), tap the "Listen" link. Or navigate directly to:

```
http://audio.local:8080/listen
```

### What the Listener Gets

- Play/Stop toggle — audio starts on tap (satisfies mobile autoplay policies)
- Level meter showing audio activity
- Auto-reconnect if WiFi drops momentarily
- ~600-700ms end-to-end latency (much lower than caption text delay)

### Technical Notes

- Ogg/Opus encoding at 128kbps via WebSocket
- Web Audio API decoding on the client
- Independent connection limit (`max_audio_clients`, default 50)
- Works alongside captions — same server, different WebSocket endpoint

See `docs/hearing-assist-stream.md` for full implementation details.

---

## How the WebSocket Connection Works (Both Targets)

The flow is the same for TV and phone:

1. Browser loads the HTML page from the server (`/display?mode=X`)
2. JavaScript in that page opens a WebSocket to `ws://<server>:8080/ws`
3. Server immediately sends the last 10 captions as JSON messages
4. From then on, every new caption is pushed to all connected clients in real-time
5. Server pings every 30 seconds; if a client doesn't respond, it gets dropped (frees resources)

Each caption message looks like:

```json
{
  "text": "And that's what grace means in this context.",
  "language": "en",
  "timestamp": 1750025546.123,
  "sequence_number": 47
}
```

The client-side JavaScript is minimal — receives JSON, updates the DOM. No framework, no build step, works on any browser from the last 5 years.

---

## Network Topology

```
[Mixer Board] --aux audio--> [USB Interface] --> [Fedora Mini PC / Audio Server]
                                                          |
                                              port 8080 (HTTP + WS)
                                                          |
                                 ┌─────────────────┬──────┴──────┐
                                 │                 │             │
                           [Caption TV]    [Phone 1]    [Phone 2] ...
                           (HDMI or WiFi)  (church WiFi) (church WiFi)
```

All devices must reach the server's IP on port 8080. The server binds to `0.0.0.0` so it's accessible from any interface on the host machine.

## Services Available

The server provides multiple services from a single endpoint:

| Path | Service | Description |
|------|---------|-------------|
| `/` | Home page | Links to all services, themed UI |
| `/display` | Live captions | TV, scroll, and current display modes |
| `/listen` | Audio stream | Live audio playback (hearing assist) |
| `/ws` | Caption WebSocket | Real-time caption text delivery |
| `/ws/audio` | Audio WebSocket | Live Ogg/Opus audio segments |
| `/status` | System status | Audio levels, uptime, client count (PIN-protected) |
| `/qr` | QR code page | mDNS URL for scanning (`audio.local`) |
| `/qr-ip` | QR code page | LAN IP URL for Android fallback |

---

## Network Requirements

- Church WiFi must allow devices on the same subnet to communicate (client isolation disabled)
- Server needs a stable IP address (static IP recommended, or mDNS via Avahi)
- Port 8080 must not be blocked by any local firewall on the host
- No internet required for service delivery — everything is local network only
- Recommended: dedicated SSID or VLAN for AV equipment if the church network is complex

---

## Kiosk Mode Setup (for Caption TV)

### Chromium Kiosk

```bash
chromium-browser --kiosk --noerrdialogs --disable-infobars "http://<server-ip>:8080/display?mode=tv"
```

### Chromium on Raspberry Pi

Add to `/etc/xdg/lxsession/LXDE-pi/autostart`:
```
@chromium-browser --kiosk --noerrdialogs --disable-infobars http://<server-ip>:8080/display?mode=tv
```

---

## QR Code Access

The server provides two dedicated QR code pages:

### mDNS Version (`/qr`)

```
http://<server>:8080/qr
```

Displays a QR code encoding the `audio.local` URL. Works reliably on iPhones/iPads and most desktop browsers. Best for Apple-heavy audiences.

### IP Version (`/qr-ip`)

```
http://<server>:8080/qr-ip
```

Displays a QR code encoding the server's LAN IP address. Use this as a fallback for Android devices (especially pre-Android 12) that may not resolve `.local` addresses.

### Raw QR Images

- `/qr.png` — QR image using `audio.local`
- `/qr-ip.png` — QR image using the server's LAN IP

These can be embedded elsewhere or printed directly.

### Usage

- Display the `/qr` or `/qr-ip` page on the main screen before service starts
- Print the QR image and post in the lobby/bulletin
- Include in digital announcements

The home page at `/` provides links to all three display modes (scroll, TV, current) for users who arrive via QR code.
