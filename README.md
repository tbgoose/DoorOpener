# 🚪 DoorOpener Web Portal

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=for-the-badge" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/docker-ready-2496ed?style=for-the-badge&logo=docker&logoColor=white" alt="Docker Ready">
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=for-the-badge" alt="PRs Welcome">
</p>

A simple, secure, and modern web portal for triggering a Home Assistant switch—perfect for apartment, office, or shared entry doors. Features per-user PINs, audit logging, and an admin dashboard.

---

## ⭐ Features

- **Modern, mobile-friendly web UI**
- **Home Assistant API integration** 
- **Per-user PINs** for secure access
- **Audit logging** with timestamp, user, and IP
- **Brute-force protection**
- **Docker support** for easy deployment

---

## 🚀 Quick Start

### 1. Clone & Configure
```bash
# Clone the repository
 git clone https://github.com/Sloth-on-meth/DoorOpener.git
 cd DoorOpener
# Copy and edit the config
 cp config.ini.example config.ini
# Edit config.ini with your Home Assistant info and PINs
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the App
```bash
python app.py
```
Visit [http://localhost:5000](http://localhost:5000) or your server IP.

### 4. Docker (Optional)
```bash
docker-compose up -d --force-recreate
```

---

## ⚙️ Configuration Example (`config.ini`)
```ini
[HomeAssistant]
url = http://your-ha-url:8123
switch_entity = switch.dooropener_zigbee
battery_entity = sensor.dooropener_zigbee_battery
# Get a long-lived token from your Home Assistant profile
# https://my.home-assistant.io/redirect/profile/
token = YOUR_LONG_LIVED_TOKEN

[pins]
alice = 1234
bob = 5678
charlie = 9012


```

---

## 🔑 Security & Logging
- **Brute-force protection:** Too many failed PIN attempts blocks further tries for 5 minutes.
- **Audit log:** All door open attempts (success/failure) are logged to `logs/log.txt` (timestamp, user, IP, result). This file is accessible on the host if you mount the `logs/` directory via Docker.
- **PINs:** Each resident/user gets their own PIN. Legacy single-PIN mode is also supported.
- **Production:** By default, debug mode is off unless `FLASK_DEBUG=true` is set in the environment.

---

## 🛠️ Endpoints
- `/` — Main web UI
- `/open-door` — POST endpoint for opening the door (requires PIN)
- `/battery` — Shows battery level of the door device

---

## 🏗️ Docker Deployment
- `Dockerfile` and `docker-compose.yml` provided
- To access logs on your host, add this to your `docker-compose.yml`:
  ```yaml
  services:
    dooropener:
      ...
      volumes:
        - ./logs:/docker/DoorOpener/logs
  ```
  This will make all logs available at `./logs/log.txt` on your host.
- Standard commands:
  ```bash
  docker-compose up -d --force-recreate
  docker-compose logs -f
  docker-compose down
  docker-compose build
  ```

---


## 💡 Tips
- Always use HTTPS if exposing to the internet.
- Restrict access to the admin panel via reverse proxy/firewall.
- For more advanced logging or user management, contributions are welcome!

## Security Considerations

This application is designed for use on a local network. For additional security:

- Consider adding authentication
- Use HTTPS if exposing to the internet
- Restrict access using a reverse proxy or firewall rules

## Docker Deployment

The application includes Docker support for easy deployment:

- `Dockerfile`: Defines the container image
- `docker-compose.yml`: Orchestrates the container deployment

### Docker Commands

- Start the application:
  ```
  docker-compose up -d
  ```

- View logs:
  ```
  docker-compose logs -f
  ```

- Stop the application:
  ```
  docker-compose down
  ```

- Rebuild after changes:
  ```
  docker-compose build
  docker-compose up -d --force-recreate
  ```
