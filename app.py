#!/usr/bin/env python3
"""
DoorOpener Web Portal v1.2
---------------------------
A secure Flask web app to open a door via Home Assistant API, with visual keypad interface,
enhanced multi-layer security, timezone support, and comprehensive brute force protection.
"""
import os
import json
import time
import logging
import requests
import secrets
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, render_template, request, jsonify, session
from werkzeug.middleware.proxy_fix import ProxyFix
from configparser import ConfigParser
import pytz

# --- Timezone Setup ---
# Get timezone from environment variable, default to UTC
TZ = os.environ.get('TZ', 'UTC')
try:
    TIMEZONE = pytz.timezone(TZ)
    print(f"Using timezone: {TZ}")
except pytz.exceptions.UnknownTimeZoneError:
    print(f"Unknown timezone '{TZ}', falling back to UTC")
    TIMEZONE = pytz.UTC
    TZ = 'UTC'

def get_current_time():
    """Get current time in the configured timezone"""
    return datetime.now(TIMEZONE)

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

# Configure secure session cookies
app.config.update(
    SESSION_COOKIE_SECURE=True,  # Only send over HTTPS (reverse proxy handles this)
    SESSION_COOKIE_HTTPONLY=True,  # Prevent XSS access to cookies
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
    PERMANENT_SESSION_LIFETIME=timedelta(days=30)  # Default permanent session duration
)

# --- Configuration ---
config = ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_path)

# Per-user PINs from [pins] section
user_pins = dict(config.items('pins')) if config.has_section('pins') else {}

# Admin Configuration
admin_password = config.get('admin', 'admin_password', fallback='4384339380437neghrjlkmfef')

# Server Configuration
server_port = int(os.environ.get('DOOROPENER_PORT', config.getint('server', 'port', fallback=6532)))
test_mode = config.getboolean('server', 'test_mode', fallback=False)

# Home Assistant Configuration
ha_url = config.get('HomeAssistant', 'url', fallback='http://homeassistant.local:8123')
ha_token = config.get('HomeAssistant', 'token')
entity_id = config.get('HomeAssistant', 'switch_entity')  # Backward compatible; can be lock or switch
battery_entity = config.get('HomeAssistant', 'battery_entity', 
                           fallback=f'sensor.{entity_id.split(".")[1]}_battery')

# Extract device name from entity
if '.' in entity_id:
    device_name = entity_id.split('.')[1]
else:
    device_name = entity_id

# Headers for HA API requests
ha_headers = {
    'Authorization': f'Bearer {ha_token}',
    'Content-Type': 'application/json'
}

# --- Enhanced Security & Rate Limiting ---
ip_failed_attempts = defaultdict(int)
ip_blocked_until = defaultdict(lambda: None)
session_failed_attempts = defaultdict(int)
session_blocked_until = defaultdict(lambda: None)
global_failed_attempts = 0
global_last_reset = get_current_time()
MAX_ATTEMPTS = 5
BLOCK_TIME = timedelta(minutes=5)
MAX_GLOBAL_ATTEMPTS_PER_HOUR = 50
SESSION_MAX_ATTEMPTS = 3

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

def get_client_identifier():
    """Get client identifier using multiple factors for better security"""
    # Use request.remote_addr as primary (can't be spoofed easily)
    primary_ip = request.remote_addr
    
    # Create session-based identifier if available
    session_id = session.get('_session_id')
    if not session_id:
        session_id = secrets.token_hex(16)
        session['_session_id'] = session_id
    
    # Combine multiple factors for identifier
    user_agent = request.headers.get('User-Agent', '')[:100]  # Limit length
    accept_lang = request.headers.get('Accept-Language', '')[:50]
    
    # Create composite identifier (harder to spoof than just IP)
    identifier = f"{primary_ip}:{hash(user_agent + accept_lang) % 10000}"
    
    return primary_ip, session_id, identifier

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

def check_global_rate_limit():
    """Check global rate limiting across all requests"""
    global global_failed_attempts, global_last_reset
    now = get_current_time()
    
    # Reset global counter every hour
    if now - global_last_reset > timedelta(hours=1):
        global_failed_attempts = 0
        global_last_reset = now
    
    return global_failed_attempts < MAX_GLOBAL_ATTEMPTS_PER_HOUR

