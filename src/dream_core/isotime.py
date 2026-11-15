"""ISO-8601 timestamp parsing that behaves the same on Python 3.10 and 3.11+.

Several runners write timestamps with ``time.strftime("%Y-%m-%dT%H:%M:%S%z")``, which
gives a UTC offset without a colon (``-0500``). Python 3.11+ ``datetime.fromisoformat``
accepts that; Python 3.10's only accepts ``-05:00`` and has no ``Z`` suffix support.
Archived run data contains the colon-less form, so readers must accept it.

On Python 3.11+ this is exactly ``datetime.fromisoformat``. On 3.10 it first rewrites a
trailing ``±HHMM`` / ``±HHMMSS`` offset to ``±HH:MM`` / ``±HH:MM:SS`` and a trailing ``Z``
to ``+00:00``; everything else is passed through unchanged, so invalid input still raises.
"""
import re
import sys
from datetime import datetime

_OFFSET = re.compile(r"([+-])(\d{2})(\d{2})(\d{2})?$")


def fromisoformat(value):
    """Parse ``value`` like Python 3.11+ ``datetime.fromisoformat`` for the formats DREAM writes."""
    if sys.version_info >= (3, 11) or not isinstance(value, str):
        return datetime.fromisoformat(value)
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    if "T" in text or " " in text:  # only touch an offset that follows a time part
        text = _OFFSET.sub(lambda m: f"{m[1]}{m[2]}:{m[3]}" + (f":{m[4]}" if m[4] else ""), text)
    return datetime.fromisoformat(text)
