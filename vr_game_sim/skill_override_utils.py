from __future__ import annotations

import math
from enum import Enum
from typing import Any


def _values_equal(a: Any, b: Any) -> bool:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(float(a), float(b), rel_tol=1e-9, abs_tol=1e-9)
    return a == b


def sanitize_for_json(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: sanitize_for_json(sub_val) for key, sub_val in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_json(item) for item in value]
    return value


def diff_structures(base: Any, modified: Any) -> Any | None:
    if isinstance(base, dict) and isinstance(modified, dict):
        diff: dict[Any, Any] = {}
        for key, mod_value in modified.items():
            if key not in base:
                diff[key] = sanitize_for_json(mod_value)
                continue
            sub_diff = diff_structures(base[key], mod_value)
            if sub_diff is not None:
                diff[key] = sanitize_for_json(sub_diff)
        return diff or None
    if isinstance(base, list) and isinstance(modified, list):
        diff_map: dict[int, Any] = {}
        max_len = max(len(base), len(modified))
        for index in range(max_len):
            in_modified = index < len(modified)
            in_base = index < len(base)
            if not in_modified:
                continue
            mod_item = modified[index]
            if in_base:
                sub_diff = diff_structures(base[index], mod_item)
                if sub_diff is not None:
                    diff_map[index] = sanitize_for_json(sub_diff)
            else:
                diff_map[index] = sanitize_for_json(mod_item)
        return diff_map or None
    if _values_equal(base, modified):
        return None
    return sanitize_for_json(modified)
