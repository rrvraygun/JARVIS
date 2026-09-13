"""Read-only broker adapter for registry and local knowledge views."""

from __future__ import annotations

import importlib.util
import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .actions import ActionRegistry
from .package_inventory import (
    preview_install_transaction,
    preview_remove_transaction,
    scan_available_cached,
    scan_rpm,
)
from .package_knowledge import cache_path, package_context, read_catalog, write_catalog
from .power_inventory import scan_power_inventory

MAX_INSPECTION_DISPLAY_BYTES = 4 * 1024


def format_host_inspection(result: dict[str, Any]) -> str:
    """Render structured, bounded host evidence for an agent conversation."""
    if not result.get("read_only", False):
        return "HOST INSPECTION: unavailable"
    lines = [
        "HOST INSPECTION (READ-ONLY)",
        f"request scopes: {', '.join(result.get('scopes', ())) or 'none'}",
    ]
    platform = result.get("platform")
    if isinstance(platform, dict):
        lines.extend(["", "PLATFORM"])
        lines.extend(f"- {key}: {value}" for key, value in platform.items())
    power = result.get("power")
    if isinstance(power, dict):
        lines.extend(["", format_power_inspection(power)])
    packages = result.get("packages")
    if isinstance(packages, dict):
        lines.extend(["", format_package_inspection(packages)])
    rendered = "\n".join(lines)
    encoded = rendered.encode("utf-8")
    if len(encoded) <= MAX_INSPECTION_DISPLAY_BYTES:
        return rendered
    return (
        encoded[: MAX_INSPECTION_DISPLAY_BYTES - 120].decode("utf-8", errors="ignore").rstrip()
        + "\n[host inspection display truncated]"
    )


def format_power_inspection(result: dict[str, Any]) -> str:
    """Render inspection evidence for conversation context without raw JSON."""
    if not result.get("read_only", False):
        return "Inspection unavailable: invalid collector result."
    lines = [
        "HOST INSPECTION: POWER",
        f"collector: {result.get('collector', 'unknown')}",
        f"providers: {len(result.get('providers', []))}",
        f"settings: {len(result.get('settings', []))}",
        f"power-related packages: {len(result.get('packages', []))}",
        f"kernel modules observed: {len(result.get('loaded_modules', []))}",
        "",
        "PROVIDERS",
    ]
    lines.extend(f"- {value}" for value in result.get("providers", [])[:24])
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in result.get("settings", [])[:48]:
        grouped.setdefault(str(item.get("section", "Other")), []).append(item)
    for section in sorted(grouped, key=str.casefold):
        lines.extend(["", f"SETTINGS: {section}"])
        for item in grouped[section]:
            lines.append(
                f"- {item.get('setting', 'unknown')}: {item.get('current', 'unavailable')} "
                f"[choices: {item.get('choices', 'unavailable')}; source: {item.get('source', 'unknown')}; "
                f"writable_by_jarvis: {str(bool(item.get('writable_by_jarvis'))).lower()}]"
            )
    lines.extend(["", "POWER-RELATED INSTALLED PACKAGES"])
    for item in result.get("packages", [])[:32]:
        lines.append(
            f"- {item.get('name', 'unknown')} {item.get('nevra', '')} | "
            f"category: {item.get('category', 'other')} | purpose: {item.get('purpose', 'unknown')} | "
            f"origin: {item.get('origin', 'unknown')} | vendor: {item.get('vendor', 'unknown')}"
        )
    modules = [str(item) for item in result.get("loaded_modules", [])[:48]]
    lines.extend(["", "LOADED / EXPOSED KERNEL MODULES"])
    for index in range(0, len(modules), 12):
        lines.append("- " + ", ".join(modules[index : index + 12]))
    lines.extend(["", "LIMITATIONS"])
    lines.extend(f"- {value}" for value in result.get("limitations", []))
    rendered = "\n".join(lines)
    encoded = rendered.encode("utf-8")
    if len(encoded) <= MAX_INSPECTION_DISPLAY_BYTES:
        return rendered
    clipped = encoded[: MAX_INSPECTION_DISPLAY_BYTES - 180].decode("utf-8", errors="ignore")
    return (
        clipped.rstrip()
        + "\n\n[inspection display truncated; refresh or query a specific section for more detail]"
    )


