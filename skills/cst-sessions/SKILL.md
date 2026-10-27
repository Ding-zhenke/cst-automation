---
name: cst-sessions
description: Manage independent persistent CST environments for separate conversations, including recovery and deduplication.
---

# Persistent conversation sessions

For actual CST work in Codex conversations, use the persistent session entry point by default.
Read [the session guide](../../docs/guides/conversation_sessions.md). Do not change user-global MCP configuration.

- Before the first actual modeling call, allocate one conversation-specific recovery reference with
  the CLI or ensure_cst_session. Use an explicit authorized absolute root, normally this repository's
  `work/sessions`, and a fresh UUID reference file in `work/conversations` for each new conversation.
- Retain and report that reference path in the conversation so interrupted work can resume. Later
  turns reuse it. New chats/forks create new bindings unless the user explicitly asks to recover one.
- Route every modeling, configuration, solve and online read through this session with an explicit
  project_id. Never use connect_to_any, last-active-window routing, or standalone setup/close scripts.
- Complete actual-parameter geometry preview and wait for review under cst-modeling before history
  submission. Stable stage_id and request_id identify retries. A preview hash does not prove review.
- Query original job receipts after a timeout/disconnect. Resume the original worker when lost;
  never resubmit uncertain work under a fresh ID or copy/rebuild the original model automatically.
- needs_reconcile requires scene evidence. Do not automatically call reconcile_cst_session: only
  use it after explicit user review of the saved baseline and idle state; preserve evidence levels.
- Leave the DE running between tasks and replies. Close only after the user explicitly asks. A CLI
  or MCP disconnect is not a close request. Close affects only the bound session.
- If sandbox launch/identity checks fail, preserve exact diagnostics and use the approved execution
  context for this same fixed entry point; do not invent paths, attach targets or launch workarounds.
- Keep native/process/offline/geometry/solver evidence separate. Fake backend never certifies CST.
