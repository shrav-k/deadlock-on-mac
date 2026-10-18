"""Compatibility import; implementation lives in core.wine."""
import sys
from .core import wine as _implementation
sys.modules[__name__] = _implementation
