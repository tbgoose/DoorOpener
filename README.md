# 🚨 Help Wanted: Home Assistant Add-on Needed!

**I couldn't figure out how to turn this project into a proper Home Assistant add-on. If you know how, please open a PR!**

> **Important:** Any add-on solution must not break standalone usage. The project must remain fully usable both as a Home Assistant add-on _and_ as a standalone app (Docker, pip, etc).

---

# 🚪 DoorOpener

A secure web interface for controlling smart door openers via Home Assistant. Features a modern glass-morphism UI with visual keypad, per-user PINs, audio feedback, battery monitoring, and comprehensive security.

![Version 1.6.0](https://img.shields.io/badge/version-1.6.0-blue?style=flat-square)

<img width="2554" height="1187" alt="image" src="https://github.com/user-attachments/assets/e9e2fd6c-aa32-4ea1-933f-668fad3fbfc4" />

<img width="2554" height="1187" alt="image" src="https://github.com/user-attachments/assets/4d5259fa-ee7b-4d03-a02b-b77301cebf0c" />

## What It Does

DoorOpener provides a web-based keypad interface to remotely open doors connected to Home Assistant. Users enter their personal PIN on a visual keypad, and the system securely communicates with Home Assistant to trigger the door opener.

**Key Features:**
- Visual 3x4 keypad interface with auto-submit
- Individual PINs for each user
- Audio feedback (success chimes, failure sounds)
- Real-time battery monitoring for Zigbee devices
- Multi-layer security with rate limiting and IP blocking
- Admin dashboard for viewing access logs
- Test mode for safe development
- **Supports Home Assistant `switch`, `lock`, and `input_boolean` entities**

## Quick Start

### Docker (Recommended)

You can run DoorOpener using the prebuilt image from GitHub Container Registry (ghcr.io):

```bash
git clone https://github.com/Sloth-on-meth/DoorOpener.git
cd DoorOpener
cp config.ini.example config.ini
cp .env.example .env
# Edit config.ini with your Home Assistant details and PINs
# Edit .env to set DOOROPENER_PORT if different from 6532
docker run -d --env-file .env -v $(pwd)/config.ini:/app/config.ini:ro -v $(pwd)/logs:/app/logs -p 6532:6532 ghcr.io/sloth-on-meth/dooropener:latest
```

This will start DoorOpener using the official image. If you need to change the port, update the .env file and adjust the `-p` argument accordingly.

#### Building Locally (Optional)
If you want to build the image yourself:
```bash
docker build -t dooropener:latest .
docker run -d --env-file .env -v $(pwd)/config.ini:/app/config.ini:ro -v $(pwd)/logs:/app/logs -p 6532:6532 dooropener:latest
```


<!--
#### Using the public ghcr.io image

(Registry-based deployment is currently disabled)
-->


## Configuration

### Environment Variables (.env file)

```bash
# Port configuration (optional, defaults to 6532)
DOOROPENER_PORT=6532

# Timezone (optional, defaults to UTC)
TZ=America/New_York
```

### Application Config (config.ini)

```ini
[HomeAssistant]
url = http://homeassistant.local:8123
token = your_long_lived_access_token
switch_entity = switch.your_door_opener

[pins]
alice = 1234
bob = 5678

[admin]
admin_password = secure_password

[server]
# Overridden by DOOROPENER_PORT env var if set
port = 6532
# Set to true for testing without opening door
test_mode = false

[security]
# Maximum failed attempts per IP before blocking
max_attempts = 5 
# Block time in minutes after max attempts reached
block_time_minutes = 5
# Maximum global attempts per hour across all users
max_global_attempts_per_hour = 50
# Maximum failed attempts per session before blocking
session_max_attempts = 3
```

### OIDC (Authentik) — Experimental

> IMPORTANT: This OIDC/Authentik integration is a rudimentary, first-pass implementation. It has not been fully verified end‑to‑end in production. It may not work in your setup. Use at your own risk and please open issues/PRs with fixes.

DoorOpener can optionally integrate with Authentik using in‑app OIDC. When enabled, users can sign in via SSO, and—optionally—open the door without a PIN.

```ini
[oidc]
enabled = false                     # Set to true to enable OIDC
issuer = https://auth.example.com/application/o/dooropener
client_id = your_client_id
client_secret = your_client_secret
redirect_uri = https://your.domain/oidc/callback

# Optional group required for admin dashboard access
admin_group = dooropener-admins

# Optional group allowed to open the door via OIDC (pinless)
# Leave empty to allow any authenticated OIDC user
user_group = dooropener-users

# If true, OIDC users still must enter a PIN (no pinless open)
require_pin_for_oidc = false
```

Notes:
- In development over HTTP, set `SESSION_COOKIE_SECURE=false` (env) so the browser sends the session cookie.
- Set a stable secret across instances via `FLASK_SECRET_KEY` (env) or `[server] secret_key` in `config.ini`.
- The implementation is minimal and may require adjustments to claims (e.g., `groups`) depending on your Authentik setup.

**Configuration Priority:**
1. Environment variables (`.env` file) - highest priority
2. `config.ini` settings
3. Default values

## Usage

1. **Access Interface** - Visit `http://localhost:6532`
2. **Enter PIN** - Use the visual keypad to enter your 4-8 digit PIN
3. **Auto-Submit** - Door opens automatically when valid PIN length is entered
4. **Admin Access** - Click gear icon for admin dashboard (view logs, manage users)

## Security Features

- **Configurable Rate Limiting** - Customizable failed attempt limits and block times
- **Multi-Layer Protection** - IP-based, session-based, and global rate limiting
- **Progressive Delays** - Increasing delays (1s→16s) after failed attempts
- **Session Tracking** - Prevents easy bypass of security measures  
- **Audit Logging** - All attempts logged with timestamps, IPs, and results
- **Input Validation** - PIN format validation and request sanitization
- **Security Headers** - XSS protection, clickjacking prevention, CSP

### Security Configuration

All security parameters are configurable via `config.ini`:

- `max_attempts` - Failed attempts per IP before blocking (default: 5)
- `block_time_minutes` - Block duration in minutes (default: 5)
- `max_global_attempts_per_hour` - Global rate limit across all users (default: 50)
- `session_max_attempts` - Failed attempts per session before blocking (default: 3)

## API Endpoints

- `GET /` - Main interface
- `POST /open-door` - Door control (requires PIN unless OIDC pinless is enabled and user is authorized)
- `GET /battery` - Battery level data
- `GET /admin` - Admin dashboard

## Development

**Test Mode:** Set `test_mode = true` in config to test interface without opening door.

**Manual Installation:**
```bash
pip install -r requirements.txt
python app.py
```

## License

Open source - see repository for details.
