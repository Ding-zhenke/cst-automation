# DS 原生扫参与自动后处理：已确认入口与缺口

2026-11-04；仅静态检查仓库、本机 CST 2026 官方帮助和 SDK Python 源码。
没有连接 CST、读取 SDK 结果库、打开工程、执行模板/求解或部署运行库。

## 自动更新必须由原生任务持有模板

DS 的 `Home > Simulation > New Task > Post-Processing` 是原生入口。
官方对话框说明明确：所定义后处理步骤在 solver run 后自动计算；模板列表按顺序执行。
激活状态需要区分：`On` 计算但不保存参数化结果，`On (Parametric)` 计算并保存参数化结果，
`Off` 不自动计算但仍可手动 Evaluate。`Evaluate Current Run` 与每轮求解后的执行方式相同；
`All Runs` 是模板支持的交互式事后重评估能力，不代表每一轮都自动重评估全部旧 Run ID。

输出由框架管理在 `Tasks\<后处理任务>\1D/0D`，并非向固定 `Results` 叶写一次 `.sig`。
因此已有 `write_real_curve` 仍是快照工具；它不会注册任务回调。
已有 `.rtjson` 中找到源码，也不证明该模板已经启用、顺序正确或确实在新 Run 后执行。

## 已有 HB 与原生 Parameter Sweep API

可读源码：`cst_solver/circuit/native.py`。

```python
configure_hb_task(schematic, task_name, tones, *, diamond=False, create=False)
replace_parameter_sweep_sequences(schematic, task_name, sequences)
read_spectral_component(schematic, tree_path, frequency, *, result_id,
                        rtol=1e-10, atol=1e-8)
```

HB 为 `SimulationTask.Type("spectral lines")`；每个 tone 恰含 frequency/order，接受原生参数表达式，
不固化为数值。`create=True` 只建新名称；默认要求已有兼容任务。调用采用实际任务完整路径。
函数仅替换基频定义，不配置源切向、端口激励、偏置或实际源幅度；这些必须已经绑定到所扫电路参数。
频率数字沿用任务当前单位（可能为局部单位），不由参数名称后缀推断单位。

父任务必须已是 `parameter sweep`；序列接口调用 `SetSimulationType(task_name)`、
`DeleteAllSequences`、`AddSequence`、`AddParameter_ArbitraryPoints`，保留子任务，不新建父任务或模板绑定。
一个 sequence 内是各参数点的**笛卡尔积**；sequence 之间分别执行，不是按数组行同步配对。
如需任意配对工况，使用每个工况一个 sequence、每参数单点，避免意外扩大组合。

可构建的原生任务关系为：电路参数扫描父任务下按实际顺序执行 HB 和原生 Post-Processing；
必要时用 Simulation Task Sequence 明确先后关系。官方 Parameter Sweep 处理所有子任务；
Task Sequence 顺序更新全部子任务。实际层级、启用状态与执行日志仍须来源工程验收。
当只扫电路参数并复用已有 EM 数据时，不为后处理额外加入 EM Block Simulation/网格求解任务。
必须另行核对已有 EM 矩阵对全部混频分量及 DC 的覆盖；队列入口本身不保证该覆盖。

官方 `SimulationTask` 还提供：

```text
Reset; Name(taskname); Type(type); Create
MoveInTree(newparent, nexttask)
```

`Type` 在 Create 前设置，创建后不能改；`Name`/newparent 使用完整父路径。
MoveInTree 的 nexttask 是新层级内不带父路径的任务名，空值表示放到该层级最后；
newparent 为空表示顶层。它能调整已有任务位置，**不是嵌入脚本 setter**。
本次不调用这些方法、不生成待执行的工程变更脚本。

## 官方 Python 模板签名

```python
def define(def_params, calling_app, prj, settings):
    # 返回 cst.tbpp.TemplateSettings(result_type=..., eval_type=...)
    ...

def evaluate(eval_params, calling_app, prj, settings):
    # 单结果 return Result0D/Result1D/Result1DComplex
    # 多结果 yield (result_name, result_object)
    ...
```

参数名必须是官方名称，顺序任意，可省略不使用的参数。result_type 支持
`0D/1D/1DC/M0D/M1D/M1DC`；eval_type 支持 `single_run/all_runs`。
上面是签名示意，不能把占位函数当作可计算的派生指标模板。
DS Post-Processing 中 `calling_app=prj.schematic`；在 3D 上下文则是 model3d。
`eval_params.result_id` 是框架传入的运行身份；读取原生输入须传该 ID，不回退到最后一次或 0。
`settings` 是框架持久化的字典，只允许 str/int/float/bool/None/list/dict[str,...] 的递归组合。

