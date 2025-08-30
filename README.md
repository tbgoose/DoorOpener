# Door Opener Web Application

A simple web application that allows neighbors to open the apartment building's downstairs door by triggering a Home Assistant switch via MQTT.

## Features

- Clean, mobile-friendly web interface
- MQTT integration with Home Assistant
- Easy to deploy and configure

## Setup Instructions

1. Clone this repository
2. Create a `config.ini` file based on the `config.ini.example` template:
   ```
   cp config.ini.example config.ini
   ```
3. Edit `config.ini` with your MQTT broker details and Home Assistant entity information
4. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```
5. Run the application:
   ```
   python app.py
   ```
6. Access the web interface at `http://your-server-ip:5000`

## Configuration

The `config.ini` file contains the following settings:

- `[MQTT]` section:
  - `host`: MQTT broker hostname or IP address
  - `port`: MQTT broker port (default: 1883)
  - `username`: MQTT username
  - `password`: MQTT password

- `[HomeAssistant]` section:
  - `switch_entity`: The entity ID of your door switch in Home Assistant
  - `topic`: The MQTT topic to publish to (default: homeassistant/switch/door_opener/set)

## Security Considerations

This application is designed for use on a local network. For additional security:

- Consider adding authentication
- Use HTTPS if exposing to the internet
- Restrict access using a reverse proxy or firewall rules
