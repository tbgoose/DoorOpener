# 🚪 DoorOpener Web Portal v1.1

<p align="center">
  <img src="https://img.shields.io/badge/version-1.1.0-blue?style=for-the-badge" alt="Version 1.1.0">
  <img src="https://img.shields.io/badge/flask-2.3.3-green?style=for-the-badge&logo=flask&logoColor=white" alt="Flask 2.3.3">
  <img src="https://img.shields.io/badge/docker-ready-2496ed?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Ready">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge" alt="PRs Welcome">
</p>

A modern, secure web portal for controlling smart door openers via Home Assistant. Features a premium glass morphism UI with visual keypad interface, per-user PINs, audio feedback, real-time battery monitoring, and comprehensive security features.
<img width="1920" height="949" alt="image" src="https://github.com/user-attachments/assets/5ea98bb2-1328-45ac-b18c-f51894f423bf" />
<img width="1920" height="949" alt="image" src="https://github.com/user-attachments/assets/79cefb52-2757-47e3-9c1c-4bf418743971" />

---

## ✨ Features

### 🎨 Modern UI/UX
- **Glass Morphism Design** - Premium frosted glass interface with backdrop blur
- **Visual Keypad Interface** - Touch-friendly 3x4 keypad replacing traditional text input
- **Auto-Submit PIN Entry** - Door opens automatically when valid PIN length is entered
- **Audio Feedback** - Success chimes and "womp womp" failure sounds using Web Audio API
- **Responsive Layout** - Optimized for desktop, tablet, and mobile devices
- **Custom Background Support** - Dynamic background image with blur effects
- **Interactive Feedback** - Visual button states, haptic vibration, and toast notifications
- **Real-time Battery Display** - Color-coded battery indicator with gradient fills
- **Keyboard Support** - Physical keyboard input (0-9, Backspace, Enter) alongside touch
- **Admin Access Button** - Floating gear icon in bottom-right corner for easy admin access

### 🔐 Security & Access Control
- **Per-User PIN System** - Individual PINs for each resident/user
- **Per-IP Rate Limiting** - Individual IP tracking with progressive delays (1s, 2s, 4s, 8s, 16s)
- **Advanced Brute-Force Protection** - 5 failed attempts = 5 minute IP-specific lockout
- **Input Validation** - PIN format validation (4-8 digits) with sanitization
- **Security Headers** - XSS protection, clickjacking prevention, CSP, and MIME sniffing protection
- **Admin Dashboard** - Password-protected admin panel with session-based authentication
- **Comprehensive Audit Logging** - All access attempts logged in JSON format with timestamp, user, IP, and result
- **Real Client IP Detection** - Proper IP extraction through reverse proxy headers (X-Forwarded-For, X-Real-IP)
- **Session Security** - CSRF protection and secure session handling
- **Reverse Proxy Optimized** - Security headers and IP detection optimized for nginx/Apache/Cloudflare

### 🏠 Home Assistant Integration
- **Native HA API** - Direct integration with Home Assistant switch entities
- **Zigbee Device Support** - Automatic device detection and battery monitoring
- **Real-time Status** - Live battery level updates and device state monitoring
- **Flexible Configuration** - Support for any Home Assistant switch entity

### 🧪 Testing & Development
- **Test Mode** - Safe testing without physical door operation (`test_mode = true`)
- **Simulated Success** - Shows success messages and logs without Home Assistant API calls
- **Full Feature Testing** - All keypad, audio, and security features work in test mode

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
# Copy and customize environment file (recommended)
cp .env.example .env
# Edit .env to set DOOROPENER_PORT if different from 6532
docker compose up -d
```

**Alternative with direct environment variable:**
```bash
export DOOROPENER_PORT=6532
docker compose up -d
```

### 3. Manual Installation
```bash
pip install -r requirements.txt
python app.py
```

Visit [http://localhost:6532](http://localhost:6532) to access the portal.

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

[admin]
# Admin dashboard password
admin_password = your_secure_admin_password

[server]
# Port for the web server (default: 6532)
port = 6532
# Test mode - when true, shows success message but doesn't actually open door
test_mode = false
```

### Port Configuration (Recommended: Environment Variables)

**Preferred Method - Environment Variables:**
```bash
# Set in .env file or export directly
export DOOROPENER_PORT=6532
```

**Alternative - config.ini:**
```ini
[server]
# Port for the web server (default: 6532)
port = 6532
```

**Priority Order:**
1. `DOOROPENER_PORT` environment variable (highest priority)
2. `config.ini` `[server]` `port` setting  
3. Default fallback: 6532

### Test Mode

For testing the interface without actually opening the door, enable test mode:

```ini
[server]
test_mode = true
```

When enabled:
- ✅ Shows success message with "(TEST MODE)" indicator
- ✅ All keypad functionality works normally
- ✅ Rate limiting and logging still apply
- ❌ **No actual Home Assistant API call is made**
- ❌ **Door will NOT physically open**

Perfect for testing PIN validation, user interface, and keypad functionality safely.

### Background Image (Optional)
Place your custom background image as `/static/background.jpg` for a personalized interface.

---

