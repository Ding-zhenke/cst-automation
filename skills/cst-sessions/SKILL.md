---
name: cst-sessions
description: Manage independent persistent CST environments for separate conversations, including recovery and deduplication.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# Persistent conversation sessions

Run session commands and background workers without a visible console window.
On Windows use the applicable hidden launch options and retain logs and errors;
show an interactive console only when the user explicitly requests one. This
does not dismiss or conceal CST dialogs needed for diagnosis.

Routine status, stop review, parameter updates and saved-baseline acceptance reuse
the [existing operations and examples](../../docs/guides/reusable_operations.md).
Do not turn an API status check into GUI control or a worker restart. Maintenance
development runs independently of engineering optimization; new code/installed
skills do not establish that the active worker loaded them.

参数修改 → EM → HB 使用[强制工作流接口](../../docs/guides/workflow_enforcement.md)：
空闲时绑定工程规格，提交入口与 worker 自动检查。不能用可选 checklist、
`passed=true` 或助手承诺代替；旧 worker 能力不符时等待安全升级，不重启正在求解的环境。

For actual CST work in Codex conversations, use the persistent session entry point by default.
Use [in-situ validation](../cst-in-situ-validation/SKILL.md) to validate and improve automation while carrying out the authorized engineering task.
Read [the session guide](../../docs/guides/conversation_sessions.md). Do not change user-global MCP configuration.
Read [project reuse and delivery](references/project-lifecycle.md) for scans, native
checks, relocation checks, temporary tabs, backups and final artifacts.

For multi-turn builds, EM→circuit handoffs and optimization, maintain and reload
the [workflow checkpoint](references/workflow-checkpoint.md) before continuing.
It preserves the latest requirements and binds each observation to its actual
inputs; run its read-only checker before dependent submissions. It does not
replace native inspection or the session's job/recovery checks.

At task start identify the exact project and saved baseline and obtain explicit
user confirmation if it has not already been given. Record the authorization,
scope, project identity and baseline evidence in the conversation checkpoint.
That authorization persists through discussion and later turns for the same
baseline and already authorized recovery, modeling and solving. Do not ask the
user to repeat it merely because another turn or review step occurred. Verify
current job state, file identity, idle state and evidence independently; renewed
review is needed when an unconfirmed write, material baseline change or unknown
scene makes the existing authorization insufficient.

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
- Initial create/import obtains the existing environment before registering the new project
  intent; do not treat a first copied input as a missing old reviewed tab. For an already failed
  copied/registered import, follow [initial-intent recovery](../../docs/guides/initial_project_intent_recovery.md):
  no automatic replay or review bypass; genuinely review disk/idle, record resolution through
  the existing API, then inspect/continue the same project ID. Never hand-write human_reviewed.
- Query original job receipts after a timeout/disconnect. Resume the original worker when lost;
  never resubmit uncertain work under a fresh ID or copy/rebuild the original model automatically.
- Cooperative worker upgrade requires `cooperative-worker-upgrade-v1`, an idle unfenced session,
  and, for native sessions, a verified absent DE. Freeze first through the documented begin/finish
  API and retain the frozen state until the replacement advertises the requested capabilities.
  Legacy workers cannot respond to this protocol; ordinary upgrade does not preserve a live DE.
  Do not force-stop a worker, close a DE, or represent fake tests as native upgrade evidence.
- For an explicitly approved preserved-DE native handoff trial, use the separate
  [native worker handoff](../../docs/guides/native_worker_handoff.md) protocol.
  Read its entire procedure before use. It freezes, verifies, cooperatively exits,
  verifies the exact original DE and repeats native checks on the replacement's SDK
  thread before a fresh token-bound release. No create/reopen/force-stop fallback.
  The owning session reported native acceptance of a 0.3.44 independent small project,
  including failed-launch recovery and client interruption continuation, with unchanged
  DE/tab/test parameter and synthetic three-point stored curve. No EM was computed:
  this does not certify physical results, real EM/HB preservation, all SDK/worker versions
  or the main engineering project. Preserve target-specific review and authorization;
  do not infer approval from installing new code. See the guide and VALIDATION record.
  Windows launcher/actual-worker PID differences require the protocol's nonce and
  parent-identity admission, never a relaxed identity comparison. A consumed launch
  that failed before admission uses only the guide's explicit reviewed recovery;
  confirm the entire failed process tree is gone. Recovery does not launch a worker.
  For a worker that created its DE, use the guide's explicit owned path and its
  separate exit-risk acceptance; confirm_borrowed_worker must be false. Validate
  an actual owned-worker small-project handoff before the engineering target.
  A creator process exiting with its DE intact alone is not full handoff acceptance.
  The owning session subsequently reported 0.3.46 owned-worker handoff acceptance
  on both an independent synthetic-data project and its reviewed engineering target:
  original DE, registered tabs, full parameters and current result tree remained.
  Existing unqualified matrices remained unqualified. This is scoped lifecycle
  evidence, not matrix-value equivalence, EM/HB success or universal SDK compatibility.
