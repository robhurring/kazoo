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


def _looks_like_path(value: str) -> bool:
    """A `--db` value that looks like a path to a .graph file rather than a bare name."""
    return ("/" in value) or value.endswith(DB_SUFFIX)


def _resolve_name(name: str | None) -> str:
    """Validate a bare DB name. Callers pre-filter path-style values."""
    resolved = name or os.environ.get("KAZOO_DB") or DEFAULT_DB_NAME
    if resolved in {"", ".", ".."}:
        raise ValueError(f"invalid db name: {resolved!r}")
    return resolved


def db_path(name: str | None = None) -> Path:
    """Resolve filesystem path for a DB.

    If `name` looks like a path (contains '/', ends in .graph, or starts with
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




def rename_db(old: str, new: str) -> tuple[Path, Path]:
    src = db_path(old)
    dest = db_path(new)
    if not src.exists():
        raise FileNotFoundError(f"database does not exist: {src}")
    if dest.exists():
        raise FileExistsError(f"target database already exists: {dest}")
    src.rename(dest)
    return src, dest


_GZIP_MAGIC = b"\x1f\x8b"


class _PrefixedStream:
    """Read-only stream that yields `prefix` first, then delegates to `inner`."""

    def __init__(self, prefix: bytes, inner):
        self._prefix = prefix
        self._inner = inner

    def read(self, n: int = -1) -> bytes:
        if self._prefix:
            if n < 0 or n >= len(self._prefix):
                head = self._prefix
                self._prefix = b""
                tail = self._inner.read(-1 if n < 0 else n - len(head))
                return head + (tail or b"")
            out = self._prefix[:n]
            self._prefix = self._prefix[n:]
            return out
        return self._inner.read(n)


def _maybe_gunzip(stream):
    """If `stream` starts with gzip magic bytes, transparently decompress."""
    head = stream.read(2)
    if not head:
        return stream
    rejoined = _PrefixedStream(head, stream)
    if head == _GZIP_MAGIC:
        import gzip
        return gzip.GzipFile(fileobj=rejoined)
    return rejoined


def export_to_stream_gzipped(name: str | None, stream) -> Path:
    """Stream the DB file's bytes through gzip into the given binary stream."""
    import gzip

    src = db_path(name)
    if not src.exists():
        raise FileNotFoundError(f"database does not exist: {src}")
    with src.open("rb") as f, gzip.GzipFile(fileobj=stream, mode="wb", compresslevel=6) as gz:
        shutil.copyfileobj(f, gz)
    return src


def import_from_stream(name: str | None, stream) -> Path:
    """Replace the named DB with bytes from a binary stream.

    Auto-detects gzipped input via magic bytes. Always replaces — the .grz
    file is the source of truth. Refuses zero-byte input so we never produce
    an empty/corrupt DB.
    """
    dest = db_path(name)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    if tmp.exists():
        tmp.unlink()
    bytes_written = 0
    source = _maybe_gunzip(stream)
    try:
        with tmp.open("wb") as f:
            while True:
                chunk = source.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)
        if bytes_written == 0:
            raise ValueError("no bytes on stdin — refusing to create an empty DB")
        tmp.replace(dest)  # atomic on POSIX
    finally:
        if tmp.exists():
            tmp.unlink()
    return dest
