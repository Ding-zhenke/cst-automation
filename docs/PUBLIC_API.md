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

FakeBackend 的 `solve` 结果保留请求的 `run_id`（默认 0），用于验证身份字段的传递；`run_token` 仍带 `fake-` 前缀，产物仍为合成数据。

## `cst_mcp` 扩展入口

通用 MCP 包导出 `register_tool(name, definition, handler, *, replace=False)` 与 `dispatch(name, arguments=None)`。definition 为 MCP tool definition 字典；handler 接受 JSON arguments dict 并返回 `{'ok': True, ...}` / `{'ok': False, 'error': ...}` 结构。重复名字报结构化 `tool_exists`，未知工具返回 `unknown_tool`。领域包应在自己的可执行入口显式注册扩展，不允许 cst_mcp 自动 import TPC。

写操作需标注为 write tool 并通过 `RunService`；MCP adapter 本身不得直接发 CST VBA。stdio stdout 仅用于 MCP 协议帧，诊断写 stderr/产物。包不安装或改写用户 MCP 客户端配置。

## 兼容与版本策略

- 首个拆分版 `0.1.x` 保留 `cst_solver`、`tpc_service`、`cst_mcp` 导入名，以及源 `curves/s2p` 的函数行为。
- `0.x` 的跨包协议变更按次要版本明确记录；`1.x` 承诺稳定公共 API。新增/移除 handler kind、任务状态、错误码字段或工具扩展行为需更新此文档和测试。
- TPC 提供的 `tpc_toolkit.curves` 与 `.s2p` 延迟兼容入口由 TPC 维护，本仓库不分发旧 `tpc_toolkit`。