## 🛠️ API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/open-door` | POST | Door control endpoint (requires PIN) |
| `/battery` | GET | Real-time battery level data |
| `/admin` | GET | Admin dashboard interface |
| `/admin/auth` | POST | Admin authentication endpoint |
| `/admin/logs` | GET | JSON log data for admin dashboard |

### Request Examples

**Open Door:**
```bash
curl -X POST http://localhost:6532/open-door \
  -H "Content-Type: application/json" \
  -d '{"pin": "1234"}'
```

**Check Battery:**
```bash
curl http://localhost:6532/battery
```

---

## 🔒 Security Features

### Advanced Security Features

#### Per-IP Rate Limiting
- **Individual IP Tracking** - Each IP address has separate failure counters
- **Progressive Delays** - Increasing delays: 1s → 2s → 4s → 8s → 16s for repeated failures
- **IP-Specific Lockouts** - 5 failed attempts = 5 minute block for that IP only
- **Automatic Reset** - Successful authentication clears failure counter

#### Security Headers (Reverse Proxy Optimized)
- **X-Content-Type-Options**: `nosniff` - Prevents MIME sniffing attacks
- **X-Frame-Options**: `DENY` - Prevents clickjacking via iframes
- **X-XSS-Protection**: `1; mode=block` - Browser XSS filtering
- **Content-Security-Policy** - Restrictive CSP to prevent XSS attacks
- **Referrer-Policy**: `strict-origin-when-cross-origin` - Controls referrer information
- **HTTPS Enforcement** - Left to reverse proxy (nginx/Apache/Cloudflare)

#### Input Validation & Sanitization
- **PIN Format Validation** - Enforces 4-8 digit numeric PINs only
- **Request Sanitization** - Proper JSON parsing with comprehensive error handling
- **Length Limits** - Prevents buffer overflow and DoS attempts
- **Type Checking** - Ensures data integrity and prevents injection attacks

### Audit Logging
All door access attempts are logged to `logs/log.txt` in JSON format with:
- ISO timestamp
- Client IP address
- Username (if PIN matched)
- Result (SUCCESS/FAILURE)
- Failure reason (if applicable)

**Example Log Entries:**
```json
{"timestamp": "2024-01-15T10:30:45.123456", "ip": "192.168.1.100", "user": "alice", "status": "SUCCESS", "details": "Door opened"}
{"timestamp": "2024-01-15T10:31:12.789012", "ip": "192.168.1.101", "user": "UNKNOWN", "status": "FAILURE", "details": "Invalid PIN, PIN: 9999"}
```

---

## 🐳 Docker Deployment

### Production Configuration
The included `docker-compose.yml` provides:

**Port Configuration:**
- Uses `DOOROPENER_PORT` environment variable (defaults to 6532)
- Environment variable takes priority over `config.ini` settings
- Recommended to use `.env` file for port configuration

**Container Features:**
- **Health Checks** - Automatic container health monitoring
- **Resource Limits** - CPU (0.5 cores) and memory (256MB) constraints
- **Log Management** - Automatic log rotation (10MB max, 3 files)
- **Volume Mounts** - Persistent configuration and logs
- **Restart Policy** - Automatic restart unless manually stopped

### Docker Commands
```bash
# Start the application
docker compose up -d

# View real-time logs
docker compose logs -f

# Stop the application
docker compose down

# Rebuild after code changes
docker compose build && docker compose up -d --force-recreate

# Check container health
docker compose ps
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
│   ├── index.html        # Main web interface
│   └── admin.html        # Admin dashboard interface
├── static/
│   └── background.jpg    # Custom background (optional)
└── logs/
    └── log.txt          # Audit log file (JSON format)
```

---

## 🔧 Admin Dashboard

### Access
Visit `/admin` to access the password-protected admin dashboard for viewing and managing access logs.

### Features
- **Secure Login** - Password protection using `admin_password` from config.ini
- **Log Viewing** - Sortable and filterable table of all access attempts
- **Real-time Data** - Live log data with refresh functionality
- **Modern UI** - Glass morphism design matching the main interface

### Sorting & Filtering
- **Sort by:** Time (newest/oldest), User, Status
- **Filter by:** User (all users or specific user)
- **Filter by:** Status (all, success only, failures only)

### Usage
1. Click the gear icon (⚙️) in the bottom-right corner of the main interface
2. Or navigate directly to `http://localhost:6532/admin`
3. Enter your admin password (configured in `config.ini`)
4. View, sort, and filter access logs with real-time data
5. Use the refresh button to update data

### Security Considerations
- Admin sessions are maintained securely using Flask sessions
- All admin access attempts are logged for audit purposes
- Password should be changed from default in production deployments

### Known Issues
- **Admin Login Persistence**: Admin login currently logs out on every page refresh. Session persistence is not working properly despite cookie configuration. This is a known issue that needs to be resolved.

---

## ⚠️ Security Disclaimer

**Important Notice**: This project was developed by someone who is not a security expert. While best practices have been implemented where possible, this software should be used with caution in production environments.

### Security Recommendations
- **Change Default Passwords**: Always change the default admin password before deployment
- **Use HTTPS**: Deploy behind a reverse proxy with SSL/TLS termination


### Liability
This software is provided "as is" without warranty. Users are responsible for their own security assessments and implementations.

-----

## 📄 License

This project is open source. Please check the repository for license details.
