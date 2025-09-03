# 🚪 DoorOpener

A secure web interface for controlling smart door openers via Home Assistant. Features a modern glass-morphism UI with visual keypad, per-user PINs, audio feedback, battery monitoring, and comprehensive security.

![Version 1.4.0](https://img.shields.io/badge/version-1.4.0-blue?style=flat-square)

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

### Home Assistant Add-on

1. Add repository: `https://github.com/Sloth-on-meth/DoorOpener`
2. Install "DoorOpener" from add-on store
3. Configure with your Home Assistant token and switch entity
4. Start and access at `http://homeassistant.local:6532`

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
port = 6532  # Overridden by DOOROPENER_PORT env var if set
test_mode = false  # Set to true for testing without opening door
```

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

- **Rate Limiting** - Progressive delays (1s→16s) and IP blocking after 5 failed attempts
- **Session Tracking** - Prevents easy bypass of security measures  
- **Audit Logging** - All attempts logged with timestamps, IPs, and results
- **Input Validation** - PIN format validation and request sanitization
- **Security Headers** - XSS protection, clickjacking prevention, CSP

## API Endpoints

- `GET /` - Main interface
- `POST /open-door` - Door control (requires PIN)
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
