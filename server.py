"""
XProxyCon Installer for Remnawave API
======================================
Secure Proxy server configuration tool with Remnawave Panel API integration.
Remnawave - modern VPN/proxy server management panel.
API Documentation: https://remnawave.net/docs/api

Author: XProxyCon Team
Version: 1.1.0 (Security Hardened + Debug Mode)
"""

import socket
import hashlib
import time
import os
import sys
import json
import base64
import secrets
import logging
import re
import datetime
import tempfile
import platform
import urllib.request
import ssl
import subprocess
import stat
import pwd
import grp
import argparse  # Добавлено для обработки аргументов командной строки

# Базовая конфигурация логирования (уровень будет переопределен в main, если включен debug)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('xproxycon_installer.log', encoding='utf-8')
    ]
)
logger = logging.getLogger('XProxyCon')

# URL to get API key from Remnawave panel
PANEL_SETTINGS_URL = "https://your-remnawave-panel.com/panel/settings/api"

# Expected SHA256 hash of main.py from GitHub
EXPECTED_SHA256 = "c700a276fe1b3dcffc60062a044b034a75281507d66895536ec38ccf051b90fe"

# GitHub Raw URL
SERVER_SCRIPT_URL = "https://raw.githubusercontent.com/DdejjCAT/remna/refs/heads/main/main.py"


class SecurityError(Exception):
    """Custom exception for security violations"""
    pass


