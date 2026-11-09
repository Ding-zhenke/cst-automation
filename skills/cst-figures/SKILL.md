---
name: cst-figures
description: Use when plotting supplied CST or electromagnetic research data, parameter-based geometry previews, field maps, spectra, or device comparison figures with reproducible scientific styles.
---

**完整读取要求：** 必须读完本文件及当前操作要求的引用章节。只读前几十行、搜索摘要或工具输出截断都不算完成；连续补齐缺失内容后才能执行依赖的写入或求解。上下文压缩后若只剩摘要，先重新读取，不能靠用户提醒。

# 科研图与结构预览

数据及尺寸由当前工程、用户输入或已保存结果取得；绘图本身不授权修改模型或运行求解。通用结构图和科研数据图使用 Python/Matplotlib 等精确工具，不能用生图猜测数据或真实尺寸。

- 先核对输入列、坐标、单位、复数约定及无效样本；保持采样事实，不擅自平滑、插值、补零或删除异常点。
- 结构图与建模共用参数和坐标，等比例画真实轮廓、层叠、端口、极性及关键尺寸；未知量标待确认，夸张显示注明非按比例。专门晶格/相区语义使用目标领域规范。
- 用户要求全参数或独立优化变量时，使用建模的实体段→参数覆盖表检查标注完整性；
  主图放不下就补局部图。固定量、派生量、独立变量和同初值的独立实例要可区分，
  不以“主要参数已标”替代用户要求的全部范围。
- 数据图按物理问题组织，器件指标由 [cst-device-characterization](../cst-device-characterization/SKILL.md)确定，读取身份由 [cst-results](../cst-results/SKILL.md)保留。
- 字体、字号、配色及导出先读[统一样式](references/style.md)。[样式资产](assets/research.mplstyle)提供可覆盖默认值；用局部 style context，不永久更改全局样式。
- 保存可复现源码、实际输入/来源和 PNG；仅用户明确要求时生成 SVG/PDF。建模示意图默认仅保留最终 PNG，同图原位更新，不生成阶段图集。打开导出图检查遮挡、裁切、缺字、图例、色条与最终字号。画出图不等于物理结论通过。

普通绘图直接生成；用户明确需要交互精修且环境可用时再接已有绘图工具，相关第三方插件不随本插件打包或自动安装。
