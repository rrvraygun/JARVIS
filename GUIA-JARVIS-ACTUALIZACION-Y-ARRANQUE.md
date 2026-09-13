# JARVIS: updates, capabilities, and startup guide

Updated: September 11, 2026.

In Conversation, the specialist selector and action buttons now form a vertical
sidebar: **New**, **History**, **Copy**, and **Clear** stay below the selector.
When the selector opens, its menu overlays the sidebar without moving the buttons.

The **Agents** tab includes a **Global model** selector. One choice applies to all
specialists and is saved in `runtime/jarvis-model.json` for new turns; active turns
keep their current model. Options are GPT-6 Astra, GPT-5.6 Sol, GPT-5.6 Terra,
GPT-5.6 Luna, and GPT-5.5. **Reasoning effort** and **Context window** are saved
with the model. Context options are Auto, 8k, 16k, 32k, 64k, 128k, 256k, 512k,
800k, 1M, and 1.05M. The controls have their own visible size and open inside
the **Agents** tab.

Live activity is rendered inside the Conversation panel. It stays below your
question while the agent works and moves below the agent response as soon as it
appears. It shows phase, elapsed time, fragments, tool, and query; private details
and unsanitized results remain hidden.

The action rail has a fixed width inside the conversation container. **New**,
**History**, **Copy**, and **Clear** no longer move with a screen-edge anchor;
checkpoint controls remain with their message.

The checkpoint keeps the **↶ Checkpoint** label and its original size. It is placed
on its own row below the message, aligned right with a top separator and a short
side margin. Its menu is built after the button and opens below it in a fixed
vertical layer. The conversation width stays fixed and the button remains
accessible. The menu never overlaps the button or recalculates the side border.

### Conversation and activity fixes — September 12

Permission formats and App Server negotiation were corrected so a greeting can
complete. An authenticated test returned “Hey!”. Package inspection now accepts
the installation specialist's `inspect_packages` alias and recognizes natural
requests such as “node”. A live MCP query confirmed Node.js 22 and 24 with fresh
observations.

Internal missing-observation notices now appear in the activity state instead of
inserting duplicated placeholder messages in the chat. The activity indicator
shows streaming and tools; a tool error is never presented as a successful
inspection. Restart JARVIS to load these changes.

## Delivery state

The updated interface and source are kept in:

```text
/home/tipexxx/Escritorio/Proyecto/codex-agent-system/runtime/staged/jarvis-2026-09-11-recovered
```

The boot and update executors are installed and registered with Polkit. Their
owners and fingerprints were checked by a separate process. The previous main
JARVIS installation was not replaced; start from the path above to use these
changes.

The normal terminal passed a visible test with a real command, and the usual
account connection was checked. Neither result proves a complete agent turn or
a real system update.

## Step-by-step startup

### 1. Enter the new version

Open a regular terminal and do not start JARVIS as root:

```bash
cd /home/tipexxx/Escritorio/Proyecto/codex-agent-system/runtime/staged/jarvis-2026-09-11-recovered
```

Run the following commands from this directory. The executors do not need to be
installed again.

### 2. Test the interface and terminal immediately

```bash
.venv/bin/python scripts/smoke-normal-terminal.py --approve-printf-smoke
```

This test opens the interface, shows a review for one fixed `printf`, runs it
once in the normal terminal, and checks the return to the interface. Confirmation
is automated only for that harmless command. It does not use the model or root
executors.

The final output must include `JARVIS_VISIBLE_SMOKE_PASSED`. SVG captures and a
JSON result are stored in a new directory under `runtime/validation/`, whose path
the test prints.

### 3. Open the interface without connecting to the agent

```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python -m jarvis_tui --bundle-root "$PWD"
```

Use this to explore the views and check that the interface opens. It does not
enable model conversation by itself. Add `--plain` for labels that rely less on
color.

### 4. Prepare this version's private profile

The recovered copy did not include `runtime/codex-home/config.toml`. Before the
first connected start, create the profile with the renderer shipped in the code:

```bash
PYTHONPATH="$PWD/tui/src" .venv/bin/python - <<'PY'
from pathlib import Path
from jarvis_tui.runtime_profile import render, check

bundle = Path.cwd()
profile = bundle / "runtime/codex-home/config.toml"
if not profile.exists() and not profile.is_symlink():
    profile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with profile.open("x") as stream:
        stream.write(render(bundle))
    profile.chmod(0o600)
check(bundle)
print("JARVIS profile verified")
PY
```

This creates only local JARVIS configuration. It does not copy credentials or
change the usual Codex configuration. An existing profile is checked without
being overwritten. If the check fails, keep the error for review instead of
changing controls to force startup.

### 5. Start with an agent connection

```bash
bash scripts/launch-tui.sh
```

The launcher verifies that it imports this checkout and connects to the App
Server using `runtime/codex-home`. Even if the usual account probe passed, this
separate profile may request sign-in.

If **Sign in with ChatGPT** appears, complete sign-in in the official browser,
then select **Refresh session**. Do not copy credential files into the project
or paste passwords and tokens into chat.