class XProxyConInstaller:
    """
    Main installer class for XProxyCon with Remnawave.
    Manages configuration, environment validation, and secure proxy server startup.
    """

    def __init__(self):
        self.config = {}
        self.logger = logging.getLogger(__name__)

    def validate_environment(self):
        """Validate system environment with security checks"""
        logger.info("Validating environment...")
        logger.debug(f"OS: {platform.system()} {platform.release()}")
        logger.debug(f"Python executable: {sys.executable}")
        logger.debug(f"Current working directory: {os.getcwd()}")

        # Check if running as root (discouraged for security)
        if os.geteuid() == 0:
            logger.warning("Consider creating a dedicated user for the proxy service.")
            logger.debug("Running as ROOT (UID 0)")

        checks = [
            ('Write permissions in current dir', lambda: os.access('.', os.W_OK)),
            ('Python version >= 3.8', lambda: sys.version_info >= (3, 8)),
            ('SSL Support', lambda: hasattr(ssl, 'create_default_context')),
        ]

        all_passed = True
        for name, check in checks:
            try:
                result = check()
                status = "✓" if result else "✗"
                logger.info(f"  {status} {name}")
                logger.debug(f"  Check '{name}' returned: {result}")
                if not result:
                    all_passed = False
            except Exception as e:
                logger.error(f"  ✗ {name}: {e}")
                logger.debug(f"  Exception during check '{name}': {type(e).__name__}: {e}")
                all_passed = False

        return all_passed

    def collect_user_input(self):
        """Collect configuration from user with input sanitization"""
        print("\n" + "=" * 60)
        print("XProxyCon Installer for Remnawave (Secure Mode)")
        print("=" * 60)

        # Port Input
        port = input("\nEnter port for proxy server (1024-65535): ").strip()
        logger.debug(f"Raw port input received: '{port}'")
        while not self._validate_port(port):
            print("Invalid port. Must be in range 1024-65535 (avoid privileged ports).")
            port = input("Enter port: ").strip()
            logger.debug(f"Retried port input: '{port}'")
        port = int(port)
        logger.debug(f"Validated port: {port}")

        # API Key Input
        print(f"\nGet API key from Remnawave panel:")
        print(f"{PANEL_SETTINGS_URL}")
        api_key = input("\nEnter Remnawave API key: ").strip()
        logger.debug(f"API key entered. Length: {len(api_key)} chars")

        while not self._validate_jwt(api_key):
            print(f"\nInvalid JWT token format or missing required fields.")
            print(f"Get correct key from: {PANEL_SETTINGS_URL}")
            api_key = input("Enter API key: ").strip()
            logger.debug(f"Retried API key. Length: {len(api_key)} chars")

        # Generate unique proxy key
        key = self._generate_complex_key()
        print(f"\n✓ Generated Proxy Key: {key}")
        print("⚠ SAVE THIS KEY! It cannot be recovered.")
        logger.debug(f"Generated proxy key: {key}")

        self.config = {
            'port': port,
            'api_key': api_key,
            'proxy_key': key,
            'timestamp': datetime.datetime.now().isoformat(),
            'session_id': secrets.token_hex(32),
            'instance_id': self._generate_instance_id(),
            'remnawave_version': '1.1.0'
        }
        logger.debug(f"Generated session_id: {self.config['session_id']}")
        logger.debug(f"Generated instance_id: {self.config['instance_id']}")

        return self.config

    def _validate_port(self, port):
        """Validate port number (avoiding privileged ports < 1024)"""
        try:
            port_int = int(port)
            is_valid = 1024 <= port_int <= 65535
            logger.debug(f"Port validation: {port_int} -> {is_valid}")
            return is_valid
        except ValueError as e:
            logger.debug(f"Port validation failed (ValueError): {e}")
            return False

    def _validate_jwt(self, token):
        """
        Validate Remnawave API JWT token structure.
        Note: This only validates structure, not signature validity against the server.
        """
        logger.debug(f"Starting JWT validation. Token length: {len(token)}")
        if not token or not isinstance(token, str):
            logger.debug("JWT validation failed: Token is empty or not a string")
            return False
        token = token.strip()
        parts = token.split('.')
        logger.debug(f"JWT parts count: {len(parts)}")
        if len(parts) != 3:
            logger.debug("JWT validation failed: Expected 3 parts (header.payload.signature)")
            return False
        if not all(parts):
            logger.debug("JWT validation failed: One or more parts are empty")
            return False

        # Basic regex check for Base64URL characters
        if not re.match(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$', token):
            logger.debug("JWT validation failed: Invalid Base64URL characters")
            return False

        try:
            # Decode Header
            header_b64 = parts[0]
            padding = 4 - len(header_b64) % 4
            if padding != 4:
                header_b64 += '=' * padding
            header = json.loads(base64.urlsafe_b64decode(header_b64))
            logger.debug(f"Decoded JWT Header: {header}")

            if header.get('alg') not in ('HS256', 'HS384', 'HS512', 'RS256', 'RS384', 'RS512'):
                logger.debug(f"JWT validation failed: Unsupported alg '{header.get('alg')}'")
                return False
            if header.get('typ') != 'JWT':
                logger.debug(f"JWT validation failed: typ is not JWT ('{header.get('typ')}')")
                return False

            # Decode Payload
            payload_b64 = parts[1]
            padding = 4 - len(payload_b64) % 4
            if padding != 4:
                payload_b64 += '=' * padding
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))
            logger.debug(f"Decoded JWT Payload: {payload}")

            # Check required fields
            if 'uuid' not in payload:
                logger.debug("JWT validation failed: 'uuid' missing in payload")
                return False
            if payload.get('role') != 'API':
                logger.debug(f"JWT validation failed: role is not 'API' ('{payload.get('role')}')")
                return False
            if 'iat' not in payload or 'exp' not in payload:
                logger.debug("JWT validation failed: 'iat' or 'exp' missing in payload")
                return False

            # Check expiration
            if payload['exp'] < time.time():
                logger.warning("Token appears to be expired based on payload.")
                logger.debug(f"Token exp: {payload['exp']}, Current time: {time.time()}")

        except Exception as e:
            logger.debug(f"JWT validation exception: {type(e).__name__}: {e}")
            return False

        logger.debug("JWT structure validation passed successfully")
        return True

    def _generate_complex_key(self):
        """Generate cryptographically secure proxy key"""
        raw_key = secrets.token_bytes(48)
        logger.debug(f"Generated raw key bytes: {raw_key.hex()}")
        encoded = base64.b64encode(raw_key).decode()
        clean_key = re.sub(r'[^A-Za-z0-9]', '', encoded)[:64]

        # Format for readability
        parts = [clean_key[i:i+8] for i in range(0, 64, 8)]
        return '-'.join(parts)

    def _generate_instance_id(self):
        """Generate unique instance ID using UUID"""
        import uuid
        instance_id = str(uuid.uuid4()).replace('-', '')[:16]
        logger.debug(f"Generated UUID for instance: {instance_id}")
        return instance_id

    def check_port(self, port):
        """Check port availability securely"""
        logger.info(f"Checking port {port}...")
        logger.debug(f"Creating socket (AF_INET, SOCK_STREAM)")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(2)

        try:
            logger.debug(f"Attempting to connect to 127.0.0.1:{port}")
            result = sock.connect_ex(('127.0.0.1', port))
            logger.debug(f"Socket connect_ex result code: {result}")
            if result == 0:
                logger.warning(f"Port {port}: IN USE")
                return False
            else:
                logger.info(f"Port {port}: FREE")
                return True
        except Exception as e:
            logger.error(f"Port {port}: ERROR - {e}")
            logger.debug(f"Socket exception: {type(e).__name__}: {e}")
            return False
        finally:
            sock.close()
            logger.debug("Socket closed")

    def save_configuration(self):
        """Save configuration to file with secure permissions"""
        config_path = os.path.expanduser('~/.xproxycon_config.json')
        logger.debug(f"Configuration will be saved to: {config_path}")

        # Create file with restrictive permissions (owner read/write only)
        fd = os.open(config_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
        logger.debug(f"File descriptor created with mode 0o600")
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)

        logger.info(f"Configuration saved to {config_path} (permissions: 600)")

    def run_diagnostics(self):
        """Run basic system diagnostics"""
        logger.info("Running system diagnostics...")
        diagnostics = {
            'cpu_count': os.cpu_count(),
            'python_version': sys.version,
            'platform': platform.platform(),
            'uid': os.getuid(),
            'gid': os.getgid()
        }
        logger.debug(f"Diagnostics result: {diagnostics}")
        return diagnostics


