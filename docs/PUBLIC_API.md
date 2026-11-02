# cst-automation 与领域包的公共接口

状态：`0.1.0` 首发接口，见 `docs/VALIDATION.md` 的离线验证边界。此文件是 TPC/em-enclosure 实现领域适配器的接口来源；变更接口时必须同步调整兼容性说明和验证记录。

## 依赖和模块导入

- 通用包名：`cst-automation`；Python 包名：`cst_solver`、`tpc_service`、`cst_mcp`、`cst_automation`。
- 核心导入：`from cst_solver import setup, Result`；数据分析：`from cst_automation.curves import contiguous_bands, find_resonances`；Touchstone 分组文本：`from cst_automation.s2p import read_s2p_groups`。
- TPC/腔体依赖 `cst-automation>=0.1,<1`。本地联调可以配置 editable path dependency；不得把机器绝对路径写进发行元数据。
- 导入 `cst_solver`、`tpc_service`、`cst_mcp` 或 `cst_automation` 不启动 CST，不修改 `sys.path`，不加载 CST DLL。第一次真实 CST 调用由 `cst_solver.environment` 发现/加载本机 CST 安装库。CST 的 `cst` 模块仅随 CST Studio Suite 提供，不从 PyPI 安装。
- Optional extra `mcp` 要求 Python 3.10+，并依赖 `mcp>=1.29,<2`；当前 `cst_mcp` 适配 MCP Python SDK 1.x API。
- 依赖方向：TPC/em-enclosure → 本包 → CST Studio Suite（仅真实 CST 操作）。本包不得 import `mesh_grid`、`topo_modeler`、`topo_templates`、`em_enclosure` 或 `tpc_toolkit`。

## 环境发现与诊断约定

发行包不携带开发机安装路径。未配置时自动发现常见安装目录；显式参数、环境变量、用户 JSON 或兼容的 `config.py` 仍按原有优先级覆盖发现结果。显式配置无效时报告错误，不静默回退到其他安装。

`python -m cst_solver doctor [--json] [--probe]` 始终输出 JSON，`--json` 是显式格式选项。`diagnose_environment()` 保留原有字段；默认离线检查若发现配置的 SDK 目录不存在、没有可发现的 SDK 或已知接口 ABI 不匹配，返回 `status="unavailable"` 并在 `errors` 中给出原因，CLI 退出码为 1。其余未经导入的状态仍为 `not_probed`，退出码 0 只表示离线检查未发现阻断项。`probe=True` 才尝试导入接口；`importable` 不证明许可、工程读回或求解可用。

## Runtime guard API

### 消息观察契约修复（2026-11-02）

`RunContract.after_submit(record, *, messages=None, error=None,
messages_state='not_read', message_source='caller')` 要求直接调用者显式声明消息观察状态。
`run_and_record(submit, *, read_messages=None, note='', message_source='callback')`
自动记录 reader 的调用/迭代状态；setup.run_checked 使用来源 sdk_pending_queue。

新增 messages_state=not_read/read/read_failed、messages_read_attempted、messages_read、
message_source、messages_read_error。messages_clean 是 bool|None：完整读取时为空/非空
对应 True/False，未读或失败为 None。默认/显式空 messages 不构成已读证据；
直接 after_submit 的 read 状态须同时提供 messages。reader 的部分迭代结果保留，读取失败为
read_failed；None 等非可迭代返回按失败报告，不补成空成功。
未读/读取失败时原 succeeded 降为 unverified（messages_not_read/messages_unreadable），
已有 failed 保持 failed。messages_read_error 的旧 record 字段仍接受并优先判读取失败。

warnings_scope=audit；native_warnings_state=unknown、native_warnings=None，
native_solver_status=unknown（当前没有原生状态 reader）。消息队列读空不证明日志无警告。
mesh_convergence/validation_passed 仍与运行契约状态独立，不由未读消息或原生返回推断。

CstBackend 在成功及失败的 result_summary.run_contract 中保留完整运行记录，失败 error.details
亦保留该记录；服务状态/落盘和现有 MCP 查询原样传播，不增加隐式日志读取、求解或工具注册。
这是修复旧的误报成功行为；依赖 messages_clean 恒为 bool 的消费者需处理 None。

### Offline repair additions (2026-11-02)

