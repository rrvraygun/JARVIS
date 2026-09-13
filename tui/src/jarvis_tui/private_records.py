"""Owner-only, bounded operational records with immutable reservations."""

from __future__ import annotations

import json
import os
import re
import stat
from pathlib import Path
from typing import Any

NAME = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$")


def directory(path: Path, *, create: bool = True) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("record_root_invalid")
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(part, mode=0o700, dir_fd=fd)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise ValueError("record_root_not_private")
        return fd
    except BaseException:
        os.close(fd)
        raise


def write_once(root: Path, name: str, value: dict[str, Any], limit: int = 1_048_576) -> None:
    if not NAME.fullmatch(name):
        raise ValueError("record_name_invalid")
    data = json.dumps(value, sort_keys=True, ensure_ascii=True).encode()
    if len(data) > limit:
        raise ValueError("record_oversized")
    parent = directory(root)
    try:
        fd = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent
        )
        try:
            with os.fdopen(fd, "wb", closefd=False) as stream:
                stream.write(data)
                stream.flush()
                os.fsync(fd)
        finally:
            os.close(fd)
        os.fsync(parent)
    finally:
        os.close(parent)


def read(root: Path, name: str, limit: int = 1_048_576) -> dict[str, Any]:
    if not NAME.fullmatch(name):
        raise ValueError("record_name_invalid")
    parent = directory(root, create=False)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.geteuid()
                or info.st_mode & 0o077
                or info.st_nlink != 1
                or info.st_size > limit
            ):
                raise ValueError("record_unsafe")
            data = os.read(fd, limit + 1)
        finally:
            os.close(fd)
    finally:
        os.close(parent)
    if len(data) > limit:
        raise ValueError("record_oversized")
    value = json.loads(data)
    if not isinstance(value, dict):
        raise ValueError("record_invalid")
    return value
