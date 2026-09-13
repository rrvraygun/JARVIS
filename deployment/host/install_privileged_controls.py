#!/usr/bin/python3 -I
"""Install only pinned JARVIS helper bytes; no boot/package operation or grant."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
from pathlib import Path

BUNDLE = Path(__file__).resolve().parents[2]
STATE = Path("/var/lib/jarvis/privileged-control")
FILES = (
    (
        "vm-lab/scripts/jarvis_privileged_control.py",
        "/usr/libexec/jarvis_privileged_control.py",
        0o644,
        "7eae720d37a6409d3d5cedb483e24b5b9ecd33016acf6e540830849e49959095",
    ),
    (
        "vm-lab/scripts/jarvis_boot_control.py",
        "/usr/libexec/jarvis-boot-control",
        0o755,
        "077df94b7a06ab4a9cd44e5628c132cddb12feeda8a315bf873fbfdf33458c47",
    ),
    (
        "vm-lab/scripts/jarvis_update_control.py",
        "/usr/libexec/jarvis-update-control",
        0o755,
        "794c28ad1fd0910500c2891097dbc913d909ac35f32e8ed69ba8efb9b4e521c9",
    ),
    (
        "deployment/host/org.jarvis.boot-control.policy",
        "/usr/share/polkit-1/actions/org.jarvis.boot-control.policy",
        0o644,
        "72ba833402ae0d4a66a3ba902f4f9f99e5297578e35de2d60933cb7f17262818",
    ),
    (
        "deployment/host/org.jarvis.update-control.policy",
        "/usr/share/polkit-1/actions/org.jarvis.update-control.policy",
        0o644,
        "4aedc91926d2c642f4b041865a9776beddb7d76ecebeba7fb97c0edb0f722297",
    ),
)


def safe_directory(path: Path) -> None:
    for part in [*reversed(path.parents), path]:
        info = part.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise ValueError("unsafe directory: " + str(part))


def read_pinned(path: Path, expected: str, installed: bool = False) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1048576:
            raise ValueError("unsafe file")
        if installed and (info.st_uid != 0 or info.st_mode & 0o022):
            raise ValueError("unsafe installed owner/mode")
        with os.fdopen(os.dup(fd), "rb") as stream:
            data = stream.read(1048577)
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError("digest mismatch: " + str(path))
        return data
    finally:
        os.close(fd)


def verify() -> None:
    for _, destination, mode, expected in FILES:
        path = Path(destination)
        safe_directory(path.parent)
        read_pinned(path, expected, installed=True)
        if stat.S_IMODE(path.lstat().st_mode) != mode:
            raise ValueError("installed mode mismatch")


def install(uid: int) -> None:
    # Read/hash every source before any host mutation. Existing installations
    # are never overwritten; upgrades need a separate reviewed plan.
    prepared = [(Path(dst), mode, read_pinned(BUNDLE / src, sha)) for src, dst, mode, sha in FILES]
    for path, _, _ in prepared:
        safe_directory(path.parent)
        if os.path.lexists(path):
            raise ValueError("destination already exists: " + str(path))
    safe_directory(STATE.parent)
    if os.path.lexists(STATE):
        raise ValueError("state already exists; review required")
    # Publish helpers first, Polkit policies last. No approval is created.
    created = []
    directories = []
    receipt = {
        "status": "installed",
        "uid": uid,
        "files": [{"path": dst, "sha256": sha} for _, dst, _, sha in FILES],
        "operation_approvals_created": 0,
        "boot_or_package_commands_run": 0,
    }
    try:
        for path in [
            STATE,
            *(
                STATE / name
                for name in ("approvals", "reservations", "results", "transactions", "backups")
            ),
            STATE / "approvals" / str(uid),
        ]:
            path.mkdir(mode=0o700)
            directories.append(path)
        for path, mode, data in prepared:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
            created.append(path)
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fchmod(stream.fileno(), mode)
                os.fsync(stream.fileno())
        verify()
        receipt_path = STATE / "installation.json"
        with receipt_path.open("x") as stream:
            created.append(receipt_path)
            json.dump(receipt, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Revert only objects created by this invocation. Nonempty directories
        # are preserved; failure to clean is explicitly a partial installation.
        cleanup_failed = []
        for path in reversed(created):
            try:
                path.unlink()
            except OSError:
                cleanup_failed.append(str(path))
        for path in reversed(directories):
            try:
                path.rmdir()
            except OSError:
                cleanup_failed.append(str(path))
        if cleanup_failed:
            print(
                json.dumps(
                    {"status": "partial_installation_requires_review", "paths": cleanup_failed}
                )
            )
        raise
    print(json.dumps(receipt, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--uid", type=int, default=1000)
    args = parser.parse_args()
    if os.geteuid() != 0 or args.uid != 1000:
        raise SystemExit("Root required; reviewed workstation uid is 1000")
    if args.install:
        install(args.uid)
    else:
        verify()
        print('{"status":"installed_files_verified"}')


if __name__ == "__main__":
    main()
