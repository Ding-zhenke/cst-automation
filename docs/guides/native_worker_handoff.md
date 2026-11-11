# 保留原 DE 的受控 worker 交接

状态：已实现显式试验入口并进行离线测试；真实 SDK 析构、旧 worker 部署兼容性和
DE 存续仍待授权实机验收。普通 worker-upgrade 继续拒绝活 DE；本接口不是默认升级路径。

## 适用条件

- 原任务、后处理及 SDK 调用已完整返回；原会话 ready，无排队任务、未决写入或弹窗。
- 所有登记工程已保存，完整登记摘要与磁盘一致；原 DE 中恰好是登记的未关闭标签。
- 旧 worker 已通过 cooperative-worker-upgrade-v1 协议运行，且已独立确认它借用原 DE。
- 操作者已明确批准这次未完成原生验收的交接，保存了原任务、结果和审阅证据。
- 本入口只读回 Model3D 的空闲及全参数/表达式。原理图任务空闲、非参数修改已保存，
  仍由所属会话审阅确认；缺少确认不能提交。

Python setup.attach 标记 _attached=True；本库没有自动析构关闭逻辑，借用实例 close()
也不关闭 DE。本机 Python SDK 的 connect(pid) 包装器没有 Python __del__，但底层是
编译扩展，因此不能从这些源码推断所有版本的进程退出都保留 DE。协议在旧 worker
退出后重新核验原 DE，丢失时停在冻结状态，绝不自动另建或重开工程。

## 入口与审阅字段

使用原 root、reference 和同一仓库解释器的会话 CLI：

```text
python -m tpc_service.sessions --root <原会话根目录> --reference <原引用文件> begin-native-worker-handoff --review-file <审阅JSON>
python -m tpc_service.sessions --root <原会话根目录> --reference <原引用文件> finish-native-worker-handoff
```

Python 对应 SessionManager.begin_native_worker_handoff / finish_native_worker_handoff；
MCP 为 begin_cst_native_worker_handoff（review 对象）/ finish_cst_native_worker_handoff。
身份凭证沿用原引用；不要创建新会话或替换引用。

审阅 JSON 必须提供下列字段，数值来自现场审阅，不能从示例抄写确认：

| 字段 | 要求 |
|---|---|
| environment_identity | 完整原 DE pid/started/image |
| worker_identity | 完整原 worker pid/started/image |
| project_digests | 全部登记 project_id 到原 saved/disk SHA256 的映射 |
| review_note | 当前审阅记录及本次交接授权说明 |
| required_capabilities | 非空能力列表；新网格接口需 hf-tet-adaptation-controls-v1 |
| confirm_idle | 原任务、原生 EM/原理图均空闲的真实确认 |
| confirm_saved_tabs | 全部标签保存且无未知修改的真实确认 |
| confirm_borrowed_worker | 旧 worker 使用借用 DE 句柄的真实确认 |
| accept_unverified_native_handoff | 已批准本次受控原生交接验收，必须为 true |

begin 只冻结队列、保存审计，不取得 CST 句柄，不请求旧 worker 立即退出。
finish 是有副作用的控制接口；原生读回发生在 finish 和新 worker 中，不可作为普通状态查询。

## 状态顺序

1. reviewing：首次 finish 在已冻结条件下，使用精确 PID 借用已开标签，核验
   全参数/表达式、原生 EM idle、弹窗和磁盘基线；全参数重复读取以检测中途变化。
2. stop_requested：旧 worker 在其空闲循环写 stop_ack 并自行 return；不调用 kill、
   close 或任何模型操作。finish 必须同时看到 ack 和旧进程已退出。
3. starting：再次验证同一 DE/标签/参数。一次性启动令牌原子消费后启动新 worker；
   不确定启动、启动失败或进程丢失都不会自动重试。新 worker 必须在自己的 SDK
   线程借用原标签并复查，不能走普通 Runtime.environment 的创建/重开 fallback。
4. release_requested：finish 请求带新令牌的最终读回；新 worker 在原 SDK 线程
   再次核验后写 release_verified。所有维护阶段都禁止普通任务分发。
5. release_verified：finish 核验令牌、进程、能力、原生证明和不超过 2 秒的观测时效；
   过期则发新令牌重新核验。调用方应以约 0.5 秒间隔轮询 finish，遇异常立即停止推进。
6. complete：解除冻结，保留 last_worker_upgrade 审计、原 job 和原错误。重新确认
   worker 能力后才可提交新参数；交接完成不证明网格、求解或几何验收通过。

大工程的完整文件哈希放在原生观测之前。最终放行窗口比较先前哈希所对应的文件
size/mtime_ns/ctime_ns/inode，防止反复大文件哈希耗尽 2 秒窗口。这不是对恶意保留
元数据篡改的防护，也不是排他锁定用户手动 UI；验收时仍应避免外部操作原 DE。

## 失败时

保持冻结并保存结构化错误（包括实际弹窗证据）。使用普通 status 查看；不要重复
设置任务，不使用 resume/reconcile/普通 finish-worker-upgrade 绕过冻结，不手改
session.json。原 DE 消失、标签缺失、参数/摘要变化、读回未知、缺能力均不能放行。
本版本没有自动放弃或回滚交接入口；需依据具体阶段单独审阅恢复，不能自动重启。

## 实机验收范围

先在独立已保存的小型工程验证旧 worker 正常退出、DE 身份/标签不变、新 worker
借用成功和原结果可读，再由所属会话执行获批的工程交接。留存每次状态、旧/新身份、
读回、时间、摘要与错误。维护端的离线替身测试不替代这一验收。