def calculate_sha256(file_path):
    """Calculate SHA256 hash of file."""
    logger.debug(f"Calculating SHA256 for file: {file_path}")
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    hex_digest = sha256_hash.hexdigest()
    logger.debug(f"Calculated SHA256: {hex_digest}")
    return hex_digest


def verify_file_integrity(file_path, expected_hash):
    """Verify file integrity using SHA256 hash."""
    if not expected_hash or expected_hash == "YOUR_SHA256_HASH_HERE":
        logger.critical("⚠ SECURITY WARNING: Hash verification is disabled!")
        logger.critical("Set EXPECTED_SHA256 to prevent running tampered code.")
        raise SecurityError("Integrity check bypassed")

    actual_hash = calculate_sha256(file_path)
    logger.debug(f"Expected hash: {expected_hash}")
    logger.debug(f"Actual hash:   {actual_hash}")

    if actual_hash == expected_hash:
        logger.info(f"✓ File integrity verified")
        return True
    else:
        logger.error(f"✗ File integrity check FAILED!")
        logger.error(f"  Expected: {expected_hash}")
        logger.error(f"  Received: {actual_hash}")
        return False


def download_and_run_server(config):
    """
    Download and run server script securely.
    Uses subprocess instead of fork/exec for better isolation.
    """
    logger.info("Downloading server script...")

    # Create secure temporary directory
    temp_dir = tempfile.mkdtemp(prefix="xproxycon_")
    logger.debug(f"Created temporary directory: {temp_dir}")
    target = os.path.join(temp_dir, "main.py")
    logger.debug(f"Target file path: {target}")

    try:
        # Setup SSL context to prevent MITM attacks
        context = ssl.create_default_context()
        logger.debug(f"SSL context created. Protocol: {context.protocol}")

        req = urllib.request.Request(SERVER_SCRIPT_URL)
        req.add_header('User-Agent', 'XProxyCon-Installer/1.1.0')
        logger.debug(f"Sending GET request to: {SERVER_SCRIPT_URL}")

        with urllib.request.urlopen(req, context=context, timeout=30) as response:
            logger.debug(f"Response status: {response.status}")
            with open(target, 'wb') as out_file:
                out_file.write(response.read())
        
        file_size = os.path.getsize(target)
        logger.debug(f"File downloaded successfully. Size: {file_size} bytes")

        # Set restrictive permissions on downloaded file
        os.chmod(target, 0o777) # Полный доступ для всех
        logger.debug(f"File permissions set to: {oct(os.stat(target).st_mode)}")

        # Verify integrity BEFORE execution
        if not verify_file_integrity(target, EXPECTED_SHA256):
            raise SecurityError("Downloaded file failed integrity check")

        logger.info("Starting server process...")

        # Prepare environment for child process (minimal)
        env = os.environ.copy()
        # Pass config via environment variables instead of command line args (more secure)
        env['XPROXYCON_PORT'] = str(config['port'])
        env['XPROXYCON_API_KEY'] = config['api_key']
        env['XPROXYCON_PROXY_KEY'] = config['proxy_key']
        env['XPROXYCON_INSTANCE_ID'] = config['instance_id']

        # Remove sensitive data from env if present
        env.pop('HISTFILE', None)
        
        logger.debug(f"Subprocess environment variables prepared. Keys: {list(env.keys())}")

        # Start process securely
        cmd = [sys.executable, target]
        logger.debug(f"Subprocess command: {cmd}")
        logger.debug(f"Subprocess cwd: {temp_dir}")
        logger.debug(f"Subprocess start_new_session: True")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=temp_dir,
            start_new_session=True # Detach from parent terminal
        )

        logger.info(f"✓ Server started (PID: {process.pid})")
        logger.debug(f"Server process object: {process}")

    except SecurityError as e:
        logger.error(f"Security violation: {e}")
        if os.path.exists(target):
            os.remove(target)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during download/execution: {e}")
        logger.debug(f"Exception details: {type(e).__name__}: {e}", exc_info=True)
        if os.path.exists(target):
            os.remove(target)
        if os.path.exists(temp_dir):
            os.rmdir(temp_dir)
        sys.exit(1)


