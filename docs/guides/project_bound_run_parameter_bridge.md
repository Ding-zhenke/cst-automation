# 工程绑定的存储参数 ByRef 桥接

## 文档契约与验证范围

本机官方帮助 VBA_DES/special_vbacommands/projectobject.htm 的 GetParameterCombination
规定三个参数：固定正 Schematic resultID，以及两个 Variant ByRef（名称数组、double 值数组），
返回 Boolean；不存在组合时返回 False，不支持 Current Run 0。ResultTree 文档负责列出
实际存在的正 ID。这里使用 VBA 处理 ByRef，不假定 Python 代理返回 tuple、数组或修改 list。

该接口目前只有官方文档及离线传输契约验证；未在本 API 聊天执行宏，也未验证 CST/WinWrap
的实际宏编译与桥接行为。回执 native_bridge_verified=False、solver_verified=False；成功解析
替身数据不会修改此标记。后续实机核验属于所属会话的独立证据。

## 优先使用所属会话的显式入口

确认当前求解真正空闲、队列无运行/等待任务、没有未处理弹窗后，保留原 DE 和工程。
更新源码不刷新已有 worker；只由所属会话在空闲后按既有恢复规则加载，不重开正在计算的环境。
首次选择实际 ResultTree 中已有的一个正 Schematic ID，先准备下列通用参数 JSON：

```json
{
  "project_id": "owned-project",
  "kind": "build",
  "settings": {
    "operation": "read_run_parameters",
    "result_id": "Schematic:RunID:3",
    "confirm_idle": true
  }
}
```

示例 ID 是离线占位，不保证实际存在；使用原恢复引用、相同 project_id 和实际枚举的 ID，
通过 sessions CLI submit --operation circuit --params-file 或已有会话 submit API 提交。
不另建绑定，不连接任意窗口。 此查询还要求原 worker 已持有该工程的有效缓存句柄和仍存活的原环境身份；
没有缓存句柄或标签已关闭时直接拒绝，不为读取重开标签、重新 attach 或启动环境。
若刚加载新 worker，先由所属会话独立、明确恢复原工程上下文，再提交此探针。confirm_idle=True 是调用方断言，idle_verified 仍为 False，
不是自动检测结果。已有 needs_reconcile 不因只读查询或该断言被绕过。

MCP 使用既有 submit_cst_session_operation，operation=circuit 并传入上面的 params；
不提供会自行打开/关闭工程的通用查询工具。通用 circuit 服务没有可信 host 的 borrowed_project
标志、借用 factory 及精确路径授权时，在触碰原生对象之前拒绝该操作。该标志不是 JSON 参数。
输出目录固定受 session workdir 限制，不能用请求参数导出到正式目录或其他目录。

## 绑定与审计

读操作仅使用已提供的 project 对象：

1. 原生调用前核对 project.filename() 与已登记的预期工程路径。
2. 仅在 project.schematic 上调用现有 execute_vba_code；宏首先读取
   GetProjectPathName("Project")（官方定义为不带 .cst 的资源主目录），核对预期资源目录。
3. 调用固定的 GetParameterCombination(resultID, names, values)，检查 Boolean、数组维度边界和计数。
4. 写一次全新 token 命名的查询回执；请求清单/生成代码先保存，原始回执保留。
5. 调用后再次核对 filename，解析时核对 token、资源路径、固定 ID、行数、结束标记、
   唯一名称及有限 double 值。截断、缺文件、未解析、错误工程/ID、异常均失败，不重试或猜测。

不会保存工程、关闭标签、修改参数、添加 History、更新任务、启动求解或连接新 DE。
只写会话 workdir 下的查询审计文件。宏异常与不完整输出保留，调用方检查原 job 和审计，
不因输出文件存在就宣称成功。

名称及资源路径用 Hex$(AscW(character)) 的 UTF-16 code-unit 顺序传输，A 对应 0041；
解析器按 UTF-16 BE 解码，支持中文与补充字符，避免本地 ANSI 文件编码改变身份。
数值由 VBA Str$(CDbl(value)) 写成点号十进制/科学计数，解析器拒绝本地逗号或不明确格式；
比较仍采用明确容差，不称十进制文本传输与 double bitwise 相同。

## 接入参数选择器

首次实机只读核验应将一个已知正 ID 的名称/值与所属会话已有的独立原生存储组合逐项比较，
包含一个非默认条件；再确认错误正 ID/Run 0 不会被当成当前 UI 参数。保留工程摘要、
回执、版本与原始日志，只给桥接读取增加证据，不给求解或模板执行增加验收等级。

查询成功后，用返回的 parameters 构建 parameters_by_id，交给
select_schematic_result_id 或传入 resolve_schematic_result_id 的 read_parameters 回调。
只能用于同一目标工程和实际目标节点共同存在的 ID；全套必要曲线和影响结果的参数仍需核对。

这个空闲时的 VBA 查询入口不证明可以在正在执行的 Python Post 回调内嵌套运行 VBA。
不要在 evaluate 中自动调用它：回调嵌套宏/重入，以及真正 Python ByRef ABI 都还需独立
实机核验。对已完成并保存的扫描，可在空闲时先读取固定 ID 的真实组合，再进行只读后处理。
对未来边求解边回调的接入，保留未验证边界，不把当前方案称作自动模板桥已通过。
