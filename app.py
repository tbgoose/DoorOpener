#!/usr/bin/env python3
import os
import configparser
import paho.mqtt.client as mqtt
import json
import time
import logging
from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Support for reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Set secret key for sessions/CSRF protection
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# Load configuration
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

if not os.path.exists(config_path):
    raise FileNotFoundError(f"Config file not found at {config_path}. Please create it based on config.ini.example")

config.read(config_path)

# MQTT Configuration
mqtt_host = config['MQTT']['host']
mqtt_port = int(config['MQTT']['port'])
mqtt_username = config['MQTT']['username']
mqtt_password = config['MQTT']['password']

# Get switch entity and extract device name for Zigbee2MQTT
switch_entity = config['HomeAssistant']['switch_entity']
device_name = switch_entity.split('.')[1] if '.' in switch_entity else switch_entity

# For Zigbee2MQTT, the topic is typically zigbee2mqtt/DEVICE_NAME/set
zigbee_topic = f"zigbee2mqtt/{device_name}/set"

# Use configured topic or fallback to zigbee topic
mqtt_topic = config.get('HomeAssistant', 'topic', fallback=zigbee_topic)

# For direct Home Assistant service calls
ha_service_topic = "homeassistant/service/switch/turn_on"

# Initialize MQTT client
client = mqtt.Client()
client.username_pw_set(mqtt_username, mqtt_password)

# Log received messages
def on_message(client, userdata, message):
    logger.info(f"Received message on topic {message.topic}: {message.payload.decode()}")

client.on_message = on_message

@app.route('/')
def index():
    return render_template('index.html')

# Disabled in production for security - only enable if needed for debugging
# @app.route('/mqtt-info')
# def mqtt_info():
#     return jsonify({
#         "host": mqtt_host,
#         "topic": mqtt_topic,
#         "zigbee_topic": zigbee_topic,
#         "ha_service_topic": ha_service_topic,
#         "device_name": device_name,
#         "entity": switch_entity
#     })

@app.route('/open-door', methods=['POST'])
def open_door():
    try:
        data = request.get_json()
        pin_from_request = (data.get('pin').strip() if data and data.get('pin') else None)
        pin_required = config.get('Security', 'pin', fallback=None)
        if pin_required is not None:
            pin_required = pin_required.strip()
            if not pin_required:
                return jsonify({"status": "error", "message": "PIN not set in config"}), 500
            if not pin_from_request:
                return jsonify({"status": "error", "message": "PIN required"}), 400
            if pin_from_request != pin_required:
                return jsonify({"status": "error", "message": "Invalid PIN"}), 403
        else:
            return jsonify({"status": "error", "message": "PIN not set in config"}), 500
        # Connect to MQTT broker
        client.connect(mqtt_host, mqtt_port, 60)
        client.loop_start()
        # Subscribe to topics for debugging
        client.subscribe(f"zigbee2mqtt/{device_name}/#")
        # Try different approaches to trigger the door switch
        success = False
        error_messages = []
        # Approach 1: Direct Zigbee2MQTT command
        try:
            # For Zigbee2MQTT switches, typically use "state": "ON"
            zigbee_payload = json.dumps({"state": "ON"})
            logger.info(f"Publishing to {zigbee_topic}: {zigbee_payload}")
            client.publish(zigbee_topic, zigbee_payload)
            success = True
        except Exception as e:
            error_messages.append(f"Zigbee approach failed: {str(e)}")
        # Approach 2: Home Assistant service call
        if not success:
            try:
                ha_payload = json.dumps({"entity_id": switch_entity})
                logger.info(f"Publishing to {ha_service_topic}: {ha_payload}")
                client.publish(ha_service_topic, ha_payload)
                success = True
            except Exception as e:
                error_messages.append(f"HA service approach failed: {str(e)}")
        # Wait briefly to capture any responses
        time.sleep(1)
        # Disconnect from MQTT broker
        client.loop_stop()
        client.disconnect()
        if success:
            return jsonify({"status": "success", "message": "Door open command sent"})
        else:
            return jsonify({"status": "error", "message": "\n".join(error_messages)}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    # In production, debug should be False
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
