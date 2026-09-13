"""Bounded Fedora RPM inventory and deterministic classification."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

MAX_BYTES = 16 * 1024 * 1024
PACKAGE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9+_.:-]{0,199}$")
MAX_TRANSACTION_PACKAGES = 200
RPM_ARCH = re.compile(r"^(?:aarch64|i[3-6]86|noarch|ppc64le|s390x|src|x86_64)$", re.IGNORECASE)
PROTECTED_REMOVAL_PACKAGES = frozenset(
    {
        "audit",
        "bash",
        "coreutils",
        "dnf",
        "dnf5",
        "filesystem",
        "glibc",
        "kernel",
        "networkmanager",
        "polkit",
        "rpm",
        "selinux-policy",
        "setup",
        "shadow-utils",
        "sudo",
        "systemd",
    }
)
PACKAGE_FIELDS = "%{NAME}|%{VERSION}|%{RELEASE}|%{ARCH}|%{VENDOR}|%{SUMMARY}\\n"
# DNF5 preserves a literal backslash-n in --qf output, unlike rpm.  Pass an
# actual record newline so cached repository rows remain individually parseable.
REPOSITORY_FIELDS = (
    "%{name}|%{epoch}|%{version}|%{release}|%{arch}|%{repoid}|%{vendor}|%{license}|%{summary}\n"
)


class PackagePreviewError(RuntimeError):
    """A preview failure with audit-safe structured diagnostics only."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        audit_details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.audit_details = dict(audit_details or {})


def _package_set_digest(values: Sequence[str]) -> str:
    return hashlib.sha256(
        json.dumps(sorted(values, key=str.casefold), separators=(",", ":")).encode()
    ).hexdigest()


def canonicalize_package_preview(output: str) -> str:
    """Remove DNF diagnostics that can vary between identical dry-runs.

    The approval binds the transaction sections, not cache/log housekeeping
    emitted on stderr (for example a read-only dnf log warning).
    """
    rows: set[str] = set()
    name_pattern = re.compile(
        r"^[A-Za-z0-9][A-Za-z0-9+_.:-]{0,199}(?:\.(?:aarch64|i[3-6]86|noarch|ppc64le|s390x|src|x86_64))?$",
        re.IGNORECASE,
    )
    for raw in output.splitlines():
        line = " ".join(raw.strip().split())
        lowered = line.casefold()
        if (
            "cannot open log file" in lowered
            or lowered.startswith("last metadata expiration check:")
            or lowered.startswith("warning: cannot open")
        ):
            continue
        fields = line.split()
        if len(fields) >= 2 and name_pattern.fullmatch(fields[0]):
            # Repository and size columns can change between identical DNF
            # simulations; package identity and version are the bound effect.
            rows.add(f"{fields[0]} {fields[1]}")
    return "\n".join(sorted(rows, key=str.casefold))


def _valid_bound_rpm_state(value: str) -> bool:
    fields = value.split("|")
    if len(fields) != 4 or "." not in fields[3] or any(character.isspace() for character in value):
        return False
    name, epoch, version, release_arch = fields
    release, arch = release_arch.rsplit(".", 1)
    return bool(
        PACKAGE_NAME.fullmatch(name)
        and epoch.isascii()
        and epoch.isdigit()
        and all(part and len(part) <= 200 for part in (version, release, arch))
    )


@dataclass(frozen=True)
class PackageRecord:
    name: str
    version: str
    release: str
    arch: str
    vendor: str
    summary: str
    category: str
    purpose: str
    origin: str

    @property
    def nevra(self) -> str:
        return f"{self.name}-{self.version}-{self.release}.{self.arch}"


@dataclass(frozen=True)
class RepositoryPackageRecord:
    name: str
    epoch: str
    version: str
    release: str
    arch: str
    repository: str
    vendor: str
    license: str
    summary: str
    category: str
    purpose: str
    evidence: str = "sourced:cached-dnf-metadata"

    @property
    def nevra(self) -> str:
        epoch = "" if self.epoch in {"", "0", "(none)"} else f"{self.epoch}:"
        return f"{self.name}-{epoch}{self.version}-{self.release}.{self.arch}"


