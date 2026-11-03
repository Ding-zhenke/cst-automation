# 工程复用、检查与最小交付

## 操作前确定一个目标

记录当前对话恢复引用、session_id、project_id、正式 CST 绝对路径和批准范围。
参数、材料、网格、求解配置、DC/HB/瞬态任务、扫描和扫描角点均复用该工程。
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
   `sequence_name`、`parameters={参数名: 数值列表}`；按需显式 `replace_all=true`。
   该操作只配置，不启动求解。相同 sequence 内各轴为全组合，先核对工况总数。
   低层 API 是 `configure_discrete_sweep` / `add_sweep_parameter_arbitrary_points`。
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

优先检查正式工程的保存基线。确需异路径打开时，使用同一 DE 中的一份临时副本，
登记 `lifetime="temporary"` 和具体 `copy_reason`，复用其检查身份。
禁止为每次失败创建 `relocated_v2`、`portable_v3` 或时间戳副本。
检查通过后，在清理阶段提交 `close_project(project_id)` 并等到 `tab_closed=true`、
`saved=true`、`environment_closed=false`；再删除有确定归属的临时副本。
临时工程应同时返回 `retired=true`，登记已转入审计记录，后续恢复不依赖该临时文件。
检查失败/存在弹窗时先读取现场并解决，不直接删去打开或状态不明的工程。
重连后复用已打开的同路径标签；正常结束只保留正式工程标签。
`close_project` 关闭一个已登记标签；`close` 关闭整个所属 DE，不能混用。

## 审批后的交付只保留必需文件

每个正式拓扑默认保留：

- 最终 `.cst` 与 CST 必需的同名配套数据目录；
- 能复现该模型的建模 `.py`（配置集中保存，避免几十个阶段脚本/JSON/BAS）；
- 需要的示意图仅 `.png`，同一图覆盖更新，不默认生成 SVG/PDF/多版预览。

用户明确要求的独立参考、其他格式或服务器压缩包按其要求增加。
“搬到服务器”本身不要求同时保留多层交付目录、展开包和 ZIP。
阶段回执、恢复引用和日志在既有私有 `work` 中复用；它们不是备份或交付模型。
正在使用的恢复引用/工程不得删除。不要为每次保存、核验、角点、打包建立备份。
用户已要求删除备份时，限定到本任务确认归属的备份与冗余图稿，核对最终文件存在后
直接清理，不额外建立“删除前备份”。不要扫描并删除其他任务或参考模型。

交付报告只说明最终路径、配套建模脚本、已完成的核验和未运行的求解。
相同输入已经通过的检查不因打包、格式变化或回复结束而重复执行。
