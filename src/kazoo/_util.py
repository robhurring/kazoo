from __future__ import annotations

import re

NODE_TYPE = "NODE"
REL_TYPE = "REL"

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def valid_ident(name: str, kind: str = "identifier") -> str:
    if not _IDENT_RE.match(name):
        raise ValueError(f"invalid {kind}: {name!r}")
    return name


def is_ident(name: str) -> bool:
    return bool(_IDENT_RE.match(name))
