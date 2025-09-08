#!/usr/bin/env python3
"""
DoorOpener Web Portal v1.6
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
from flask import Flask, render_template, request, jsonify, session, abort, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from configparser import ConfigParser
import pytz
try:
    from authlib.integrations.flask_client import OAuth
    from authlib.jose import jwt
except Exception:
    OAuth = None

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

# Add a logger for general errors if not already present
logger = logging.getLogger('dooropener')
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)

# --- Flask App Setup ---
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
# Prefer fixed secret from environment; fallback to temporary random (will be overridden by config.ini later if present)
_env_secret = os.environ.get('FLASK_SECRET_KEY')
if _env_secret:
    app.secret_key = _env_secret
    app.config['RANDOM_SECRET_WARNING'] = False
else:
    app.secret_key = secrets.token_hex(32)
    app.config['RANDOM_SECRET_WARNING'] = True

# Configure secure session cookies
# Allow overriding SESSION_COOKIE_SECURE via env for local HTTP/dev setups
_secure_cookie = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
app.config.update(
    SESSION_COOKIE_SECURE=_secure_cookie,  # Only send over HTTPS when true
    SESSION_COOKIE_HTTPONLY=True,  # Prevent XSS access to cookies
    SESSION_COOKIE_SAMESITE='Lax',  # CSRF protection
    PERMANENT_SESSION_LIFETIME=timedelta(days=30)  # Default permanent session duration
)

# --- Configuration ---
config = ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
config.read(config_path)

# If no env secret key was provided, allow overriding the temporary random with config.ini
if not _env_secret:
    try:
        _cfg_secret = config.get('server', 'secret_key', fallback=None)
        if _cfg_secret:
            app.secret_key = _cfg_secret
            app.config['RANDOM_SECRET_WARNING'] = False
        elif app.config.get('RANDOM_SECRET_WARNING'):
            logging.getLogger('dooropener').warning(
                'FLASK_SECRET_KEY not set and no [server] secret_key in config.ini; '
                'sessions may become invalid across restarts or multiple workers.'
            )
    except Exception:
        pass

# Per-user PINs from [pins] section
user_pins = dict(config.items('pins')) if config.has_section('pins') else {}

# Admin Configuration
admin_password = config.get('admin', 'admin_password', fallback='4384339380437neghrjlkmfef')

# Server Configuration
server_port = int(os.environ.get('DOOROPENER_PORT', config.getint('server', 'port', fallback=6532)))
test_mode = config.getboolean('server', 'test_mode', fallback=False)

# OIDC Configuration
oidc_enabled = config.getboolean('oidc', 'enabled', fallback=False)
oidc_issuer = config.get('oidc', 'issuer', fallback=None)
oidc_client_id = config.get('oidc', 'client_id', fallback=None)
oidc_client_secret = config.get('oidc', 'client_secret', fallback=None)
oidc_redirect_uri = config.get('oidc', 'redirect_uri', fallback=None)
oidc_admin_group = config.get('oidc', 'admin_group', fallback='')
oidc_user_group = config.get('oidc', 'user_group', fallback='')
require_pin_for_oidc = config.getboolean('oidc', 'require_pin_for_oidc', fallback=False)

oauth = None
if oidc_enabled and OAuth is not None and all([oidc_issuer, oidc_client_id, oidc_client_secret, oidc_redirect_uri]):
    try:
        oauth = OAuth(app)
        oauth.register(
            name='authentik',
            server_metadata_url=f"{oidc_issuer}/.well-known/openid-configuration",
            client_id=oidc_client_id,
            client_secret=oidc_client_secret,
            client_kwargs={
                'scope': 'openid email profile groups'
            }
        )
        logger.info('OIDC (Authentik) client registered')
    except Exception as e:
        logger.error(f'Failed to register OIDC client: {e}')
        oauth = None

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
# Load security settings from config
MAX_ATTEMPTS = config.getint('security', 'max_attempts', fallback=5)
BLOCK_TIME = timedelta(minutes=config.getint('security', 'block_time_minutes', fallback=5))
MAX_GLOBAL_ATTEMPTS_PER_HOUR = config.getint('security', 'max_global_attempts_per_hour', fallback=50)
SESSION_MAX_ATTEMPTS = config.getint('security', 'session_max_attempts', fallback=3)

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
    # Prevent caching of dynamic/admin JSON endpoints to avoid stale auth state
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
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
    try:
        if not isinstance(pin, str):
            raise ValueError("PIN must be a string")
        if not pin.isdigit() or not (4 <= len(pin) <= 8):
            return False, None
        return True, pin
    except Exception as e:
        logger.error(f"Error validating PIN input: {e}")
        return False, None

@app.after_request
def after_request(response):
    return add_security_headers(response)

@app.route('/')
def index():
    return render_template('index.html', oidc_enabled=bool(oauth), require_pin_for_oidc=require_pin_for_oidc)

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

        # Determine if OIDC session can open without PIN
        oidc_auth = bool(session.get('oidc_authenticated'))
        oidc_groups = session.get('oidc_groups', [])
        oidc_user = session.get('oidc_user')
        oidc_user_allowed = (not oidc_user_group) or (oidc_user_group in oidc_groups)

        data = request.get_json(force=True, silent=True)
        pin_from_request = data.get('pin') if data else None

        # If no PIN provided but OIDC user is authenticated and allowed, proceed without PIN
        if (not pin_from_request) and oidc_auth and oidc_user_allowed and not require_pin_for_oidc:
            matched_user = oidc_user or 'oidc-user'
            # Reset failed attempts upon authorized OIDC use
            ip_failed_attempts[identifier] = 0
            session_failed_attempts[session_id] = 0
            if identifier in ip_blocked_until:
                del ip_blocked_until[identifier]
            if session_id in session_blocked_until:
                del session_blocked_until[session_id]

            # Test or production flow mirrors the successful PIN path
            if test_mode:
                reason = 'Door opened (TEST MODE) via OIDC'
                log_entry = {
                    "timestamp": now.isoformat(),
                    "ip": primary_ip,
                    "session": session_id[:8],
                    "user": matched_user,
                    "status": "SUCCESS",
                    "details": reason
                }
                attempt_logger.info(json.dumps(log_entry))
                display_name = matched_user.capitalize() if isinstance(matched_user, str) else 'User'
                return jsonify({"status": "success", "message": f"Door open command sent (TEST MODE).\nWelcome home, {display_name}!"})

            try:
                if entity_id.startswith('lock.'):
                    url = f"{ha_url}/api/services/lock/unlock"
                elif entity_id.startswith('input_boolean.'):
                    url = f"{ha_url}/api/services/input_boolean/turn_on"
                else:
                    url = f"{ha_url}/api/services/switch/turn_on"
                payload = {"entity_id": entity_id}
                response = requests.post(url, headers=ha_headers, json=payload, timeout=10)
                response.raise_for_status()
                if response.status_code == 200:
                    reason = 'Door opened via OIDC'
                    log_entry = {
                        "timestamp": now.isoformat(),
                        "ip": primary_ip,
                        "session": session_id[:8],
                        "user": matched_user,
                        "status": "SUCCESS",
                        "details": reason
                    }
                    attempt_logger.info(json.dumps(log_entry))
                    display_name = matched_user.capitalize() if isinstance(matched_user, str) else 'User'
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
            except requests.RequestException as e:
                logger.error(f"Error communicating with Home Assistant: {e}")
                return jsonify({"status": "error", "message": "Failed to contact Home Assistant"}), 502
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

        # If we reach here, require a PIN (either because provided or policy demands it)
        if not data or 'pin' not in data:
            logger.warning("No PIN provided in request body")
            return jsonify({"status": "error", "message": "PIN required"}), 400
        
        # Validate PIN format
        pin_valid, validated_pin = validate_pin_input(pin_from_request)
        if not pin_valid:
            # Increment all counters on invalid input
            ip_failed_attempts[identifier] += 1
            session_failed_attempts[session_id] += 1
            global_failed_attempts += 1
            
            reason = "Invalid PIN format"  # Error message
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
                elif entity_id.startswith('input_boolean.'):
                    url = f"{ha_url}/api/services/input_boolean/turn_on"
                else:
                    url = f"{ha_url}/api/services/switch/turn_on"
                payload = {"entity_id": entity_id}
                response = requests.post(url, headers=ha_headers, json=payload, timeout=10)
                
                response.raise_for_status() # Raise an exception for bad status codes
                
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
            except requests.RequestException as e:
                logger.error(f"Error communicating with Home Assistant: {e}")
                return jsonify({"status": "error", "message": "Failed to contact Home Assistant"}), 502
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
    return render_template('admin.html', oidc_enabled=bool(oauth))

# --- OIDC (Authentik) Routes ---
@app.route('/login')
def login_redirect():
    if not oauth:
        # Fallback to local login page
        return redirect(url_for('admin'))
    
    # Generate a random state and store it in the session
    session['oidc_state'] = secrets.token_hex(16)
    
    # Start OIDC flow with the generated state
    return oauth.authentik.authorize_redirect(
        redirect_uri=oidc_redirect_uri,
        state=session['oidc_state'],
        nonce=session['oidc_nonce']  # Nonce already implemented
    )

@app.route('/oidc/callback')
def oidc_callback():
    if not oauth:
        return redirect(url_for('admin'))
    try:
        # Validate the state parameter to prevent CSRF attacks
        if request.args.get('state') != session.pop('oidc_state', None):
            abort(401, "Invalid state")
        
        # Authorize the access token from the OIDC provider
        token = oauth.authentik.authorize_access_token()
        
        # Extract the ID token and claims
        id_token = token.get('id_token')
        claims = {}
        try:
            # Authlib stores parsed claims at token['userinfo'] or use userinfo() call
            claims = token.get('userinfo') or oauth.authentik.parse_id_token(token)
        except Exception:
            try:
                claims = oauth.authentik.userinfo(token=token)
            except Exception:
                claims = {}

        # Validate the nonce value to prevent replay attacks
        if claims.get('nonce') != session.pop('oidc_nonce', None):
            abort(401, "Invalid nonce")

        # Verify the ID token signature and claims
        public_key = config.get('oidc', 'public_key', fallback=None)
        if public_key:
            try:
                claims = jwt.decode(id_token, key=public_key)
                # Validate signature, expiration, audience, etc.
                claims.validate()
            except Exception as e:
                logger.error(f"ID token validation error: {e}")
                return abort(401)

        # Extract user information from the claims
        user = claims.get('email') or claims.get('preferred_username') or claims.get('name') or 'oidc-user'
        groups = claims.get('groups') or claims.get('roles') or []
        if isinstance(groups, str):
            groups = [g.strip() for g in groups.split(',') if g.strip()]

        # Determine roles based on group membership
        is_admin = (not oidc_admin_group) or (oidc_admin_group in groups)
        is_user_allowed = (not oidc_user_group) or (oidc_user_group in groups)

        # Store OIDC session information
        session['oidc_authenticated'] = True
        session['oidc_user'] = user
        session['oidc_groups'] = groups

        # Redirect to admin page if the user is an admin
        if is_admin:
            session['admin_authenticated'] = True
            session['admin_login_time'] = get_current_time().isoformat()
            session['admin_user'] = user
            return redirect(url_for('admin'))
        else:
            # Redirect to the home page for normal users
            return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"OIDC callback error: {e}")
        return abort(401)

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

@app.route('/auth/status')
def auth_status():
    """Return current authentication status and OIDC capability flags for UI."""
    return jsonify({
        "oidc_enabled": bool(oauth),
        "oidc_authenticated": bool(session.get('oidc_authenticated')),
        "user": session.get('oidc_user'),
        "groups": session.get('oidc_groups', []),
        "require_pin_for_oidc": require_pin_for_oidc,
    })

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
            try:
                with open(log_path, 'r') as f:
                    for line in f:
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
                        except json.JSONDecodeError as e:
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
            except Exception as e:
                logger.error(f"Error reading log file: {e}")
        return jsonify({"logs": logs})
    except Exception as e:
        logger.error(f"Exception in admin_logs: {e}")
        return jsonify({"error": "Failed to load logs"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=server_port, debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true')
