# 消息读取三态契约（已实施，离线验证）

2026-11-02。来源会话报告：`run_checked(..., read_messages=False)` 返回空 messages、
messages_clean=True 和空 warnings，但同次原生日志包含最大自适应轮次终止和低质量四面体警告。
现已在仓库源码实施并完成离线验证；没有打开工程、连接 CST 或修改已安装运行环境。
来源会话提供的只读证据文件未纳入通用仓库，也未据此推断设备性能。

## 修复前的代码原因

- `cst_solver/simulation/solver.py` 的 run_checked 在禁用读消息时将 reader 设为 None。
- `cst_solver/run_contract.py` 的 run_and_record 将 messages 初始化为 []；没有 reader 时
  仍把 [] 交给 after_submit，没有记录“未尝试读取”。
- after_submit 使用 `messages_clean = not message_list`，因此把“未读取”和“已读取且为空”
  混同。读取异常也可能在输出中留下 messages_clean=True，虽然 status 已降为 unverified。
- warnings 当前主要记录审计/落盘相关提示，不是 Model.log 中全部原生警告的收集器；
  空 warnings 不能证明原生日志无警告。

## 已实现状态字段

| 场景 | messages_state | messages_read_attempted | messages_read | messages_clean |
|---|---|---|---|---|
| 显式禁用或未提供 reader | not_read | False | False | None |
| reader 完整成功，返回空队列 | read | True | True | True |
| reader 完整成功，返回非空队列 | read | True | True | False |
| reader 调用或迭代失败 | read_failed | True | False | None |

messages_clean 为 True/False/None 三态；messages_state 区分 unknown 的原因。
messages=[] 可以保留兼容容器，但不能再单独用它判定干净。读取失败保留异常和已读取的
部分消息（若能捕获），不以部分迭代当完整成功，不回补干净状态。

显式保存 message_source 与检查范围，例如 sdk_pending_queue；消息队列读取成功也不能证明
Model.log 没有历史警告，因为消息可能已被其他读取者清空，且队列和日志的覆盖范围不同。
若将来读取日志，记录独立 log_status、路径/运行归属、原始严重性及证据，不能静默混入队列来源。

after_submit 的直接调用者需要显式提供 messages_state/消息来源，不能由默认 messages=None
或 messages=[] 猜出是否实际读过。新增参数及兼容策略已写入 PUBLIC_API。
对直接提供消息列表的情况，来源应记为 caller，不能谎称 SDK 队列已被读取。

## 运行结论与警告范围

- 未读/读失败：消息干净条件未建立。在现有“消息干净才 succeeded”的契约下，
  原本可能为 succeeded 的结果降为 unverified，带 messages_not_read/messages_unreadable
  诊断；已有异常或原生失败仍保持 failed，不能被证据缺失降级为较轻状态。
- 警告列表必须区分审计提示与原生警告。未检查原生日志时 native_warnings 状态为 unknown，
  不能把 [] 当“原生无警告”。可在现有 warnings 中加“消息未读取”的审计提示，但不伪造原生警告。
- native_solver_status 仅依据明确原生状态，缺失时 unknown，不能由“调用未抛异常”推为 SUCCESS。
- mesh_convergence 独立：达到 MaxPasses 且 Delta S 超过目标为 not_converged；未读取收敛证据
  为 unknown。原生 solver SUCCESS 与 not_converged 可以同时成立。
- validation_passed 不能仅因 native SUCCESS、结果指纹变化或消息容器为空而为 True。

布尔三态会影响消费者：尤其检查 `messages_clean is False` 的调用方，需要同时处理 None。
服务/MCP/落盘协议须覆盖新字段，不能只改返回 JSON 标签而保留旧成功判定。

## 离线验证范围

1. 使用假 solver、假指纹和假 sink 验证 read_messages=False 完全不调用 reader，
   输出 not_read/False/None，status 不因空消息变 succeeded；不启动或连接 CST。
2. reader 返回空/非空列表、调用异常、迭代中途异常：逐一验证表中状态、错误、原始消息保留。
3. 提交异常且消息未读/读取失败：保持 failed，兼存观察错误；不同运行之间状态不泄漏。
4. 直接 after_submit 的 messages=None、显式 []、caller 提供列表与 observation 状态，
   不将未声明来源的空列表当成已读 SDK 队列。
5. 用仓库内合成日志（不复制具体工程数据）包含 Warning、MaxPasses、低质量 tetra 文本；
   证明未读队列不能声称日志干净。若没有新增日志 reader，测试只验证 unknown，不能假称已解析。
6. 合成日志即使包含原生 SUCCESS、最大轮次和质量警告，因为未实现日志 reader，原生状态、
   原生警告和 mesh 收敛仍为 unknown；不根据文件存在或关键词补值。独立 mesh 评价器保持原有边界。
7. JSONL、服务和 MCP 传播消息状态/来源/错误；不清空已有证据，不把 None 序列化成 True。
   既有契约成功用例需补明确“已读”证据，保持缺结果、未变化、sink 失败等回归。

新增 23 项离线测试，完整回归 572 passed、2 skipped（MCP extra 未安装）、1 GUI deselected。
后端成功、失败及保存异常均保留 result_summary.run_contract；失败还保留 error.details.run_contract，
服务落盘、MCP 查询不把 None 改写为 True。现有 MCP 工具未新增或隐式注册。
代码已修改，尚无本轮真机验收；未部署到全局环境或插件缓存。
