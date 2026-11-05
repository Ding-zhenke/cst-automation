# 几何验证未通过与只读原生审阅

## 分开消息级别、调用返回与几何结论

validate_model 保留原生消息结构，分别记录 before/rebuild/合并计数。纯 INFO 不把正常
Rebuild 返回记为异常；但任何非空 INFO 或 WARNING 都保持 status=unverified，不因正文
看似无害或已有缓存就给几何/依赖通过。ERROR、未知消息或 Rebuild 异常为 error，历史
repr/字符串不靠文本解析升级。无消息的原 success 口径仍只针对 Rebuild 和消息队列。

rebuild_performed/rebuild_returned 表示是否调用、是否正常返回；rebuild_ok=True 不是
外部源有效或当前几何正确。dependency_validation=unknown，消息范围为未绑定原生
Run ID 的待处理队列。INFO 提到的外部模板缺失，仍须独立核对缓存、实际实体及完整
依赖；缓存文件存在不等于原生持久化、可重建或求解通过。

## 已返回保存的失败回执

set_parameters/model_api/configure_sweep/3D history 已返回、验证也已返回且 Rebuild 正常
返回时，验证不通过仍可保存部分证据。session_geometry_unverified 带 geometry_outcome，
包括同工程路径、operation/job/operation_id、验证原文、保存摘要和明确返回标志。

worker 只在原 ready、无未知任务/启动意图/监测失败，且登记/回执/磁盘摘要和身份全部
一致时保持 ready。job 仍 failed、review_required=True，geometry_verified/validation_passed
保持 False；不写成功 checkpoint。depends_on 不接受这个失败阶段，调用方必须暂停
依赖阶段并核验，不按 ready 自动继续建模或求解。

Rebuild 异常没有正常返回证明，不追加保存，继续围栏。保存异常、缺回执、摘要变化、
原有 needs_reconcile 或弹窗失败也不自动放行。旧 job 缺少新增回执时不补写成功，不把
新版离线测试当作旧执行的无写入证明。加载新代码不清除当前围栏。

## 旧几何错误围栏中的显式只读入口

默认 inspect 在 needs_reconcile 内仍只返回围栏元数据。需要实际原生审阅时，由所属
会话在确证原 DE 空闲、无弹窗和无其他运行/排队任务后，沿原恢复引用提交 operation=inspect：

```json
{
  "project_id": "existing-project",
  "native_readback": true,
  "read_only_review": true,
  "confirm_idle": true,
  "expected_digest": "实际登记和磁盘一致的64位小写SHA256",
  "parameter_names": ["parameter_to_review"],
  "solid_names": []
}
```

占位摘要不是有效请求。可按原 inspect 契约选择实体/采样点；省略 solid_names 才枚举
实体。该入口不接受宏、表达式执行或任意 SDK 方法。

只读入口限于 session_geometry_unverified 围栏或原 ready，无 launch_intent/uncertain_jobs
及已知弹窗；要求保存登记/预期/磁盘摘要一致、原 DE 身份仍存活、目标实际在打开列表。
借用原 app；若刚加载 worker，可仅精确 attach 原 PID，核对进程身份和实际 PID。
不调用 Runtime.environment/project 的恢复流程，不 open/activate 任何标签，不创建 DE，
不 Rebuild/save/solve，不消费消息队列，不制造 human_reviewed/last_resolution。
目标不在真实打开列表中就拒绝，不能以这条只读请求重新打开它。

只执行既有 inspect_native 的受限参数、实体、材料、体积/点归属 getters。前后检查
原身份、文件摘要和目标句柄。readback_verified 仅指这些 getter 是否读回无错误；
geometry_verified/solver_verified/idle_verified 仍为 False。保留原 session 状态及原错误，
返回 message_read_status=not_read_preserve_queue。查询失败也不清围栏，另记读审阅错误；
若监测到弹窗等运行问题，仍按原安全围栏处理。

实际读回、外部依赖和几何判断仍由所属会话审阅。该入口提供证据，不是几何审批或
解除围栏接口；继续写入仍按既有恢复/授权规则处理。不要为新诊断接管其他会话或
中断正在运行的求解；这里的实现和离线替身测试不认证当前真实工程。