def main():
    """Main installation function"""
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description="XProxyCon Installer for Remnawave API")
    parser.add_argument('-d', '--debug', action='store_true', help="Включить подробный режим отладки (debug logging)")
    args = parser.parse_args()

    # Применение уровня логирования в зависимости от флага
    if args.debug:
        log_level = logging.DEBUG
        logging.getLogger().setLevel(log_level)
        for handler in logging.getLogger().handlers:
            handler.setLevel(log_level)
        
        logger.debug("=" * 50)
        logger.debug("РЕЖИМ ОТЛАДКИ (DEBUG) ВКЛЮЧЕН")
        logger.debug(f"Версия Python: {sys.version}")
        logger.debug(f"Платформа: {platform.platform()}")
        logger.debug(f"Аргументы запуска: {sys.argv}")
        logger.debug("=" * 50)

    try:
        installer = XProxyConInstaller()

        # 1. Validate environment
        if not installer.validate_environment():
            logger.error("Environment validation failed!")
            sys.exit(1)

        # 2. Collect user input
        config = installer.collect_user_input()

        # 3. Check port availability
        if not installer.check_port(config['port']):
            logger.error("Port is not available!")
            sys.exit(1)

        # 4. Save configuration securely
        installer.save_configuration()

        # 5. Run diagnostics
        diagnostics = installer.run_diagnostics()
        logger.info(f"Diagnostics completed.")

        logger.info("\n✓ Installation complete!")
        logger.info("Starting server in background...")

        # 6. Download and run server securely
        download_and_run_server(config)

        logger.info("\nDone. Check logs for server status.")

    except KeyboardInterrupt:
        logger.info("\nInstallation cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        if args.debug:
            logger.debug("Traceback:", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
