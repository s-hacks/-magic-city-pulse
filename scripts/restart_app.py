"""Serialize restarts, stop only this project's server, and verify readiness."""
import fcntl
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def listeners(port):
    result = subprocess.run(['lsof', '-nP', '-t', '-iTCP:' + str(port), '-sTCP:LISTEN'], capture_output=True, text=True)
    return {int(pid) for pid in result.stdout.split() if pid.isdigit()}


def is_project_server(pid):
    cwd = subprocess.run(['lsof', '-a', '-p', str(pid), '-d', 'cwd', '-Fn'], capture_output=True, text=True).stdout
    command = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True).stdout
    return 'n' + str(ROOT) + '\n' in cwd and 'app.py' in command


def port_available(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def stop_existing(port):
    pids = listeners(port)
    for pid in pids:
        if not is_project_server(pid):
            raise RuntimeError(f'Port {port} belongs to another application (PID {pid}); leaving it running.')
    for pid in pids:
        print(f'Stopping existing Magic City Pulse server ({pid})…', flush=True)
        try: os.kill(pid, signal.SIGTERM)
        except ProcessLookupError: pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        # Wait for the socket, rather than a potentially lingering zombie process.
        if not listeners(port) and port_available(port): return
        time.sleep(.1)
    for pid in pids & listeners(port):
        if is_project_server(pid):
            try: os.kill(pid, signal.SIGKILL)
            except ProcessLookupError: pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not listeners(port) and port_available(port): return
        time.sleep(.1)
    raise RuntimeError(f'Port {port} is still busy. No second server was started.')


def main():
    os.chdir(ROOT)
    sys.path.insert(0,str(ROOT))
    from config import load_env
    load_env()
    port = int(os.getenv('PORT', '8000'))
    # Held only during restart/readiness, so a later restart can stop the server.
    with (ROOT / '.restart.lock').open('a') as lock:
        try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print('A Magic City Pulse restart is already in progress. Keeping that launch.', flush=True)
            return 0
        try: stop_existing(port)
        except RuntimeError as exc:
            print(str(exc),flush=True)
            return 1
        print('Starting Magic City Pulse…', flush=True)
        process = subprocess.Popen([sys.executable, str(ROOT / 'app.py')], cwd=ROOT)
        deadline = time.monotonic() + 12
        ready = False
        while time.monotonic() < deadline:
            if process.poll() is not None:
                print('The app exited before it was ready.',flush=True)
                return process.returncode or 1
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/status',timeout=1) as response:
                    ready = response.status == 200
                if ready: break
            except OSError: pass
            time.sleep(.15)
        if not ready:
            process.terminate()
            process.wait()
            print('The app did not become ready; the launch was stopped.',flush=True)
            return 1
        from scripts.build_dataset import atomic_json, now
        atomic_json(ROOT/'data'/'server_status.json',{'ready':True,'port':port,'pid':process.pid,'checked_at':now()})
        print(f'Ready: http://127.0.0.1:{port}', flush=True)
    try: return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        process.wait()
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
