import socket
import sys
import time
import threading
import readline
import os

class FRSandboxClient:
    def __init__(self, host="nevpn2.fenst4r.live", port=7384):
        self.host = host
        self.port = port
        self.socket = None
        self.running = True
        self.buffer = ""
        
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"✅ Connected to {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    def authenticate(self):
        """Авторизация на сервере"""
        try:
            time.sleep(2)
            self.socket.send(b"root\n")
            time.sleep(0.5)
            self.socket.send(b"fenst4risalive\n")
            time.sleep(0.5)
            print("🔐 Authentication sent")
            return True
        except Exception as e:
            print(f"❌ Auth failed: {e}")
            return False
    
    def reader_thread(self):
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    print("\n🔌 Connection closed by server")
                    break
                
                text = data.decode('utf-8', errors='ignore')
                self.buffer += text
                
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    if line.strip() or not line.endswith("# "):
                        sys.stdout.write(line + '\n')
                        sys.stdout.flush()
                
                if self.buffer and '\n' not in self.buffer:
                    sys.stdout.write(self.buffer)
                    sys.stdout.flush()
                    
            except socket.error as e:
                if self.running:
                    print(f"\n❌ Socket error: {e}")
                break
            except Exception as e:
                print(f"\n❌ Reader error: {e}")
                break
    
    def writer_thread(self):
        histfile = os.path.expanduser("~/.frsandbox_history")
        try:
            readline.read_history_file(histfile)
        except FileNotFoundError:
            pass
        
        while self.running:
            try:
                sys.stdout.flush()
                
                cmd = sys.stdin.readline()
                if not cmd:
                    break
                
                cmd = cmd.strip()
                if not cmd:
                    continue
                
                if cmd.lower() == "exit":
                    self.socket.send(b"exit\n")
                    break
                elif cmd.lower() == "clear":
                    os.system('clear' if os.name == 'posix' else 'cls')
                    continue
                elif cmd.lower() == "help":
                    self.show_help()
                    continue
                elif cmd.lower() == "history":
                    self.show_history()
                    continue
                
                self.socket.send(cmd.encode() + b"\n")
                
                try:
                    readline.write_history_file(histfile)
                except:
                    pass
                
            except KeyboardInterrupt:
                print("\n⏹ Interrupted")
                break
            except Exception as e:
                print(f"❌ Writer error: {e}")
                break
    
    def show_help(self):
        help_text = """
╔══════════════════════════════════════════════╗
║  FRSANDBOX Client Commands                  ║
╠══════════════════════════════════════════════╣
║  exit    - Disconnect from server           ║
║  clear   - Clear screen                     ║
║  history - Show command history             ║
║  help    - Show this help                   ║
╚══════════════════════════════════════════════╝
        """
        print(help_text)
    
    def show_history(self):
        histfile = os.path.expanduser("~/.frsandbox_history")
        try:
            with open(histfile, 'r') as f:
                lines = f.readlines()
                print("\n📜 Command History:")
                for i, line in enumerate(lines[-20:], 1):
                    print(f"  {i}. {line.strip()}")
        except:
            print("No history available")
    
    def run(self):
        if not self.connect():
            return
        
        if not self.authenticate():
            self.socket.close()
            return
        
        print("\n" + "="*50)
        print("[Pusherxddd]")
        print("   Type 'help' for commands, 'exit' to quit")
        print("="*50 + "\n")
        
        reader = threading.Thread(target=self.reader_thread, daemon=True)
        writer = threading.Thread(target=self.writer_thread, daemon=True)
        
        reader.start()
        writer.start()
        
        writer.join()
        self.running = False
        
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()
        except:
            pass
        
        print("\n👋 Disconnected from FRSANDBOX")

def main():
    client = FRSandboxClient()
    
    try:
        client.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()
