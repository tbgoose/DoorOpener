# Changelog

## v[1.3.0] - 2025-09-03

### 🚀 Features & Improvements
- Now you do not have to build anymore - ghcr setup!
### 🐛 Bug Fixes
- api error

---

## v[1.2.0] - 2025-09-02

### 🔒 Enhanced Security Features

#### ✨ New Security Improvements
- **Multi-Layer Rate Limiting** - Session-based (3 attempts), IP-based (5 attempts), and global (50/hour) protection
- **Enhanced IP Detection** - Uses `request.remote_addr` instead of spoofable client headers
- **Session Tracking** - Unique session identifiers prevent easy bypass of rate limits
- **Suspicious Request Detection** - Blocks requests with missing/bot User-Agent headers
- **Composite Identifiers** - IP + User-Agent/language fingerprinting for better tracking

#### 🎨 Visual Interface Improvements
- **Visual Keypad Interface** - Replaced text input with responsive 3x4 grid keypad (0-9, backspace, enter)
- **Auto-Submit PIN Entry** - Door opens automatically when valid PIN length (4-8 digits) is entered
- **Perfect Alignment** - PIN display and keypad visually centered and width-matched
- **Keyboard Support** - Physical keyboard input (0-9, Backspace, Enter) works alongside touch

#### 🔊 Audio & Feedback Features
- **Success Sound** - Ascending chime sequence using Web Audio API
- **Failure Sound** - "Womp womp" descending trombone effect for invalid attempts
- **Visual Feedback** - Button animations, haptic vibration, toast notifications
- **Responsive Design** - Optimized for both desktop and mobile devices

#### 🧪 Testing & Development
- **Test Mode** - Safe testing without physical door operation (`test_mode = true` in config.ini)
- **Simulated Success** - Shows success messages and logs without Home Assistant API calls
- **Full Feature Testing** - All keypad, audio, and security features work in test mode

#### 🌍 Timezone Support
- **Environment Variable** - Set `TZ` environment variable for local timezone (default: UTC)
- **Consistent Logging** - All timestamps in logs use the configured timezone
- **Docker Integration** - Timezone configuration through docker-compose environment

#### 🛠️ Technical Improvements
- **Enhanced Logging** - Session IDs, composite identifiers, and detailed status tracking
- **Progressive Security** - Multiple blocking mechanisms with different thresholds
- **Dependency Updates** - Added pytz for robust timezone handling

#### 🐛 Bug Fixes
- Fixed variable reference errors in logging statements
- Resolved import conflicts with configparser
- Improved error handling in security functions

---

## [1.1.0] - 2025-09-02

### 🔧 Configuration Improvements

#### ✨ New Features
- **Environment Variable Port Configuration** - Port can now be configured via `DOOROPENER_PORT` environment variable
- **Flexible Configuration Priority** - Environment variables take precedence over config.ini settings
- **Docker Environment Integration** - Seamless port configuration through .env files and docker-compose

#### 🛠️ Technical Improvements
- **Simplified Docker Setup** - Removed complex startup scripts in favor of environment variable approach
- **Better Configuration Management** - Clear priority order: ENV var → config.ini → default fallback
- **Enhanced Documentation** - Updated README with environment variable best practices

#### 📝 Configuration Priority Order
1. `DOOROPENER_PORT` environment variable (highest priority)
2. `config.ini` `[server]` `port` setting
3. Default fallback: 6532

#### 🐛 Bug Fixes
- Fixed Docker container not respecting config.ini port settings
- Improved port configuration consistency between host and container

---

## [1.0.0] - 2025-09-02

### 🎉 Initial Release

#### ✨ Features
- **Modern Glass Morphism UI** - Premium frosted glass interface with backdrop blur effects
- **Per-User PIN Authentication** - Individual PINs for each resident/user
- **Zigbee Device Integration** - Automatic device detection and real-time battery monitoring
- **Admin Dashboard** - Password-protected admin panel with audit logging
- **Rate Limiting & Security** - Per-IP progressive delays and brute-force protection
- **Docker Containerization** - Complete Docker setup with health checks and resource limits
- **Responsive Design** - Optimized for desktop, tablet, and mobile devices

#### 🔐 Security Features
- Per-IP rate limiting with progressive delays (1s, 2s, 4s, 8s, 16s)
- 5-minute IP lockout after 5 failed attempts
- Secure session management with HTTPOnly cookies
- Input validation and sanitization
- Comprehensive audit logging

#### 🔧 Technical Features
- Home Assistant API integration
- MQTT battery level monitoring
- Real-time status updates
- Custom background image support
- Haptic feedback on mobile devices
- Toast notifications for user feedback

#### 📱 User Interface
- Glass morphism design with backdrop filters
- Color-coded battery indicators
- Interactive button states with animations
- Mobile-optimized touch interface
- Admin access via floating gear icon

#### 🐳 Docker Support
- Multi-stage Docker build
- Health checks and restart policies
- Resource limits (0.5 CPU cores, 256MB RAM)
- Log rotation and volume mounts
- Environment-based configuration

### 🐛 Known Issues
- Admin login persistence: Sessions don't persist across page refreshes
- SESSION_COOKIE_SECURE set to False for local HTTP development

### 🔧 Configuration
- Supports any Home Assistant switch entity
- Configurable user PINs via config.ini
- Customizable admin password
- Environment variable support for secrets
