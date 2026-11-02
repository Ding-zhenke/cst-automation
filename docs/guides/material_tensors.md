# 磁导率张量材料

## 求解器选择

| 材料路径 | 可表示的磁导率 | T / Transient | 本仓库接口 |
|---|---|---|---|
| Normal | 标量与内置色散 | 按具体模型支持范围 | `create_material_custom` |
| Anisotropic | 对角 `MuX/MuY/MuZ` | 可用的对角各向异性路径，具体色散另核查 | 尚无专用封装 |
| Normal + 磁 Gyrotropic | 饱和偏置铁氧体的 Polder 张量，含非对角项 | 官方瞬态示例使用此路径 | `create_material_gyrotropic`（SI 参数）；不能向现有标量色散入口直接传入 Gyrotropic |
| Tensor formula | 完整复数 3×3，各项为常量或频率表达式 | **不支持**；仅四面体网格的通用频域求解器 | `create_material_tensor` |

任意九项独立频率函数与 Polder 铁氧体模型的自由度不同，不能通过重命名材料类型互相替代。新接口不会自动切换当前求解器，也不会自动把任意张量拟合成时域模型。

## 完整复数矩阵

```python
# app 是已有 setup 会话；以下调用会提交材料历史，不自动保存或求解。
app.create_material_tensor(
    'complex_mu', epsilon=12,
    mu_tensor=[
        [2-0.01j, 0.3j, 0],
        [-0.3j, 2-0.01j, 0],
        [0, 0, 1],
    ],
    color='#4ec9b0',
)
```

矩阵按 `[行][列]` 排列，0/1/2 分别为默认全局 x/y/z 轴。所有九项均显式提交，不自动施加对称性、互易性或 Hermitian 条件。输入是相对磁导率，使用数学约定 `mu = real + j*imag`；例如 `2-0.01j` 的虚部为 `-0.01`，接口写入 CST `TensorFormulaImag` 的值为 `+0.01`。这符合 Help 的负虚部约定；对角正的负虚部表示损耗。

`epsilon` 为实标量或 CST 参数表达式，写入介电张量的三个对角元，其余电项沿用官方默认零。此接口不提供电导率或任意复数介电张量参数。

## 项目变量与频率表达式

```python
# 先在 CST 参数表中定义 eps_r、mu_d、kappa_m、loss、f0_hz。
# f0_hz 的数值用 Hz，例如 10e9，而不是项目 GHz 刻度上的 10。
app.create_material_tensor(
    'parameterized_mu', epsilon='eps_r',
    mu_tensor=[
        ['mu_d', 0, 0],
        [0, 'mu_d', 0],
        [0, 0, 1],
    ],
    mu_imag=[
        ['-loss', 'kappa_m*f/f0_hz', 0],
        ['-kappa_m*f/f0_hz', '-loss', 0],
        [0, 0, 0],
    ],
)
```

这是参数传递示例，不是经过物理标定的材料模型。实部也可使用 `1+fm_hz^2/(f0_hz^2-f^2)` 等公式，需自行处理频带内的极点和损耗。`mu_tensor` 中字符串表示实部；表达式的虚部通过独立 `mu_imag` 矩阵传入，不能用字符串 `a+j*b` 代替。`mu_imag` 仍表示数学虚部，接口只在整条公式外包 `-(...)` 转换为 CST 所需负虚部。

`mu_imag` 提供时，`mu_tensor` 不允许 Python 复数元素，避免虚部重复指定。矩阵接受严格 3×3 list/tuple；实数须有限，布尔值、空字符串、引号及控制字符会在访问工程前被拒绝。`color/colour` 是互斥别名。

表达式字符串保留给 CST，Python 不求值、不替换参数，也不验证项目参数是否存在。Help 将公式参数标注为 expression，并为该材料规定 `f` 是频率 Hz；本轮离线测试证明参数字符串和符号完整传入命令，实际参数解析与扫参重建仍需原生工程读回确认。这里的 `f` 不是时变调制变量 `t`，不能用于声称实现了时变磁导率。

## 支持 T 求解器的磁 Gyrotropic 路径

官方 Help 的 “One-way Transmission Device” 示例使用偏置铁氧体，激励为 9–12 GHz 高斯脉冲，后处理明确描述 transient calculation，支持把原生磁 Gyrotropic 作为 T 求解器的材料路线。

在沿 z 饱和偏置时，Help 定义

\[
\mu_r(\omega)=\begin{pmatrix}
\mu_1(\omega)&\mu_2(\omega)&0\\
-\mu_2(\omega)&\mu_1(\omega)&0\\
0&0&1
\end{pmatrix},\qquad
\mu_1=\mu_\infty+
\frac{\omega_m(\omega_l+j\omega\alpha)}{(\omega_l+j\omega\alpha)^2-\omega^2},\quad
\mu_2=\frac{j\omega\omega_m}{(\omega_l+j\omega\alpha)^2-\omega^2}.
\]

这里公式和原生模型的两个频率参数均使用角频率 `omega`，单位 rad/s；`omega=2*pi*frequency_hz`。材料采用 Normal 类型加磁 Gyrotropic 色散；Help 明确指出磁 Gyrotropic 不能选择 Anisotropic 材料类型。SI 输入包括 Larmor 角频率、旋磁角频率、阻尼因子和偏置方向；Gauss 输入包括 Landé 因子、饱和磁化参数、共振线宽和偏置场，并涉及参考频率换算。本接口只封装 SI 输入，避免隐式 Gauss 换算；已有纯标量色散系数列表保持原行为。

