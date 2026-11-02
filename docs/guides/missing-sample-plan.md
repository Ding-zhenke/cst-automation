# 只补算指定缺失样点：离线计划与实际频点核对

2026-11-02。仅离线代码与本机官方帮助核查；未连接 CST、打开工程/结果/在写日志，
未启动求解、修改物理模型、自适应设置或部署运行时。不复制具体器件结果数据。

## 已核实的采样语义

官方位置：`Online Help/mergedProjects/VBA_3D/special_vbasolver/special_vbasolver_fdsolver_object.htm`。

- `ResetSampleIntervals(enum {"all","adaptation","single","inactive","infinite"} key)`
  删除采样区间定义，不是删除已存频点结果或缓存。
- `AddSampleInterval(double min, double max, int samples,
  enum {"Automatic","Single","Equidistant","Logarithmic"} key, bool adaptation)`
  定义区间；Single 可令上下限相同、样本数为 1。adaptation 指示是否用于顺序 tetra 自适应。
- `ForceRecalculateOldSamples(bool flag)` 说明通常先检查已存结果避免重复，强制重算用于
  某些不能自动识别的变化（如导入源内容变化）；已有结果时还会关闭自适应，首轮无结果除外。
  它不等于“只重算刚设的 Single 点”，也不等于保留当前细网格继续 refinement。

来源会话的实际陷阱：在含已有高频结果的副本设置一个低频 Single 点后，强制重算使原生日志
先计算旧的高频点并列出多个点；该周期被中止。这证明实际点集不符合单低频诊断意图，
不能判为该低频精度失败或通过。False 的后续尝试在本消息发出时仍待原生日志确认，不能
仅据设置改成 False 宣称有效。官方段落加实测共同界定边界，不推断任意工程的完整点集/顺序。

## 已实现的纯离线接口

```python
from cst_solver.sampling import plan_missing_samples, assess_sample_execution

plan = plan_missing_samples(
    [.001], frequency_unit='GHz', available_frequencies=[5, 8],
    context_verified=True)
# plan['expected_new_frequencies'] == [.001]
# plan['force_recalculate_old_samples'] is False

report = assess_sample_execution(
    plan, [8], log_complete=False, aborted=True)
# status='aborted', frequency_status='mismatch', accuracy_status='not_assessed'
```

这些数值仅为通用示例。函数不生成或执行任何宏。计划可用于求解前报告：
requested、available、reused_requested、条件性的 expected_new、单位及推荐的强制重算开关。
None 表示不知道已有结果，[] 表示明确没有结果。精确数值去重，不把邻近频点用宽容差合并。
不处理 DC/频率表达式或自动单位转换，要求有限正数和明确的 Hz/kHz/MHz/GHz/THz。

只有调用方已核对同一工程的缓存身份（mesh、参数、源、归一化等）有效，且仅保留指定 Single
区间、没有额外 automatic/monitor/adaptation 采样时，才应设置 context_verified=True。
否则 expected_new_frequencies=None；即使 True，仍是条件性预期，不是原生排队点集保证。
推荐 ForceRecalculateOldSamples=False 不自动验证缓存，也不替调用方暗中关闭自适应。

## 诊断归属与中止分类

`assess_sample_execution` 接受调用方明确从同一次运行原生日志取得的“实际频点观测”，
单位必须与 plan 一致；本函数不解析原始日志，也不把频率设置、区间汇总或旧周期当实际计算。

- 意外频点出现即 mismatch；日志不完整不能因目标点尚未出现判精度失败。
- 完整日志缺预期点为 frequency_mismatch；日志不完整但无意外点为 incomplete。
- 中止作为独立 aborted 状态保留，同时仍可报告频点 mismatch，绝不映射为 direct accuracy failure。
- 匹配仅说明 sample set matched。accuracy_status 始终 not_assessed，validation_passed=False；
  不代表求解成功、端口矩阵齐全、网格通过或线性残差达标。
- 所有端口残差/矩阵记录必须绑定实际 frequency、mesh pass、端口/激励、run/周期身份和日志位置。
  不能把某个高频点的完整端口残差列表，按“当前请求频率”重标为低频；也不能取全局最后残差。
  若频率归属不明，保留 unassigned/unknown，不得纳入目标频率的精度结论。

本轮不新增原生日志语法解析器，不读取当前任务证据，不更改 RunContract 的原生状态读回。
已有 native abort、频点不符、未读取消息与求解精度/网格收敛的证据应分别报告。