- A failed circuit run_task with explicit returned/saved receipts may leave the session ready
  after project/run identity, saved and disk digests, and absence of prior uncertainty/dialogs
  are verified. The job remains failed and the solver outcome unverified/review_required.
  Review missing numerical evidence before dependent tasks; ready alone does not approve them.
  Missing leaf logs do not by themselves mean an SDK write is still running. Existing historical
  needs_reconcile is not cleared automatically; distinguish that fence from numerical review.
- Geometry validation may return unverified with INFO messages despite a normally returned
  Rebuild. A fully identified returned/saved failure remains failed/review_required; ready is
  not geometry/dependency acceptance. For an existing geometry fence, use the explicit
  [bounded read-only review](../../docs/guides/geometry_validation_review.md) only after actual idle
  confirmation and digest checks; it never rebuilds, saves, opens missing tabs or clears the fence.
- A ready session with a reviewed external file save uses the separate
  [saved-baseline acceptance](../../docs/guides/conversation_sessions.md#接受已审阅的外部保存) operation.
  Require old/new digests, original idle open tab, complete native parameters,
  reviewed block types/properties and explicit authorization. Do not manufacture
  a failure fence, call reconcile on ready, or hand-edit session state. Acceptance
  invalidates old EM/HB evidence; it does not approve a solve or change parameter ranges.
  Existing incompatible workers are refused, never automatically restarted.
- A returned 3D abort, Model3D running=False, ready or completed reconcile does not
  certify DS sequence idle. Before handoff after a stop, read
  [stop scope](../../docs/guides/solver_stop_scope.md). Pending Abort scope confirmation
  or unknown DS/postprocessing state prevents new writes and handoff; do not reuse
  an earlier idle assertion or infer idle from log-file lock release.
- needs_reconcile requires actual scene evidence and a matching explicit baseline authorization.
  Reuse existing authorization when its scope covers the reviewed recovery; do not invent user
  approval. Resolve only the explicitly reviewed uncertain job IDs, never unrelated failures.
  Reconcile does not certify the solver, erase original errors or authorize replay.
- For a returned 3D History Error with a changed saved file and a verified successful
  native archive, read the entire [fenced archive recovery procedure](../../docs/guides/model3d_archive_recovery.md).
  Use the controller begin/finish interface to freeze, preserve the failed companion,
  cooperatively retire stale handles and restore the exact archive in the same DE.
  Do not substitute schematic recovery, ordinary reload, partial companion copying
  or preemptive reconcile. Completion still requires targeted scene reconciliation;
  ambiguous mutations are not replayed. The owning session reported one complete
  0.3.61–0.3.65 native recovery and handoff; see VALIDATION for its limited scope.
  Preserve native Discrete port mode counts of 0 in recovery inventories; only
  Waveguide requires a positive count. Do not replace the observed 0 with 1.
  The archive backup excludes only its root Model.lok, recording metadata and
  explicitly uncopied content. Continue an empty uncommitted backup only through
  the same reviewing transaction; never delete a partial snapshot to retry.
  For the exact pre-close companion-difference refusal after worker exit, use the
  guide's explicit full-hash SimProps drift review. It preserves Temp deltas and
  the original backup/token; other content changes or any close intent refuse.
  After a verified reopen rejected only for the guide's exact three reviewed INFO
  messages, use postopen review, never restore/close/open again. This read-only
  continuation still requires full identity/history/parameter/port checks and
  does not certify geometry, external dependencies or solving.
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
- For existing EM parameter points, `set_parameters` uses the session-owned
  `app.update()` and message validation; `solve` does not add a full rebuild.
  Full `Rebuild` on geometry/history operations can delete results: preserve
  required history before topology changes. Native save/reopen acceptance remains separate.
