#!/bin/bash
set -e

# Write config.ini based on HA add-on options (passed as env vars)
cat <<EOF > /app/config.ini
[HomeAssistant]
url = ${DOOROPENER_URL:-http://homeassistant.local:8123}
token = ${DOOROPENER_TOKEN}
switch_entity = ${DOOROPENER_SWITCH_ENTITY:-switch.dooropener_zigbee}

[pins]
# Example PINs, users should edit in add-on config or mount their own
alice = 1234
bob = 5678

[admin]
admin_password = ${DOOROPENER_ADMIN_PASSWORD:-admin123}

[server]
port = 6532
test_mode = ${DOOROPENER_TEST_MODE:-false}
EOF

# Run the main app
exec python3 /app/app.py
