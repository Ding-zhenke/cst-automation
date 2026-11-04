---
name: cst-sessions
description: Manage independent persistent CST environments for separate conversations, including recovery and deduplication.
---

# Persistent conversation sessions

For actual CST work in Codex conversations, use the persistent session entry point by default.
Read [the session guide](../../docs/guides/conversation_sessions.md). Do not change user-global MCP configuration.
Read [project reuse and delivery](references/project-lifecycle.md) for scans, native
checks, relocation checks, temporary tabs, backups and final artifacts.

- Before the first actual modeling call, allocate one conversation-specific recovery reference with
  the CLI or ensure_cst_session. Use an explicit authorized absolute root, normally this repository's
  `work/sessions`, and a fresh UUID reference file in `work/conversations` for each new conversation.
- Retain and report that reference path in the conversation so interrupted work can resume. Later
  turns reuse it. New chats/forks create new bindings unless the user explicitly asks to recover one.
- Route every modeling, configuration, solve and online read through this session with an explicit
  project_id. Never use connect_to_any, last-active-window routing, or standalone setup/close scripts.
- For a new device, default to create_project (an empty MWS/DS project), reusing reviewed modeling
  code rather than importing an old CST as a template. Use an existing project for requested
  continuation/recovery or required project content. Once bound, retain that project across stages,
  scans and retries; a clean start is not permission to discard uncertain work.
- Complete actual-parameter geometry preview and wait for review under cst-modeling before history
  submission. Stable stage_id and request_id identify retries. A preview hash does not prove review.
- Query original job receipts after a timeout/disconnect. Resume the original worker when lost;
  never resubmit uncertain work under a fresh ID or copy/rebuild the original model automatically.
- A failed circuit run_task with explicit returned/saved receipts may leave the session ready
  after project/run identity, saved and disk digests, and absence of prior uncertainty/dialogs
  are verified. The job remains failed and the solver outcome unverified/review_required.
  Review missing numerical evidence before dependent tasks; ready alone does not approve them.
  Missing leaf logs do not by themselves mean an SDK write is still running. Existing historical
  needs_reconcile is not cleared automatically; distinguish that fence from numerical review.
- needs_reconcile requires scene evidence. Do not automatically call reconcile_cst_session: only
  use it after explicit user review of the saved baseline and idle state; preserve evidence levels.
- Keep the working project and its DE while the approved task is active, including replies and
  disconnects. Once modeling is complete and the formal CST plus paired data are verified, use
  session `close_project` to save, close and retire this task's process projects, then delete their
  confirmed process files and paired folders under [project lifecycle](references/project-lifecycle.md).
  This includes `model.cst` copies not originally marked temporary; retain the DE and audit reference.
  Preserve unfinished/uncertain projects, formal deliverables, required dependencies, user-retained
  references and other tasks. Closing the whole DE still requires the user's request.
- If sandbox launch/identity checks fail, preserve exact diagnostics and use the approved execution
  context for this same fixed entry point; do not invent paths, attach targets or launch workarounds.
- Keep native/process/offline/geometry/solver evidence separate. Fake backend never certifies CST.
