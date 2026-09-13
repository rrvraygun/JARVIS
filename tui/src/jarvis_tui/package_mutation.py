"""Conservative natural-language planning for exact Fedora package changes."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import MutationReview, PackageMutationOperation, PackageTransactionPlan
from .package_inventory import PACKAGE_NAME, PROTECTED_REMOVAL_PACKAGES


@dataclass(frozen=True)
class PackageMutationClarification:
    code: str
    question: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class PackageMutationPlanningResult:
    matched: bool
    plan: PackageTransactionPlan | None = None
    review: MutationReview | None = None
    clarification: PackageMutationClarification | None = None
    denial_code: str | None = None
    denial_message: str | None = None


class PackageMutationPlanner:
    _REQUEST = re.compile(
        r"^\s*(?:(?:can|could|would)\s+you\s+|please\s+|por\s+favor\s+|puedes\s+|podr[ií]as\s+)?"
        r"(?P<verb>install|uninstall|remove|instala(?:r)?|desinstala(?:r)?|elimina(?:r)?)"
        r"\b(?P<body>.*?)\s*$",
        re.IGNORECASE,
    )
    _FILLER = frozenset(
        {
            "a",
            "an",
            "and",
            "all",
            "con",
            "e",
            "el",
            "en",
            "favor",
            "just",
            "la",
            "las",
            "los",
            "only",
            "on",
            "package",
            "packages",
            "paquete",
            "paquetes",
            "please",
            "por",
            "related",
            "relacionada",
            "relacionadas",
            "relacionado",
            "relacionados",
            "solo",
            "solamente",
            "system",
            "sistema",
            "the",
            "to",
            "todos",
            "todas",
            "with",
            "y",
        }
    )
    _NONEXACT = frozenset(
        {
            "everything",
            "latest",
            "newest",
            "recommended",
            "todo",
            "último",
            "ultimo",
        }
    )
    _DEPENDENCY_NOTE = re.compile(
        r"\s*,\s*(?:implying|which\s+(?:will|would)\s+remove|"
        r"que\s+(?:eliminar[aá]|desinstalar[aá]))\b.*$",
        re.IGNORECASE,
    )
    _OPTION_REFERENCE = re.compile(r"^\s*(?:option|opci[oó]n)?\s*[1-3]\s*$", re.IGNORECASE)

    def __init__(self, *, identifier) -> None:
        self.identifier = identifier

    @staticmethod
    def _request_text(text: str) -> str:
        # Accept ordinary terminal punctuation and a common accidental trailing
        # '=' without treating punctuation within a package name as valid.
        return text.strip().rstrip(".?!=")

    def recognizes(self, text: str) -> bool:
        """Whether text is a package-operation form, even if it needs one answer."""
        return isinstance(text, str) and bool(self._REQUEST.fullmatch(self._request_text(text)))

    def plan(self, text: str) -> PackageMutationPlanningResult:
        if not isinstance(text, str) or not text.strip() or len(text) > 1_000:
            return PackageMutationPlanningResult(matched=False)
        match = self._REQUEST.fullmatch(self._request_text(text))
        if match is None:
            return PackageMutationPlanningResult(matched=False)
        body = self._DEPENDENCY_NOTE.sub("", match.group("body"))
        normalized = body.translate(str.maketrans("\"'`", "   "))
        raw_tokens = tuple(item for item in re.split(r"[\s,]+", normalized.strip()) if item)
        nonexact = any(item.casefold() in self._NONEXACT for item in raw_tokens)
        invalid = tuple(
            item
            for item in raw_tokens
            if item.casefold() not in self._FILLER
            and item.casefold() not in self._NONEXACT
            and not PACKAGE_NAME.fullmatch(item)
        )
        raw_names = tuple(
            dict.fromkeys(
                item
                for item in raw_tokens
                if item.casefold() not in self._FILLER
                and item.casefold() not in self._NONEXACT
                and PACKAGE_NAME.fullmatch(item)
            )
        )
        if invalid:
            return PackageMutationPlanningResult(
                matched=True,
                denial_code="package_mutation.invalid_names",
                denial_message="The package request contains names outside the exact package grammar.",
            )
        if not raw_names:
            return PackageMutationPlanningResult(
                matched=True,
                clarification=PackageMutationClarification(
                    "package_mutation.non_exact_name"
                    if nonexact
                    else "package_mutation.missing_name",
                    "Which exact Fedora package names should be the DNF transaction roots?",
                    (
                        "Enter one exact package name",
                        "Enter 2-3 exact package names",
                        "Cancel",
                    ),
                ),
            )
        if nonexact:
            return PackageMutationPlanningResult(
                matched=True,
                clarification=PackageMutationClarification(
                    "package_mutation.non_exact_name",
                    "This needs exact Fedora package names. Which packages should I use?",
                    (
                        "Provide exact package names",
                        "Inspect cached package candidates",
                        "Cancel",
                    ),
                ),
            )
        if len(raw_names) > 20 or any(not PACKAGE_NAME.fullmatch(name) for name in raw_names):
            return PackageMutationPlanningResult(
                matched=True,
                denial_code="package_mutation.invalid_names",
                denial_message="The package set is invalid or exceeds the 20-package limit.",
            )
        verb = match.group("verb").casefold()
        operation = (
            PackageMutationOperation.INSTALL
            if verb in {"install", "instala", "instalar"}
            else PackageMutationOperation.REMOVE
        )
        if operation == PackageMutationOperation.REMOVE and any(
            name.casefold() in PROTECTED_REMOVAL_PACKAGES or name.casefold().startswith("kernel-")
            for name in raw_names
        ):
            return PackageMutationPlanningResult(
                matched=True,
                denial_code="package_mutation.protected_package",
                denial_message="Protected or boot-critical packages cannot be removed by this workflow.",
            )
        plan = PackageTransactionPlan(
            plan_id=self.identifier("package_plan"),
            operation=operation,
            packages=raw_names,
            rollback=(
                "Undo uses the authoritative transaction record and requires a separate fresh approval."
            ),
            risk=3,
        )
        review = MutationReview(
            plan.plan_digest,
            "allow_for_user_review",
            "package_review.preview_required",
            (f"Resolve one exact DNF {operation.value} transaction for: " + ", ".join(raw_names)),
            plan.rollback,
        )
        return PackageMutationPlanningResult(matched=True, plan=plan, review=review)

    def continuation_text(self, original: str, response: str) -> str | None:
        """Rebuild one package request from a missing-root clarification.

        Clarification answers are data, not a new model conversation.  This
        keeps valid package continuations on the deterministic route.
        """
        match = self._REQUEST.fullmatch(self._request_text(original))
        answer = response.strip()
        if match is None or not answer or self._OPTION_REFERENCE.fullmatch(answer):
            return None
        return f"{match.group('verb')} package {answer}"