`cst_solver.native` provides `vba_capabilities(project)`,
`execute_vba(project, code, *, target, timeout=None)`,
`circuit_probe_code(name, pin, reference=None, *, direction_inwards=True)` and
`new_net_code(component_ports)`. Targets are explicitly `model3d` or `schematic`;
no trial execution/fallback after native failure. Builders return VBA, not execution
or readback evidence. Net code uses an empty name, retains the generated name in
`GeneratedNetName`, applies topology and checks each pin's net name.

`cst_solver.host` provides `diagnose_host_session()`, `process_identity(pid)` and
`open_host_session(filename=None, *, pid=None, expected_creation_time=None)`.
The checked session entry refuses inaccessible/unknown desktops; attaching requires
PID plus creation time. It never retries or falls back to creating another DE.
Desktop accessibility does not prove IPC availability or machine idleness.
Legacy `setup` remains available; callers requiring preflight use this checked entry.

Dialog snapshots add process/owner creation identity and classification; raw
decoration snapshots remain in `list_dialogs` with `blocking=False`.
`acknowledge_known_error(snapshot, *, expected_creation_time, button)` requires
complete exact title/body and identity, rechecks them before sending a standard
Win32 button click, and returns `readback_status='required'`; it never clears a
monitor failure or claims recovery. Qt buttons without a supported click path
remain actionable diagnostics.
The initial acknowledgement policy recognizes only exact `History Error` titles
and OK/确定 buttons. Unknown titles are reported, not acknowledged.
Service errors `cst_dialog_monitor_failed` and `cst_dialog_scope_unknown` distinguish
failed observation and unconfirmed ownership from `cst_step_timeout`.

`cst_solver.convergence.mesh_convergence_report(samples, *, target,
expected_frequencies, required_passes=1, max_passes=None, computation_completed=None,
warnings=())` evaluates explicit per-frequency, per-pass Delta S observations.
It preserves residuals and warnings without interpreting them as equivalent to
Delta S. Missing frequency/pass data stays unknown. It does not read native
results or configure refinement. Existing run contracts add
`mesh_convergence='unknown'` and `validation_passed=False`: solver completion
does not certify mesh convergence. No documented explicit CONTINUE selector has
been found; do not substitute ForceRecalculateOldSamples or quiet mode.

```python
from cst_solver.guards import get_guard_state, get_guard_mode, set_guard_mode
```

`cst_solver.guards` 是守卫状态/发现的稳定模块入口；`cst_solver` 包根也继续导出这些名字。`get_guard_state(owner)` 以宿主对象（通常是 `setup` 实例）隔离状态；传入 `None` 得到一次性状态。`set_guard_mode("off" | "warn" | "strict")` 设置进程级模式并返回旧模式。`GuardState`、`GuardFinding`、`CstGuardError`、`assert_gain_mode`、`require_project_file` 等公开符号见该模块的 `__all__`。`cst_solver._guards` 是实现模块，新的领域适配器应导入 `cst_solver.guards` 或包根，避免依赖下划线模块。

TPC 当前源码仍有 `cst_solver._guards` 导入；相同函数已由稳定公开模块转出。将 TPC 调用点迁至 `cst_solver.guards` 属于 TPC 仓库的后续适配，本轮不改动源 TPC。

## 曲线与 S 参数 API

### `cst_solver.Result`：联合枚举与自适应 Pass 曲线

```python
enumerate_result_paths(*, modeler=None) -> dict
read_adaptive_s_parameter(tree_path, *, run_id, frequency_unit=None) -> dict
read_adaptive_s_parameters(*, run_id, modeler=None, frequency_unit=None) -> dict
```

`modeler` 只能由调用方显式传入已授权、与结果工程对应的 Model3D 对象；仅调用其
`get_tree_items()`。不创建/连接/关闭设计环境，不从 setup 或全局对象寻找会话。
默认仅枚举离线 results。枚举返回 `items=[{path, sources}]`（来源为 results/modeler，
精确路径去重，保留来源顺序）、`sources` 状态、`errors` 和 `complete`；读取失败不等于空树。
本接口不验证调用方 modeler 与结果工程的身份对应关系，该核对由调用方负责。

单条读取仅接受完整 `1D Results\Adaptive Meshing\f=...\S-Parameters\S...` 路径，
要求 xlabel 为 Pass、轮次为严格递增正整数，复数 S 数据长度匹配且有限。
返回 `path`、`sources=['caller']`、显式 `run_id`、可用时的 `native_run_id`、
`axis='mesh_pass'`、原始 `xlabel`、独立数组 `passes`/`s_complex`、`parameter`、
`adaptation_frequency`（raw/value/unit/source/unit_source）和 `normalization`。
频率原始标记来自路径；不能解析时 value=None，路径未带单位且调用方未给单位时 unit=None。
不推断工程单位、不转换频率或重归一化。`normalization` 保留
`get_ref_imp_data()` 返回的原生参考阻抗数据及来源、错误；缺失为 unknown，
`wave_definition='unknown'`、`renormalized=False`，不声称完整波归一化约定已被验证。
单条路径、run 或轴/数据错误抛异常，不回退最新 run；显式 run_id=0 仍是原生当前结果别名，
此时保留 run_id=0 和可能不同的 native_run_id；非零 run 与原生 run 不一致时拒绝读取。

