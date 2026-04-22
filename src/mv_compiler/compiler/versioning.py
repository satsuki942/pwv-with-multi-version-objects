import re
from pathlib import Path
from typing import Optional, Tuple


VERSIONED_NAME_PATTERN = re.compile(r"(.+)__(\d+)__$")
VERSIONED_MODULE_FILENAME_PATTERN = re.compile(r"(.+)__(\d+)__\.py$")
SYNC_MODULE_FILENAME_PATTERN = re.compile(r"(.+)_sync\.py$")
SYNC_FUNCTION_PATTERN = re.compile(r"_?sync_from_v(\d+)_to_v(\d+)")


def parse_versioned_name(name: str) -> Tuple[Optional[str], Optional[str]]:
    match = VERSIONED_NAME_PATTERN.match(name)
    if match:
        return match.group(1), match.group(2)
    return None, None


def parse_versioned_module_filename(filename: str | Path) -> Tuple[Optional[str], Optional[int]]:
    match = VERSIONED_MODULE_FILENAME_PATTERN.match(Path(filename).name)
    if match:
        return match.group(1), int(match.group(2))
    return None, None


def parse_sync_module_filename(filename: str | Path) -> Optional[str]:
    match = SYNC_MODULE_FILENAME_PATTERN.match(Path(filename).name)
    if match:
        return match.group(1)
    return None


def parse_sync_function_name(name: str) -> Tuple[Optional[int], Optional[int]]:
    match = SYNC_FUNCTION_PATTERN.match(name)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None