def is_request_suspicious():
    """Detect suspicious request patterns"""
    # Check for missing or suspicious headers
    user_agent = request.headers.get('User-Agent', '')
    if not user_agent or len(user_agent) < 10:
        return True
    
    # Check for common bot patterns
    suspicious_agents = ['curl', 'wget', 'python-requests', 'bot', 'crawler']
    if any(agent in user_agent.lower() for agent in suspicious_agents):
        return True
    
    # Check for rapid requests (basic timing check)
    if not hasattr(request, 'start_time'):
        request.start_time = get_current_time()
    
    return False

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
            logger.info(f"Battery response: {state_data}")
            
            # Handle different battery level formats
            if battery_level is not None:
                try:
                    # Convert to float and ensure it's a valid percentage
                    battery_float = float(battery_level)
                    if 0 <= battery_float <= 100:
                        return jsonify({"level": int(battery_float)})
                    else:
                        logger.warning(f"Battery level out of range: {battery_float}")
                        return jsonify({"level": None})
                except (ValueError, TypeError):
                    logger.warning(f"Invalid battery level format: {battery_level}")
                    return jsonify({"level": None})
            else:
                logger.warning("Battery level is None")
                return jsonify({"level": None})
        else:
            logger.error(f"Failed to fetch battery state: {response.status_code} {response.text}")
            return jsonify({"level": None})
    except Exception as e:
        logger.error(f"Exception fetching battery: {e}")
        return jsonify({"level": None})