### 按 Run ID 读取原生结果

官方 `VBA_DES/special_vbacommands/result_tree_object.htm` 的对象名为 `DSResultTree`，公开：

```text
GetResultIDsFromTreeItem(treeItemName) -> variant array of string IDs
GetResultFromTreeItem(treeItemName, resultID) -> result object
```

ID 示例格式为 `Schematic:RunID:1`，是原始字符串，不应解析成任意整数再回传。
第二个方法可返回 Result0D、Result1D、Result1DComplex、Result2D、ResultMatrix；
没有数据返回 Nothing，错误树路径/不支持数据类型会报错，不能当作零值。
本仓库现有 schematic 桥接使用 `calling_app.ResultTree.GetResultFromTreeItem(path, eval_params.result_id)`；
`read_spectral_component` 正是从该对象读取 x/yre/yim 并唯一匹配频率，不加载外部结果库。

官方 Project 页还有 VBA 签名
`GetParameterCombination(resultID, parameterNames, parameterValues) -> bool`，后两项为输出参数，
可以把 Result ID 解析为参数组合；本次没有推断 Python 对该 by-reference 方法的返回形式。
不以 `GetLastResultID()` 替代模板框架 ID，尤其不能在 All Runs 评估中把每条输出都读成最新结果。
本次静态搜索的官方帮助未找到名为 `ReadResult` 的通用公开方法；若旧脚本有该函数，须取得其实现，
不能把私人 helper 名称当作 SDK 签名。

多输出模板可由框架管理传输/反射、各二端器件实际差分电压及相位结果，但具体算法仍需由项目提供：
传输/反射要有真实入射/出射波与方向、阻抗和归一化定义；有限功率比值不自动等于增量小信号 S。
实际二端电压须按 A−K 复数相减，不能用偏置源代替；相位必须明确频率分量、参考及展开轴。
单次 HB 的谱线轴不等于扫参 RF 轴；跨 run 组曲线要按参数和方向分组，保留各 Run ID、单位及缺项。
这些项目定义和器件数量不作为通用包的默认值。

## 嵌入源码、设置入口与当前缺口

已有通用入口在 `cst_automation/result_templates.py`：

```python
validate_python_result_template(source)
stage_python_result_template(template_source, library_root, *, group, name)
inspect_embedded_python_result_template_files(project_resources, *, metadata_path)
replace_embedded_python_result_template(template_source, project_resources, *,
                                        metadata_path, expected_sha256)
```

stage 只写显式库目录下的 `.rtpy`，不是安装/绑定；replace 只更新已有 `.rtjson` 指向的源码，
保留绑定设置，要求旧源码 SHA-256，仍须在后续获授权时原生保存、重开核验。
inspect 是本次新增离线只读能力：从显式提供的解包副本 `.rtjson` 找到模块，保留原始 metadata、
源码路径及摘要，并静态验证入口。不导入旧源码；即使源码缺失也保留 metadata 与错误。
它不能定位一个不存在的历史外部脚本，也不会扫描正在使用的工程。

同步远端 0.3.5 后，该宽松文件审计命名为 `inspect_embedded_python_result_template_files`，
避免覆盖远端同名但不同合同的 `inspect_embedded_python_result_template(..., expected_settings, expected_sha256=None)`。
后者检查 local_copy、批准设置、源码及 Summary.rpp 对应项；二者都不能证明原生注册或自动运行。

在本次检查的官方 SimulationTask 页面与可读 SDK wrapper 中，**未找到首次绑定 Python 模板、
设置其内嵌源码/字典、切换该模板 Active/Parametric 的公开自动化 setter**。
`Type("template")` 仅证明任务类型存在，不足以创建一个已设置且可运行的后处理模板。
不猜造 `SetTemplate`/`SetPythonScript`，不改写未知 `.rtjson` 字段伪装原生绑定。
首次绑定仍以官方对话框选择库模板为已知入口；之后才可用已存在绑定的源码更新 API。

可读 SDK 的 `cst/tbpp/__main__.py` 是内部执行器，会调用 get_current_project、导入执行模板并使用
`_get_tbpp_startup_info/_set_tbpp_result_info`；**不是离线绑定工具，不能在外部试运行来探测能力**。
本次仅按文本读取该源码，没有导入或调用。

