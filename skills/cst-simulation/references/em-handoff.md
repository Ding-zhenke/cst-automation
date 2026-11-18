# EM 交接与验证

正常返回保存但有原生警告的 EM，可按 [探索性保存结果证据](../../../docs/guides/saved_em_qualification.md#警告结果的外部探索性证据)
创建外部 ADS 探索用独立回执，保留失败和警告；它不生成 Touchstone、不满足
服务内 HB 放行、不认证网格收敛。必须分别核对外部文件映射、DC 和全部混频覆盖。

Before HB consumes new or changed EM data, apply the [HB coverage and stop gates](../../cst-circuit/references/hb-and-postprocessing.md#hb-运行前的放行门槛). Read each actual passive block/file's valid data interval, including 0 Hz and the highest retained mixing frequency from actual tones/orders; a global frequency setting or a reference NPORT on another topology is insufficient. After topology/EM changes, pass bounded representative forward/reverse cases (DC operating point, actual RF incidence/matching and spectra) before the full parent sweep. The first initialization/numerical failure stops later groups and dependent templates without valid current-run inputs. These are caller orchestration requirements, not capabilities implied by the EM solver or HB configuration wrappers.

For multi-stage work, reload the [workflow checkpoint](../../cst-sessions/references/workflow-checkpoint.md)
and check the requested stage before submission. Compare available evidence to the
latest requirements, not merely to the script's defaults; record explicitly waived
unavailable readbacks rather than silently inventing or blocking on them. A representative-point
check is an intermediate gate: retain the authorized full sweep and its expected
case set as a pending deliverable. Native warning review and numerical acceptance
remain separate from checklist consistency.
