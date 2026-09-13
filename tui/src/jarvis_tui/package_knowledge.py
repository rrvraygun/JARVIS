"""Persistent, provenance-aware package catalog for host inspection."""

from __future__ import annotations

import datetime as dt
import gzip
import hashlib
import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .package_inventory import PackageRecord, RepositoryPackageRecord

MAX_CACHE_BYTES = 64 * 1024 * 1024
QUERY_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "available",
        "cached",
        "catalog",
        "check",
        "find",
        "for",
        "from",
        "how",
        "i",
        "install",
        "is",
        "it",
        "list",
        "management",
        "me",
        "my",
        "of",
        "on",
        "package",
        "packages",
        "please",
        "should",
        "search",
        "show",
        "the",
        "to",
        "use",
        "which",
        "with",
        "related",
    }
)
PACKAGE_QUERY_ALIASES = {
    # Fedora uses `golang` for the distribution Go toolchain. A bare `go`
    # query otherwise ranks unrelated go-* utilities and RPM macro packages.
    "go": ("golang",),
    # Common Fedora roots for energy/power-management catalog searches. These
    # are search hints, not a recommendation or installation decision.
    "energy": ("power-profiles-daemon", "powertop", "tlp", "tuned"),
    "management": ("power-profiles-daemon", "powertop", "tlp", "tuned"),
}


def package_context(
    payload: dict[str, Any], query: str, limit: int = 24
) -> tuple[dict[str, Any], ...]:
    """Return ranked records with bounded, clearly-labelled local alternatives.

    RPM conflict metadata is authoritative only when queried for a concrete
    package. These same-purpose entries are therefore an inference based on
    catalog classification, not a claim that the packages conflict.
    """
    records = search_catalog(payload, query, limit=limit)
    installed = [item for item in payload.get("records", []) if item.get("state") == "installed"]
    enriched: list[dict[str, Any]] = []
    for item in records:
        value = dict(item)
        alternatives = [
            candidate["name"]
            for candidate in installed
            if candidate.get("name") != item.get("name")
            and candidate.get("purpose") == item.get("purpose")
            and candidate.get("category") == item.get("category")
        ]
        value["installed_same_purpose"] = sorted(set(alternatives), key=str.casefold)[:8]
        value["relationship_evidence"] = "inferred:catalog-category-and-purpose"
        value["documentation"] = {
            "packaged_docs": item.get("state") == "installed",
            "official_source_status": "not_collected",
            "network_required_for_refresh": True,
        }
        enriched.append(value)
    return tuple(enriched)


def _record(item: PackageRecord | RepositoryPackageRecord, state: str) -> dict[str, Any]:
    value = {
        "name": item.name,
        "version": item.version,
        "release": item.release,
        "arch": item.arch,
        "vendor": item.vendor,
        "summary": item.summary,
        "category": item.category,
        "purpose": item.purpose,
        "state": state,
    }
    if isinstance(item, PackageRecord):
        value["origin"] = item.origin
        value["nevra"] = item.nevra
    else:
        value.update(
            {
                "epoch": item.epoch,
                "repository": item.repository,
                "license": item.license,
                "origin": item.repository,
                "nevra": item.nevra,
                "evidence": item.evidence,
            }
        )
    return value


def cache_path(bundle_root: Path) -> Path:
    return bundle_root / "runtime/knowledge/package-catalog.json.gz"


def write_catalog(
    bundle_root: Path,
    installed: Iterable[PackageRecord],
    available: Iterable[RepositoryPackageRecord],
) -> dict[str, Any]:
    records = [_record(item, "installed") for item in installed]
    records.extend(_record(item, "available") for item in available)
    records.sort(
        key=lambda item: (
            item["name"].casefold(),
            item["arch"],
            item["version"],
            item["state"],
        )
    )
    payload = {
        "schema_version": 2,
        "collected_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "sources": ["rpmdb", "dnf-cacheonly-repoquery"],
        "installed_count": sum(item["state"] == "installed" for item in records),
        "available_count": sum(item["state"] == "available" for item in records),
        "documentation_policy": {
            "packaged_docs": "available on demand for installed RPMs",
            "official_source_refresh": "requires explicit network approval",
        },
        "records": records,
    }
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    payload["content_hash"] = hashlib.sha256(encoded).hexdigest()
    target = cache_path(bundle_root)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_suffix(".tmp")
    with gzip.open(temporary, "wb", compresslevel=6) as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode())
    os.replace(temporary, target)
    target.chmod(0o600)
    return {
        key: payload[key]
        for key in (
            "collected_at",
            "installed_count",
            "available_count",
            "content_hash",
        )
    }


def read_catalog(bundle_root: Path) -> dict[str, Any] | None:
    target = cache_path(bundle_root)
    try:
        if target.stat().st_size > MAX_CACHE_BYTES:
            return None
        with gzip.open(target, "rb") as stream:
            payload = json.loads(stream.read(MAX_CACHE_BYTES + 1))
        if not isinstance(payload, dict) or payload.get("schema_version") not in {1, 2}:
            return None
        if not isinstance(payload.get("records"), list):
            return None
        return payload
    except (OSError, EOFError, ValueError, TypeError, json.JSONDecodeError):
        return None


def search_catalog(
    payload: dict[str, Any], query: str, limit: int = 24
) -> tuple[dict[str, Any], ...]:
    terms = tuple(
        part.casefold().strip(".,:;!?()[]{}")
        for part in query.split()
        if part and part.casefold().strip(".,:;!?()[]{}") not in QUERY_STOPWORDS
    )
    records = payload.get("records", [])
    ranked: list[tuple[int, dict[str, Any]]] = []
    aliases = {alias for term in terms for alias in PACKAGE_QUERY_ALIASES.get(term, ())}
    for item in records:
        name = str(item.get("name", "")).casefold()
        haystack = " ".join(
            str(item.get(key, ""))
            for key in (
                "name",
                "version",
                "summary",
                "category",
                "purpose",
                "vendor",
                "origin",
                "repository",
            )
        ).casefold()
        name_hits = {
            term
            for term in terms
            if name == term or name.startswith(term + "-") or name.startswith(term + "+")
        }
        other_hits = {term for term in terms if term in haystack}
        if terms and not (name_hits or other_hits) and name not in aliases:
            continue
        score = sum(12 if term in name_hits and name == term else 8 for term in name_hits)
        score += sum(2 for term in other_hits - name_hits)
        if name in aliases:
            score += 32
        if item.get("state") == "installed":
            score += 1
        ranked.append((score, item))
    ranked.sort(
        key=lambda value: (
            -value[0],
            str(value[1].get("name", "")).casefold(),
            str(value[1].get("version", "")),
        )
    )
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for _, item in ranked:
        key = (str(item.get("name", "")), str(item.get("state", "")))
        if key in seen:
            continue
        seen.add(key)
        selected.append(item)
        if len(selected) >= max(1, min(limit, 100)):
            break
    return tuple(selected)
