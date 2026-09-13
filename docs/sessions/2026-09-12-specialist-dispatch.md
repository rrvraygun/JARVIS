# Specialist greeting dispatch fix

The prior classifier-only fix missed broker.prepare_turn_request, which still
sent readOnly.access. Removed that field from specialist dispatch as well,
retaining readOnly/networkAccess=false and the existing granular approvals.
The current-user native read scope is documented in tui-contract.md.

A live probe then exposed another protocol rejection:
askForApproval.granular requires experimentalApi capability. Initialization now
declares experimentalApi=true; no execution authority or approval is granted by
that negotiation. Tests cover the handshake and exact permission payloads.

After the second correction, a separate authenticated App Server session using
the candidate's own profile accepted a fixed greeting, returned "Hey!", and
reported turn status completed with error=null. This probe exercised the live
transport and model using the dispatch permission payload, not a full TUI click
flow or a privileged operation. No credentials were copied or printed.

Final focused validation: 46 tests passed across App Server, broker and session.
Independent dispatch_review reviewed the permission correction. Existing
conversations and failed audit records were retained; no failed task was replayed.
Restart JARVIS to load the corrected modules and submit a new greeting.
