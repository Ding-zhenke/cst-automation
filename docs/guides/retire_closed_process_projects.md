# 已关闭过程工程的显式退休

close_project 默认关闭 working 工程后保留登记；temporary 原规则会退休。
对已完成交付、标签已经关闭、仍为 working 的过程副本，现在有显式退休路径。
它只改变所属会话登记，不删除文件，不打开标签，不连接、保存或关闭 DE。

## 调用前核对

所属会话先核对正式交付及配套资源/依赖完整，不再依赖待清理的过程工程；保留用户要求
的参考和其他任务数据。确认没有正在执行、排队或未知任务，DE 空闲且没有未处理弹窗。
这些现场/交付事实由调用方审阅，API 不以文件存在或摘要相同自动证明交付通过。

退役对象须已通过所属会话正常 close_project 关闭/保存，tab_closed=True 且没有缓存句柄。
若尚未关闭，先用原默认关闭操作，审阅关闭回执，再提交显式退休；retire=True 不代替
原生关闭，也不会为退休重开工程。已删除或保存摘要变化的活动登记不得强制退休。

## 明确请求

沿原恢复引用，在同一会话提交 operation=close_project；params 为：

```json
{
  "project_id": "process-model",
  "retire": true,
  "expected_digest": "填写原关闭回执及磁盘一致的64位小写SHA256",
  "confirm_idle": true,
  "review_note": "正式交付及依赖已经独立核对，此过程副本不再使用；现场空闲且标签关闭"
}
```

摘要占位文本不是有效请求；必须使用实际预期摘要。MCP 沿既有
submit_cst_session_operation，或 sessions CLI submit --operation close_project --params-file。
使用新的明确退休 request-id/operation-id，不修改过去的关闭 job；相同退休请求按现有机制去重。

API 核对：登记 project_id 和当前会话归属；规范绝对路径位于当前
work/sessions/<session>/projects/<project_id>/ 内的 .cst；请求、登记与磁盘摘要相同；
已登记保存/关闭；session ready，无未知任务/启动意图/已知弹窗/关闭请求，无其他
queued/running/needs_reconcile job，无目标缓存句柄，且没有其他登记共用该文件（含别名）。
路径中的跳转不得逃逸过程目录。外部正式工程不属于这个显式退休入口。

confirm_idle=True 是现场空闲断言，回执 idle_verified=False。API 不查询 DE 的原生打开列表，
tab_closed 依据既有关闭登记，不是本轮新取得的原生关闭证明。调用方仍须按生命周期规范
核对真实打开列表；不为元数据退休启动、接管或重新连接环境。

registry.lock 串行化队列检查和登记变更，防止新任务在检查与移动之间被接受。
成功仅将同一项目从 projects 移至 retired_projects，保留原 lifetime/saved_digest，
增加 retirement_review（摘要、审阅说明、空闲断言、关闭证据来源、当前 job ID 和时间）。
已有退休登记可按同一摘要幂等返回，不重写审阅记录；调用方后续删除文件不使该回执失效。

## 回执与后续清理

应核对 retired=True、already_closed=True、tab_closed=True、saved=True、
environment_closed=False、files_deleted=False 和 saved_digest。该回执不验证正式交付内容，
也不允许泛化删除。原失败/关闭 job 保留，不将退休视为几何、求解或数据验收。

然后由所属会话严格核对待删绝对路径、归属、正式工程排除、配套目录和依赖，再按既有
生命周期规则删除这个过程文件及同名资源。API 自身不删除、移动、覆盖或建立备份。
运行或未知状态仍保留现场，不用改 session.json、把 lifetime 偷换成 temporary 或手动
删除活动登记来绕过流程。更新代码及插件不热刷新当前 worker，加载由所属会话在空闲后负责。