@app.route('/open-door', methods=['POST'])
def open_door():
    try:
        primary_ip, session_id, identifier = get_client_identifier()
        now = get_current_time()
        global global_failed_attempts
        
        # Check for suspicious requests first
        if is_request_suspicious():
            reason = 'Suspicious request detected'
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": primary_ip,
                "session": session_id[:8],
                "user": "UNKNOWN",
                "status": "SUSPICIOUS",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": "Request blocked"}), 403
        
        # Check global rate limit
        if not check_global_rate_limit():
            reason = 'Global rate limit exceeded'
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": primary_ip,
                "session": session_id[:8],
                "user": "UNKNOWN",
                "status": "GLOBAL_BLOCKED",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": "Service temporarily unavailable"}), 429
        
        # Check session-based blocking (harder to bypass)
        if session_blocked_until[session_id] and now < session_blocked_until[session_id]:
            remaining = (session_blocked_until[session_id] - now).total_seconds()
            reason = f'Session blocked for {int(remaining)} more seconds'
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": primary_ip,
                "session": session_id[:8],
                "user": "UNKNOWN",
                "status": "SESSION_BLOCKED",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": "Too many failed attempts. Please try again later."}), 429
        
        # Check IP-based blocking (fallback)
        if ip_blocked_until[identifier] and now < ip_blocked_until[identifier]:
            remaining = (ip_blocked_until[identifier] - now).total_seconds()
            reason = f'IP blocked for {int(remaining)} more seconds'
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": primary_ip,
                "session": session_id[:8],
                "user": "UNKNOWN",
                "status": "IP_BLOCKED",
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
            # Increment all counters on invalid input
            ip_failed_attempts[identifier] += 1
            session_failed_attempts[session_id] += 1
            global_failed_attempts += 1
            
            reason = validated_pin  # Error message
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": primary_ip,
                "session": session_id[:8],
                "user": "UNKNOWN",
                "status": "INVALID_FORMAT",
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
            ip_failed_attempts[identifier] = 0
            session_failed_attempts[session_id] = 0
            if identifier in ip_blocked_until:
                del ip_blocked_until[identifier]
            if session_id in session_blocked_until:
                del session_blocked_until[session_id]

            # Check if test mode is enabled
            if test_mode:
                # Test mode: simulate successful door opening without API call
                reason = 'Door opened (TEST MODE)'
                log_entry = {
                    "timestamp": now.isoformat(),
                    "ip": primary_ip,
                    "session": session_id[:8],
                    "user": matched_user,
                    "status": "SUCCESS",
                    "details": reason
                }
                attempt_logger.info(json.dumps(log_entry))
                display_name = matched_user.capitalize()
                return jsonify({"status": "success", "message": f"Door open command sent (TEST MODE).\nWelcome home, {display_name}!"})
            
            # Production mode: try to open door via Home Assistant
            try:
                if entity_id.startswith('lock.'):
                    url = f"{ha_url}/api/services/lock/unlock"
                else:
                    url = f"{ha_url}/api/services/switch/turn_on"
                payload = {"entity_id": entity_id}
                response = requests.post(url, headers=ha_headers, json=payload, timeout=10)
                
                if response.status_code == 200:
                    reason = 'Door opened'
                    log_entry = {
                        "timestamp": now.isoformat(),
                        "ip": primary_ip,
                        "session": session_id[:8],
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
                        "ip": primary_ip,
                        "session": session_id[:8],
                        "user": matched_user,
                        "status": "FAILURE",
                        "details": reason
                    }
                    attempt_logger.info(json.dumps(log_entry))
                    return jsonify({"status": "error", "message": reason}), 500
            except Exception as e:
                import traceback
                reason = 'Internal server error during API call'
                log_entry = {
                    "timestamp": now.isoformat(),
                    "ip": primary_ip,
                    "session": session_id[:8],
                    "user": matched_user,
                    "status": "API_FAILURE",
                    "details": reason,
                    "exception": str(e),
                    "traceback": traceback.format_exc()
                }
                attempt_logger.info(json.dumps(log_entry))
                return jsonify({"status": "error", "message": reason}), 500
        else:
            # Failed authentication - increment all counters
            ip_failed_attempts[identifier] += 1
            session_failed_attempts[session_id] += 1
            global_failed_attempts += 1
            
            # Check session-based blocking first (harder to bypass)
            if session_failed_attempts[session_id] >= SESSION_MAX_ATTEMPTS:
                session_blocked_until[session_id] = now + BLOCK_TIME
                reason = f'Invalid PIN. Session blocked for {int(BLOCK_TIME.total_seconds()//60)} minutes after {SESSION_MAX_ATTEMPTS} failed attempts'
            elif ip_failed_attempts[identifier] >= MAX_ATTEMPTS:
                ip_blocked_until[identifier] = now + BLOCK_TIME
                reason = f'Invalid PIN. Access blocked for {int(BLOCK_TIME.total_seconds()//60)} minutes after {MAX_ATTEMPTS} failed attempts'
            else:
                # Apply progressive delay based on session attempts (more secure)
                delay = get_delay_seconds(session_failed_attempts[session_id])
                if delay > 0:
                    time.sleep(delay)
                remaining_attempts = min(
                    SESSION_MAX_ATTEMPTS - session_failed_attempts[session_id],
                    MAX_ATTEMPTS - ip_failed_attempts[identifier]
                )
                reason = f'Invalid PIN. {remaining_attempts} attempts remaining'
            
            log_entry = {
                "timestamp": now.isoformat(),
                "ip": primary_ip,
                "session": session_id[:8],
                "user": "UNKNOWN",
                "status": "AUTH_FAILURE",
                "details": reason
            }
            attempt_logger.info(json.dumps(log_entry))
            return jsonify({"status": "error", "message": reason}), 401

    except Exception as e:
        try:
            primary_ip, session_id, _ = get_client_identifier()
        except:
            primary_ip = request.remote_addr
            session_id = "unknown"
        
        log_entry = {
            "timestamp": get_current_time().isoformat(),
            "ip": primary_ip,
            "session": session_id[:8] if session_id != "unknown" else "unknown",
            "user": "UNKNOWN",
            "status": "EXCEPTION",
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
    remember_me = data.get('remember_me', False) if data else False
    
    if password == admin_password:
        session['admin_authenticated'] = True
        session['admin_login_time'] = get_current_time().isoformat()
        
        # Set session to be permanent if remember_me is checked
        if remember_me:
            session.permanent = True
            # Set cookie to expire in 30 days
            app.permanent_session_lifetime = timedelta(days=30)
        else:
            session.permanent = False
            # Session expires when browser closes
            
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Invalid admin password"}), 403

@app.route('/admin/check-auth', methods=['GET'])
def admin_check_auth():
    """Check if admin is currently authenticated"""
    if session.get('admin_authenticated'):
        login_time = session.get('admin_login_time')
        return jsonify({
            "authenticated": True, 
            "login_time": login_time
        })
    else:
        return jsonify({"authenticated": False})

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    """Logout admin user"""
    session.pop('admin_authenticated', None)
    session.pop('admin_login_time', None)
    session.permanent = False
    return jsonify({"status": "success", "message": "Logged out successfully"})

@app.route('/admin/logs')
def admin_logs():
    """Get parsed log data for admin dashboard"""
    # Check if admin is authenticated
    if not session.get('admin_authenticated'):
        return jsonify({"error": "Authentication required"}), 401
        
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
    app.run(host='0.0.0.0', port=server_port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
