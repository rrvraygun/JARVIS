# Knowledge lifecycle

## Records

- **Fact revision:** one observed value with collector, timestamp, freshness,
  privacy class, prerequisites, and source evidence.
- **Documentation revision:** immutable content or metadata with version scope and
  a content hash.
- **Command attempt:** exactly one invocation and its sanitized outcome.
- **Error report:** the mismatch between expected and observed behavior, linked
  to the attempt and evidence used.
- **Lesson revision:** proposed reusable guidance with prerequisites, exclusions,
  validation, confidence, and status.
- **Decision record:** concise auditable rationale, not hidden reasoning.

## Promotion

`observation -> diagnosed -> fix verified -> draft lesson -> repeated matching
success -> promotion candidate -> user approved -> active`

Three matching verified successes are the default threshold for candidacy.
Automation may create a candidate but may not approve it. Evidence must be
independent of the original failed attempt and match the lesson's prerequisites.

## Invalidation

Globally prefer an active lesson on the enrolled workstation only while its
prerequisites match. Suspend it after a tool or Fedora version change, conflicting
official evidence, unexpected output, changed side effects, or failed validation.
Create a new revision; never edit or delete the old one.

## Retention

Keep audit events and confirmed lesson revisions indefinitely. Retain bounded
sanitized raw output according to size and diagnostic value, then keep only its
hash and reviewed extract. Legal/incident holds override normal expiry.

