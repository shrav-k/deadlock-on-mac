"""Cooperative diagnostic cancellation, without signalling a process group."""
from contextlib import contextmanager
import os
import select
import signal
import threading


@contextmanager
def cancellation(control=None):
    stopped = threading.Event()
    finished = threading.Event()
    previous = {sig: signal.signal(sig, lambda *_: stopped.set())
                for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}

    def watch():
        # Only the GUI's explicit private pipe is monitored. Ordinary CLI stdin
        # (including /dev/null) must never silently cancel a diagnostic.
        while not finished.is_set():
            if select.select([control], [], [], 0.1)[0]:
                if not os.read(control.fileno(), 64):
                    stopped.set()
                    return

    reader = threading.Thread(target=watch, daemon=True) if control is not None else None
    try:
        if reader:
            # Handle an already-closed parent before starting any child work.
            if select.select([control], [], [], 0)[0] and not os.read(control.fileno(), 64):
                stopped.set()
            else:
                reader.start()
        yield stopped
    finally:
        finished.set()
        if reader and reader.ident is not None:
            reader.join(timeout=1)
        for sig, handler in previous.items():
            signal.signal(sig, handler)
