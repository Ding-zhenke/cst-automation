# 参数修改 → EM → HB 强制检查

本机制在会话提交入口和 worker 执行入口自动运行，不依赖助手主动调用检查脚本。
适用于同工程的数值独立参数 → 原生 EM → network HB 链；不是任意拓扑、
瞬态联合或原生多点 EM 扫描的通用认证器。

## 使用顺序

1. 完成初始建模、保存和审阅。在所属会话空闲时，将用户批准的参数规则、
   原生设置断言和数值门槛写入规格文件。规则来自当前工程，不能用示例默认值代替。
2. 用 `SessionManager.bind_workflow(session_id, credential, project_id, spec)`，
   MCP `bind_cst_workflow`，或会话 CLI 的
   `bind-workflow --project-id <id> --spec-file <absolute-json-path>` 绑定。
   绑定不启动 CST。修改已有规格必须提供当前 `expected_revision`；忙碌时拒绝。
3. 通过原有 submit 提交 `set_parameters`，等待其成功回执，再提交 `solve`。
   若该任务失败但调用和刷新已返回并保存，且依据原回执、相同保存摘要、定向
   reconcile、完整的原生参数及必要实体读回确认同一基线，所属会话可按既有授权
   接续 EM，无需重复写参数。原任务保持 resolved/失败审计，不称 succeeded。
   `depends_on` 只接受 succeeded，不能把原失败任务作为依赖；在审阅完备的条件下
   可不声明该失败任务，仍必须遵守当前绑定规格、版本和执行前原生检查。
   此路线不认证几何、外部依赖、网格或求解，现场不明或证据不足时不放行。
   不把未来参数点和求解提前排入同一队列；输入代数变化会使旧排队请求失效。
4. EM 成功后，从该次实际数据生成数值分析报告，提交
   `accept_workflow_evidence`，参数为 `project_id/em_job_id/report_path`。
   此操作只读文件并存储证据，不取得 CST 工程。
5. 提交 `circuit`，`kind=solve`、`operation=run_task`，目标任务及设置须匹配规格，
   `reuse=never`，明确提供 `expected_results`。执行前重新读回参数、HB 原生断言，
   检查同一次 EM 的报告和全部数据文件摘要。

## 规格及证据

完整字段见 [公共协议](../PUBLIC_API.md#mandatory-parameter--em--hb-workflow-contracts)。
规格 `schema_version=1`，必需字段如下：

| 字段 | 内容 |
|---|---|
| `parameters` | 每个参数的固定 `value` 或 `min/max`，以及 `affects=em/hb` |
| `initial_values` | 绑定时所有声明参数的目标数值，使用工程原生单位 |
| `em_checks`, `hb_checks` | 非空原生断言列表，包含 `source/name/expected`，属性断言另含 `property` |
| `hb_task`, `hb_request` | 实际 HB/父任务名，以及 `mode=network` 等精确请求要求 |
| `evidence_rules` | 报告各数值指标的 `min/max`，不接受布尔通过标记 |

原生断言支持参数、Block 属性和 SimulationTask 属性。使用目标版本实际支持的
getter 和属性名；不可读会拒绝求解，不猜测或忽略。数值期望可带非负 `atol`。
参数表达式、别名、NaN、未声明参数和固定值变化会被拒绝。

报告必须恰含 `em_job_id/em_saved_digest/metrics/artifacts`。`metrics` 提供规格
要求的有限实数；`artifacts` 为非空列表，每项恰含绝对 `path` 和 `sha256`。
系统核对成功 EM 回执及输入代数，重算文件摘要和数值比较，并存储报告快照。
报告是可信分析输入：当前不独立重算拟合算法或证明整个频段的采样覆盖。
覆盖、无源性、拟合误差等指标应来自实际原始数据分析；不得编造数字以放行。

## 失效、失败和升级

EM 参数、几何及 EM 配置变动在写入前清除旧 EM 放行证据。重新运行 EM 也先清除
旧证据，即使新求解失败也不能沿用上一轮。仅 HB 参数变化保留匹配 EM，但强制
重新核对 HB 设置。失败写入仍按原会话规则保留不确定性，不自动回滚或重试。

绑定后的 raw history、非托管 study 和 EM 原生扫参配置拒绝执行；用已有受控逐点
链，或先实现适合该扫描的逐工况证据适配。禁止删除规格、侧车文件或改用旧服务
入口绕过。旧临时 EM/电路服务在构造 CST app 前拒绝已标记工程。

未绑定的原生会话提交参数修改、EM 或电路求解也会拒绝。插件更新不会热更新
正在运行的 worker。旧 worker 缺少 `parameter-em-hb-v1` 能力时，新受保护请求
会被拒绝；原任务、状态查询和原回执不受修改。等现有任务完成且确认空闲后，
再按正常维护流程使用新 worker，不为本功能中断求解。

该机制防止服务入口的流程遗漏，不是阻止直接 SDK、手动 CST 或人为篡改文件的
安全边界；规格没有声明的工程条件也不会自动得到认证。离线测试和实机验收分开记录。

SDK 返回失败时，普通失败回执仍不能放行。仅对已保存结果与 SDK abort 矛盾的特定
情况，使用 [已保存 EM 资格核验](saved_em_qualification.md)；它保留原错误、独立读取
原生结果，不解除保护或触发重算。MOR/DC 与文件交接入口及明确限制见同页。
