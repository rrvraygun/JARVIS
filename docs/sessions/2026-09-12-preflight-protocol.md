# Preflight protocol correction

The reported Node inspection request failed before a classifier turn ID was
returned. Reproducing its payload against the installed Codex App Server using
an intentionally nonexistent thread returned -32600: readOnly.access is no
longer supported. No model turn or host operation ran in this diagnostic.

Changed the classifier policy to type=readOnly, networkAccess=false, retaining
approvalPolicy=never. The same protocol probe then reached thread lookup and
returned thread not found, proving the original validation rejection is gone.
This is not an end-to-end successful classifier/model result.

The session regression asserts the complete sandbox payload. All 28 session
tests passed before adding that assertion; the final focused run includes it.
Independent reviewer protocol_fix_review confirmed the wire correction and
identified the read-scope implication, now reflected in the TUI contract:
standard current-user reads, not a documentation-only filesystem restriction.
No root helpers, credentials, existing conversations or audit records changed.

Restart JARVIS to load the corrected Python module, then submit the original
request once. The clipboard warning is independent and was not modified.
