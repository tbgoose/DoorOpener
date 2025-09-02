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

# --- Logging Setup (door attempts only) ---
import pathlib
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
# Ensure the logs directory exists before creating the handler
try:
    os.makedirs(log_dir, exist_ok=True)
except Exception as e:
    print(f'Could not create log directory: {e}')
log_path = os.path.join(log_dir, 'log.txt')

# We'll use a dedicated logger for door attempts only
attempt_logger = logging.getLogger('door_attempts')
attempt_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_path)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
attempt_logger.handlers = [file_handler]

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
FAILED_ATTEMPTS = 3
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

# Admin Configuration
admin_password = config.get('admin', 'admin_password', fallback='admin123')

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
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": client_ip,
                "user": "UNKNOWN",
                "status": "FAILURE",
                "details": f"Blocked: still blocked for {remaining}s"
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": f"Too many failed attempts. Try again in {remaining//60}m {remaining%60}s."}), 429

        if not pin_from_request:
            reason = 'PIN required'
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": client_ip,
                "user": "UNKNOWN",
                "status": "FAILURE",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
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
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": client_ip,
                "user": "UNKNOWN",
                "status": "FAILURE",
                "details": f"{reason}, PIN: {pin_from_request}"
            }
            attempt_logger.info(json.dumps(log_entry))
            if FAILED_ATTEMPTS >= MAX_ATTEMPTS:
                BLOCKED_UNTIL = now + BLOCK_TIME
                FAILED_ATTEMPTS = 0
                remaining = int((BLOCKED_UNTIL - now).total_seconds())
                log_entry = {
                    "timestamp": now.isoformat(),
                    "ip": client_ip,
                    "user": "UNKNOWN",
                    "status": "FAILURE",
                    "details": "Blocked: too many failed attempts"
                }
                attempt_logger.info(json.dumps(log_entry))
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
            response = requests.post(url, headers=ha_headers, json=payload, timeout=10)
            if response.status_code == 200:
                result = 'SUCCESS'
                reason = 'Door opened'
                log_entry = {
                    "timestamp": now.isoformat(),
                    "ip": client_ip,
                    "user": matched_user,
                    "status": "SUCCESS",
                    "details": reason
                }
                attempt_logger.info(json.dumps(log_entry))
                display_name = matched_user.capitalize() if matched_user else 'resident'
                return jsonify({"status": "success", "message": f"Door open command sent.\nWelcome home, {display_name}!"})
            else:
                result = 'FAILURE'
                reason = f'HA API error: {response.status_code} - {response.text}'
                log_entry = {
                    "timestamp": now.isoformat(),
                    "ip": client_ip,
                    "user": matched_user,
                    "status": "FAILURE",
                    "details": reason
                }
                attempt_logger.info(json.dumps(log_entry))
                return jsonify({"status": "error", "message": reason}), 500
        except Exception as e:
            result = 'FAILURE'
            reason = f'API call failed: {str(e)}'
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": client_ip,
                "user": matched_user,
                "status": "FAILURE",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": reason}), 500
    except Exception as e:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "ip": "UNKNOWN",
            "user": "UNKNOWN",
            "status": "FAILURE",
            "details": f"Exception in open_door: {e}"
        }
        attempt_logger.info(json.dumps(log_entry))
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/admin')
def admin():
    """Admin dashboard for viewing login attempts"""
    return render_template('admin.html')


@app.route('/admin/auth', methods=['POST'])
def admin_auth():
    """Authenticate admin access"""
    data = request.get_json()
    password = data.get('password', '').strip() if data else ''
    
    if password == admin_password:
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Invalid admin password"}), 403


@app.route('/admin/logs')
def admin_logs():
    """Get parsed log data for admin dashboard"""
    try:
        logs = []
        log_path = os.path.join(os.path.dirname(__file__), 'logs', 'log.txt')
        
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Parse JSON log format
                    try:
                        # Handle log lines that may have timestamp prefix from logging module
                        # Format: "2025-09-02 11:42:33,123 - INFO - {json}"
                        json_start = line.find('{')
                        if json_start != -1:
                            json_part = line[json_start:]
                            log_data = json.loads(json_part)
                        else:
                            log_data = json.loads(line)
                            
                        logs.append({
                            'timestamp': log_data.get('timestamp'),
                            'ip': log_data.get('ip'),
                            'user': log_data.get('user') if log_data.get('user') != 'UNKNOWN' else None,
                            'status': log_data.get('status'),
                            'details': log_data.get('details')
                        })
                    except json.JSONDecodeError:
                        # Fallback for old format logs: timestamp - ip - user - status - details
                        try:
                            # Check if it's the old dash-separated format
                            if ' - ' in line and not line.startswith('{'):
                                parts = line.split(' - ', 4)
                                if len(parts) >= 4:
                                    timestamp = parts[0]
                                    ip = parts[1]
                                    user = parts[2] if parts[2] != 'UNKNOWN' else None
                                    status = parts[3]
                                    details = parts[4] if len(parts) > 4 else None
                                    
                                    logs.append({
                                        'timestamp': timestamp,
                                        'ip': ip,
                                        'user': user,
                                        'status': status,
                                        'details': details
                                    })
                        except Exception as e:
                            logger.error(f"Error parsing old format log line: {line}, error: {e}")
                            continue
                    except Exception as e:
                        logger.error(f"Error parsing JSON log line: {line}, error: {e}")
                        continue
        
        return jsonify({"logs": logs})
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return jsonify({"logs": []}), 500


if __name__ == '__main__':
    # In production, debug should be False
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
