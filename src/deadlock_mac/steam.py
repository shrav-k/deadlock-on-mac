"""Compatibility import; implementation lives in core.steam."""
import sys
from .core import steam as _implementation
sys.modules[__name__] = _implementation
