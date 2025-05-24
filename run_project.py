import os
import sys
import webbrowser
import subprocess
import time
from threading import Timer

def run_flask_app():
    try:
        flask_process = subprocess.Popen(
            ['python', 'server/app.py'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        time.sleep(2)  # Allow server some time to start
        Timer(1, lambda: webbrowser.open('http://localhost:5000')).start()

        # Optionally: Stream output to console
        for line in flask_process.stdout:
            print(line.decode(), end='')

        flask_process.wait()
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    run_flask_app()
