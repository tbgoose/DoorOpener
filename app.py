#!/usr/bin/env python3
"""
DoorOpener Web Portal
---------------------
A simple Flask web app to open a door via Home Assistant API, with per-user PINs and admin logging.
"""
import os
import configparser
import json
import time
import logging
from flask import Flask, render_template, request, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
from datetime import datetime, timedelta
import secrets

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'door_access.log'))
    ]
)
logger = logging.getLogger(__name__)

# --- Flask App Setup ---
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # Reverse proxy support
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))  # Session/CSRF protection

# --- Configuration ---
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_path)

# Per-user PINs from [pins] section (user: pin)
user_pins = dict(config.items('pins')) if config.has_section('pins') else {}

# Home Assistant API config
ha_url = config.get('HomeAssistant', 'url', fallback='http://homeassistant.local:8123')
ha_token = config.get('HomeAssistant', 'token')
switch_entity = config.get('HomeAssistant', 'switch_entity')
battery_entity = config.get('HomeAssistant', 'battery_entity', fallback=f'sensor.{switch_entity.split(".")[1]}_battery')

# HTTP headers for HA API requests
ha_headers = {
    'Authorization': f'Bearer {ha_token}',
    'Content-Type': 'application/json'
}

# --- Brute-force Protection ---
FAILED_ATTEMPTS = 0
BLOCKED_UNTIL = None
MAX_ATTEMPTS = 5
BLOCK_TIME = timedelta(minutes=5)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'door_access.log'))
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

# Load per-user PINs from [pins] section
user_pins = dict(config.items('pins')) if config.has_section('pins') else {}

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
        client_ip = request.remote_addr
        data = request.get_json()
        pin_from_request = (data.get('pin').strip() if data and data.get('pin') else None)
        matched_user = None
        pin_valid = False
        result = 'FAILURE'
        reason = ''

        # Brute-force protection (reuse existing logic)
        if BLOCKED_UNTIL and now < BLOCKED_UNTIL:
            remaining = int((BLOCKED_UNTIL - now).total_seconds())
            logger.warning(f"Blocked attempt from {client_ip}: still blocked for {remaining}s")
            return jsonify({"status": "error", "message": f"Too many failed attempts. Try again in {remaining//60}m {remaining%60}s."}), 429

        if not pin_from_request:
            reason = 'PIN required'
            logger.warning(f"PIN required but not provided from {client_ip}")
            log_entry = f"{now.isoformat()} - {client_ip} - UNKNOWN - FAILURE - {reason}"
            logger.info(log_entry)
            return jsonify({"status": "error", "message": "PIN required"}), 400

        # Check against per-user PINs
        for user, user_pin in user_pins.items():
            if pin_from_request == user_pin:
                matched_user = user
                pin_valid = True
                break

        if not pin_valid:
            # Optionally, fallback to single PIN (legacy)
            pin_required = config.get('Security', 'pin', fallback=None)
            if pin_required and pin_from_request == pin_required.strip():
                matched_user = 'LEGACY'
                pin_valid = True

        if not pin_valid:
            FAILED_ATTEMPTS += 1
            reason = 'Invalid PIN'
            logger.warning(f"Invalid PIN attempt from {client_ip}, PIN: {pin_from_request}")
            log_entry = f"{now.isoformat()} - {client_ip} - UNKNOWN - FAILURE - {reason}, PIN: {pin_from_request}"
            logger.info(log_entry)
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

        # Call Home Assistant API to turn on the switch
        try:
            url = f"{ha_url}/api/services/switch/turn_on"
            payload = {"entity_id": switch_entity}
            logger.info(f"Calling HA API: {url} for user: {matched_user}")
            response = requests.post(url, headers=ha_headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = 'SUCCESS'
                reason = 'Door opened'
                log_entry = f"{now.isoformat()} - {client_ip} - {matched_user} - SUCCESS - {reason}"
                logger.info(log_entry)
                display_name = matched_user.capitalize() if matched_user else 'resident'
                return jsonify({"status": "success", "message": f"Door open command sent.\nWelcome home, {display_name}!"})
            else:
                result = 'FAILURE'
                reason = f'HA API error: {response.status_code} - {response.text}'
                log_entry = f"{now.isoformat()} - {client_ip} - {matched_user} - FAILURE - {reason}"
                logger.error(log_entry)
                return jsonify({"status": "error", "message": reason}), 500
        except Exception as e:
            result = 'FAILURE'
            reason = f'API call failed: {str(e)}'
            log_entry = f"{now.isoformat()} - {client_ip} - {matched_user} - FAILURE - {reason}"
            logger.error(log_entry)
            return jsonify({"status": "error", "message": reason}), 500
    except Exception as e:
        logger.error(f"Exception in open_door: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# --- Admin panel endpoints ---
from flask import send_from_directory
admin_password = config.get('admin', 'admin_password', fallback=None)
admin_tokens = set()

@app.route('/admin')
def admin_panel():
    return render_template('admin.html')

@app.route('/admin-login', methods=['POST'])
def admin_login():
    data = request.get_json()
    pwd = data.get('password') if data else None
    if not admin_password or not pwd or pwd != admin_password:
        return jsonify({'status': 'error', 'message': 'Invalid admin password'}), 403
    token = secrets.token_urlsafe(32)
    admin_tokens.add(token)
    return jsonify({'status': 'success', 'token': token})

@app.route('/admin-logs')
def admin_logs():
    token = request.args.get('token')
    if not token or token not in admin_tokens:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
    # Parse door_access.log for per-user counts
    log_path = os.path.join(os.path.dirname(__file__), 'door_access.log')
    user_counts = {}
    try:
        with open(log_path, 'r') as f:
            for line in f:
                # Example: 2025-09-01T12:54:00 - 192.168.1.51 - alice - SUCCESS - Door opened
                parts = line.strip().split(' - ')
                if len(parts) >= 4 and parts[3] == 'SUCCESS':
                    user = parts[2]
                    user_counts[user] = user_counts.get(user, 0) + 1
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Log read error: {e}'}), 500
    return jsonify({'logs': user_counts})

if __name__ == '__main__':
    # In production, debug should be False
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
