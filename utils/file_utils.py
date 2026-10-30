"""File-writing helpers shared across the project."""
import json
import os
import uuid
from pathlib import Path
from typing import Any


def write_json_atomic(path: str | os.PathLike, data: Any, *, indent: int = 2) -> None:
    """Write *data* as UTF-8 JSON to *path* atomically.

    The JSON is written to a uniquely named temp file next to the target and
    then renamed over it, so a crash mid-write can never truncate the existing
    file and concurrent writers never share a temp file. Serialization errors
    are raised before the target is touched.
    """
    target = Path(path)
    payload = json.dumps(data, indent=indent, ensure_ascii=False)
    tmp = target.with_name(f"{target.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
