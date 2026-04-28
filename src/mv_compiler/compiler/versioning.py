import re
from typing import Optional, Tuple


VERSIONED_NAME_PATTERN = re.compile(r"(.+)__(\d+)__$")
SYNC_FUNCTION_PATTERN = re.compile(r"_?sync_from_v(\d+)_to_v(\d+)")


def parse_versioned_name(name: str) -> Tuple[Optional[str], Optional[str]]:
    match = VERSIONED_NAME_PATTERN.match(name)
    if match:
        return match.group(1), match.group(2)
    return None, None


def parse_sync_function_name(name: str) -> Tuple[Optional[int], Optional[int]]:
    match = SYNC_FUNCTION_PATTERN.match(name)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None
