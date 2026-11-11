# Modern HF Tet 曲率阶数

0.3.55 通过原会话 model_api 提交：

```json
{"method":"configure_tetrahedral_mesh","kwargs":{"settings":{"curvature_order":2}}}
```

项目、阶段和完整 calls 的 preview_digest 仍按原工作流提供。只接受严格整数
`{1,2,3}`，拒绝 bool、浮点、字符串、null 和范围外值；省略字段不写默认。
仅为该字段生成：

```vb
MeshSettings.SetMeshType "Tet"
MeshSettings.Set "CurvatureOrder", "2"
```

不改变场基函数 FDSolver.OrderTet、AccuracyTet、端口、几何、局部尺寸、edge/Snap
或自适应预算。MeshSettings 的 Tet 组选择不是切换求解器；本字段用于已审阅的
modern HF Tet 工程。不增加 Fixed/Off 策略、优化上限或猜测 getter。
CurvatureOrderPolicy 保持不变；调用成功不能证明当前自动策略下有效曲率一定为 2，
须由所属会话核对保存历史和实际 mesher input、网格及日志。

## 官方依据和允许值

以下路径相对 CST Studio Suite 2026 安装目录：

- `Online Help/mergedProjects/3D/special_mesh/special_mesh_mesh_props_general.htm`
  的 Curved element 小节：有限元阶数 p 对应建议曲率阶数 p 到 2p-1；因此二阶
  基函数的官方建议明确涵盖 2 和 3。1 等价于关闭曲面网格。此建议不是任意阶数的
  API 取值范围，本接口仅开放上述有限集合，也不声称 2 能改善当前数值收敛。
- `Library/Macros/Wizard/Compare Solvers^+DS.mcr`：75–85 行 general-purpose
  HF Frequency Domain 分支设置 Tet/CurvatureOrder=3、OrderTet=Second；128–139 行
  Fflat 对照使用 CurvatureOrder=1。提供精确现代命令示例。维护只读该宏，未执行。
- `Library/Python/lib/cstapps/_impl/eda/emag/_impl/vba_snippets.py`：588–645 行
  HF Tet 模板含 CurvatureOrder 和 CurvatureOrderPolicy=automatic。自动模式下所存
  order 值不能直接代替有效阶数读回；不照抄整个含 Reset 的模板。

## 强制边界

整批先校验，提交与执行同时要求实际 worker 能力 `hf-tet-curvature-order-v1`，
以及既有 `content-bound-settings-history-v1`、`mesh-settings-no-rebuild-v1`。
纯设置批次读消息并保存，不 Rebuild、不求解；混合几何批次按原规则执行，故保持
单独设置批次。标题绑定完整命令内容，不因后续稀疏 Snap 更新丢失曲率历史。
旧 worker 不自动升级，已运行求解不受安装影响，空闲后由所属会话受控交接。

readback_verified/mesh_verified/solver_verified 仍为 False；没有新增专用 getter。
离线用例只验证范围、命令、批次拒绝、能力门槛、无重建路径及历史替身重放。
真实 CST 生效和保存重开由所属会话另行验收，原失败 EM 与数值目标保持。
