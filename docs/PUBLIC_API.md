# cst-automation 与领域包的公共接口

## Design Studio 电路扩展（0.2 开发接口，分阶段实测）

用户已批准 2026-10-19 场路联合设计及真实几何/端口预览；本轮已分阶段实测。具体通过范围和未通过项以 `docs/VALIDATION.md`、`docs/CIRCUIT_LIVE_REPORT.md` 为准。

- `cst_automation.circuit_schema.validate_circuit_spec(spec)` 返回独立、规范化的 JSON 规格；数值元件属性须附显式单位，表达式仅允许安全算术与已声明参数。
- `cst_automation.circuit_preview.preview_circuit(spec, output_dir)` 离线输出 SVG、连接表、参数与输入摘要，不加载 CST。
- `setup.circuit` 为惰性 `CircuitAPI`；`setup.new_circuit_project()` 创建 DS 工程。现有三维接口默认行为不变。
- `cst_solver.circuit.circuit_capabilities(probe='static', app=None)` 静态发现不加载 SDK；live 仅使用显式传入的会话。发现、离线验证、实机读回、solver 验收分别报告。
- `CircuitAPI` 提供 `inspect/list_block_types/list_pins/apply/set_properties/validate/link_em/inspect_dependencies/bundle/run_checked`；仅运行指定任务，不运行所有任务。
- `CircuitResult(path)` 选择 `get_schematic()`，读取结果必须显式指定实际树路径和 run ID；复数 CSV 分实虚列并附元数据。
- CST 2026 实测电路树路径为 `Tasks\\<task_name>\\...`；任务筛选/运行同时兼容原先离线规格的 `<task_name>\\...`，不改写返回的真实路径。结果原始数组无 Quantity 时，单位读取 SDK 的轴标签；仅明确的 S 参数树及空纵轴标签可识别为无量纲，其他缺失单位继续报错。
- `run_checked(task_name, *, mode, expected_results, reuse='never', note='')` 区分 `network` 与 `transient_cosim`，缺目标执行、模式、归属或两侧耦合证据时返回 `unverified`。未实测的证据提取不得推定成功。
- `register_circuit_handlers(service, *, replace=False)` 显式安装路由；已有 handler 默认冲突，显式 replace 时组合旧路由。`params.workflow='circuit'` 才进入电路实现。`build` 对应 configure/inspect/read_results/package，`solve` 对应 run_task，`study` 对应 parameter_sequence。
- `RunService.register_workflow(workflow, handlers, *, replace=False)` 原子注册按 workflow 分流的 build/solve/study handler；显式 replace 允许与已有领域 handler 共存，未匹配 workflow 的任务仍走原 handler，不读取/覆盖其私有状态。
- 保留现有任务 kind/status；电路 `unverified` 映射服务 failed，错误 `circuit_result_unverified`；失败返回可携带 artifacts/run_identity/result_summary/saved，旧默认值不变。
- `cst_mcp.circuit_tools.register_circuit_tools()` 显式注册六个工具；SDK 操作一律进入唯一 worker。预览写文件也限制在服务工作目录。
- 错误码：`circuit_unavailable/spec_invalid/topology_invalid/mode_unsupported/dependency_missing/build_partial/result_unverified/result_read_failed`（每项完整前缀 `circuit_`）。
- 对 SDK 尚不能可靠查询/重定位的属性、依赖或任务完成状态，明确报告 unknown/unsupported，不能以缓存或空值替代。
- 二极管原生类型为 `CircuitSemi\\Diode`；保留离线阶段的 `CircuitSemiconductor\\Diode` 作为兼容输入别名，创建时转换为原生名称。列出类型不代表其非线性求解已经验收。
- `bundle` 先显式保存工程；副本不包含工程根目录的会话锁 `Model.lok`。其他复制错误仍保留失败产物并报错。返回的 staging 标志不自动提升为链接搬运验收通过。
- 实机兼容修正：`set_units()` 使用 CST 2026 的 `Units.SetUnit`，不下发 `Reset/Length`；温度别名 Celsius/Kelvin/Fahrenheit 对应 degC/K/degF，电路量单位由关联 schematic 设置。`create_discrete_port` 使用明确坐标（非拾取点）及官方 `Voltage/Current` 命令；CST 无 `DiscretePort.Folder`，非空 `folder` 在提交前报错，空默认值不下发该命令。
- 运行记录保留消息原始对象；明确的 `type=INFO` 是信息，警告、错误或无法识别的非空消息仍要求审阅。电路原生完成证据须同时包含本次指定任务的新日志段、必要输入完整读回且一致、该任务保存后的当前曲线（run 0）；旧历史 run ID 不由当前执行证明。仅有旧完成日志加无关追加、读取失败的相同未知值、同秒未变化日志均不能证明新执行；真实瞬态联合模式继续要求两侧独立执行证据。
- CST 2026 的同工程离散端口瞬态联合，还须匹配三维日志中的实际任务名、新的三维求解开始/完成记录、原生 `SUCCESS` 状态，以及每个三维端口带 `[cosim <task>]` 标识的电压/电流时域曲线。曲线必须覆盖任务时长；未能校准的外部工程或端口形式继续返回未验证。run 0 始终是保存工程的当前别名，审计摘要和导出的 CSV 用于保留本次数据，不能当作不可变历史编号。

