# Typed 设置历史保留

CST 2026 官方 VBA Application.AddToHistory 文档说明：新块与紧邻前块标题相同时，
前块会被删除，原生假定同名对应相同内容。Python Model3D.add_to_history 文档说明其
调用 AddToHistory 创建并执行块，但未单独重述同名压缩规则。所属工程会话通过该
typed 路径观察到：完整配置后紧邻同名稀疏 cap 修改，及连续局部/edge 修改后仅
SnapFalse，保存历史仅剩最后块。维护侧未独立访问现场；这是官方规则与所属会话
原生报告相互支持的缺陷证据，不是维护侧新夹具验收。

0.3.54 对 configure_tetrahedral_mesh、configure_fd_frequency、
configure_fd_parallelization、configure_fd_linear_solver 使用“原标题 + 完整 VBA
内容 SHA-256”标题。只规范化换行 CRLF/CR→LF；不重排命令、不删除字符串空格。
不同内容稳定区分，相同内容标题稳定；A→B→A 仍保留三个连续不同标题的块。
标题体积与历史数量会相应增加。原命令、参数、稀疏语义和调用顺序均保持。

不自动合并或补默认设置、不改端口/几何、不使用 NoModelChange 绕过结果失效；
设置批次仍不 Rebuild、不求解。所有请求依旧整批先校验。提交与执行同时检查实际
worker 的 content-bound-settings-history-v1 能力；旧 worker 拒绝新设置任务，
不自动重启，已在求解的任务不受安装影响。所属会话待空闲后按既有受控交接流程升级。

回执新增 history_caption，仍保留 readback_verified=False；摘要只能证明命令绑定，
不是保存重开或有效设置读回。历史替身模拟相邻同名替换，验证完整 profile→稀疏
修改→保存重放保留前置设置；真实 CST 后续由所属会话在获准空闲点验证。
升级不恢复此前丢失的块，也不提升既有失败 EM 或结果资格。

官方依据（CST 2026 安装根目录下）：

- Online Help/mergedProjects/VBA_3D/common_vbaapp/common_vbaappapplication_object.htm：AddToHistory、AddToHistoryNoModelChange。
- Online Help/Python/source/cst.interface.html：Model3D.add_to_history。

结果不兼容窗口是另一机制。quiet 模式不能抑制需要用户输入的窗口；本修复不自动
选择缓存/删除、不承诺消除窗口。选用“存入缓存”后的旧工程结果与当前工程有效
结果需分别核对，不能把缓存中的旧配置误作当前设置。