批量接口联合枚举后只读取自适应 S 路径，替换每条 sources 为实际枚举来源。
返回 `curves`、`enumeration`、逐路径 `errors`、`complete` 及
`matrix_completeness='not_evaluated'`。没有候选项时 status=not_found，
枚举或读取失败时 status=partial/failed，全部已发现曲线可读时 status=ok；
ok/complete 不证明端口、频率或矩阵齐全。归一化元数据缺失保留在曲线中，不丢弃复数数据。
不做轮次插值、Delta S 排名或原生收敛验收。

普通 `list_s_parameters()` 仅匹配主频率树 `1D Results\S-Parameters\S...`，
不能把 Adaptive Meshing 的 Pass 曲线名称混入普通频率曲线发现、批量读取或导出。
原有通用 `read_1D` 仍按原始轴返回数据；它不将 Pass 曲线认证为频率曲线。

### `cst_automation.curves`

```python
contiguous_bands(
    freqs: Sequence[float], values: Sequence[float], *,
    threshold_db: float, criterion: str = "below",
    max_gap_ghz: Optional[float] = None,
) -> List[Dict[str, Any]]

find_resonances(
    freqs: Sequence[float], values: Sequence[float], *,
    kind: str = "min", min_prominence_db: float = 0.0,
    band: Optional[Tuple[float, float]] = None,
) -> List[Dict[str, Any]]

match_resonances(first, second, *, tolerance_ghz=None, name='') -> Dict[str, Any]
resonance_criterion(first, second, *, limit_ghz=1.0, tolerance_ghz=None,
                    name='') -> Dict[str, Any]
```

保持来源 `tpc_toolkit.curves` 的实际签名和返回结构（实现迁移后由 introspection 与兼容测试固化）：频率单位 GHz；输入曲线为 dB；连续合格点按采样索引分段，可选最大频率间隔；谐振用三点局部极值及 prominence，不插值。输入长度不一致、非法 criterion/kind 等继续抛 `ValueError`。唯一规则实现位于本模块；MCP 适配可包装错误，但不得重写判据。

### `cst_automation.s2p`

```python
read_s2p_groups(filepath) -> tuple[numpy.ndarray, numpy.ndarray]
filter_by_frequency(data, freq_range, atol=1e-6)
filter_parameters_by_condition(data, param_strings, freq_range, threshold,
                               comparison='less', mode='any')
find_param_indices(original_params, selected_params)
```

逐字迁移原函数（以签名检查为准），保持分组文本解析、NumPy 数组返回、标签与异常行为。Touchstone 的其他格式/复数网络矩阵不在此函数承诺范围内。

## `tpc_service` 生命周期与状态

`RunService(workdir, backend=None, *, clock=None, recover=True, autostart=True)` 创建运行服务。默认 backend 是惰性加载 CST 的 `CstBackend`；离线使用必须显式传入 `FakeBackend` 或自定义 backend。worker 单线程串行执行。服务重启时 queued/running 记录标记 interrupted，不自动重跑；排队任务可取消为 interrupted，运行中的 CST 不承诺可取消。`close_project` 只关闭服务拥有的会话。产物必须受限在服务 workdir 中。

```python
service.register_handler(
    kind: str,
    handler: DomainHandler,
    *,
    replace: bool = False,
) -> None

class DomainHandler(Protocol):
    def __call__(
        self,
        *,
        project: Mapping[str, Any],
        params: Mapping[str, Any],
        job: Mapping[str, Any],
        backend: Backend,
    ) -> Mapping[str, Any]: ...
```

`kind` 是 `RunService.submit` 已接受的操作之一：`build`、`solve`、`study`。handler 在调用 `submit` 前注册；它会在唯一 worker 线程同步执行，不能自行并行启动 CST、不能把 session 放进返回值/任务 JSON。`project`/`params`/`job` 是本次调用的只读快照；不得修改它们并假定改动会持久化。`backend` 提供通用 CST 操作能力，领域包可调用其公开方法，不应访问服务私有状态。handler 结果字段与 backend 一致：`ok`、`error`、`log`、`artifacts`、`run_identity`、`result_summary`；有项目保存/求解的操作必须返回 `saved: True` 才可成功。