def format_package_inspection(result: dict[str, Any]) -> str:
    """Render package catalog metadata and ranked use-case matches."""
    if not result.get("available", False):
        return f"HOST INSPECTION: PACKAGES\nstatus: unavailable ({result.get('error', 'unknown')})"
    lines = [
        "HOST INSPECTION: PACKAGES",
        f"installed packages: {result.get('installed_count', 0)}",
        f"cached available packages: {result.get('available_count', 0)}",
        f"catalog collected: {result.get('collected_at', 'unknown')}",
        f"catalog hash: {result.get('content_hash', 'unknown')}",
        f"catalog freshness: {'stale' if result.get('stale') else 'fresh'}",
        "",
        "MATCHES FOR CURRENT REQUEST",
    ]
    matches = result.get("matches", [])
    if not matches:
        lines.append("- No matching package records found in the catalog.")
    for item in matches[:24]:
        location = item.get("repository") or item.get("origin") or "unknown"
        lines.append(
            f"- {item.get('name', 'unknown')} {item.get('nevra', '')} | state: {item.get('state', 'unknown')} | "
            f"category: {item.get('category', 'other')} | purpose: {item.get('purpose', 'unknown')} | "
            f"origin: {location} | summary: {item.get('summary', 'unknown')}"
        )
        alternatives = item.get("installed_same_purpose", [])
        if alternatives:
            lines.append(
                "  installed alternatives with the same classified purpose (inferred, not RPM conflicts): "
                + ", ".join(str(value) for value in alternatives[:8])
            )
        documentation = item.get("documentation", {})
        if documentation.get("packaged_docs"):
            lines.append(
                "  documentation: installed RPM docs can be inspected locally; official refresh needs approval"
            )
    if result.get("scan_error"):
        lines.extend(["", f"scan warning: {result['scan_error']}; using the last valid catalog"])
    rendered = "\n".join(lines)
    encoded = rendered.encode("utf-8")
    if len(encoded) <= MAX_INSPECTION_DISPLAY_BYTES:
        return rendered
    return (
        encoded[: MAX_INSPECTION_DISPLAY_BYTES - 120].decode("utf-8", errors="ignore").rstrip()
        + "\n[package display truncated]"
    )