## 本机官方依据与验证

以下相对安装根目录 `D:/CST2026/CST Studio Suite 2026/`：

- `Online Help/mergedProjects/DES/analysis/postprocessing/templatebasedpostprocessing.htm`：原生入口、自动执行、Active/Parametric、Current/All Runs。
- `Online Help/mergedProjects/DES/analysis/postprocessing/tbppoverview.htm`：列表顺序、原生 Tasks 输出。
- `Online Help/mergedProjects/DES/analysis/postprocessing/post_processing_template_layout_python.htm`：define/evaluate、上下文、Run ID、settings、yield。
- `Online Help/mergedProjects/VBA_DES/special_vbacommands/simulationtaskobject.htm`：Type=template/spectral lines/parameter sweep，MoveInTree 等公开任务操作。
- `Online Help/mergedProjects/VBA_DES/special_vbacommands/result_tree_object.htm`、`projectobject.htm`：按字符串 Result ID 枚举/读取结果与参数组合。
- `Online Help/mergedProjects/DES/analysis/simulation/simulation_task_overview.htm`：Parameter Sweep 与 Task Sequence 的子任务语义。
- `Online Help/mergedProjects/DES/analysis/parametersweep/special_solvopt_parametersweep.htm`：sequence 内组合积与 sequence 间独立执行。
- `AMD64/python_cst_libraries/cst/tbpp/data_types.py`、`_impl/module.py`、`__main__.py`：可读的 dataclass、签名检查、框架执行实现。

测试仅使用合成 `.rtjson/.rtpy` 和临时目录；验证只读、摘要、原样设置、未知/缺失源码及路径边界。
完整离线测试结果为 956 passed、3 skipped（缺 MCP extra）、2 deselected（实机/UI 未执行）。
首次受限测试在既有目录联接边界用例中遇到 WinError 5，放行仓库 work 内的临时联接后完整测试通过。
静态语法合格不证明原生绑定、自动更新或指标数值已经通过。工程交付验收仍需在独立获授权的阶段，
更改一个电路参数并运行原生父任务，检查新 Run ID、全部派生输出与设置联动，排除旧缓存/静态快照。

## 补查：ParameterSweep.Start 与 SimulationTask.Update

来源会话报告原生父任务 Update 长时间未返回，且尚无新 Run 的导出/自动报告；
另报告 GUI 曾显示 Creating project file 接近完成、日志独占锁定、solver CPU 累计较少。
本会话未独立复测或读取该工程，不以这些旁证判定求解开始、死锁、失败或成功。
后续来源实测 Start 遇到子进程拥有的 Connection Check；逐 pin 与 Net.Reset 后查询确认的断开项
仅为批准保留的孤立 3D 块。先前 Update 是否也被同一警告阻挡仍未证明，
当前 Ignore 处理计划也不替代新 HB Run ID/结果；证据边界见
[连接检查诊断](connection-check-and-dialog-scope.md)。

官方 `VBA_DES/special_vbacommands/parametersweepobject.htm` 明确给出：

```text
DSParameterSweep.SetSimulationType(task)
DSParameterSweep.EnableSequence(sequence_name, enable)
DSParameterSweep.Start() -> int
```

其示例为选定具名 Parameter Sweep task、定义 sequence/points 后 `.Start`。
页面推荐在 3D 工程 schematic 的 VBA 中使用 `DSParameterSweep`，避免与 3D ParameterSweep 歧义；
本仓库 Python 对象已经限定在 `schematic.ParameterSweep`，不能据此认定存在同样歧义。
`SetSimulationType` 必须先调用；省略或传空值会选顶层扫描并评估工程全部 active tasks，
不应拿空值作为具名父任务的替代。`Start` 虽标为 int，但该页未定义成功/失败码或异步 job 语义；
其返回值不能独立作为全部工况成功的判据。

同一本机官方 `simulationtaskobject.htm` 对 `Update` 明确写为：
执行指定任务，包括全部子任务，且必须先 Name；嵌套 Name 包含完整父路径。
因此 `Reset; Name(parent); Update` 是有文档依据的层级执行调用，不能仅凭它未返回认定调用错误。
`UpdateResults` 才是工程全部任务更新，且不属于 SimulationTask 对象。
两页均未承诺调用立即返回、提供超时取消或保证两种入口的内部路径完全相同；
不能宣称改成 Start 一定解除等待、或等待说明尚未执行任何子任务。
仓库 `cst_solver/circuit/adapter.py` 的 task runner 使用 `.Update()`，
`native.py` 的 `replace_parameter_sweep_sequences` 只配置，不隐式启动 Start/Update。

