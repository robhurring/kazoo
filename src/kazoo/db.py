from __future__ import annotations

import os
import shutil
from pathlib import Path

APP_NAME = "kazoo"
DEFAULT_DB_NAME = "default"
DB_SUFFIX = ".graph"


def data_root() -> Path:
    """Root directory holding all kazoo-managed databases.

    Strict XDG Base Directory layout on every OS: honors $XDG_DATA_HOME,
    falls back to ~/.local/share/kazoo (also on macOS — not ~/Library/...).
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_NAME


def _resolve_name(name: str | None) -> str:
    resolved = name or os.environ.get("KAZOO_DB") or DEFAULT_DB_NAME
    if "/" in resolved or resolved in {"", ".", ".."}:
        raise ValueError(f"invalid db name: {resolved!r}")
    return resolved


def db_path(name: str | None = None) -> Path:
    """Resolve filesystem path (a single file) for a named DB."""
    return data_root() / f"{_resolve_name(name)}{DB_SUFFIX}"


def list_dbs() -> list[str]:
    root = data_root()
    if not root.exists():
        return []
    return sorted(p.stem for p in root.iterdir() if p.is_file() and p.suffix == DB_SUFFIX)


def open_db(name: str | None = None, *, create: bool = True):
    import kuzu  # lazy: kuzu is a large native module; avoid importing for cheap commands

    path = db_path(name)
    if not path.exists():
        if not create:
            raise FileNotFoundError(f"database does not exist: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
    database = kuzu.Database(str(path))
    return kuzu.Connection(database)


def remove_db(name: str | None = None) -> Path:
    path = db_path(name)
    if not path.exists():
        raise FileNotFoundError(f"database does not exist: {path}")
    path.unlink()
    return path


def backup_db(name: str | None, dest: Path) -> Path:
    src = db_path(name)
    if not src.exists():
        raise FileNotFoundError(f"database does not exist: {src}")
    if dest.is_dir():
        dest = dest / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return dest


def rename_db(old: str, new: str) -> tuple[Path, Path]:
    src = db_path(old)
    dest = db_path(new)
    if not src.exists():
        raise FileNotFoundError(f"database does not exist: {src}")
    if dest.exists():
        raise FileExistsError(f"target database already exists: {dest}")
    src.rename(dest)
    return src, dest


def restore_db(src: Path, as_name: str | None) -> Path:
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"backup file not found: {src}")
    dest = db_path(as_name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        raise FileExistsError(f"target database already exists: {dest}")
    shutil.copy2(src, dest)
    return dest
