"""Run the owned grid until Escape/Close, manager cancellation, or parent exit.

The helper receives a private stdin pipe. Closing that pipe requests a normal
window close; it cannot target Steam, the game, or another Wine application.
"""
import queue
import subprocess
import threading
import time

from .diagnostic_control import cancellation
from .storage import ManagerError


def run(command, *, env, cwd, stopped, report=print, capture=lambda line: None):
    if stopped.is_set():
        raise ManagerError('Display test cancelled before startup.')
    process = subprocess.Popen(command + ['--control-stdin'], env=env, cwd=cwd,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, bufsize=1)
    lines = queue.Queue()

    def read():
        try:
            for line in process.stdout:
                lines.put(line)
        finally:
            lines.put(None)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    output, closed, deadline = [], False, None
    try:
        while True:
            if stopped.is_set() and not closed:
                process.stdin.close()
                closed = True
                deadline = time.monotonic() + 20
                report('Closing the owned test grid…')
            if deadline is not None and time.monotonic() >= deadline:
                # Only our diagnostic child, never wineserver or another app.
                process.kill()
                raise ManagerError('Display diagnostic did not acknowledge close within 20 seconds; its helper was stopped.')
            try:
                line = lines.get(timeout=0.1)
            except queue.Empty:
                continue
            if line is None:
                break
            output.append(line)
            capture(line)
            if line.startswith(('test_window=', 'pointer_click=', 'window_active=', 'test_window_closed=', 'control_check=')):
                report(line.rstrip())
        process.wait(timeout=20)
        return subprocess.CompletedProcess(command, process.returncode, ''.join(output), '')
    finally:
        if not closed:
            process.stdin.close()
        if process.poll() is None:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        reader.join(timeout=2)
        process.stdout.close()