def classify(name: str, summary: str, vendor: str) -> tuple[str, str]:
    text = f"{name} {summary} {vendor}".casefold()
    rules = (
        (
            "nvidia/gpu",
            ("nvidia", "cuda", "cudnn", "egl-wayland"),
            "NVIDIA graphics, compute, or acceleration",
        ),
        (
            "intel",
            ("intel", "oneapi", "level-zero", "va-intel"),
            "Intel graphics, media, or compute",
        ),
        ("gnome", ("gnome", "mutter", "gtk", "glib"), "GNOME desktop platform"),
        (
            "lighting",
            ("backlight", "brightness", "keyboard-led", "rgb", "openrgb"),
            "Display or keyboard lighting",
        ),
        (
            "kernel",
            ("kernel", "kmod", "dracut", "firmware"),
            "Kernel, drivers, or firmware",
        ),
        (
            "development",
            ("gcc", "clang", "python", "rust", "cargo", "cmake", "nodejs"),
            "Programming and development",
        ),
        (
            "virtualization",
            ("libvirt", "qemu", "podman", "docker"),
            "Virtual machines or containers",
        ),
        ("audio", ("pipewire", "pulseaudio", "alsa", "wireplumber"), "Audio stack"),
        (
            "network",
            ("networkmanager", "wifi", "wireless", "bluez"),
            "Networking and Bluetooth",
        ),
        (
            "security",
            ("selinux", "openssl", "gnupg", "audit"),
            "Security and integrity",
        ),
    )
    for category, needles, purpose in rules:
        if any(needle in text for needle in needles):
            return category, purpose
    return "other", "General system or user-space component"


def parse_rpm_output(output: str, *, origin: str = "rpmdb") -> tuple[PackageRecord, ...]:
    records: list[PackageRecord] = []
    for line in output.splitlines():
        fields = line.split("|", 5)
        if len(fields) != 6 or not fields[0] or len(fields[0]) > 200:
            continue
        name, version, release, arch, vendor, summary = (field.strip() for field in fields)
        category, purpose = classify(name, summary, vendor)
        records.append(
            PackageRecord(name, version, release, arch, vendor, summary, category, purpose, origin)
        )
    return tuple(records)


