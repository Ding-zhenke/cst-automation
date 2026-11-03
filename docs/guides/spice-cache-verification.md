# SPICE 缓存身份修复

2026-11-03。实现范围为文件型 `configure_nonlinear_model`；仅离线验证，未连接 CST，未部署运行时。

原实现将 `GetFile()` 返回值与源路径相等作为验收条件，误拒绝工程内部缓存。
现保留两个路径的含义，比较批准源快照与实际引用文件的 SHA-256；路径相同也不能绕过内容检查。
相对引用只按绑定工程文件的父目录解析；没有明确基准时保持 unknown，不使用工作目录或源文件兜底。

`readback.spice_verification` 分别记录内容、模型、显式方言、端口名称/顺序及缓存归属。
归属确认要求解析后的目标位于当前工程资源的 `Model/DS/Block/<block_name>/`；
工程资源内其他未校准布局保持 unknown（包括无法绑定的其他 block/numeric 目录），资源外引用为归属不符。
直接引用源文件标为 `source_reference`，缓存归属保持 unknown。
明确不一致为 `circuit_build_partial`，各维度证据保留在失败 readback；缓存文件不可读、缺基准及不可解析声明保持
unknown（JSON null），返回 `verification_complete=False`，不是通过。
原生 metadata/pins 查询异常仍沿用部分失败合同，保留已有读回和异常，不伪造未完成的核验表。

端口解析仅覆盖唯一的简单 `.SUBCKT` 声明；多模型文件按显式选中名称寻找，重名、复杂参数/续行、
未知编码不猜测。include/lib 依赖不展开，闭包保持 unknown。`pin_mapping_verified` 仅比较端口名称/顺序；
接线、极性、完整电气语义没有据此验收。`verification_complete` 仅汇总上述身份维度，不验证接线、
保存重开或求解；整体 `readback_verified` 和 `solver_verified` 仍为 False。

离线回归使用合成模型与临时目录，覆盖不同路径相同内容、相对引用和 cwd 隔离、跨工程/未绑定 block、
源快照变更、内容/模型/方言/端口不一致、缓存不可读、直引源文件及未知依赖/复杂声明。
先复现旧断言失败，再实现修复。完整离线测试：949 passed、3 skipped、2 deselected；
跳过项缺少 MCP extra，真实 CST 与 GUI 测试未执行。

没有新增服务操作或隐式连接，没有调用 `SetCacheFiles`，没有自动保存、重开、重导入或求解。
