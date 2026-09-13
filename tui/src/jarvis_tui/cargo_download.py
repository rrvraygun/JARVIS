"""Single reviewed HTTPS crate request; no redirects, proxies, credentials or retries."""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import ssl
import sys
from pathlib import Path

MAX_ARCHIVE = 8 * 1024 * 1024


def validate(name: str, version: str, checksum: str) -> str:
    if (
        not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?", version)
        or len(version) > 80
        or not re.fullmatch(r"[a-f0-9]{64}", checksum)
    ):
        raise ValueError("crate_identity_invalid")
    return "/crates/" + name + "/" + name + "-" + version + ".crate"


def download(name: str, version: str, checksum: str, destination: Path) -> dict[str, object]:
    route = validate(name, version, checksum)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    connection = http.client.HTTPSConnection(
        "static.crates.io", timeout=10, context=ssl.create_default_context()
    )
    try:
        connection.request(
            "GET",
            route,
            headers={"Accept-Encoding": "identity", "User-Agent": "JARVIS-reviewed-download/1"},
        )
        response = connection.getresponse()
        if (
            response.status != 200
            or response.getheader("Content-Encoding", "identity") != "identity"
        ):
            raise ValueError("crate_response_rejected")
        length = response.getheader("Content-Length")
        if length is not None and not 0 < int(length) <= MAX_ARCHIVE:
            raise ValueError("crate_archive_limit")
        digest = hashlib.sha256()
        size = 0
        with os.fdopen(os.dup(descriptor), "wb") as stream:
            while True:
                data = response.read(65536)
                if not data:
                    break
                size += len(data)
                if size > MAX_ARCHIVE:
                    raise ValueError("crate_archive_limit")
                digest.update(data)
                stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if digest.hexdigest() != checksum:
            raise ValueError("crate_checksum_mismatch")
        return {"status": "downloaded", "sha256": checksum, "bytes": size, "attempts": 1}
    finally:
        connection.close()
        os.close(descriptor)


if __name__ == "__main__":
    try:
        if len(sys.argv) != 5:
            raise ValueError("crate_arguments_invalid")
        print(json.dumps(download(sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4]))))
    except (OSError, ValueError, http.client.HTTPException) as exc:
        print(
            json.dumps(
                {"status": "download_failed_or_partial", "error": type(exc).__name__, "attempts": 1}
            )
        )
        raise SystemExit(1)
