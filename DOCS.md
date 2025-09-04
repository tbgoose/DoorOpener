# Home Assistant Add-on Documentation

**DoorOpener can be run as a Home Assistant add-on!**
- See the `addon/` directory for all required files
- Follow the instructions below to install as a local or custom add-on


---

## Docker Compose Usage

The default `docker-compose.yml` now uses the official image from [ghcr.io](https://ghcr.io/sloth-on-meth/dooropener). You do **not** need to build the image locally.

- To use the prebuilt image, simply run:
  ```bash
  docker-compose up -d
  ```
- If you want to build locally (for development), uncomment the `build:` section and comment out the `image:` line in `docker-compose.yml`.

---

# NOTE: THIS PART WAS ALL VIBECODED - I HAVE NO EXPERIENCE BUILDING HA ADDONS AND I DO NOT HAVE SUPERVISED RUNNING

## Installation

### Method 1: Add-on Store (Recommended)

1. **Add Repository**
   - Go to Home Assistant → Settings → Add-ons → Add-on Store
   - Click the three dots menu → Repositories
   - Add: `https://github.com/Sloth-on-meth/DoorOpener`

2. **Install Add-on**
   - Find "DoorOpener" in the add-on store
   - Click Install

3. **Configure Add-on**
   - Go to Configuration tab
   - Set your PIN codes, admin password, and Home Assistant token
   - Configure your door lock entity (supports `switch`, `lock`, or `input_boolean` types)

4. **Start Add-on**
   - Go to Info tab
   - Click Start
   - Access at `http://homeassistant.local:6532`

### Method 2: Manual Installation

1. Create addon directory in Home Assistant:
   ```bash
   mkdir -p /config/addons/local/dooropener
   ```

2. Copy all addon files to the directory:
   - `config.yaml`
   - `Dockerfile.addon` 
   - `build.yaml`
   - `run.sh`
   - `app.py`
   - `templates/`
   - `static/`
   - `requirements.txt`

3. Restart Home Assistant and install from Local Add-ons

## Configuration

### Required Settings

```yaml
pins:
  username1: "1234"
  username2: "5678"
admin:
  admin_password: "secure-admin-password"
homeassistant:
  ha_token: "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  switch_entity: "switch.door_lock"
```

### Optional Settings

```yaml
server:
  port: 6532
  test_mode: false
security:
  max_attempts: 5
  block_time_minutes: 5
  session_max_attempts: 3
  max_global_attempts_per_hour: 50
```

## Getting Home Assistant Token

1. Go to Home Assistant → Profile → Security
2. Scroll to "Long-lived access tokens"
3. Click "Create Token"
4. Give it a name like "DoorOpener"
5. Copy the token and use it in the addon configuration

## Finding Your Switch Entity

1. Go to Home Assistant → Settings → Devices & Services
2. Find your door lock device
3. Click on it to see entities
4. Copy the entity ID (e.g., `switch.front_door_lock`)

## Troubleshooting

### Add-on Won't Start
- Check logs in the add-on Log tab
- Verify Home Assistant token is valid
- Ensure switch entity exists and is accessible

### Can't Access Web Interface
- Check if port 6532 is available
- Verify add-on is running in Info tab
- Try accessing via Home Assistant IP: `http://192.168.1.100:6532`

### Door Won't Open
- Enable test mode to verify interface works
- Check Home Assistant logs for API errors
- Verify switch entity is correct and controllable

## Security Notes

- Use strong, unique PIN codes for each user
- Set a secure admin password
- Consider enabling test mode for initial setup
- Monitor logs for suspicious activity
- The add-on includes comprehensive brute force protection
