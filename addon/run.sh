#!/usr/bin/with-contenv bashio

# Get addon options
CONFIG_PATH="/data/options.json"

# Create config.ini from addon options
cat > /app/config.ini << EOF
[pins]
$(bashio::config 'pins' | jq -r 'to_entries[] | "\(.key) = \(.value)"')

[admin]
admin_password = $(bashio::config 'admin.admin_password')

[homeassistant]
ha_url = $(bashio::config 'homeassistant.ha_url')
ha_token = $(bashio::config 'homeassistant.ha_token')
switch_entity = $(bashio::config 'homeassistant.switch_entity')

[server]
port = $(bashio::config 'server.port')
test_mode = $(bashio::config 'server.test_mode')

[security]
max_attempts = $(bashio::config 'security.max_attempts')
block_time_minutes = $(bashio::config 'security.block_time_minutes')
session_max_attempts = $(bashio::config 'security.session_max_attempts')
max_global_attempts_per_hour = $(bashio::config 'security.max_global_attempts_per_hour')
EOF

# Set timezone if provided
if bashio::config.has_value 'timezone'; then
    export TZ=$(bashio::config 'timezone')
fi

# Set Flask secret key
export FLASK_SECRET_KEY=$(bashio::addon.uuid)

# Log startup info
bashio::log.info "Starting DoorOpener v1.2.0..."
bashio::log.info "Port: $(bashio::config 'server.port')"
bashio::log.info "Test mode: $(bashio::config 'server.test_mode')"
bashio::log.info "Timezone: ${TZ:-UTC}"

# Start the application
cd /app
exec python3 app.py
