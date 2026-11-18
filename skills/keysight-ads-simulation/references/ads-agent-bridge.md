# ADS Agent Bridge: ADS 2025 compatibility and multi-machine setup

ADS Agent Bridge is a separate third-party product, not part of the CST or Keysight installations. Source: https://github.com/cottman99/ads-agent-bridge. Use this path when an ADS task needs a selected schematic or DDS context; official ADS Python and the dataset remain independent evidence sources. Do not assume that copying this skill installs the Bridge or transfers any local ADS settings.

## Diagnosis and setup on each machine

1. Identify the local ADS version, Bridge package version, and the actual DE/DDS add-on registrations with `ads-agent --pretty doctor --ads-root <ADS-root> --no-ping` and `ads-agent --pretty addon status`. A registration alone is not proof the boot file exists or the add-on loaded. If the file is missing, install the package from the upstream project in a persistent, isolated Python environment and use `ads-agent addon install`; it backs up the DE/DDS registration XML. Do not copy paths, tokens, licenses or runtime records from another machine.
2. For Bridge **0.2.0a2** only, if ADS DE initialization fails because `Application.add_main_popup_callback` does not exist, use the bundled `scripts/ads_bridge_2025_compat.py` with the Bridge environment's Python. Pass the `context_ui.py` sibling of the *registered* `de_entrypoint.py` as `--addon-file`. First run without `--apply` to inspect both target paths, then add `--apply`. The patch refuses unfamiliar code/version and existing backup collisions; it preserves backups. It patches the installed package resource as well as its registered add-on so a subsequent `addon install` retains the fix. After a Bridge upgrade or reinstall, recheck; do not assume an upstream version needs the same patch.
3. The fix makes the unsupported workspace-tree popup optional. Design-window popup registration remains required. If either the tree callback or selection API is absent, report the tree surface unavailable; do not claim the tree context menu works. Preserve all other registered add-ons. Do not restart, close, or attach to another user's active ADS/CST process or alter a running solver.
4. Verify with a new disposable empty workspace and separately identified ADS process, using `ads-agent launch`, `status`, and `bridge ping`/`bridge status`. If startup presents a product/license selection, inspect the actual options and use the user's known choice only when unambiguous; do not guess or change license configuration. A `workspace-ready` DE session, successful ping, and UI status `ready` establish loading, not successful diode simulation. Verify DDS independently when needed. Old windows started before repair may still have stale dialogs; a new process is needed to load new files.

## API only access to an existing desktop session

Install ADS Agent Bridge and its matching EDA Bridge Runtime together in an
isolated environment. Use `ads-agent setup --ads-root <ADS-root> --non-interactive
--skip-skill --no-background-docs` to register the vendor add-ons and retain the
existing Codex skill. Preserve the same `ADS_AGENT_HOME` for setup and client
calls. Use the approved licensed host for ADS operations.

From the independent client, use `ads-agent addon status` to check DE and DDS
registration and `ads-agent bridge sessions` to discover loaded endpoints. For
a managed slot, use `ads-agent status --slot <slot>` and
`ads-agent bridge runtime-snapshot --slot <slot> --profile de`. Match PID,
workspace, and the qualified design or DDS document before an operation.
Submit a versioned `native.execute` request using
`ads-agent runtime execute --request request.json`. Read back the returned
design/window identity, and verify save or DDS reopening separately. Keep
upstream request schemas and capabilities matched to the installed release.

Package installation, XML registration, a loaded endpoint in the target
process, and a successful action are separate observations. An external DE
import or a process found by PID does not attach the bridge. If the session
list has no endpoint for the target and no supported external live loading
path is available, report the missing endpoint. The registered add-on can
load at the next normal launch. Preserve the running session. Use the official
headless API for separately authorized tasks that do not require its window.

### Start and verify a new Windows session without desktop input

If the new process starts a product selector before publishing an endpoint,
check for an existing user-selected product. For an authorized launch on the
licensed host, use [the Windows launcher](../scripts/start_ads_bridge_workspace.ps1)
with the configured `ADS_AGENT_HOME`:

```powershell
& .\scripts\start_ads_bridge_workspace.ps1 -AdsAgent $adsAgent -Workspace $workspace -AdsInstance $instanceId -Slot $slot
& $adsAgent --pretty bridge sessions
```

The launcher sets Keysight's documented `ADS_PRODSEL_PREVIOUS` and
`ADS_PRODSEL_AUTOSTART` only for the launch and reuses the saved product.
Use a fresh slot and a disposable workspace for acceptance. A startup timeout
with a selector present is not a diagnosis of a damaged add-on.

For Bridge 0.2.0a2, the installed Python client's
`ads_agent_bridge.bridge_client.request` can capture DE workspace context
with `request("context_capture_workspace", {}, slot, "de")`. Use the returned
context reference in the `native.execute` envelope. In live mode, verify the
native PID and workspace before calling the schematic window API. Read
`db_design_is_modified` and `db_is_design_read_only` from the exact design
context, and record the latter as editability rather than ownership of all
workspace locks. For DDS, the owning DE can call
`de_open_datadisplay(absolute_path, False)`. Follow up in the matching DDS
endpoint with `context_capture_dds_file` and the exact absolute `path`, then
use live `ads.python.dds` observation to read the open document and its pages.

On Windows with ADS 2026 base, DE API 630 and both bridge packages at
0.2.0a2, this path reached ready DE and DDS endpoints after the new process
used the saved startup product. An independent client opened the editable
scratch schematic, verified its window identity, observed the modified flag
after a native transaction and its reset after save, and independently read
the saved instance from disk. The same client opened a scratch DDS through
DE and read back its exact path and page in the matching DDS process. The
embedded DE add-on loaded without a compatibility patch despite an external
`keysight.ads.de.app` import failure. The preexisting DE and DDS processes did
not publish endpoints and were left running.

## Prior native validation

On Windows with ADS 2025 Update 2 and Bridge 0.2.0a2, an independent DE process initially failed with `AttributeError: Application has no attribute add_main_popup_callback`. After the local capability-gated patch, it opened an empty workspace, reported `workspace-ready`, returned a successful DE ping and UI `ready` with design-window available and workspace-tree unavailable. DDS separately returned a successful ping. The focused context UI tests passed. These are one-machine startup and connection observations; other machines, actual context capture, ADS HB results, and diode/EM convergence require separate validation. One upstream full-suite bootstrap test failed during output decoding in the local Windows environment; do not report the full suite as passing.
