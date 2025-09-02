#!/usr/bin/env python3
"""
DoorOpener Web Portal
---------------------
A secure Flask web app to open a door via Home Assistant API, with per-user PINs, 
per-IP rate limiting, admin logging, and security headers.
"""
import os
import configparser
import json
import time
import logging
from flask import Flask, render_template, request, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
import requests
from datetime import datetime, timedelta
import secrets
from collections import defaultdict

# --- Logging Setup ---
log_dir = os.path.join(os.path.dirname(__file__), 'logs')
try:
    os.makedirs(log_dir, exist_ok=True)
except Exception as e:
    print(f'Could not create log directory: {e}')
log_path = os.path.join(log_dir, 'log.txt')

# Dedicated logger for door attempts
attempt_logger = logging.getLogger('door_attempts')
attempt_logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_path)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
attempt_logger.handlers = [file_handler]

# --- Flask App Setup ---
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))

# --- Configuration ---
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_path)

# Per-user PINs from [pins] section
user_pins = dict(config.items('pins')) if config.has_section('pins') else {}

# Admin Configuration
admin_password = config.get('admin', 'admin_password', fallback='admin123')

# Home Assistant Configuration
ha_url = config.get('HomeAssistant', 'url', fallback='http://homeassistant.local:8123')
ha_token = config.get('HomeAssistant', 'token')
switch_entity = config.get('HomeAssistant', 'switch_entity')
battery_entity = config.get('HomeAssistant', 'battery_entity', 
                           fallback=f'sensor.{switch_entity.split(".")[1]}_battery')

# Extract device name from switch entity
device_name = switch_entity.split('.')[1] if '.' in switch_entity else switch_entity

# Headers for HA API requests
ha_headers = {
    'Authorization': f'Bearer {ha_token}',
    'Content-Type': 'application/json'
}

# --- Per-IP Rate Limiting ---
ip_failed_attempts = defaultdict(int)
ip_blocked_until = defaultdict(lambda: None)
MAX_ATTEMPTS = 5
BLOCK_TIME = timedelta(minutes=5)

# Configure main logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), 'door_access.log'))
    ]
)
logger = logging.getLogger(__name__)

def get_client_ip():
    """Get real client IP from reverse proxy headers"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr

def add_security_headers(response):
    """Add security headers for reverse proxy deployment"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = ("default-src 'self'; "
                                                   "script-src 'self' 'unsafe-inline'; "
                                                   "style-src 'self' 'unsafe-inline'; "
                                                   "img-src 'self' data:; "
                                                   "font-src 'self'")
    # Don't add HSTS here since reverse proxy should handle HTTPS
    return response

def get_delay_seconds(attempt_count):
    """Calculate progressive delay: 1s, 2s, 4s, 8s, 16s"""
    return min(2 ** (attempt_count - 1), 16) if attempt_count > 0 else 0

def validate_pin_input(pin):
    """Validate PIN input format and length"""
    if not pin or not isinstance(pin, str):
        return False, "PIN is required"
    
    pin = pin.strip()
    
    if len(pin) < 4 or len(pin) > 8:
        return False, "PIN must be 4-8 digits"
    
    if not pin.isdigit():
        return False, "PIN must contain only numbers"
    
    return True, pin

@app.after_request
def after_request(response):
    return add_security_headers(response)

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
        return jsonify({"level": None})

@app.route('/open-door', methods=['POST'])
def open_door():
    try:
        client_ip = get_client_ip()
        now = datetime.utcnow()
        
        # Check if IP is currently blocked
        if ip_blocked_until[client_ip] and now < ip_blocked_until[client_ip]:
            remaining = (ip_blocked_until[client_ip] - now).total_seconds()
            reason = f'IP blocked for {int(remaining)} more seconds'
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": client_ip,
                "user": "UNKNOWN",
                "status": "BLOCKED",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": "Too many failed attempts. Please try again later."}), 429

        # Get and validate PIN input
        data = request.get_json()
        pin_from_request = data.get('pin') if data else None
        
        # Validate PIN format
        pin_valid, validated_pin = validate_pin_input(pin_from_request)
        if not pin_valid:
            ip_failed_attempts[client_ip] += 1
            reason = validated_pin  # Error message
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": client_ip,
                "user": "UNKNOWN",
                "status": "FAILURE",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": reason}), 400

        pin_from_request = validated_pin
        matched_user = None

        # Check PIN against user database
        for user, user_pin in user_pins.items():
            if pin_from_request == user_pin:
                matched_user = user
                break

        if matched_user:
            # Reset failed attempts on successful auth
            ip_failed_attempts[client_ip] = 0
            if client_ip in ip_blocked_until:
                del ip_blocked_until[client_ip]

            # Try to open door via Home Assistant
            try:
                url = f"{ha_url}/api/services/switch/turn_on"
                payload = {"entity_id": switch_entity}
                response = requests.post(url, headers=ha_headers, json=payload, timeout=10)
                
                if response.status_code == 200:
                    reason = 'Door opened'
                    log_entry = {
                        "timestamp": now.isoformat(),
                        "ip": client_ip,
                        "user": matched_user,
                        "status": "SUCCESS",
                        "details": reason
                    }
                    attempt_logger.info(json.dumps(log_entry))
                    display_name = matched_user.capitalize()
                    return jsonify({"status": "success", "message": f"Door open command sent.\nWelcome home, {display_name}!"})
                else:
                    reason = f'Home Assistant API error: {response.status_code}'
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
        else:
            # Failed authentication - increment counter and apply rate limiting
            ip_failed_attempts[client_ip] += 1
            
            # Check if we should block this IP
            if ip_failed_attempts[client_ip] >= MAX_ATTEMPTS:
                ip_blocked_until[client_ip] = now + BLOCK_TIME
                reason = f'Invalid PIN. IP blocked for {int(BLOCK_TIME.total_seconds()//60)} minutes after {MAX_ATTEMPTS} failed attempts'
            else:
                # Apply progressive delay
                delay = get_delay_seconds(ip_failed_attempts[client_ip])
                if delay > 0:
                    time.sleep(delay)
                remaining_attempts = MAX_ATTEMPTS - ip_failed_attempts[client_ip]
                reason = f'Invalid PIN. {remaining_attempts} attempts remaining'
            
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": client_ip,
                "user": "UNKNOWN",
                "status": "FAILURE",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": reason}), 401

    except Exception as e:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "ip": get_client_ip(),
            "user": "UNKNOWN",
            "status": "FAILURE",
            "details": f"Exception in open_door: {e}"
        }
        attempt_logger.info(json.dumps(log_entry))
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/admin/auth', methods=['POST'])
def admin_auth():
    data = request.get_json()
    password = data.get('password', '').strip() if data else ''
    if password == admin_password:
        session['admin_authenticated'] = True
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
    app.run(host='0.0.0.0', port=5000, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
