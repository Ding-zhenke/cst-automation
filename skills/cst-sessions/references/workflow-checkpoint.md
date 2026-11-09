# 跨轮次要求与阶段交接

适用于跨多轮建模、EM→HB、优化迭代及中断恢复。简单的只读查询不必建立新清单。
清单保存在用户工程的工作目录，通用库和插件不保存私有几何或器件数值。

## 每轮恢复入口

保存一份 `workflow.json`，记录 recovery_reference、project_id、当前要求、输入版本、
阶段所需检查和证据路径。用户纠正后先更新当前要求，再实施；旧值在变更记录中保留，
不同时存在两份都称为当前的规格。每轮开始及提交求解前读取清单，不依赖聊天摘要。
同时核对原任务状态：有活动或未决写入则先恢复原任务，不因清单不完整重交求解。

按当前任务列齐需求，不能仅抄已完成项：

| 阶段 | 必要交接内容 |
|---|---|
| 几何 | 审阅范围、参数值/公式/单位/独立性、实际对象名、材料层叠、各段与参数的对应、端口表 |
| EM | 物理端口/参考阻抗、边界、实际频率表、局部网格、自适应点/轮数/停止条件、成本依据 |
| HB | 当前矩阵与端口顺序、归一化和源/负载阻抗、DC 拟合及混频覆盖、逐管接线、双向代表工况、完整扫描轴 |
| 后处理 | 当前任务/节点/探针映射、输入运行身份、预期工况集合、指标定义、必需图和原始复数数据 |

任务是“只配置”时，检查配置证据；不将求解证据列为必须执行项，不为了填清单新增求解。
预览已批准或参数扫描已授权时保持该授权，不要求每轮重新确认。

## 依赖失效

每个检查显式声明依赖哪些输入。改变基板/材料/几何时，重新审查馈线与匹配、网格、EM
矩阵、DC 拟合和下游 HB。改变源阻抗/幅值/阶数时，重查源归一化、频域需求与代表工况。
改变拓扑、端口、探针或任务名时，重查接线及模板节点映射。已有结果继续归档，但不能
用旧检查签名放行新输入。无关图形样式变化不使 EM 数据失效。

## 可执行一致性检查

使用本 skill 的 `scripts/check_workflow.py`（相对本文件为
[../scripts/check_workflow.py](../scripts/check_workflow.py)），仓库 `.venv` 或项目已配置的
Python 均可运行；仅标准库，不连接 CST、不写文件。插件包含同一脚本。

最小格式（示例值不构成任何器件默认设置）：

```json
{
  "schema_version": 1,
  "identity": {"project_id": "example", "recovery_reference": "absolute-reference-path"},
  "inputs": {"source_spec_revision": "A", "geometry_revision": "A"},
  "stages": {"before_hb": ["source_impedance", "matrix_quality"]},
  "requirements": {
    "source_impedance": {"expected": 75, "depends_on": ["source_spec_revision"]},
    "matrix_quality": {"expected": true, "depends_on": ["geometry_revision"]}
  },
  "observations": {}
}
```

先取得实际读回/分析 JSON，再为对应 requirement 记录 observation：

```json
{
  "basis_sha256": "digest-of-current-requirement-basis",
  "path": "readback.json",
  "sha256": "sha256-of-the-actual-file-bytes",
  "pointer": "/ports/source_ohm"
}
```

`path` 相对清单目录或为绝对路径；`pointer` 是 RFC 6901 JSON pointer，选中实际值。
数值、单位和容差由领域检查器归一化，不能用手写 `true` 替代原生读回或拟合结论。
`--basis requirement_id` 输出当前要求、工程身份及所声明输入的摘要；在采集证据时
记录，不能在输入改变后单独刷新摘要来复用旧证据。所有影响该检查的输入必须加入
`depends_on`；输入字段记录具体值或内容摘要，修改时同步更新，不维护永不变的标签。

```powershell
& <project-python> <skill-path>/scripts/check_workflow.py <workflow.json> --basis source_impedance
& <project-python> <skill-path>/scripts/check_workflow.py <workflow.json> --stage before_hb
```

返回码：0 为声明项一致，1 为缺项/过期/文件变更/值不匹配，2 为无效清单。
求解编排调用方在提交前运行；非零时处理具体缺项，不提交依赖它的下一阶段。
调用方仍须核对实时会话状态和当前工程，检查器不能锁住 CST 或替代会话的防重机制。

这不是通用求解器的自动拦截器，不证明清单列全、人工证据真实、网格收敛或物理指标
达标。当前 service/MCP 的 solve 接口不会自动调用它。对话恢复规则加上调用方显式
检查才能起作用；不要声称插件安装后所有违规调用都必然被系统拒绝。
