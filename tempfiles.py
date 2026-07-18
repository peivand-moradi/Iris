import atexit
import shutil
import tempfile
from pathlib import Path

TEMP_DIR = Path(tempfile.gettempdir()) / "iris"
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def new_temp_path(suffix: str) -> Path:
    """Reserve a new temp file path inside TEMP_DIR. Caller is responsible for writing to it."""
    fd, name = tempfile.mkstemp(suffix=suffix, dir=TEMP_DIR)
    import os

    os.close(fd)
    return Path(name)


def cleanup(path: Path | None) -> None:
    """Delete a path only if it lives inside our managed temp directory.

    Sample assets under samples/ are never inside TEMP_DIR, so this is safe
    to call unconditionally on every provider-returned path.
    """
    if path is None:
        return
    try:
        resolved = path.resolve()
        if TEMP_DIR.resolve() in resolved.parents:
            resolved.unlink(missing_ok=True)
    except OSError:
        pass


def cleanup_all() -> None:
    shutil.rmtree(TEMP_DIR, ignore_errors=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)


atexit.register(cleanup_all)
