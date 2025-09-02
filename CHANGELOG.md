# Changelog

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
