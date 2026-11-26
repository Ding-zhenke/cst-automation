# 工程复用、检查与最小交付

## 新器件从空工程开始

新器件建模默认通过所属会话 `create_project` 新建空 MWS/DS 工程，不需要查找旧
`.cst` 模板。旧案例用于读取参数和复用可复现的建模代码；提交前检查当前 API、
材料、端口和命令的版本适用性，移除只为清理旧模型而写的删除步骤。
只有用户要求续改/恢复已有工程，或任务需要不可替代的已有工程内容时才导入 CST，
并记录复用理由。不要把有历史错误的工程当模板再靠追加删除、禁用错误步骤来清理。

“从空工程开始”只决定新模型的起点。绑定后的阶段构建、扫参、求解和恢复仍复用
同一工程；发生错误先查原任务及保存基线，不自动新建版本或重放整台设备。

创建/导入先取得所属环境，再登记新工程意图；首次复制输入不按丢失的旧工程处理。已复制或登记后失败时，按[初始意图恢复](../../../docs/guides/initial_project_intent_recovery.md)核对磁盘和原生空闲状态，用现有 API 记录定向处理后在原 project_id 接续；禁止手写 human_reviewed 或重放未知写入。

对已保存且未绑定工作流的空工程，初始参数使用所属会话 `initialize_parameters`。绑定已审阅的保存摘要、完整映射摘要与依赖顺序，使用已有且兼容的空闲 worker；核对原生读回和保存回执。部分写入保留原失败，禁止整批静默重试或临时拼写 StoreParameter history。

## 操作前确定一个目标

记录当前对话恢复引用、session_id、project_id、正式 CST 绝对路径和批准范围。
参数、材料、网格、求解配置、DC/HB/瞬态任务、扫描和扫描角点均复用该工程。
创建/导入到正式位置时，使用显式 `working_path` 与该路径的
`authorize_working_path=true`；续算已有正式文件可用经摘要与归属核对的 `adopt_project`，
不强制先复制成 `model.cst` 再搬运。签名、拒绝覆盖及未知打开的占用保护见
[正式工程路径](../../../docs/guides/session_formal_project_paths.md)。
这些是后续新请求入口，不授权改名、移动或重开当前运行工程；现有任务先沿原引用完成。
只有实际电路连接/几何拓扑改变，或用户需要独立参考工程时才创建新版本。
示意图审批和既有授权可连续覆盖后续配置；不要因例行保存、打包反复索取批准。

使用当前通用库工作区的 `.venv/Scripts/python.exe` 绝对路径，先检查
`sys.executable`、`cst_solver.__file__`、`tpc_service.__file__` 和 CLI `--help`。
不使用命令搜索路径中的裸 `python`，不导入旧 TPC 迁移源中的同名包。
会话根目录遵守仓库约定；在本机通用库工作区固定为其 `work/sessions`，
恢复引用放 `work/conversations`。已有会话继续用原引用，不重新分配。
请求参数用 UTF-8 JSON 文件，复杂 Python 写成 `.py`；避免多层 shell 引号。

## 一次配置，原位核验

1. 先查已安装的源码/签名和能力，再构造请求。没有 API 不猜名称或参数。
2. 参数扫描使用会话 `configure_sweep`：`project_id`、稳定 `stage_id`、
   `sequence_name`、`parameters`；每个参数可用数值列表，或
   `{"mode":"linear"或"logarithmic","start":下界,"stop":上界,"samples":点数}`。
   按需显式 `replace_all=true`。该操作只配置，不启动求解。
   相同 sequence 内各轴为全组合，先核对工况总数。对数范围上下界须为正数；
   零状态另用离散点序列。低层 API 为 `configure_sweep`、
   `add_sweep_parameter_samples(..., logarithmic=False/True)`；离散接口继续保留。
3. 角点在原 `project_id` 上逐一设置、重建、读回，然后恢复默认值并保存。
   不为角点、核验前后或重新打开创建过程模型、另存文件或 DE。
4. 参数、实体材料、体积与点归属通过 `inspect(native_readback=true)` 查询，
   可传 `parameter_names`、`solid_names`、`sample_points=[{id,solid,point:[x,y,z]}]`。
   它不写 history、不重建、不保存；坐标/体积沿用工程几何单位。
   断言、容差比较和报告输出留在 Python。不得把 `Open/Print/Close #`、CSV 导出、
   GetVolume 检查、绝对报告路径或一次性断言写进可重播的建模历史。
   查询错误必须报告；读回不替代重建、求解或数值收敛证据。
5. 当前安装版本没有查询能力时说明具体缺项，先补明确的只读接口；
   不通过追加 audit history、禁用错误历史或修改原生缓存来伪造检查通过。

## 临时检查标签有明确终点

优先检查正式工程的保存基线。确需异路径打开时，在同一 DE 登记一份 `lifetime="temporary"` 的副本，写明 `copy_reason`，复用该检查身份。结束后按[关闭、退休和清理](../../cst-project-lifecycle/SKILL.md#关闭退休和清理)核对回执和路径。

## 审批后的交付只保留必需文件

按[核对正式交付](../../cst-project-lifecycle/SKILL.md#核对正式交付)确认最终 CST、配套目录、依赖和用户要求的文件，完成本任务过程工程的收尾。
