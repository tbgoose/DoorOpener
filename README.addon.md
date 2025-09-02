# Home Assistant Add-on: DoorOpener

![Supports aarch64 Architecture][aarch64-shield] ![Supports amd64 Architecture][amd64-shield] ![Supports armhf Architecture][armhf-shield] ![Supports armv7 Architecture][armv7-shield] ![Supports i386 Architecture][i386-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg

Secure web interface for door control with visual keypad, multi-layer security, and audio feedback.

## About

DoorOpener provides a beautiful, secure web interface to control door locks through Home Assistant. Features include:

- **Visual Keypad Interface** - Touch-friendly 3x4 grid keypad
- **Multi-Layer Security** - Session, IP, and global rate limiting
- **Audio Feedback** - Success chimes and failure sounds
- **Test Mode** - Safe testing without physical door operation
- **Battery Monitoring** - Real-time Zigbee device battery levels
- **Timezone Support** - Configurable timezone for logging

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "DoorOpener" add-on
3. Configure the add-on (see Configuration section)
4. Start the add-on
5. Access the interface at `http://homeassistant.local:6532`

## Configuration

```yaml
pins:
  alice: "1234"
  bob: "5678"
admin:
  admin_password: "your-secure-admin-password"
homeassistant:
  ha_url: "http://supervisor/core"
  ha_token: "your-long-lived-access-token"
  switch_entity: "switch.your_door_lock"
server:
  port: 6532
  test_mode: false
security:
  max_attempts: 5
  block_time_minutes: 5
  session_max_attempts: 3
  max_global_attempts_per_hour: 50
```

### Configuration Options

- **pins**: User PIN codes (username: "pin")
- **admin.admin_password**: Admin panel password
- **homeassistant.ha_token**: Long-lived access token from HA
- **homeassistant.switch_entity**: Your door lock switch entity ID
- **server.test_mode**: Enable test mode for safe development
- **security**: Rate limiting and security thresholds

## Support

For issues and feature requests, visit the [GitHub repository](https://github.com/Sloth-on-meth/DoorOpener).
