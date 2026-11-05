# -*- coding: utf-8 -*-
"""
CST 结构化验收 Mixin 模块
==========================
把「验收必须读 ``get_messages()`` 并跑 ``Rebuild()``」这条**口头约定**
变成一个有返回值、可被脚本判断的 API。

为什么需要它
------------
本仓库 AGENTS.md 要求分阶段重建并读取实际消息：

    除检查调用异常外，还须检查 ``get_messages()``；
    某些非法 VBA 只写入消息列表，不能根据调用正常返回判定成功。

但在此之前这条约定**没有任何 API 支撑**：每个脚本都要自己抄一遍
「读消息 → 判空 → 跑 Rebuild → 再读消息」。抄错一次（比如忘了重建、
或者只看返回值不看消息）就会把失败当成功。本模块把它固化下来。

@author: PC
"""

from cst_solver._guards import get_guard_state
from cst_automation.run_messages import observe_messages


class ValidationMixin:
    """
    CST 结构化验收 Mixin
    提供 ``validate_model()``：一次调用给出「工程当前是否健康」的结构化结论
    """

    def get_messages(self):
        """
        读取并清空 CST 的待处理消息。

        CST 的 VBA 失败**不会**抛 Python 异常，只会往消息队列里写一条；
        非空可能包含 INFO/WARNING/ERROR，不能仅凭非空判定失败；保留原生类型。
        本仓库按读取后消费队列处理，因此调用方应立即持久化原始消息。

        :return: list, 消息列表（可能是字符串或消息对象）；空列表表示无消息
        """
        return list(self.cst_file.get_messages() or [])

    def validate_model(self, rebuild=True, messages_prefix='1D Results'):
        """
        验收当前工程：读消息 + 跑 Rebuild + 再读消息，返回结构化结果。

        :param rebuild: bool, 是否执行 ``Rebuild()`` 重放工程历史，默认 True。
            重放会重新生成几何，是发现「参数改了但历史没重建」的最后一道检查。
        :param messages_prefix: str, 预留参数（当前未用于过滤，仅为将来按导航树
            筛消息留出签名位置）
        :return: dict::

            {
              "status":     "success" | "unverified" | "error",
              "messages":   [ ... ],               # 本次验收到的问题消息（含 rebuild 阶段）
              "rebuild_ok": bool,                  # Rebuild 本身是否干净
              "before":     [ ... ],               # 调用前积压的历史消息（已清空）
              "guard":      {...},                 # 守卫层发现摘要
            }

        判定规则（与 WORKFLOW §3 一致，不引入新口径）：

        - 原生 INFO/WARNING 保留为 unverified；ERROR/未知消息为 error。
          非空 INFO 也不认证外部依赖或几何有效性。
        - ``rebuild=False`` 时 ``rebuild_ok`` 恒为 True（未执行即不作失败论）
        - 本方法**不抛异常**，调用方按 ``status`` 分流；这样它既能用在
          断言脚本里，也能用在「先跑一遍看看能不能继续」的探测场景
        """
        state = get_guard_state(self)

        before = self.get_messages()
        rebuild_ok = True
        rebuild_returned = False
        rebuild_messages = []

        if rebuild:
            try:
                self.cst_file.model3d.Rebuild()
            except Exception as exc:          # 只有 Rebuild 本身炸了才走到这里
                rebuild_ok = False
                rebuild_messages = [f'Rebuild() 抛出异常：{exc!r}']
            else:
                rebuild_returned = True
                rebuild_messages = self.get_messages()
                _, rebuild_summary = observe_messages(rebuild_messages)
                if any(rebuild_summary[key] for key in ('warning', 'error', 'unknown')):
                    rebuild_ok = False
                else:
                    # 历史已重放 ⇒ 参数与几何重新一致，清掉脏标记
                    state.mark_rebuilt()

        messages, summary = observe_messages(list(before) + list(rebuild_messages))
        _, before_summary = observe_messages(before)
        _, rebuild_summary = observe_messages(rebuild_messages)
        status = ('error' if summary['error'] or summary['unknown'] or (rebuild and not rebuild_returned)
                  else 'unverified' if messages else 'success')
        return {
            'status': status,
            'messages': messages,
            'rebuild_ok': rebuild_ok,
            'rebuild_performed': bool(rebuild), 'rebuild_returned': rebuild_returned,
            'message_summary': summary, 'before_summary': before_summary, 'rebuild_summary': rebuild_summary,
            'dependency_validation': 'unknown', 'validation_scope': 'rebuild_and_message_queue',
            'message_scope': 'pending_queue_unbounded',
            'before': before,
            'guard': state.summary(),
        }