### 原生 SI 接口与 CST 参数

```python
# app 是已有 setup 会话。以下仅创建材料；数值仅示范接口，不代表拟合后的铁氧体。
from math import pi
app.create_material_gyrotropic(
    'ferrite_si', epsilon=12,
    larmor_omega=2*pi*10e9,       # 对应 10 GHz，传入 rad/s
    gyrotropic_omega=2*pi*5e9,    # 对应 5 GHz，传入 rad/s
    damping=0.002,              # 无量纲 alpha
    bias_direction=(0, 0, -1),
    mu_infinity=1, kappa=0, color='#4ec9b0',
)

# 在 CST 参数表中预先定义 eps_r、fl_ghz、fm_hz、alpha、theta。
# theta 为弧度；方向始终是单位向量，可通过参数扫角度。
app.create_material_gyrotropic(
    'ferrite_parameterized', epsilon='eps_r',
    larmor_omega='2*pi*fl_ghz*1e9',
    gyrotropic_omega='2*pi*fm_hz',
    damping='alpha',
    bias_direction=('sin(theta)', 0, 'cos(theta)'),
)
```

所有物理参数均支持有限实数或 CST 参数表达式，字符串原样保留，由 CST 解析。此处输入的是原生模型参数，**不使用** Tensor formula 的频率占位符 `f`，也不定义时变参数 `t`；材料色散由 CST 自身的 Gyrotropic 模型生成。参数表中数值的单位由调用方负责，两个 omega 表达式求值后必须是 rad/s，`epsilon`、`mu_infinity` 为相对量，`kappa` 为 S/m。工程频率显示单位可以是 GHz，接口通过材料局部 `SetMaterialUnit "Hz", "mm"` 固定基本频率刻度，不修改工程全局单位，也不把角频率自动换成普通频率。

命令映射如下，先设置模型与 SI 模式，再提交系数：

| 接口参数 | 原生命令 | 输入单位 |
|---|---|---|
| `larmor_omega` | `DispCoeff1Mu` | rad/s |
| `gyrotropic_omega` | `DispCoeff2Mu` | rad/s |
| `damping` | `DispCoeff3Mu` | 无量纲 |
| `bias_direction` 三分量 | `DispCoeff4MuX/Y/Z` | 无量纲单位向量 |
| `mu_infinity` | `MuInfinity` | 相对磁导率 |

数值频率、阻尼、电导率要求非负，高频相对磁导率为正；数值方向以 `rel_tol=1e-9, abs_tol=1e-12` 检查单位长度，不做自动归一化。含表达式时不求值，调用方应保证参数存在、方向归一化及整个扫参范围有效。空表达式、布尔、复数、非有限数、引号/控制字符、错误向量维度和颜色别名冲突均在访问工程前报错。

**偏置来源边界**：Help 提供 Automatic（自动发现并导入磁静态场）和 Homogeneous field（使用材料内偏置向量）等模式，但没有给出 `SetMagnetostaticDepSourceField` 切换这些模式的明确 VBA 枚举。本接口 Reset 后仅写模型参数和方向，未指定来源模式或导入场；在已有磁静态 field source 的工程中，需核实材料实际使用 Homogeneous field，才能依赖输入方向。本接口未实现/验证非均匀偏置场耦合，也没有声称偏置来源已原生读回。

调用仅提交一个材料历史块，不自动保存、rebuild、选择求解器或求解。T 求解器路线由官方示例支持；当前封装仍只有离线命令生成证据，原生解析、来源选择和求解器接受性未验收。

**计算开销判断（工程推断，未做本机基准）**：与非色散固定实数磁导率相比，原生时域色散需要额外状态更新，并耦合磁场分量，通常增加每步运算和内存。总耗时还取决于实际时间步和衰减至终止阈值的步数；低阻尼共振可能使信号尾部更长。不能给出统一耗时倍数，也不意味着频带中每个频点都单独跑一次时域求解。量化比较应保持几何、网格、激励频带和终止阈值一致，分别记录网格数、时间步、总步数、内存与耗时。任意固定复数非对角矩阵不能直接作为已验证的 T 求解基线。

## 本地 Help 依据与验证边界

以下路径相对本机 CST 2026 的 `Online Help/`：

- `mergedProjects/VBA_3D/special_vbalayer/special_vbalayerolayer_object.htm`：Material Object / Tensor Formulas；0..2 索引、负虚部、Hz，以及 Gyrotropic 参数表。
- `mergedProjects/3D/special_struct/special_struct_layer_parameters_general.htm`：Tensor formula 仅支持四面体通用频域；对角各向异性参数及类型限制。
- `mergedProjects/3D/special_struct/special_struct_layer_parameters_dispersion.htm`：磁 Gyrotropic 的 SI/Gauss 参数、饱和均匀偏置条件，以及角频率 rad/s 与非周期频率 1/s 的区别。
- `mergedProjects/3D/special_overview/special_overview_material_overview_hf.htm`：Biased Ferrite / Polder 张量。
- `mergedProjects/EXP_HF/examplesoverview/one-way_transmission_device.htm`：官方偏置铁氧体瞬态示例。

本轮仅核对本地 Help 和离线生成历史。没有创建真实工程、切换求解器、验证原生材料读回、执行求解或测量性能；`readback_verified=False`，`solver_verified=False`。官方示例结果不代表当前工程的仿真结果。
