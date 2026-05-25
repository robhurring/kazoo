from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "kazoo"
DEFAULT_DB_NAME = "default"
DB_SUFFIX = ".kuzu"


def data_root() -> Path:
    """Root directory holding all kazoo-managed databases.

    Strict XDG Base Directory layout on every OS: honors $XDG_DATA_HOME,
    falls back to ~/.local/share/kazoo (also on macOS — not ~/Library/...).
    """
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    return base / APP_NAME


def _looks_like_path(value: str) -> bool:
    """A `--db` value that looks like a path to a .kuzu file rather than a bare name."""
    return ("/" in value) or value.endswith(DB_SUFFIX)


def _resolve_name(name: str | None) -> str:
    """Validate a bare DB name. Callers pre-filter path-style values."""
    resolved = name or os.environ.get("KAZOO_DB") or DEFAULT_DB_NAME
    if resolved in {"", ".", ".."}:
        raise ValueError(f"invalid db name: {resolved!r}")
    return resolved


def db_path(name: str | None = None) -> Path:
    """Resolve filesystem path for a DB.

    If `name` looks like a path (contains '/', ends in .kuzu, or starts with
    '~' or '.'), it's used as a file path directly. Otherwise it's resolved
    as a bare name under the XDG data dir.
    """
    candidate = name or os.environ.get("KAZOO_DB") or DEFAULT_DB_NAME
    if _looks_like_path(candidate):
        return Path(candidate).expanduser()
    return data_root() / f"{_resolve_name(candidate)}{DB_SUFFIX}"


def list_dbs() -> list[str]:
    root = data_root()
    if not root.exists():
        return []
    return sorted(p.stem for p in root.iterdir() if p.is_file() and p.suffix == DB_SUFFIX)


def open_db(name: str | None = None, *, create: bool = False):
    """Open a Kuzu Connection for the named DB.

    Auto-creates the bare default DB (no `--db` and no `$KAZOO_DB`) so
    `kazoo query ...` Just Works out of the box. Any explicit name —
    either `--db <name>` or `$KAZOO_DB` — must already exist; this
    keeps typos from silently producing an empty DB. Pass `create=True`
    for `db init`.
    """
    import kuzu  # lazy: kuzu is a large native module; avoid importing for cheap commands

    path = db_path(name)
    auto_default = name is None and os.environ.get("KAZOO_DB") is None
    if not path.exists():
        if not (create or auto_default):
            hint = f"--db {name} " if name else ""
            raise FileNotFoundError(f"database does not exist: {path} (run `kazoo {hint}db init`)")
        path.parent.mkdir(parents=True, exist_ok=True)
    database = kuzu.Database(str(path))
    return kuzu.Connection(database)


def remove_db(name: str | None = None) -> Path:
    path = db_path(name)
    if not path.exists():
        raise FileNotFoundError(f"database does not exist: {path}")
    path.unlink()
    return path


EXPLORER_IMAGE = "kuzudb/explorer:latest"


def explorer_command(
    name: str | None = None, *, port: int = 8000, image: str = EXPLORER_IMAGE
) -> list[str]:
    """Build the `docker run` argv that serves the named DB in Kuzu Explorer.

    Kuzu Explorer mounts the directory holding the database at /database and
    selects the file via $KUZU_FILE, so we mount the resolved parent and pass
    the bare filename. The host `port` maps to the container's 8000.
    """
    path = db_path(name)
    if not path.exists():
        raise FileNotFoundError(f"database does not exist: {path}")
    parent = str(path.parent.resolve())
    return [
        "docker", "run", "--rm",
        "-p", f"{port}:8000",
        "-v", f"{parent}:/database",
        "-e", f"KUZU_FILE={path.name}",
        image,
    ]
