from flask import Flask
import subprocess
import os

app = Flask(__name__)

@app.route('/start')
def start():
    import subprocess
    result = subprocess.run(['pgrep', '-f', 'launcher.py'], capture_output=True)
    if result.returncode == 0:
        subprocess.run(['pkill', '-f', 'launcher.py'])
        import time
        time.sleep(2)
    env = os.environ.copy()
    env['DISPLAY'] = ':0'
    env['XAUTHORITY'] = '/home/jetiot/.Xauthority'
    subprocess.Popen(
        ['/home/jetiot/.pyenv/versions/3.12.12/bin/python3', 'launcher.py'],
        cwd='/home/jetiot/Downloads/Hazardous Zone',
        env=env
    )
    return 'OK'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8765)
