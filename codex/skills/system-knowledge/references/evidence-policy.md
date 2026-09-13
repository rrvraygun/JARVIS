# Evidence policy

## Source order

1. Current observed state plus installed command version and local help.
2. Installed local man/info documentation.
3. Fedora documentation and package metadata matching the installed release.
4. Upstream documentation matching the installed component version.
5. Fedora release notes, change proposals, advisories, Bugzilla, and maintainer
   statements.
6. Reputable technical references such as ArchWiki and well-supported technical
   Q&A.
7. Fedora Discussion, upstream issues, specialist forums, and user reports.
8. Unverified search results, used only to discover stronger evidence.

Prefer the strongest applicable evidence, not merely the highest-ranked domain.
An upstream page for a different major version is weaker than an installed local
manual. Record URL or local locator, title, publisher, retrieved time, applicable
versions, content hash, and whether the content was complete.

## Conflict handling

- Prefer version-matched official evidence.
- Preserve both claims and describe the conflicting prerequisites.
- Reproduce ambiguity only with a bounded non-mutating test.
- Require user confirmation before community evidence influences an action.
- Suspend a lesson when observed behavior or stronger current evidence conflicts.
- Never silently broaden a command because a forum answer recommends it.

## Evidence labels

Use `observed`, `official`, `upstream`, `maintainer`, `community-corroborated`,
`anecdotal`, or `unverified`. Keep inference separate from sourced claims.