### 独立核查的配置层级

- 选定父任务：实际类型为 parameter sweep、完整任务名正确，并在 SetSimulationType 中再次明确选择。
- 任务启用：官方 `SimulationTask.SetProperty("enabled", "True/False")`；
  检查父任务、所有中间父/sequence、目标 HB 和 template 子任务，不能只看单个叶。
  disabled sequence 会禁用全部子任务，这是 Task Sequence 的层级语义；不等于 sweep 内的 sequence enabled。
- 扫描序列启用：官方另有 `EnableSequence(name, bool)`，与任务 enabled 独立。
  `AddSequence` 文档未在本次阅读范围明示默认 enabled 值，不把“已经 Add”当作显式启用证据。
  既有序列配置封装尚未调用 EnableSequence；这是需显式验收的配置缺项，不是当前等待的已证根因。
  本次没有修改运行代码或在活动任务中补调用。
- 子任务顺序：HB 必须产生模板所需输入后再执行模板；原生 Post-Processing 模板步骤列表也有自己的顺序。
  `On (Parametric)` 控制模板计算/参数化结果保留，不能替代上述任务和 sequence 的 enabled。
- 参数实际依赖：扫描参数必须真实存在，源和频率等属性须保留原生表达式并依赖这些参数；
  配置已固化的数值不会因为列入扫描而自动变为表达式。原生 `ValidateSetup` 仅检查设置约束，
  需要执行并读消息/错误，不等同全工况求解或依赖语义验收；本次不调用。
- `parallelization="Maximum"` 官方含义是最大可用线程数，不是启动开关，也不保证任务并发、CPU 忙碌或无阻塞。
  不能把低 solver CPU 直接归因为该设置，不能用修改它来猜测解锁。
- 只有确实存在 Simulation Task Sequence 时，再检查其 Loop/最大迭代、Abort if subtask fails、
  Rebuild simulation projects。官方建议 forced rebuild 默认 False；强制重建可能耗时并删除结果。
  不把这些 sequence 专属选项猜作 ParameterSweep 的通用 property，更不为排查而触发重建。

在当前调用未结束时，**不补交 Start、不重复 Update、不改变任务/序列配置、不在第二个引用维护同一工程**。
Creating project file 是来源报告的阶段线索，不证明 HB 已启动；日志锁定、没有旁路文件、主窗无可见对话框
均不足以区分持久化/打包、原生调度、跨进程等待、隐藏模态状态及实际求解。
当前阶段、调用身份、已提交时间和真实窗口/日志证据应由拥有原工程的会话保留，不能由本会话猜测补全。

后续若在独立获授权且确认没有活动任务的副本中进行诊断，可先用单点、无模板的父任务确认原生调度，
再加已有绑定模板并验收新 Run；仅在两次彼此独立的受控运行中比较 Start 与 Update。
这是一组未来诊断建议，未执行，也不构成中断当前任务或再次提交的授权。

### 来源报告：首次绑定与 ^+DS 文件名边界

来源会话通过官方 UI 完成 Python M1D 首次绑定，状态 On (Parametric)，保存后
`template.python_module.type=local_copy`，模块摘要与提供源码一致。
这新增了来源工程的一次绑定/保存证据，不等于全部自动派生输出已验收，也不是公开 setter 已找到。

来源同时实测：带 `^+DS` 后缀的 `.rtpy` 能显示在列表，首次加载传给 Python 的路径却缺失 `^`，
导致 FileNotFoundError；在其实际请求的 `+DS` 路径提供同内容副本后 define 成功。
此为来源报告的具体版本/加载路径现象，本会话未复现，官方本次所查文档未说明该重写规则。
不将复制别名推广为所有模板的安装步骤，不默认重命名已有绑定，不为猜测路径创建副本或覆盖其他模板。
后续离线审计应记录“候选文件路径、实际异常请求路径、两者 SHA、local_copy metadata 指向和保存重开摘要”
各自证据。当前 `stage_python_result_template` 使用受限普通名称，不生成含 `^/+` 的兼容性后缀；
inspect/replace 则按已有 metadata 的准确路径处理，不隐式删字符或回退匹配。

本段仅更新文档；`git diff --check` 用于文档格式核对，没有新增 live validation 或重跑求解测试。
