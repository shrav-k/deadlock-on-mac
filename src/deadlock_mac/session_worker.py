"""Private isolated entry point, shared by source and bundled-Python installs."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from deadlock_mac.game_session import worker

if __name__ == "__main__":
    workspace, profile, tool, response, log = sys.argv[1:]
    raise SystemExit(worker(Path(workspace), profile, Path(tool) if tool else None,
                            Path(response), Path(log)))
