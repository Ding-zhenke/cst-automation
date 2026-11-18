# 探索性静态 SP

用户明确指定以某次已保存、未收敛或 failed/unverified 的 EM 结果做静态 SP，并限定不重算 EM 时，授权仅覆盖指定的工程、数据和工况。保留原 EM 回执、警告、来源和收敛状态；SP 与输入均标记为探索性。正式 HB 放行仍按原工作流执行。

1. 优先使用所属会话的受管入口。启动前须可靠保证此次任务不会触发 3D 重算。若原 worker 的门槛不能表达授权，先确认旧队列已冻结、在途调用完整返回、3D 与 DS 均空闲且无待处理弹窗；保留工程身份、保存摘要、原回执和数据。只在排他条件和已有授权成立时，由唯一工程代理使用已核实的 Python 封装与官方 SDK 完成该次 SP。禁止制造资格记录、热换 worker、关闭 CST、并发附加或为取得回执另算 EM。
2. 使用实际端口、阻抗、频段及源状态。CST 2026 的原生 S-Parameters 任务使用 `cst_solver.circuit.linear_sp.configure_linear_sp_task`。频率允许任务局部单位，阻抗须实读继承的 `GetUnit("Resistance")` 为 Ohm，再写端口阻抗；此任务拒绝 `SetLocalUnit("Resistance", "Ohm")`。
3. 创建后部分失败时，先查真实任务、归属、空闲状态和错误阶段。受保护的 `prepare_static_sp` 失败按[部分配置恢复](../../../docs/guides/diode_workflow_integration.md#recover-a-returned-partial-static-preparation-offline-tested-only)处理，由所属会话或持有围栏的调用方用 `inspect_existing_linear_sp`、`complete_existing_linear_sp_task` 审阅并补完已有任务。
4. 保留配置、执行时间、原生日志、正 Schematic Run ID、存储参数、该两端口工况的四条复数曲线，并对照 SP 前后的 3D 日志和结果。日志不变仅支持此次观察，不能代替启动前对不重算的保证。记录独立 EM 求解点和插值输出点各自的数量。
5. 若由外部保存导致会话登记摘要与磁盘不同，两套记录均保留，在后续受控基线操作中核对。禁止补造旧回执、将失败改成成功，或由该次结果宣称网格/宽带收敛。