def scan_rpm(*, timeout_seconds: float = 5.0) -> tuple[PackageRecord, ...]:
    """Read the local RPM database using one fixed, non-shell command."""
    result = subprocess.run(
        ["rpm", "-qa", "--qf", PACKAGE_FIELDS],
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    if len(result.stdout.encode()) > MAX_BYTES:
        raise RuntimeError("RPM inventory exceeded the bounded output limit")
    return parse_rpm_output(result.stdout)


def parse_repository_output(output: str) -> tuple[RepositoryPackageRecord, ...]:
    records: list[RepositoryPackageRecord] = []
    for line in output.splitlines():
        fields = line.split("|", 8)
        if len(fields) != 9:
            continue
        (
            name,
            epoch,
            version,
            release,
            arch,
            repository,
            vendor,
            license_name,
            summary,
        ) = (field.strip() for field in fields)
        if not name or name.startswith("-") or len(name) > 200:
            continue
        category, purpose = classify(name, summary, vendor)
        records.append(
            RepositoryPackageRecord(
                name,
                epoch,
                version,
                release,
                arch,
                repository,
                vendor,
                license_name,
                summary,
                category,
                purpose,
            )
        )
    return tuple(records)


def scan_available_cached(
    *, updates_only: bool = False, timeout_seconds: float = 15.0
) -> tuple[RepositoryPackageRecord, ...]:
    """Read only already-cached enabled-repository metadata; never refresh it."""
    selector = "--upgrades" if updates_only else "--available"
    output = _fixed_query(
        ["dnf", "--cacheonly", "repoquery", selector, "--qf", REPOSITORY_FIELDS],
        timeout_seconds=timeout_seconds,
    )
    return parse_repository_output(output)


def package_view(
    installed: Iterable[PackageRecord],
    available: Iterable[RepositoryPackageRecord],
    mode: str,
) -> tuple[dict[str, Any], ...]:
    installed = tuple(installed)
    available = tuple(available)
    if mode not in {"installed", "available", "combined", "updates"}:
        raise ValueError("unknown package inventory mode")
    installed_keys = {(item.name, item.arch): item for item in installed}
    installed_by_category: dict[str, tuple[str, ...]] = {}
    for category in {item.category for item in installed if item.category != "other"}:
        installed_by_category[category] = tuple(
            sorted(
                {item.name for item in installed if item.category == category},
                key=str.casefold,
            )
        )
    values: list[dict[str, Any]] = []
    if mode in {"installed", "combined"}:
        for item in installed:
            values.append(
                {
                    "name": item.name,
                    "nevra": item.nevra,
                    "arch": item.arch,
                    "category": item.category,
                    "purpose": item.purpose,
                    "origin": item.origin,
                    "state": "installed",
                    "summary": item.summary,
                    "evidence": "observed:rpmdb",
                }
            )
    if mode in {"available", "combined", "updates"}:
        for available_item in available:
            current = installed_keys.get((available_item.name, available_item.arch))
            if mode == "updates" and current is None:
                continue
            alternatives = tuple(
                name
                for name in installed_by_category.get(available_item.category, ())
                if name != available_item.name
            )[:3]
            values.append(
                {
                    "name": available_item.name,
                    "nevra": available_item.nevra,
                    "arch": available_item.arch,
                    "category": available_item.category,
                    "purpose": available_item.purpose,
                    "origin": available_item.repository,
                    "state": "update-candidate" if current else "available",
                    "installed_nevra": current.nevra if current else None,
                    "installed_alternatives": alternatives,
                    "summary": available_item.summary,
                    "evidence": available_item.evidence,
                }
            )
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for value in values:
        unique[(value["name"], value["arch"], value["nevra"], value["state"])] = value
    return tuple(
        unique[key]
        for key in sorted(unique, key=lambda key: (key[0].casefold(), key[1], key[2], key[3]))
    )


@dataclass(frozen=True)
class PackageRelationship:
    subject: str
    relation: str
    object: str
    evidence: str
    authoritative: bool


def build_relationships(
    *,
    conflicts: Iterable[tuple[str, str]] = (),
    obsoletes: Iterable[tuple[str, str]] = (),
    providers: Iterable[tuple[str, str]] = (),
    similarities: Iterable[tuple[str, str]] = (),
) -> tuple[PackageRelationship, ...]:
    values: list[PackageRelationship] = []
    for subject, target in conflicts:
        values.append(
            PackageRelationship(subject, "conflicts", target, "sourced:rpm-conflicts", True)
        )
    for subject, target in obsoletes:
        values.append(
            PackageRelationship(subject, "obsoletes", target, "sourced:rpm-obsoletes", True)
        )
    grouped: dict[str, set[str]] = {}
    for package, capability in providers:
        grouped.setdefault(capability, set()).add(package)
    for capability, packages in grouped.items():
        ordered = sorted(packages)
        for index, subject in enumerate(ordered):
            for target in ordered[index + 1 :]:
                values.append(
                    PackageRelationship(
                        subject,
                        "alternative-provider",
                        target,
                        f"sourced:rpm-provides:{capability}",
                        True,
                    )
                )
    for subject, target in similarities:
        values.append(
            PackageRelationship(
                subject,
                "similar-purpose",
                target,
                "inferred:metadata-similarity",
                False,
            )
        )
    return tuple(sorted(values, key=lambda item: (item.subject, item.relation, item.object)))


def relationship_queries(name: str, *, timeout_seconds: float = 10.0) -> dict[str, tuple[str, ...]]:
    """Query cached authoritative relationship indexes for one safe package name."""
    if (
        not isinstance(name, str)
        or not name
        or name.startswith("-")
        or any(ch.isspace() for ch in name)
        or len(name) > 200
    ):
        raise ValueError("package name is invalid")
    commands = {
        "conflicts": [
            "dnf",
            "--cacheonly",
            "repoquery",
            "--whatconflicts",
            name,
            "--qf",
            "%{name}",
        ],
        "obsoletes": [
            "dnf",
            "--cacheonly",
            "repoquery",
            "--whatobsoletes",
            name,
            "--qf",
            "%{name}",
        ],
        "providers": [
            "dnf",
            "--cacheonly",
            "repoquery",
            "--whatprovides",
            name,
            "--qf",
            "%{name}",
        ],
    }
    return {
        relation: parse_dependency_output(_fixed_query(command, timeout_seconds=timeout_seconds))
        for relation, command in commands.items()
    }


def page_records(records: Sequence[Any], *, page: int, page_size: int = 100) -> tuple[Any, ...]:
    if page < 0 or page_size < 1 or page_size > 500:
        raise ValueError("package page boundary is invalid")
    start = page * page_size
    return tuple(records[start : start + page_size])


def recommendation_record(
    *,
    goal: str,
    candidates: Sequence[Mapping[str, Any]],
    relationships: Sequence[PackageRelationship] = (),
) -> dict[str, Any]:
    """Create an explainable comparison; never claim inferred fit as fact."""
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 1000:
        raise ValueError("package recommendation goal is invalid")
    if not candidates or len(candidates) > 20:
        raise ValueError("package recommendation candidate count is invalid")
    goal_words = {word.casefold() for word in goal.split() if len(word) > 2}
    comparison = []
    for candidate in candidates:
        name = str(candidate.get("name", ""))
        if not name or name.startswith("-"):
            raise ValueError("package recommendation candidate is invalid")
        searchable = " ".join(
            str(candidate.get(key, "")) for key in ("name", "category", "purpose", "summary")
        ).casefold()
        matched = sorted(word for word in goal_words if word in searchable)
        related = [item for item in relationships if item.subject == name or item.object == name]
        comparison.append(
            {
                "name": name,
                "goal_matches": matched,
                "authoritative_relationships": [
                    item.__dict__ for item in related if item.authoritative
                ],
                "inferred_relationships": [
                    item.__dict__ for item in related if not item.authoritative
                ],
                "evidence": candidate.get("evidence", "unknown"),
                "fit_score": len(matched),
            }
        )
    comparison.sort(key=lambda item: (-item["fit_score"], item["name"].casefold()))
    return {
        "schema_version": 1,
        "goal": goal.strip(),
        "comparison": comparison,
        "recommendation": comparison[0]["name"] if comparison[0]["fit_score"] > 0 else None,
        "recommendation_label": "inferred",
        "installation_performed": False,
        "limitations": [
            "metadata fit is not proof of runtime compatibility",
            "transaction simulation required before any future installation",
        ],
    }


def recommend_cached_packages(
    goal: str,
    installed: Iterable[PackageRecord],
    available: Iterable[RepositoryPackageRecord],
    *,
    limit: int = 12,
) -> dict[str, Any]:
    """Rank bounded installed/cached package candidates without a transaction."""
    if not isinstance(goal, str) or not goal.strip() or len(goal) > 300:
        raise ValueError("package recommendation goal is invalid")
    if not 1 <= limit <= 20:
        raise ValueError("package recommendation limit is invalid")
    ignored = {
        "a",
        "an",
        "and",
        "for",
        "i",
        "install",
        "latest",
        "last",
        "need",
        "package",
        "please",
        "the",
        "to",
        "version",
        "want",
        "which",
    }
    terms = tuple(
        word.casefold()
        for word in goal.replace("-", " ").split()
        if len(word) > 1 and word.casefold() not in ignored
    )
    if not terms:
        raise ValueError("package recommendation needs a product or capability term")
    ranked: list[tuple[int, dict[str, Any]]] = []
    for item in package_view(installed, available, "combined"):
        searchable = " ".join(
            str(item.get(field, "")) for field in ("name", "summary", "purpose", "category")
        ).casefold()
        score = sum(term in searchable for term in terms)
        if item["name"].casefold() in terms:
            score += 3
        elif any(item["name"].casefold().startswith(term) for term in terms):
            score += 2
        if score:
            ranked.append((score, item))
    ranked.sort(
        key=lambda entry: (
            -entry[0],
            0 if entry[1]["state"] == "update-candidate" or entry[1]["origin"] == "updates" else 1,
            entry[1]["name"].casefold(),
            entry[1]["nevra"],
        )
    )
    candidates = [item for _, item in ranked[:limit]]
    result = recommendation_record(goal=goal, candidates=candidates)
    result["recommendation"] = candidates[0]["name"] if candidates else None
    result["candidates"] = [
        {
            key: item.get(key)
            for key in (
                "name",
                "nevra",
                "state",
                "origin",
                "purpose",
                "summary",
                "evidence",
            )
        }
        for item in candidates
    ]
    result["repository_metadata_used"] = True
    result["network_used"] = False
    return result


def preview_package_transaction(
    names: Sequence[str], *, operation: str, timeout_seconds: float = 20.0
) -> dict[str, Any]:
    """Prepare one cache-only install/remove preview; never change the host."""
    if operation not in {"install", "remove"}:
        raise ValueError("package transaction operation is invalid")
    values = tuple(dict.fromkeys(str(name).strip() for name in names))
    if not values or len(values) > 20 or any(not PACKAGE_NAME.fullmatch(value) for value in values):
        raise ValueError("package transaction names are invalid")
    if operation == "remove" and any(
        name.casefold() in PROTECTED_REMOVAL_PACKAGES or name.casefold().startswith("kernel-")
        for name in values
    ):
        raise PermissionError("a protected or boot-critical package cannot be removed")
    pre_state: dict[str, str | None] = {}
    output = (
        _preview_dnf_install(values, timeout_seconds=timeout_seconds)
        if operation == "install"
        else _preview_dnf_remove(values, timeout_seconds=timeout_seconds)
    )
    affected_installs = _preview_installed_packages(output)
    affected_removals = _preview_removed_packages(output)
    if operation == "install" and (
        affected_removals
        or _preview_has_non_additive_install_effect(output)
        or re.search(r"(?:removing|eliminando|desinstalando):\s*[1-9]", output, re.IGNORECASE)
    ):
        raise RuntimeError(
            "DNF resolved this request by removing or replacing installed packages; "
            "automatic development-tool installation is limited to additive transactions"
        )
    if operation == "install":
        if (
            not affected_installs
            or len(affected_installs) > MAX_TRANSACTION_PACKAGES
            or not set(values).issubset(affected_installs)
        ):
            raise RuntimeError("DNF installation preview does not contain every requested package")
        for name in affected_installs:
            probe = subprocess.run(
                [
                    "rpm",
                    "-q",
                    "--qf",
                    "%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}.%{ARCH}",
                    name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            state = probe.stdout.strip() if probe.returncode == 0 else None
            if state is not None and len(state) > 1_024:
                raise RuntimeError("RPM installation pre-state exceeded its bound")
            pre_state[name] = state
    if operation == "remove":
        protected = sorted(
            name
            for name in affected_removals
            if name.casefold() in PROTECTED_REMOVAL_PACKAGES
            or name.casefold().startswith("kernel-")
        )
        if protected:
            raise PermissionError(
                "DNF would remove protected or boot-critical packages: " + ", ".join(protected[:12])
            )
        if not affected_removals or len(affected_removals) > MAX_TRANSACTION_PACKAGES:
            raise PackagePreviewError(
                "package_preview.resolved_set_unavailable",
                "DNF did not resolve a bounded explicit removal set.",
                audit_details={
                    "requested_count": len(values),
                    "resolved_count": len(affected_removals),
                    "requested_digest": _package_set_digest(values),
                    "resolved_digest": _package_set_digest(affected_removals),
                },
            )
        if not set(values).issubset(affected_removals):
            raise PackagePreviewError(
                "package_preview.requested_root_missing",
                "DNF's resolved removal set does not contain every requested package root.",
                audit_details={
                    "requested_count": len(values),
                    "resolved_count": len(affected_removals),
                    "requested_digest": _package_set_digest(values),
                    "resolved_digest": _package_set_digest(affected_removals),
                },
            )
        for name in affected_removals:
            probe = subprocess.run(
                [
                    "rpm",
                    "-q",
                    "--qf",
                    "%{NAME}|%{EPOCHNUM}|%{VERSION}|%{RELEASE}.%{ARCH}",
                    name,
                ],
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,
            )
            state = probe.stdout.strip() if probe.returncode == 0 else None
            if state is not None and len(state) > 1_024:
                raise RuntimeError("RPM removal pre-state exceeded its bound")
            if state is not None and not _valid_bound_rpm_state(state):
                raise RuntimeError(
                    "RPM removal pre-state is ambiguous or cannot be restored exactly"
                )
            pre_state[name] = state
        if any(value is None for value in pre_state.values()):
            raise RuntimeError("DNF removal pre-state could not be bound completely")
    output = canonicalize_package_preview(output)
    preview_digest = hashlib.sha256(output.encode()).hexdigest()
    approval_material = {
        "operation": operation,
        "names": list(values),
        "pre_state": pre_state,
        "preview_digest": preview_digest,
    }
    approval_digest = hashlib.sha256(
        json.dumps(approval_material, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "packages": list(values),
        "operation": operation,
        "affected_installs": list(affected_installs),
        "affected_removals": list(affected_removals),
        "preview": output,
        "pre_state": pre_state,
        "preview_digest": preview_digest,
        "approval_digest": approval_digest,
        "network_used": False,
        "mutated": False,
        "requires_fresh_approval": True,
        "transaction_resolved": True,
        "limitations": [
            "cache-only metadata may be stale",
            "the preview is not an approval and no transaction was executed",
        ],
    }


def preview_install_transaction(
    names: Sequence[str], *, timeout_seconds: float = 20.0
) -> dict[str, Any]:
    return preview_package_transaction(names, operation="install", timeout_seconds=timeout_seconds)


def preview_remove_transaction(
    names: Sequence[str], *, timeout_seconds: float = 20.0
) -> dict[str, Any]:
    return preview_package_transaction(names, operation="remove", timeout_seconds=timeout_seconds)


def _preview_dnf(names: Sequence[str], *, operation: str, timeout_seconds: float) -> str:
    """Run DNF's non-mutating transaction simulation.

    DNF 5 returns exit status 1 for a successful ``--assumeno`` preview because
    it deliberately aborts before committing.  A Transaction Summary is the
    authoritative success signal; all other non-zero exits remain failures.
    """
    argv = ["dnf", "--cacheonly", "--assumeno", operation]
    # DNF5 makes this a remove-subcommand option, not a global option.
    if operation == "remove":
        argv.append("--no-autoremove")
    result = subprocess.run(
        [*argv, *names],
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    output = "\n".join(part for part in (result.stdout, result.stderr) if part).strip()
    if len(output.encode()) > 2 * 1024 * 1024:
        raise RuntimeError("package transaction preview exceeded the bounded output limit")
    summary_present = re.search(
        r"(?:transaction\s+summary|resumen\s+de\s+la\s+transacci[oó]n|installing:|instalando:|removing:|eliminando:|desinstalando:)",
        output,
        flags=re.IGNORECASE,
    )
    if result.returncode not in {0, 1} or not summary_present:
        detail = output[-500:].strip().replace("\n", " ")
        raise RuntimeError(
            f"DNF could not resolve the requested installation: {detail or result.returncode}"
        )
    return output


def _preview_dnf_install(names: Sequence[str], *, timeout_seconds: float) -> str:
    """Compatibility wrapper for the additive transaction preview."""
    return _preview_dnf(names, operation="install", timeout_seconds=timeout_seconds)


def _preview_dnf_remove(names: Sequence[str], *, timeout_seconds: float) -> str:
    return _preview_dnf(names, operation="remove", timeout_seconds=timeout_seconds)


def _preview_removed_packages(output: str) -> tuple[str, ...]:
    """Extract package names from bounded DNF removal sections."""
    values: set[str] = set()
    active = False
    headings = re.compile(
        r"^\s*(removing|removing\s+dependent\s+packages|eliminando|desinstalando)(?:\s*:.*)?$",
        re.IGNORECASE,
    )
    other_heading = re.compile(
        r"^\s*(installing|upgrading|downgrading|reinstalling|replacing|instalando|actualizando)(?:\s*:.*)?$",
        re.IGNORECASE,
    )
    summary_count = re.compile(
        r"^\s*(?:installing|upgrading|downgrading|reinstalling|replacing|removing|"
        r"instalando|actualizando|degradando|reinstalando|reemplazando|eliminando|"
        r"desinstalando)\s*:\s*\d+\s+(?:packages?|paquetes?)\b",
        re.IGNORECASE,
    )
    for line in output.splitlines():
        # DNF5 follows "Transaction Summary" with e.g. "Removing: 3
        # packages".  That is a count, not a package-list heading; accepting
        # it would parse later stderr status words as package names.
        if summary_count.match(line):
            active = False
            continue
        if headings.match(line):
            active = True
            continue
        if other_heading.match(line) or re.match(
            r"^\s*(transaction summary|resumen de la transacci[oó]n)",
            line,
            re.IGNORECASE,
        ):
            active = False
            continue
        if not active or not line.strip() or set(line.strip()) <= {"-", "="}:
            continue
        token = line.strip().split()[0]
        name = token.rsplit(".", 1)[0] if "." in token else token
        if PACKAGE_NAME.fullmatch(name) and name.casefold() not in {
            "package",
            "paquete",
        }:
            values.add(name)
    # DNF5's table is a stable secondary source when a localized or extended
    # removal heading is not recognized. Only use it for a removal-only
    # transaction; an install/upgrade section must remain fail-closed.
    if not re.search(
        r"(?im)^\s*(?:installing|upgrading|downgrading|reinstalling|replacing|"
        r"instalando|actualizando|degradando|reinstalando|reemplazando)\s*:",
        output,
    ):
        table_values = _preview_table_package_names(output)
        if table_values:
            values = set(table_values)
    if not values:
        for line in output.splitlines():
            match = re.search(
                r"(?:removing|eliminando|desinstalando):\s+([A-Za-z0-9][A-Za-z0-9+_.:-]{0,199})",
                line,
                re.IGNORECASE,
            )
            if match:
                values.add(match.group(1).rsplit(".", 1)[0])
    return tuple(sorted(values, key=str.casefold))


def _preview_table_package_names(output: str) -> tuple[str, ...]:
    """Extract bounded RPM rows from DNF's transaction table, not status text."""
    values: set[str] = set()
    table_active = False
    header = re.compile(
        r"^\s*(?:package|paquete)\s+(?:arch|architecture|arquitectura|arq)\b",
        re.IGNORECASE,
    )
    for line in output.splitlines():
        if re.match(
            r"^\s*(?:transaction summary|resumen de la transacci[oó]n)",
            line,
            re.IGNORECASE,
        ):
            break
        if header.match(line):
            table_active = True
            continue
        if not table_active:
            continue
        fields = line.strip().split()
        if len(fields) < 2 or not RPM_ARCH.fullmatch(fields[1]):
            continue
        name = fields[0].rsplit(".", 1)[0] if "." in fields[0] else fields[0]
        if PACKAGE_NAME.fullmatch(name):
            values.add(name)
    return tuple(sorted(values, key=str.casefold))


def _preview_installed_packages(output: str) -> tuple[str, ...]:
    """Extract all packages in DNF install/dependency sections."""
    values: set[str] = set()
    active = False
    headings = re.compile(
        r"^\s*(installing(?:\s+(?:dependencies|weak dependencies|groups))?|"
        r"instalando(?:\s+(?:dependencias|dependencias d[eé]biles|grupos))?)(?:\s*:.*)?$",
        re.IGNORECASE,
    )
    other_heading = re.compile(
        r"^\s*(removing|upgrading|downgrading|reinstalling|replacing|eliminando|"
        r"desinstalando|actualizando)(?:\s*:.*)?$",
        re.IGNORECASE,
    )
    summary_count = re.compile(
        r"^\s*(?:installing|upgrading|downgrading|reinstalling|replacing|removing|"
        r"instalando|actualizando|degradando|reinstalando|reemplazando|eliminando|"
        r"desinstalando)\s*:\s*\d+\s+(?:packages?|paquetes?)\b",
        re.IGNORECASE,
    )
    for line in output.splitlines():
        if summary_count.match(line):
            active = False
            continue
        if headings.match(line):
            active = True
            continue
        if other_heading.match(line) or re.match(
            r"^\s*(transaction summary|resumen de la transacci[oó]n)",
            line,
            re.IGNORECASE,
        ):
            active = False
            continue
        if not active or not line.strip() or set(line.strip()) <= {"-", "="}:
            continue
        token = line.strip().split()[0]
        name = token.rsplit(".", 1)[0] if "." in token else token
        if PACKAGE_NAME.fullmatch(name) and name.casefold() not in {
            "package",
            "paquete",
        }:
            values.add(name)
    return tuple(sorted(values, key=str.casefold))


def _preview_has_non_additive_install_effect(output: str) -> bool:
    """Reject install previews that also change an installed package version.

    Those effects need version-specific rollback semantics that this narrow
    helper deliberately does not grant.  A heading is sufficient to fail
    closed; the user can use the normal agent/tool approval boundary instead.
    """
    return bool(
        re.search(
            r"(?im)^\s*(?:upgrading|downgrading|reinstalling|replacing|"
            r"actualizando|degradando|reinstalando|reemplazando)\s*:",
            output,
        )
    )


def _preview_removes_installed_packages(output: str) -> bool:
    """Compatibility predicate retained for existing fixture callers."""
    return bool(_preview_removed_packages(output))


def sort_records(records: Iterable[PackageRecord], mode: str) -> tuple[PackageRecord, ...]:
    records = tuple(records)
    if mode == "alphabetical":
        return tuple(sorted(records, key=lambda item: (item.name.casefold(), item.arch)))
    elif mode == "category":
        return tuple(
            sorted(records, key=lambda item: (item.category, item.name.casefold(), item.arch))
        )
    elif mode == "purpose":
        return tuple(
            sorted(records, key=lambda item: (item.purpose, item.category, item.name.casefold()))
        )
    else:
        raise ValueError("unknown package sort mode")


def _fixed_query(
    argv: Sequence[str], *, timeout_seconds: float = 5.0, max_bytes: int = MAX_BYTES
) -> str:
    if not argv or argv[0] not in {"rpm", "dnf"}:
        raise RuntimeError("package query executable is not allowlisted")
    result = subprocess.run(
        list(argv),
        check=True,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        shell=False,
    )
    if len(result.stdout.encode()) > max_bytes:
        raise RuntimeError("package query exceeded the bounded output limit")
    return result.stdout


def parse_dependency_output(output: str) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                line.strip()
                for line in output.splitlines()
                if line.strip() and len(line.strip()) <= 512
            }
        )
    )


def parse_file_output(output: str, *, limit: int = 2000) -> tuple[str, ...]:
    values = tuple(line.strip() for line in output.splitlines() if line.strip())
    if len(values) > limit:
        raise RuntimeError("installed-file listing exceeded the bounded item limit")
    return values


def enrich_package(
    name: str, *, include_files: bool = True, include_reverse_dependencies: bool = True
) -> dict[str, Any]:
    """Read local dependency/file ownership data for one installed package."""
    if (
        not isinstance(name, str)
        or not name
        or name.startswith("-")
        or any(ch.isspace() for ch in name)
        or len(name) > 200
    ):
        raise ValueError("package name is invalid")
    requires = parse_dependency_output(_fixed_query(["rpm", "-q", "--requires", name]))
    reverse = (
        parse_dependency_output(_fixed_query(["rpm", "-q", "--whatrequires", name]))
        if include_reverse_dependencies
        else ()
    )
    files = parse_file_output(_fixed_query(["rpm", "-ql", name])) if include_files else ()
    return {
        "package": name,
        "requires": requires,
        "required_by": reverse,
        "files": files,
        "network_used": False,
    }


def package_documentation(name: str, *, timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Return bounded documentation evidence shipped by one installed RPM."""
    if (
        not isinstance(name, str)
        or not name
        or name.startswith("-")
        or any(ch.isspace() for ch in name)
        or len(name) > 200
    ):
        raise ValueError("package name is invalid")
    identity = (
        _fixed_query(
            ["rpm", "-q", "--qf", "%{NAME}|%{VERSION}|%{RELEASE}|%{URL}\\n", name],
            timeout_seconds=timeout_seconds,
        )
        .strip()
        .split("|", 3)
    )
    if len(identity) != 4 or not identity[0]:
        raise RuntimeError("installed package identity is unavailable")
    paths = parse_file_output(
        _fixed_query(["rpm", "-qd", name], timeout_seconds=timeout_seconds), limit=256
    )
    return {
        "package": identity[0],
        "installed_version": f"{identity[1]}-{identity[2]}",
        "rpm_url": identity[3] or None,
        "packaged_documentation": paths,
        "documentation_count": len(paths),
        "network_used": False,
        "evidence": "observed:installed-rpm-metadata",
        "limitations": (
            "RPM URL metadata is not necessarily official documentation",
            "official-source refresh is a separate explicit network action",
        ),
    }


def dnf_history(*, timeout_seconds: float = 5.0) -> tuple[str, ...]:
    """Return bounded local DNF transaction history; never contacts repositories."""
    return tuple(
        line.strip()
        for line in _fixed_query(
            ["dnf", "history", "list", "--reverse", "--quiet"],
            timeout_seconds=timeout_seconds,
        ).splitlines()
        if line.strip()
    )


def repository_origins(*, timeout_seconds: float = 5.0) -> tuple[dict[str, str], ...]:
    output = _fixed_query(
        ["dnf", "repoquery", "--installed", "--qf", "%{name}|%{repoid}"],
        timeout_seconds=timeout_seconds,
    )
    values = []
    for line in output.splitlines():
        name, sep, repo = line.partition("|")
        if sep and name and repo:
            values.append({"name": name[:200], "repository": repo[:200]})
    return tuple(values)


def advisories(*, allow_network: bool = False, timeout_seconds: float = 5.0) -> tuple[str, ...]:
    """Read DNF advisories only when network access is explicitly enabled."""
    if not allow_network:
        raise PermissionError("advisory query requires explicit network approval")
    return tuple(
        line.strip()
        for line in _fixed_query(
            ["dnf", "updateinfo", "list", "--available"],
            timeout_seconds=timeout_seconds,
        ).splitlines()
        if line.strip()
    )
