#!/usr/bin/env python3
import socket
import sys
import threading
import os
import time

try:
    import pyreadline3 as readline
    READLINE_AVAILABLE = True
except ImportError:
    try:
        import readline
        READLINE_AVAILABLE = True
    except ImportError:
        readline = None
        READLINE_AVAILABLE = False

HOST = "nevpn2.fenst4r.live"
PORT = 7384
LOGIN = "root"
PASSWORD = "meowmeowmeow"
HISTORY_FILE = os.path.expanduser("~/.frsandbox_history")

def load_history():
    if not READLINE_AVAILABLE:
        return
    try:
        # Стандартный readline (Linux/macOS)
        if hasattr(readline, 'read_history_file'):
            readline.read_history_file(HISTORY_FILE)
        # pyreadline3 (Windows)
        elif hasattr(readline, 'rl') and hasattr(readline.rl, 'mode'):
            readline.rl.mode.history.load_history(HISTORY_FILE)
    except FileNotFoundError:
        pass
    except Exception:
        pass

def save_history():
    if not READLINE_AVAILABLE:
        return
    try:
        if hasattr(readline, 'write_history_file'):
            readline.write_history_file(HISTORY_FILE)
        elif hasattr(readline, 'rl') and hasattr(readline.rl, 'mode'):
            readline.rl.mode.history.save_history(HISTORY_FILE)
    except Exception:
        pass

class FRSandboxClient:
    def __init__(self):
        self.socket = None
        self.running = True
        
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((HOST, PORT))
            self.socket.settimeout(None)
            print(f"✅ Connected to {HOST}:{PORT}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def authenticate(self):
        try:
            # Читаем Login:
            data = self.socket.recv(4096)
            if not data: return False
            sys.stdout.write(data.decode('latin-1', errors='ignore'))
            sys.stdout.flush()
            
            # Отправляем логин
            self.socket.send(f"{LOGIN}\n".encode())
            
            # Читаем Password:
            data = self.socket.recv(4096)
            if not data: return False
            sys.stdout.write(data.decode('latin-1', errors='ignore'))
            sys.stdout.flush()
            
            # Отправляем пароль
            self.socket.send(f"{PASSWORD}\n".encode())
            
            # Читаем приветствие
            time.sleep(0.3)
            try:
                self.socket.settimeout(2)
                data = self.socket.recv(4096)
                if data:
                    sys.stdout.write(data.decode('latin-1', errors='ignore'))
                    sys.stdout.flush()
                self.socket.settimeout(None)
            except socket.timeout:
                pass
            
            return True
        except Exception as e:
            print(f"❌ Auth failed: {e}")
            return False
    
    def reader(self):
        while self.running:
            try:
                if not self.socket:
                    break
                data = self.socket.recv(4096)
                if not data:
                    print("\n🔌 Connection closed")
                    break
                
                # Выводим данные
                try:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                except AttributeError:
                    sys.stdout.write(data.decode('latin-1', errors='ignore'))
                    sys.stdout.flush()
                    
            except (socket.error, OSError):
                if self.running:
                    print("\n❌ Connection lost")
                break
            except Exception:
                break
    
    def writer(self):
        while self.running:
            try:
                cmd = input()
                
                if cmd is None:
                    break
                
                cmd = cmd.strip()
                if not cmd:
                    continue
                
                if cmd.lower() == "exit":
                    try:
                        self.socket.send(b"exit\n")
                    except:
                        pass
                    break
                
                try:
                    self.socket.send((cmd + "\n").encode())
                except (socket.error, BrokenPipeError, OSError):
                    if self.running:
                        print("\n❌ Connection lost")
                    break
                
            except KeyboardInterrupt:
                print("\n⏹ Interrupted")
                break
            except EOFError:
                break
            except Exception:
                break
    
    def run(self):
        print("╔════════════════════════════════════════╗")
        print("║ FRSANDBOX Client v4.1  by @error_kill  ║")
        print("╚════════════════════════════════════════╝\n")
        
        if not self.connect():
            return
        
        if not self.authenticate():
            try: self.socket.close()
            except: pass
            return
        
        # Запускаем потоки
        reader_thread = threading.Thread(target=self.reader, daemon=True)
        writer_thread = threading.Thread(target=self.writer, daemon=True)
        
        reader_thread.start()
        writer_thread.start()
        
        # Ждем завершения writer
        writer_thread.join()
        self.running = False
        
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        
        print("\n👋 Disconnected")

if __name__ == "__main__":
    # Загружаем историю команд
    load_history()
    
    try:
        client = FRSandboxClient()
        client.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        save_history()
