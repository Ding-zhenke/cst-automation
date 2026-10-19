# Python 使用

## 离线数据分析

```python
from cst_automation.curves import contiguous_bands, find_resonances
from cst_automation.s2p import read_s2p_groups

bands = contiguous_bands(freqs_ghz, s21_db, threshold_db=-3.0, criterion="above")
resonances = find_resonances(freqs_ghz, s11_db, kind="min")
```

频率单位为 GHz，曲线幅度为 dB；带宽按相邻采样点分段，极值按三点采样定义且不插值。`read_s2p_groups(filepath)` 保持既有分组文本行为。

## CST 会话

```python
from cst_solver import setup

app = setup(r"path\to\project.cst")
try:
    # 调用已提供的实体、材料、布尔、端口或 solver 方法
    app.save()
finally:
    app.close()
```

先通过参数生成并审阅几何预览，再开始写入几何。使用 `python -m cst_solver doctor --json` 查看本机安装。`cst_solver` 可离线导入；首次真实 CST 操作才加载 CST SDK。

## 通用任务服务

`RunService(workdir, backend=FakeBackend())` 可在无 CST 环境验证队列、状态和 handler。真实 `CstBackend` 对已有工程提供 solve；领域 build/study 要由领域包显式调用 `register_handler`。完整协议、参数和结果结构见 [PUBLIC_API.md](../PUBLIC_API.md)。FakeBackend 输出是合成数据，不是真实仿真结果。
