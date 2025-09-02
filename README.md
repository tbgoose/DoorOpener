# 🚪 DoorOpener Web Portal

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=for-the-badge" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/flask-2.3.3-green?style=for-the-badge&logo=flask&logoColor=white" alt="Flask 2.3.3">
  <img src="https://img.shields.io/badge/docker-ready-2496ed?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Ready">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge" alt="PRs Welcome">
</p>

A modern, secure web portal for controlling smart door openers via Home Assistant. Features a premium glass morphism UI, per-user PINs, real-time battery monitoring, and comprehensive security features.

---

## ✨ Features

### 🎨 Modern UI/UX
- **Glass Morphism Design** - Premium frosted glass interface with backdrop blur
- **Responsive Layout** - Optimized for desktop, tablet, and mobile devices
- **Custom Background Support** - Dynamic background image with blur effects
- **Interactive Feedback** - Visual button states, haptic vibration, and toast notifications
- **Real-time Battery Display** - Color-coded battery indicator with gradient fills

### 🔐 Security & Access Control
- **Per-User PIN System** - Individual PINs for each resident/user
- **Brute-Force Protection** - Automatic blocking after failed attempts (5 attempts = 5 minute lockout)
- **Comprehensive Audit Logging** - All access attempts logged with timestamp, user, IP, and result
- **Session Security** - CSRF protection and secure session handling
- **Reverse Proxy Support** - Built-in support for nginx/Apache reverse proxies

### 🏠 Home Assistant Integration
- **Native HA API** - Direct integration with Home Assistant switch entities
- **Zigbee Device Support** - Automatic device detection and battery monitoring
- **Real-time Status** - Live battery level updates and device state monitoring
- **Flexible Configuration** - Support for any Home Assistant switch entity

### 🐳 Production Ready
- **Docker Containerization** - Complete Docker setup with health checks
- **Resource Management** - CPU and memory limits for efficient operation
- **Log Rotation** - Automatic log management with size and retention limits
- **Environment Configuration** - Flexible deployment options

---

## 🚀 Quick Start

### 1. Clone & Configure
```bash
git clone https://github.com/Sloth-on-meth/DoorOpener.git
cd DoorOpener
cp config.ini.example config.ini
# Edit config.ini with your Home Assistant details and user PINs
```

### 2. Docker Deployment (Recommended)
```bash
docker-compose up -d
```

### 3. Manual Installation
```bash
pip install -r requirements.txt
python app.py
```

Visit [http://localhost:5000](http://localhost:5000) to access the portal.

---

## ⚙️ Configuration

### `config.ini` Setup
```ini
[HomeAssistant]
# Home Assistant URL (include http:// or https://)
url = http://homeassistant.local:8123
# Long-lived access token from HA Profile -> Security
token = your_long_lived_access_token_here
# Switch entity ID for your door opener
switch_entity = switch.dooropener_zigbee

[pins]
# Individual PINs for each user
alice = 1234
bob = 5678
charlie = 9012
```

### Background Image (Optional)
Place your custom background image as `/static/background.jpg` for a personalized interface.

---

## 🛠️ API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/open-door` | POST | Door control endpoint (requires PIN) |
| `/battery` | GET | Real-time battery level data |

### Request Examples

**Open Door:**
```bash
curl -X POST http://localhost:5000/open-door \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234"}'
```

**Check Battery:**
```bash
curl http://localhost:5000/battery
```

---

## 🔒 Security Features

### Brute-Force Protection
- **Threshold:** 5 failed attempts
- **Lockout Duration:** 5 minutes
- **Scope:** Global protection across all users
- **Logging:** All blocked attempts are logged

### Audit Logging
All door access attempts are logged to `logs/log.txt` with:
- ISO timestamp
- Client IP address
- Username (if PIN matched)
- Result (SUCCESS/FAILURE)
- Failure reason (if applicable)

**Example Log Entry:**
```
2024-01-15T10:30:45.123456 - 192.168.1.100 - alice - SUCCESS - Door opened
2024-01-15T10:31:12.789012 - 192.168.1.101 - UNKNOWN - FAILURE - Invalid PIN, PIN: 9999
```

---

## 🐳 Docker Deployment

### Production Configuration
The included `docker-compose.yml` provides:
- **Health Checks** - Automatic container health monitoring
- **Resource Limits** - CPU (0.5 cores) and memory (256MB) constraints
- **Log Management** - Automatic log rotation (10MB max, 3 files)
- **Volume Mounts** - Persistent configuration and logs
- **Restart Policy** - Automatic restart unless manually stopped

### Docker Commands
```bash
# Start the application
docker-compose up -d

# View real-time logs
docker-compose logs -f

# Stop the application
docker-compose down

# Rebuild after code changes
docker-compose build && docker-compose up -d --force-recreate

# Check container health
docker-compose ps
```

### Volume Mounts
- `./config.ini:/app/config.ini:ro` - Configuration (read-only)
- `./logs:/app/logs` - Persistent audit logs

---

## 📱 User Interface Features

### Interactive Elements
- **Numeric Keypad** - Mobile devices show numeric keypad for PIN entry
- **Visual Feedback** - Button color changes (green ✓ success, red ✗ error)
- **Haptic Feedback** - Device vibration on success (2 pulses) and error (1 pulse)
- **Toast Notifications** - Non-intrusive status messages in bottom-right corner
- **Shake Animation** - Visual error indication on invalid PIN

### Battery Monitoring
- **Real-time Updates** - Battery level fetched on page load
- **Color Coding** - Green (80%+), Yellow (50-79%), Orange (20-49%), Red (<20%)
- **Gradient Fills** - Animated battery fill based on current level
- **Glass Container** - Modern frosted glass battery indicator

---

## 🔧 Development

### Dependencies
- **Flask 2.3.3** - Web framework
- **Requests 2.31.0** - HTTP client for Home Assistant API
- **Gunicorn 21.2.0** - WSGI server for production
- **Werkzeug 2.3.7** - WSGI utilities and middleware

### Environment Variables
- `FLASK_DEBUG=true` - Enable debug mode (development only)
- `FLASK_SECRET_KEY` - Custom session secret (auto-generated if not set)

### File Structure
```
DoorOpener/
├── app.py                 # Main Flask application
├── config.ini.example     # Configuration template
├── requirements.txt       # Python dependencies
├── Dockerfile            # Container definition
├── docker-compose.yml    # Container orchestration
├── templates/
│   └── index.html        # Main web interface
├── static/
│   └── background.jpg    # Custom background (optional)
└── logs/
    └── log.txt          # Audit log file
```

---

## 🚨 Security Recommendations

### Network Security
- **Local Network Only** - Designed for internal network use
- **HTTPS Required** - Use SSL/TLS for internet-facing deployments
- **Reverse Proxy** - Deploy behind nginx/Apache for additional security
- **Firewall Rules** - Restrict access to authorized IP ranges

### Access Control
- **Strong PINs** - Use 4+ digit PINs, avoid common patterns
- **Regular Rotation** - Change PINs periodically
- **User Management** - Remove unused user PINs from configuration
- **Log Monitoring** - Regularly review audit logs for suspicious activity

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests for:
- UI/UX improvements
- Additional security features
- Home Assistant integrations
- Documentation updates

---

## 📄 License

This project is open source. Please check the repository for license details.
