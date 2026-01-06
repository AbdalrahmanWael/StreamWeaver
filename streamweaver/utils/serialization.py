"""
Utility functions for serialization and data handling.
"""

import json
from typing import Any, Dict


def safe_serialize(obj: Any) -> Any:
    """Safely serialize objects for JSON"""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [safe_serialize(item) for item in obj]
    elif isinstance(obj, dict):
        return {safe_serialize(k): safe_serialize(v) for k, v in obj.items()}
    elif hasattr(obj, '__dict__'):
        return safe_serialize(obj.__dict__)
    else:
        return str(obj)


def clean_event_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean event data for safe serialization"""
    cleaned = {}
    for key, value in data.items():
        try:
            json.dumps(value)
            cleaned[key] = value
        except (TypeError, ValueError):
            cleaned[key] = str(value)
    return cleaned
