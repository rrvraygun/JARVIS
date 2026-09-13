# Package availability and compatibility plan

> **Status note (2026-08-09):** this document began as a read-only feature
> plan. The implemented current package boundary, including bounded
> development-tool installation, is documented in
> [`current-product-state.md`](current-product-state.md). Statements below that
> all package transactions are disabled describe the earlier planning state.

## Objective

Extend the TUI package inventory from installed RPMs to a navigable view of
packages available from the configured Fedora repositories, including versions,
repository origin, dependency relationships, conflicts, alternatives, and
evidence-backed guidance for choosing between packages.

The feature must never install, remove, update, enable, or disable a package.
It is an information and planning capability only.

## 1. Inventory modes

The existing package view becomes a mode toggle:

- **Installed** — packages currently in the local RPM database.
- **Available** — packages advertised by enabled repositories.
- **Combined** — installed and available records joined by package name and
  architecture.
- **Updates** — available versions newer than the installed version.

Every mode retains the existing views:

- full list,
- alphabetical,
- category/classified,
- purpose-oriented.

Large lists must be paginated or incrementally filtered. The TUI must never
render an unbounded repository result into one log widget.

## 2. Package data model

Each record should carry:

- name, epoch/version/release, architecture;
- repository ID and repository priority;
- vendor, license, URL, summary, description;
- installed state and installed version;
- package size and download size where available;
- provides, requires, recommends, supplements, suggests;
- conflicts, obsoletes, and replaces;
- source package and build metadata where available;
- category and purpose classification;
- evidence source, retrieval time, cache age, and freshness state.

The package identity key is `(name, epoch, version, release, arch, repository)`.

## 3. Compatibility and “same purpose” analysis

The analysis must distinguish three relationships:

### Authoritative package-manager relationships

Read directly from RPM/DNF metadata:

- hard conflicts;
- obsoletes;
- unsatisfied requirements;
- incompatible architectures;
- mutually exclusive providers;
- transaction-level dependency failures.

These are reported as **authoritative metadata**, with the exact package
manager field that caused the relationship.

### Functional alternatives

Packages that provide the same capability are grouped using:

- identical virtual `Provides` names;
- Fedora package groups/environments;
- desktop or hardware role metadata;
- explicit replacement/alternative metadata.

These are reported as **alternative candidates**, not as conflicts. Two
packages may serve the same purpose and still be installable together.

### Inferred similarity

Name, summary, category, executable, library, and documentation similarity may
identify packages with overlapping purposes. This is only an **inference** and
must never be presented as a compatibility rule.

The UI should show a relationship explanation such as:

> `package-a` and `package-b` conflict because RPM metadata declares `Conflicts:`.

or:

> `package-a` and `package-b` are alternatives because both provide
> `video-driver`.

## 4. Repository and version sources

### Local, no-network sources

- RPM database for installed metadata;
- cached DNF repository metadata if present;
- local DNF transaction history;
- local package files and ownership data.

### Explicitly network-gated sources

- current enabled Fedora repository metadata;
- security and update advisories;
- Fedora package documentation and lifecycle metadata.

Network refresh must be a separate, clearly labelled action requiring explicit
user confirmation. A cached result must show its timestamp and repository
metadata expiration state.

The system must never claim “100% reliable” recommendations. Instead it should
use evidence labels:

- **Observed** — directly read from the local RPM/DNF state;
- **Sourced** — supported by Fedora/RPM/DNF metadata or documentation;
- **Inferred** — derived from names, capabilities, or similarity;
- **Unknown** — insufficient or stale evidence.

## 5. Knowledge-base guidance

JARVIS may answer package-selection questions using a structured knowledge
record containing:

- user goal and workload;
- candidate packages;
- required capabilities;
- compatibility constraints;
- hardware relevance;
- evidence references and retrieval timestamps;
- recommendation rationale;
- alternatives considered;
- uncertainty and missing evidence.

Recommendations must be comparative and reversible. JARVIS may explain which
package better fits a workload, but cannot install the recommendation through
this feature.

## 6. TUI design

Add a package mode selector with:

- Installed / Available / Combined / Updates;
- Full / Alphabetical / Classified / Purpose views;
- category filters such as NVIDIA/GPU, Intel, GNOME, lighting, kernel,
  development, audio, networking, virtualization, security, and other;
- architecture and repository filters;
- “show conflicts”, “show alternatives”, and “show updates” filters;
- package detail pane with dependencies, conflicts, files, repository, and
  evidence labels;
- stale-cache and network-required indicators;
- bounded search and pagination.

The full-list toggle expands the current installed list into the selected
available/combined scope without removing the existing sorted views.

## 7. Safety and authority boundaries

- No install, remove, update, downgrade, erase, or transaction execution.
- No shell or arbitrary command input.
- Fixed `rpm`/`dnf` query forms only, with timeout and output limits.
- Network refresh disabled unless separately approved.
- No package recommendation may silently become an approval or transaction.
- Repository metadata and package descriptions are untrusted input.
- Raw repository dumps must not be persisted; store normalized, bounded records.

## 8. Delivery phases

1. Add available-package and version parsers using cached metadata.
2. Add authoritative RPM conflict/provides/obsoletes graph extraction.
3. Add repository refresh as a separately gated, network-aware operation.
4. Add combined/update modes, pagination, filters, and detail views.
5. Add evidence-linked compatibility and recommendation records.
6. Add independent read-only review and adversarial parser tests.
7. Keep all package transactions disabled until a separate mutation project is
   approved.

## Completion criteria

- Installed and available modes are clearly distinguished.
- Full, alphabetical, classified, purpose, combined, and updates views work.
- Version, repository, dependency, conflict, alternative, and ownership data
  are explainable and bounded.
- Authoritative conflicts are never conflated with inferred similarity.
- Stale/cache/network state is visible.
- Package recommendations include evidence and uncertainty labels.
- No package transaction or mutation path exists.
- VM/TUI tests, manifest verification, and an independent review pass.