class ReadOnlyLocalControl:
    """Expose deterministic local reads without initializing or mutating stores."""

    QUERY_KINDS = frozenset({"facts", "sources", "attempts", "errors", "lessons", "decisions"})

    def __init__(self, bundle_root: Path) -> None:
        self.bundle_root = bundle_root.resolve()
        self.plugin_root = self.bundle_root / "plugins/jarvis-system-admin"
        self.knowledge_db = self.bundle_root / "runtime/knowledge/knowledge.db"

    def capabilities(self) -> tuple[dict[str, Any], ...]:
        value = json.loads(
            (self.plugin_root / "registry/capabilities.json").read_text(encoding="utf-8")
        )
        return tuple(dict(item) for item in value["capabilities"])

    def actions(self) -> tuple[dict[str, Any], ...]:
        registry = ActionRegistry.load(self.plugin_root / "registry/actions.json")
        return tuple(action.to_dict() for action in registry.all())

    def knowledge_status(self) -> dict[str, Any]:
        if not self.knowledge_db.is_file():
            database_status = {
                "available": False,
                "reason": "knowledge_database_missing",
            }
        else:
            with closing(self._connection()) as connection:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                metadata = {
                    str(row[0]): str(row[1])
                    for row in connection.execute("SELECT key,value FROM metadata").fetchall()
                }
            database_status = {
                "available": True,
                "read_only": True,
                "integrity": integrity,
                "schema_version": metadata.get("schema_version"),
                "encryption_state": metadata.get("encryption_state"),
            }
        catalog = read_catalog(self.bundle_root)
        database_status["package_catalog"] = {
            "available": catalog is not None,
            "installed_count": catalog.get("installed_count", 0) if catalog else 0,
            "available_count": catalog.get("available_count", 0) if catalog else 0,
            "collected_at": catalog.get("collected_at") if catalog else None,
            "content_hash": catalog.get("content_hash") if catalog else None,
            "sources": catalog.get("sources", []) if catalog else [],
        }
        return database_status

    def recovery_status(self) -> dict[str, Any]:
        """Return a redacted projection of the recorded R1/R2 evidence."""
        reports = {
            "r1": self.bundle_root / "runtime/reports/2026-08-07-r1-local-snapshot.json",
            "r2": self.bundle_root / "runtime/reports/2026-08-07-r2-live-recovery-boundary.json",
            "h1": self.bundle_root
            / "runtime/reports/2026-08-07-h1-followup-observation-20260807T162422Z.json",
            "phase5": self.bundle_root / "runtime/reports/2026-08-07-phase5-rehearsal-marker.json",
        }
        result: dict[str, Any] = {}
        for key, path in reports.items():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("report is not an object")
                result[key] = {
                    "status": value.get("status", "unknown"),
                    "date": value.get("date"),
                    "evidence_source": value.get("evidence_source"),
                }
                if key == "r2":
                    repo = value.get("repository", {})
                    comparison = value.get("independent_comparison", {})
                    result[key].update(
                        {
                            "snapshot_id": repo.get("snapshot_id"),
                            "mismatch_total": comparison.get("mismatch_total"),
                            "proof_gaps": len(comparison.get("proof_gaps", [])),
                            "boundary_covered": value.get("recovery_boundary", {}).get("boundary"),
                        }
                    )
                if key == "phase5":
                    result[key].update(
                        {
                            "operation_id": value.get("operation_id"),
                            "rollback_verified": value.get("rollback_verified"),
                            "temporary_root_removed": value.get("temporary_root_removed"),
                        }
                    )
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                result[key] = {"status": "unavailable"}
        return result

    def query_knowledge(self, kind: str, text: str, limit: int = 20) -> tuple[dict[str, Any], ...]:
        if kind not in self.QUERY_KINDS:
            raise ValueError("unsupported_query_kind")
        if not self.knowledge_db.is_file():
            raise FileNotFoundError("knowledge database is unavailable")
        bounded_limit = max(1, min(int(limit), 100))
        knowledge = self._knowledge_module()
        with closing(self._connection()) as connection:
            return tuple(knowledge.query(connection, kind, text, bounded_limit))

    def inspect_power(self) -> dict[str, Any]:
        """Run the bounded, read-only Power collector against the enrolled host."""
        inventory = scan_power_inventory()
        packages: list[dict[str, Any]] = []
        try:
            terms = (
                "power",
                "tuned",
                "ppd",
                "tlp",
                "powertop",
                "thermald",
                "upower",
                "acpi",
                "cpufreq",
                "kernel",
                "kmod",
                "firmware",
                "intel",
                "nvidia",
                "amd",
            )
            for item in scan_rpm():
                haystack = f"{item.name} {item.summary} {item.purpose}".casefold()
                if item.category in {"kernel", "intel", "nvidia/gpu"} or any(
                    term in haystack for term in terms
                ):
                    packages.append(
                        {
                            "name": item.name,
                            "nevra": item.nevra,
                            "vendor": item.vendor,
                            "summary": item.summary,
                            "category": item.category,
                            "purpose": item.purpose,
                            "origin": item.origin,
                        }
                    )
        except (OSError, RuntimeError, ValueError, TypeError):
            packages = []
        modules: list[str] = []
        try:
            proc_modules = Path("/proc/modules").read_text(encoding="utf-8", errors="replace")
            modules.extend(line.split()[0] for line in proc_modules.splitlines() if line.split())
        except OSError:
            pass
        try:
            modules.extend(path.name for path in Path("/sys/module").iterdir())
        except OSError:
            pass
        return {
            "providers": list(inventory.providers),
            "settings": [
                {
                    "section": item.section,
                    "setting": item.setting,
                    "current": item.current,
                    "choices": item.choices,
                    "source": item.source,
                    "writable_by_jarvis": item.writable_by_jarvis,
                    "control_id": item.control_id,
                }
                for item in inventory.settings
            ],
            "limitations": list(inventory.limitations),
            "packages": packages[:256],
            "loaded_modules": sorted(set(modules))[:256],
            "read_only": True,
            "collector": "jarvis_tui.power_inventory",
        }

    def inspect_platform(self) -> dict[str, str]:
        """Read a fixed, non-sensitive host identity subset without subprocesses."""
        os_release: dict[str, str] = {}
        try:
            for line in (
                Path("/etc/os-release").read_text(encoding="utf-8", errors="replace").splitlines()
            ):
                key, separator, value = line.partition("=")
                if separator and key in {"ID", "VERSION_ID", "PRETTY_NAME"}:
                    os_release[key.lower()] = value.strip().strip('"')[:160]
        except OSError:
            pass
        uname = os.uname()
        return {
            "operating_system": os_release.get("pretty_name") or os_release.get("id") or "unknown",
            "version": os_release.get("version_id", "unknown"),
            "kernel": uname.release[:160],
            "architecture": uname.machine[:80],
        }

    def inspect_host(self, request: str, *, refresh_packages: bool = False) -> dict[str, Any]:
        """Run only allowlisted read-only collectors selected from a user request."""
        if not isinstance(request, str) or len(request) > 4_000:
            raise ValueError("host inspection request is invalid")
        text = request.casefold()
        package_terms = (
            "package",
            "install",
            "rpm",
            "dnf",
            "repository",
            "repo",
            "version",
            "rust",
            "cargo",
        )
        power_terms = (
            "power",
            "battery",
            "energy",
            "cpu",
            "gpu",
            "driver",
            "module",
            "powertop",
            "tuned",
        )
        scopes = ["platform"]
        result: dict[str, Any] = {
            "read_only": True,
            "collector": "jarvis_tui.host_inspection",
            "platform": self.inspect_platform(),
        }
        if any(term in text for term in power_terms):
            scopes.append("power")
            result["power"] = self.inspect_power()
        if any(term in text for term in package_terms) or not request.strip():
            scopes.append("packages")
            result["packages"] = self.inspect_packages(request, refresh=refresh_packages)
        result["scopes"] = scopes
        return result

    def inspect_packages(self, query: str = "", *, refresh: bool = True) -> dict[str, Any]:
        """Scan and persist installed/cached package knowledge, returning ranked matches."""
        payload = None
        scan_error: str | None = None
        if refresh:
            try:
                installed = scan_rpm()
                available = scan_available_cached()
                write_catalog(self.bundle_root, installed, available)
                payload = read_catalog(self.bundle_root)
                if payload is None:
                    raise RuntimeError("package catalog could not be read after write")
            except (OSError, RuntimeError, ValueError, TypeError, TimeoutError) as exc:
                scan_error = type(exc).__name__
        if payload is None:
            payload = read_catalog(self.bundle_root)
        if payload is None:
            return {
                "available": False,
                "read_only": True,
                "error": scan_error or "package_catalog_unavailable",
                "matches": [],
            }
        return {
            "available": True,
            "read_only": True,
            "stale": bool(scan_error),
            "scan_error": scan_error,
            "collected_at": payload.get("collected_at"),
            "content_hash": payload.get("content_hash"),
            "installed_count": payload.get("installed_count", 0),
            "available_count": payload.get("available_count", 0),
            "matches": list(package_context(payload, query)),
            "catalog_path": str(cache_path(self.bundle_root).relative_to(self.bundle_root)),
            "sources": payload.get("sources", []),
        }

    def preview_package_install(self, names: tuple[str, ...]) -> dict[str, Any]:
        """Return a cache-only transaction preview without mutation authority."""
        return preview_install_transaction(names)

    def preview_package_remove(self, names: tuple[str, ...]) -> dict[str, Any]:
        """Resolve one exact removal transaction from cached metadata only."""
        return preview_remove_transaction(names)

    def _connection(self) -> sqlite3.Connection:
        uri = f"file:{quote(str(self.knowledge_db.resolve()))}?mode=ro"
        connection = sqlite3.connect(uri, uri=True)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA query_only = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    def _knowledge_module(self) -> Any:
        path = self.plugin_root / "scripts/knowledge_store.py"
        spec = importlib.util.spec_from_file_location("jarvis_readonly_knowledge", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load the knowledge query implementation")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
