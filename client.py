# frbox.py - Показываем всё, но без дублей
import socket
import sys
import time
import threading
import os
import re

try:
    import pyreadline3 as readline
    READLINE_AVAILABLE = True
except ImportError:
    try:
        import readline
        READLINE_AVAILABLE = True
    except ImportError:
        READLINE_AVAILABLE = False
        print("⚠️  Readline не доступен. Установите: pip install pyreadline3")

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

class FRSandboxClient:
    def __init__(self, host="nevpn2.fenst4r.live", port=7384):
        self.host = host
        self.port = port
        self.socket = None
        self.running = True
        self.buffer = ""
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.history_file = os.path.expanduser("~/.frsandbox_history")
        self.last_command = ""
        self.prompt = "root@frsandbox:~# "
        self.last_output = ""  # Для отслеживания последнего вывода
        
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)
            self.socket.connect((self.host, self.port))
            self.socket.settimeout(None)
            print(f"{Colors.GREEN}✅ Connected to {self.host}:{self.port}{Colors.RESET}")
            self.reconnect_attempts = 0
            return True
        except socket.timeout:
            print(f"{Colors.RED}❌ Connection timeout{Colors.RESET}")
            return False
        except Exception as e:
            print(f"{Colors.RED}❌ Connection failed: {e}{Colors.RESET}")
            return False
    
    def authenticate(self):
        try:
            print(f"{Colors.YELLOW}🔐 Authenticating...{Colors.RESET}")
            time.sleep(2)
            self.socket.send(b"root\n")
            time.sleep(0.5)
            self.socket.send(b"fenst4risalive\n")
            time.sleep(0.5)
            
            # Читаем приветствие
            data = self.socket.recv(4096)
            text = data.decode('utf-8', errors='ignore')
            print(text, end='')
            
            print(f"{Colors.GREEN}✅ Authentication successful{Colors.RESET}")
            return True
        except Exception as e:
            print(f"{Colors.RED}❌ Auth failed: {e}{Colors.RESET}")
            return False
    
    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def show_help(self):
        help_text = f"""
{Colors.CYAN}╔══════════════════════════════════════════════╗
{Colors.CYAN}║  FRSANDBOX Client Commands (frsandbox ...)   ║
{Colors.CYAN}╠══════════════════════════════════════════════╣
{Colors.CYAN}║  {Colors.GREEN}exit{Colors.RESET}     - Disconnect from server           {Colors.CYAN}║
{Colors.CYAN}║  {Colors.GREEN}reconnect{Colors.RESET} - Force reconnect                 {Colors.CYAN}║
{Colors.CYAN}║  {Colors.GREEN}clear{Colors.RESET}   - Clear screen                      {Colors.CYAN}║
{Colors.CYAN}║  {Colors.GREEN}history{Colors.RESET} - Show command history              {Colors.CYAN}║
{Colors.CYAN}║  {Colors.GREEN}help{Colors.RESET}    - Show this help                    {Colors.CYAN}║
{Colors.CYAN}╚══════════════════════════════════════════════╝{Colors.RESET}
        """
        print(help_text)
    
    def show_history(self):
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print(f"\n{Colors.YELLOW}📜 Command History:{Colors.RESET}")
                    for i, line in enumerate(lines[-20:], 1):
                        print(f"  {i}. {line.strip()}")
            else:
                print(f"{Colors.YELLOW}No history available{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error reading history: {e}{Colors.RESET}")
    
    def get_input(self, prompt=""):
        if READLINE_AVAILABLE:
            try:
                try:
                    readline.read_history_file(self.history_file)
                except FileNotFoundError:
                    pass
                
                user_input = input(prompt)
                
                if user_input.strip():
                    try:
                        readline.write_history_file(self.history_file)
                    except:
                        pass
                
                return user_input
            except:
                return input(prompt)
        else:
            return input(prompt)
    
    def reconnect(self):
        print(f"\n{Colors.YELLOW}🔄 Attempting to reconnect...{Colors.RESET}")
        
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        
        while self.reconnect_attempts < self.max_reconnect_attempts:
            self.reconnect_attempts += 1
            print(f"{Colors.YELLOW}Attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}{Colors.RESET}")
            
            if self.connect():
                if self.authenticate():
                    print(f"{Colors.GREEN}✅ Reconnected successfully!{Colors.RESET}")
                    return True
            
            time.sleep(3)
        
        print(f"{Colors.RED}❌ Failed to reconnect after {self.max_reconnect_attempts} attempts{Colors.RESET}")
        return False
    
    def reader_thread(self):
        """Поток для чтения данных от сервера - показываем всё"""
        while self.running:
            try:
                if not self.socket:
                    break
                    
                data = self.socket.recv(4096)
                if not data:
                    print(f"\n{Colors.YELLOW}🔌 Connection closed by server{Colors.RESET}")
                    break
                
                text = data.decode('utf-8', errors='ignore')
                
                # Выводим ВСЁ что пришло от сервера
                sys.stdout.write(text)
                sys.stdout.flush()
                    
            except socket.error as e:
                if self.running:
                    print(f"\n{Colors.RED}❌ Connection lost: {e}{Colors.RESET}")
                break
            except Exception as e:
                print(f"\n{Colors.RED}❌ Reader error: {e}{Colors.RESET}")
                break
    
    def writer_thread(self):
        """Поток для отправки команд"""
        while self.running:
            try:
                # Показываем промпт сервера для ввода
                colored_prompt = f"{Colors.GREEN}{self.prompt}{Colors.RESET}"
                
                cmd = self.get_input(colored_prompt)
                
                if cmd is None:
                    break
                
                cmd = cmd.strip()
                if not cmd:
                    continue
                
                # Специальные команды
                if cmd.lower() == "exit":
                    try:
                        self.socket.send(b"exit\n")
                    except:
                        pass
                    break
                elif cmd.lower() == "reconnect":
                    self.reconnect()
                    continue
                elif cmd.lower() == "clear":
                    self.clear_screen()
                    continue
                elif cmd.lower() == "help":
                    self.show_help()
                    continue
                elif cmd.lower() == "history":
                    self.show_history()
                    continue
                
                self.last_command = cmd
                
                try:
                    self.socket.send(cmd.encode() + b"\n")
                except (socket.error, BrokenPipeError) as e:
                    print(f"{Colors.RED}❌ Connection lost, reconnecting...{Colors.RESET}")
                    self.socket = None
                    if self.reconnect():
                        print(f"{Colors.YELLOW}⏳ Retrying last command...{Colors.RESET}")
                        try:
                            self.socket.send(cmd.encode() + b"\n")
                        except:
                            pass
                    continue
                
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}⏹ Interrupted{Colors.RESET}")
                break
            except Exception as e:
                print(f"{Colors.RED}❌ Writer error: {e}{Colors.RESET}")
                break
    
    def run(self):
        self.clear_screen()
        
        print(f"""
{Colors.CYAN}╔════════════════════════════════════════╗
║     FRSANDBOX Client v3.0              ║
║     by @error_kill XDDD                ║
╚════════════════════════════════════════╝{Colors.RESET}
        """)
        
        while self.running:
            if not self.socket:
                if not self.connect():
                    print(f"{Colors.RED}Failed to connect. Retrying in 5 seconds...{Colors.RESET}")
                    time.sleep(5)
                    continue
                
                if not self.authenticate():
                    self.socket.close()
                    self.socket = None
                    time.sleep(3)
                    continue
            
            print(f"\n{Colors.CYAN}{'='*50}")
            print(f"🚀 FRSANDBOX Interactive Shell")
            print(f"   Type 'help' for commands, 'exit' to quit")
            print(f"   Auto-reconnect on disconnect")
            print(f"{'='*50}{Colors.RESET}\n")
            
            reader = threading.Thread(target=self.reader_thread, daemon=True)
            writer = threading.Thread(target=self.writer_thread, daemon=True)
            
            reader.start()
            writer.start()
            
            writer.join()
            
            if self.running:
                print(f"\n{Colors.YELLOW}🔄 Connection lost. Reconnecting...{Colors.RESET}")
                self.socket = None
                if not self.reconnect():
                    print(f"{Colors.RED}❌ Cannot reconnect. Exiting.{Colors.RESET}")
                    break
        
        try:
            if self.socket:
                self.socket.close()
        except:
            pass
        
        print(f"\n{Colors.YELLOW}👋 Disconnected from FRSANDBOX{Colors.RESET}")

def main():
    client = FRSandboxClient()
    
    try:
        client.run()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  Interrupted by user{Colors.RESET}")
    except Exception as e:
        print(f"{Colors.RED}❌ Fatal error: {e}{Colors.RESET}")

if __name__ == "__main__":
    main()