As a first request, write: “Reply only JARVIS ready, without using tools”. Check
that the session is connected and that a response arrives. A complete connected
conversation test is not recorded as completed here. Text input is not command
approval.

## New capabilities and improvements

| Area | Implementation and use | Status and scope |
| --- | --- | --- |
| Normal terminal | **Run in normal terminal** in **Development**, with command, directory, and user-authority review. | Tested with a real command; uses the user's normal permissions, I/O, and network. |
| Terminal approval | Separate review from isolated execution, with a durable reservation before launch. | One-use approval, expiry, and replay rejection. |
| Command environment | Binds the environment to the review and detects changes before execution. | Environment values are not stored in the record. |
| Command result | Records attempt, process output, and mode, then returns to the interface. | Exit zero does not prove the full goal or child-process completion. |
| Isolated Cargo | Runs check, build, test, fmt, and clippy on a project copy. | Limits and isolation remain separate from the normal terminal. |
| Dependencies | Prepares changes in a copy and offers reviewed application to the original. | Originals and metadata are retained; application needs its own review. |
| Dependency downloads | One URL/checksum download with a separate approval. | Verified files can be consumed by isolated builds; Cargo has no unrestricted network. |
| Privileged execution | Separate boot/update entries, shared root module, and Polkit policies. | Installed and recognized; every operation still needs an exact request and independent evidence. |
| Kernel selection | Prepares an installed entry for the next boot. | Implemented; no kernel change or reboot occurred in these tests. |
| Initramfs repair | Generates a new image; publication is a reviewed operation that preserves the previous image. | Simulated and tested; does not certify bootability. |
| Updates | Replays a prepared DNF5 transaction with signed RPMs and checks the expected installed set. | Ignore/skip differences are rejected; no real transaction was applied in this closeout. |
| Concurrent-change prevention | Rechecks boot state and transaction fingerprint before effects. | Root maintenance must be exclusive; JARVIS does not lock out other administrators. |
| MCP and specialists | Respects the selected specialist and limits tools by process and scope. | `recovery_plan` registration corrected. |
| Interface | Health, Development, Network, Security, and Recovery views. | Graphical tests completed; slow-task notices alone are not a lockup. |
| Checkpoints | Preserves context and separates chat recovery from operation recovery. | Full recovery only exists when a linked operation is recoverable. |
| Operational records | Sanitized results, size/count limits, and a seven-day policy for new records. | No full environment, credentials, or private reasoning. |
| Recovery | Plans five system boundaries and bounded project recovery. | Full Restic automation and disaster recovery remain separate scopes. |
| Packaging | Manifest and inventory are calculated from the delivery root. | Empty manifests caused by a parent `runtime` directory are rejected. |
| Installation | Pinned hashes, existing-destination rejection, and cleanup of newly created objects on failure. | Installation completed; it does not create operation approvals. |

## How permissions work

The normal terminal runs as the current user. Privileged paths use Polkit and
may show a system authentication dialog. Authentication alone does not approve a
change: the operation must match its request, prior state, independent approval,
and recovery requirements.

The installation created:

```text
/usr/libexec/jarvis-boot-control
/usr/libexec/jarvis-update-control
/usr/libexec/jarvis_privileged_control.py
/usr/share/polkit-1/actions/org.jarvis.boot-control.policy
/usr/share/polkit-1/actions/org.jarvis.update-control.policy
```

Protected state is stored under `/var/lib/jarvis/privileged-control`, including
approvals, reservations, results, transactions, and required copies. No approval
to change packages or boot state was created.

Executors rejected empty Polkit requests with `blocked_or_indeterminate`; that
was the expected result of the probe. In a real operation the same state requires
review and is not success.

## Available checks

To check usual account availability without starting a turn:

```bash
.venv/bin/python scripts/smoke-authenticated.py --approve-account-probe
```

The expected result is `account_available: true`. Its scope is
`authenticated_connection_only`; it does not test a complete conversation.

To verify delivery files:

```bash
.venv/bin/python scripts/verify-release-manifest.py
```

To run the complete validation gate:

```bash
bash scripts/quality-gate.sh --full
```

Let it finish because graphical tests may take several minutes. In a sandbox,
socket tests can be restricted; those tests were checked separately on the host.

## What is not yet complete

- Replacing the previous main installation with this version.
- A complete authenticated agent turn using this delivery's private profile.
- A real approved kernel, initramfs, or package operation and its verification.
- Full backup automation when the external disk is connected and retention of the
  last ten copies.
- Demonstrated recovery boot and a complete current restore of the workstation.

## Where to find details

- [Updated installation and authentication record](runtime/staged/INSTALACION-2026-09-11.md).
- [Validation of the recovered copy](runtime/staged/jarvis-2026-09-11-recovered/VALIDACION.md).
- [Technical patch guide](runtime/staged/jarvis-2026-09-11-recovered/docs/PARCHE-GUIDE-2026-09.md).

This guide describes the state after executor installation. When a historical
document says that a component is pending, use the current installation record
for the current status.