详细签名、规格和验收门槛见 `docs/superpowers/specs/2026-10-19-design-studio-cosimulation-design.md`。本段是扩展协议；能力实测状态以 `docs/VALIDATION.md` 为准。

状态：`0.1.0` 首发接口，见 `docs/VALIDATION.md` 的离线验证边界。此文件是 TPC/em-enclosure 实现领域适配器的接口来源；变更接口时必须同步调整兼容性说明和验证记录。

## 依赖和模块导入

- 通用包名：`cst-automation`；Python 包名：`cst_solver`、`tpc_service`、`cst_mcp`、`cst_automation`。
- 核心导入：`from cst_solver import setup, Result`；数据分析：`from cst_automation.curves import contiguous_bands, find_resonances`；Touchstone 分组文本：`from cst_automation.s2p import read_s2p_groups`。
- TPC/腔体依赖 `cst-automation>=0.1,<1`。本地联调可以配置 editable path dependency；不得把机器绝对路径写进发行元数据。
- 导入 `cst_solver`、`tpc_service`、`cst_mcp` 或 `cst_automation` 不启动 CST，不修改 `sys.path`，不加载 CST DLL。第一次真实 CST 调用由 `cst_solver.environment` 发现/加载本机 CST 安装库。CST 的 `cst` 模块仅随 CST Studio Suite 提供，不从 PyPI 安装。
- Optional extra `mcp` 要求 Python 3.10+，并依赖 `mcp>=1.29,<2`；当前 `cst_mcp` 适配 MCP Python SDK 1.x API。
- 依赖方向：TPC/em-enclosure → 本包 → CST Studio Suite（仅真实 CST 操作）。本包不得 import `mesh_grid`、`topo_modeler`、`topo_templates`、`em_enclosure` 或 `tpc_toolkit`。

## Runtime guard API

```python
from cst_solver.guards import get_guard_state, get_guard_mode, set_guard_mode
```

`cst_solver.guards` 是守卫状态/发现的稳定模块入口；`cst_solver` 包根也继续导出这些名字。`get_guard_state(owner)` 以宿主对象（通常是 `setup` 实例）隔离状态；传入 `None` 得到一次性状态。`set_guard_mode("off" | "warn" | "strict")` 设置进程级模式并返回旧模式。`GuardState`、`GuardFinding`、`CstGuardError`、`assert_gain_mode`、`require_project_file` 等公开符号见该模块的 `__all__`。`cst_solver._guards` 是实现模块，新的领域适配器应导入 `cst_solver.guards` 或包根，避免依赖下划线模块。

TPC 当前源码仍有 `cst_solver._guards` 导入；相同函数已由稳定公开模块转出。将 TPC 调用点迁至 `cst_solver.guards` 属于 TPC 仓库的后续适配，本轮不改动源 TPC。

## 曲线与 S 参数 API

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

## `cst_mcp` 扩展入口

通用 MCP 包导出 `register_tool(name, definition, handler, *, replace=False)` 与 `dispatch(name, arguments=None)`。definition 为 MCP tool definition 字典；handler 接受 JSON arguments dict 并返回 `{'ok': True, ...}` / `{'ok': False, 'error': ...}` 结构。重复名字报结构化 `tool_exists`，未知工具返回 `unknown_tool`。领域包应在自己的可执行入口显式注册扩展，不允许 cst_mcp 自动 import TPC。

写操作需标注为 write tool 并通过 `RunService`；MCP adapter 本身不得直接发 CST VBA。stdio stdout 仅用于 MCP 协议帧，诊断写 stderr/产物。包不安装或改写用户 MCP 客户端配置。

## 兼容与版本策略

- 首个拆分版 `0.1.x` 保留 `cst_solver`、`tpc_service`、`cst_mcp` 导入名，以及源 `curves/s2p` 的函数行为。
- `0.x` 的跨包协议变更按次要版本明确记录；`1.x` 承诺稳定公共 API。新增/移除 handler kind、任务状态、错误码字段或工具扩展行为需更新此文档和测试。
- TPC 提供的 `tpc_toolkit.curves` 与 `.s2p` 延迟兼容入口由 TPC 维护，本仓库不分发旧 `tpc_toolkit`。
