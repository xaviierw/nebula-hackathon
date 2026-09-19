"""Content hashing -- the identity of an upload.

The hash is the ONLY thing derived from an uploaded file that outlives the
request. The bytes themselves are never written anywhere.
"""

from __future__ import annotations

import hashlib


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()
