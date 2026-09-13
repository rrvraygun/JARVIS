"""Unpack checksum-bound crate archives only inside the offline build sandbox."""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tarfile
from pathlib import Path, PurePosixPath

MAX_EXPANDED = 128 * 1024 * 1024


def unpack(
    archives: list[dict[str, str]], destination: Path, *, archive_root: Path = Path("/dependencies")
) -> None:
    destination.mkdir(mode=0o700)
    total = 0
    count = 0
    for crate in archives:
        label = crate["name"] + "-" + crate["version"]
        with (archive_root / (label + ".crate")).open("rb") as stream:
            data = stream.read(8 * 1024 * 1024 + 1)
        if len(data) > 8 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != crate["checksum"]:
            raise ValueError("crate_archive_drift")
        root = destination / label
        root.mkdir(mode=0o700)
        hashes = {}
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive:
                count += 1
                parts = PurePosixPath(member.name).parts
                if (
                    count > 20000
                    or not parts
                    or parts[0] != label
                    or PurePosixPath(member.name).is_absolute()
                    or ".." in parts
                    or not (member.isdir() or member.isfile())
                    or member.size < 0
                    or member.size > 8 * 1024 * 1024
                ):
                    raise ValueError("crate_member_rejected")
                relative = PurePosixPath(*parts[1:])
                output = root / relative
                if member.isdir():
                    output.mkdir(mode=0o700, parents=True, exist_ok=True)
                    continue
                if not parts[1:] or relative.as_posix() == ".cargo-checksum.json":
                    raise ValueError("crate_metadata_collision")
                total += member.size
                if total > MAX_EXPANDED:
                    raise ValueError("crate_expansion_limit")
                member_stream = archive.extractfile(member)
                if member_stream is None:
                    raise ValueError("crate_member_missing")
                content = member_stream.read(member.size + 1)
                if len(content) != member.size:
                    raise ValueError("crate_member_size_mismatch")
                output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                with output.open("xb") as target:
                    target.write(content)
                hashes[relative.as_posix()] = hashlib.sha256(content).hexdigest()
        (root / ".cargo-checksum.json").write_text(
            json.dumps({"package": crate["checksum"], "files": hashes})
        )


if __name__ == "__main__":
    try:
        metadata = json.loads(sys.argv[1])
        if not isinstance(metadata, list) or len(metadata) > 64:
            raise ValueError("crate_count_limit")
        unpack(metadata, Path("/tmp/vendor"))
        if sys.argv[2] != "/usr/bin/cargo":
            raise ValueError("vendor_command_invalid")
        os.execv(
            sys.argv[2],
            [
                sys.argv[2],
                "--config",
                'source.crates-io.replace-with="jarvis-vendor"',
                "--config",
                'source.jarvis-vendor.directory="/tmp/vendor"',
                *sys.argv[3:],
            ],
        )
    except (OSError, ValueError, KeyError, IndexError, tarfile.TarError):
        print("Vendored dependency preparation failed; no command was started.")
        raise SystemExit(78)
