#!/usr/bin/env python3
import os
import configparser
import json
import time
import logging
from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import requests

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
config.read(config_path)

# Home Assistant Configuration
ha_url = config.get('HomeAssistant', 'url', fallback='http://homeassistant.local:8123')
ha_token = config.get('HomeAssistant', 'token')
switch_entity = config.get('HomeAssistant', 'switch_entity')
battery_entity = config.get('HomeAssistant', 'battery_entity', fallback=f'sensor.{switch_entity.split(".")[1]}_battery')

# Extract device name from switch entity (e.g., switch.dooropener_zigbee -> dooropener_zigbee)
device_name = switch_entity.split('.')[1] if '.' in switch_entity else switch_entity

# Headers for HA API requests
ha_headers = {
    'Authorization': f'Bearer {ha_token}',
    'Content-Type': 'application/json'
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/battery')
def battery():
    """Get battery level from Home Assistant battery sensor entity"""
    try:
        logger.info(f"Battery endpoint called - fetching state for entity: {battery_entity}")
        url = f"{ha_url}/api/states/{battery_entity}"
        response = requests.get(url, headers=ha_headers, timeout=10)
        if response.status_code == 200:
            state_data = response.json()
            battery_level = state_data.get('state')
            return jsonify({"level": battery_level})
        else:
            logger.error(f"Failed to fetch battery state: {response.status_code} {response.text}")
            return jsonify({"level": None})
    except Exception as e:
        logger.error(f"Exception fetching battery: {e}")
        logger.error(f"Error fetching battery from Home Assistant: {e}")
        return jsonify({"level": None})


import time
from datetime import datetime, timedelta
from flask import request

# Global brute-force protection settings
FAILED_ATTEMPTS = 0
BLOCKED_UNTIL = None
MAX_ATTEMPTS = 5
BLOCK_TIME = timedelta(minutes=5)

@app.route('/open-door', methods=['POST'])
def open_door():
    try:
        global FAILED_ATTEMPTS, BLOCKED_UNTIL
        now = datetime.utcnow()
        if BLOCKED_UNTIL and now < BLOCKED_UNTIL:
            remaining = int((BLOCKED_UNTIL - now).total_seconds())
            return jsonify({"status": "error", "message": f"Too many failed attempts. Try again in {remaining//60}m {remaining%60}s."}), 429
        data = request.get_json()
        pin_from_request = (data.get('pin').strip() if data and data.get('pin') else None)
        pin_required = config.get('Security', 'pin', fallback=None)
        
        # Debug logging for PIN configuration
        logger.info(f"PIN from request: {'***' if pin_from_request else 'None'}")
        logger.info(f"PIN required from config: {'***' if pin_required else 'None'}")
        if pin_required is not None:
            pin_required = pin_required.strip()
            if not pin_required:
                return jsonify({"status": "error", "message": "PIN not set in config"}), 500
            if not pin_from_request:
                return jsonify({"status": "error", "message": "PIN required"}), 400
            if pin_from_request != pin_required:
                FAILED_ATTEMPTS += 1
                if FAILED_ATTEMPTS >= MAX_ATTEMPTS:
                    BLOCKED_UNTIL = now + BLOCK_TIME
                    FAILED_ATTEMPTS = 0
                    remaining = int((BLOCKED_UNTIL - now).total_seconds())
                    return jsonify({"status": "error", "message": f"Too many failed attempts. Try again in {remaining//60}m {remaining%60}s."}), 429
                return jsonify({"status": "error", "message": "Invalid PIN"}), 403
            else:
                # Reset on success
                FAILED_ATTEMPTS = 0
                BLOCKED_UNTIL = None
        else:
            return jsonify({"status": "error", "message": "PIN not set in config"}), 500
        # Call Home Assistant API to turn on the switch
        try:
            # Use the correct HA API endpoint format
            url = f"{ha_url}/api/services/switch/turn_on"
            payload = {"entity_id": switch_entity}
            
            logger.info(f"Calling HA API: {url}")
            logger.info(f"Payload: {payload}")
            logger.info(f"Headers: Authorization=Bearer *****, Content-Type={ha_headers.get('Content-Type')}")
            
            response = requests.post(url, headers=ha_headers, json=payload, timeout=10)
            
            logger.info(f"Response status: {response.status_code}")
            logger.info(f"Response text: {response.text}")
            
            if response.status_code == 200:
                logger.info(f"Successfully sent door open command via HA API")
                success = True
            else:
                logger.error(f"HA API call failed: {response.status_code} - {response.text}")
                # Try alternative endpoint format
                alt_url = f"{ha_url}/api/services/homeassistant/turn_on"
                logger.info(f"Trying alternative endpoint: {alt_url}")
                alt_response = requests.post(alt_url, headers=ha_headers, json=payload, timeout=10)
                
                if alt_response.status_code == 200:
                    logger.info(f"Alternative endpoint succeeded")
                    success = True
                else:
                    logger.error(f"Alternative endpoint also failed: {alt_response.status_code} - {alt_response.text}")
                    error_messages = [f"Home Assistant API error: {response.status_code} (tried both switch/turn_on and homeassistant/turn_on)"]
                    success = False
                
        except Exception as e:
            logger.error(f"Error calling Home Assistant API: {e}")
            error_messages = [f"API call failed: {str(e)}"]
            success = False
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