- 重复注册默认抛 `ServiceError(code="domain_handler_exists")`；显式 `replace=True` 替换同 kind handler。handler 注册仅在当前 `RunService` 实例生命周期有效，不写入磁盘。
- 服务调用每个任务时先查对应领域 handler，再调用 backend 内置同名方法。通用 `CstBackend.build` 与 `study` 不内置领域实现；找不到 handler 返回 `domain_handler_missing`，details 含 `kind`、可操作提示和调用 `register_handler` 的说明。通用 `CstBackend.solve` 接受已有工程并调用 CST，不依赖拓扑结果读回器。
- 传入未知 kind 时由 `submit` 抛 `ServiceError(code="unknown_job_kind")`。
- handler 抛出的异常由服务捕获并记为 `backend_failed`，保留异常类型/文本；handler 可返回 `fail_result(...)` 表达可诊断业务错误。

### 服务稳定方法签名

```python
submit(kind, *, project_id=None, project_path=None, params=None,
       request_id=None, copy=True, overwrite=False, note="") -> dict
get(job_id) -> dict
list_jobs(*, status=None, kind=None) -> list[dict]
wait(job_id, timeout=None) -> dict
logs(job_id) -> list[str]
artifacts(job_id) -> list[dict]
result(job_id) -> dict
open_project(path, *, copy=True, overwrite=False, project_id=None,
             session=None, session_owned=False, note="") -> dict
projects() -> dict
close_project(project_id, *, save=True) -> dict
cancel(job_id) -> dict
shutdown(*, wait=True, timeout=None) -> None
describe() -> dict
```

工程可用 `project_id` 或 `project_path` 指定，提交返回 queued 记录。`wait` 返回当前终态/状态快照；超时返回仍在运行的记录，不等于任务失败。重复 `request_id` 返回既有任务，不重复执行。`get`/`result` 输出保留状态、错误、产物、执行身份和弹窗诊断。完整字段和错误码保持 `tpc_service` 代码文档与测试为准。

## Fake backend 与 handler 示例

```python
from tpc_service import RunService
from tpc_service.backends.fake import FakeBackend
from tpc_service.backends.base import ok_result

service = RunService("./work/offline", backend=FakeBackend())

def offline_build(*, project, params, job, backend):
    return ok_result(saved=True, log=[f"accepted {job['job_id']}"],
                     result_summary={"mode": "offline-example"})

service.register_handler("build", offline_build)
# 提交后由 FakeBackend 支持的异步服务生命周期处理任务。
```

此例只说明 handler 调用协议，不证明 CST 安装、几何读回或求解成功。真实领域 handler 必须用安装的 `cst-automation` API 并单独记录 offline、readback、solver 证据。

FakeBackend 的 `solve` 结果保留请求的 `run_id`（默认 0），用于验证身份字段的传递；`run_token` 仍带 `fake-` 前缀，产物仍为合成数据。

## `cst_mcp` 扩展入口

通用 MCP 包导出 `register_tool(name, definition, handler, *, replace=False)` 与 `dispatch(name, arguments=None)`。definition 为 MCP tool definition 字典；handler 接受 JSON arguments dict 并返回 `{'ok': True, ...}` / `{'ok': False, 'error': ...}` 结构。重复名字报结构化 `tool_exists`，未知工具返回 `unknown_tool`。领域包应在自己的可执行入口显式注册扩展，不允许 cst_mcp 自动 import TPC。

写操作需标注为 write tool 并通过 `RunService`；MCP adapter 本身不得直接发 CST VBA。stdio stdout 仅用于 MCP 协议帧，诊断写 stderr/产物。包不安装或改写用户 MCP 客户端配置。

## 兼容与版本策略

- 首个拆分版 `0.1.x` 保留 `cst_solver`、`tpc_service`、`cst_mcp` 导入名，以及源 `curves/s2p` 的函数行为。
- `0.x` 的跨包协议变更按次要版本明确记录；`1.x` 承诺稳定公共 API。新增/移除 handler kind、任务状态、错误码字段或工具扩展行为需更新此文档和测试。
- TPC 提供的 `tpc_toolkit.curves` 与 `.s2p` 延迟兼容入口由 TPC 维护，本仓库不分发旧 `tpc_toolkit`。
