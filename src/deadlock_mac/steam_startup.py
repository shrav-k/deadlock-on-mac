"""Classify a failed launch's own log, without treating a warning as a dead game.

Steam can recover after its main-loop warning. Only use this diagnostic after
the existing process-based startup deadline, never to kill or restart a client.
"""
import os

from .storage import ManagerError, no_symlinks

MAX_BYTES = 256 * 1024


def failure_summary(path):
    try:
        fd = os.open(no_symlinks(path), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, 'rb') as stream:
            stream.seek(max(0, os.fstat(stream.fileno()).st_size - MAX_BYTES))
            text = stream.read(MAX_BYTES).decode('utf-8', errors='replace')
    except (ManagerError, OSError, ValueError):
        return None
    # Never include raw Steam output, account names or unrelated historical logs.
    if ('CSteamEngine::BMainLoop appears to have stalled' in text
            or 'fatal stalled cross-thread pipe' in text):
        return ('Deadlock did not start: Steam reported a stalled main loop before game startup. '
                'Use Exit Windows Steam, then retry after it closes. If shutdown also stalls, '
                'keep the private launch log for diagnosis. Display settings were left unchanged.')
    return None
