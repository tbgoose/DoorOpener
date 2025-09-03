# 🚪 DoorOpener

A secure web interface for controlling smart door openers via Home Assistant. Features a modern glass-morphism UI with visual keypad, per-user PINs, audio feedback, battery monitoring, and comprehensive security.

![Version 1.2.0](https://img.shields.io/badge/version-1.2.0-blue?style=flat-square)

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

> **Note:** Pre-built images on ghcr.io are not working yet and are being worked on. For now, you'll need to build locally to avoid having to build every time.

```bash
git clone https://github.com/Sloth-on-meth/DoorOpener.git
cd DoorOpener
cp config.ini.example config.ini
# Edit config.ini with your Home Assistant details and PINs
docker compose up -d
```

### Home Assistant Add-on

1. Add repository: `https://github.com/Sloth-on-meth/DoorOpener`
2. Install "DoorOpener" from add-on store
3. Configure with your Home Assistant token and switch entity
4. Start and access at `http://homeassistant.local:6532`

## Configuration

Edit `config.ini`:

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
port = 6532
test_mode = false  # Set to true for testing without opening door
```

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
