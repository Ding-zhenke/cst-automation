# DS 电路任务的截止与停止：调查记录

截至 2026-11-10，本库没有经过验证的 Design Studio 电路任务运行中取消接口；
`RunService.cancel` 只取消尚未开始的队列任务。调用端等待超时、SDK 调用返回、
3D 求解器 abort 或进程消失均不能单独证明目标 DS 任务已停止。

本机 CST 2026.1 `Online Help/advanced/commandlineoptions.htm` 记载 `-c` 启动
Design Studio，`-u` 更新 Design Studio 结果；文档未表明 `-u` 只运行指定任务。
`-b` 的 `Model.run` 脚本选项仅适用于 `-m/-s/-t`，不能直接宣称支持 DS 选定任务。
本机 DS `SimulationTask` 和 `Project` 的已检查方法尚未发现运行中取消命令；
这只是本次文档调查的范围，不证明软件不存在其他接口。

Windows Job Object 只约束实际加入的本地进程。由不同服务或远程调度创建的
计算进程不自动等于可控制的成员；Microsoft 文档明确 `Win32_Process.Create`
创建的子进程不自动加入父进程的 Job。即便禁止 breakaway 并在恢复主线程前
分配 Job，也须实测 CST 启动身份、所有真实求解进程的成员关系、远程任务及
结束后状态。`KILL_ON_JOB_CLOSE` 属于强制终止，不等同原生取消。
来源：[Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects)。

## 必须先完成的隔离验证

1. 建立不使用用户工程的 DS 测试工程；确认实际 task 和依赖，禁止远程或共享求解，
   并核对批处理是否新建独立 DE、不连接已有进程。当前尚未找到能直接确认
   `-c -u` 选定单个任务和不复用已有环境的官方合同。
2. 在新建挂起进程时分配独立 Job，拒绝 breakaway；记录创建身份及每个实际求解
   PID/启动时间/Job 成员，并观察有无外部服务、不同父进程或远程执行。任何
   无法确定或不受控的求解进程均不得触发进程级截止。
3. 使用隔离测试任务独立触发截止，分别记录提交、求解、到期、停止请求、
   全部成员结束及结果回读时间。确认没有残留计算；日志、任务状态及结果不能
   证实停止时保持 unknown。不得以 timeout 替代停机证明。
4. 上述证据成立后，另设计显式选择的进程级模式，保留原生停止与强制终止、
   提交/求解/停止耗时和退出状态。它不能代替所属持久会话或绕过工作流保护。

本轮未启动该批处理测试或停止接口，未修改生产工程，也没有发布进程级截止 API。
