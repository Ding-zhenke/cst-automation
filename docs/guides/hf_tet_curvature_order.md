# Modern HF Tet 曲率阶数

0.3.56 通过原会话 model_api 显式请求固定阶数：

```json
{"method":"configure_tetrahedral_mesh","kwargs":{"settings":{"curvature_order":2,"curvature_policy":"fixedorder"}}}
```

项目、阶段和完整 calls 的 preview_digest 仍按原工作流提供。curvature_order 只接受严格整数
`{1,2,3}`，拒绝 bool、浮点、字符串、null 和范围外值；省略字段不写默认。
上例仅生成：

```vb
MeshSettings.SetMeshType "Tet"
MeshSettings.Set "CurvatureOrder", "2"
MeshSettings.Set "CurvatureOrderPolicy", "fixedorder"
```

不改变场基函数 FDSolver.OrderTet、AccuracyTet、端口、几何、局部尺寸、edge/Snap
或自适应预算。MeshSettings 的 Tet 组选择不是切换求解器；本字段用于已审阅的
modern HF Tet 工程。curvature_policy 仅接受精确字符串 automatic/fixedorder，拒绝
off/fixed/manual 等猜测别名。两字段均稀疏：只给 order 不改策略，只给 policy 不改
存储阶数；固定阶数对照应同时明确两项。不增加优化上限或猜测 getter。
所属会话实际验证 0.3.55 的 order=2 在原自动策略下仍生成 order=3；原未生效结果
保持。新策略命令有原生语法证据，但仍须核对实际 mesher input、网格及日志。

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

## fixedorder 原生取证

所属工程会话在空闲时通过 CST 2026.1 的 Automatic3→Fixed3 界面操作取得并保存
History，版本字符串 2026.1|35.0.0|20251022，标题 set mesh properties (Tetrahedral)。
维护侧只读核对提供的 history_changes.json；相关原始三句为：

```vb
.SetMeshType "Tet"
.Set "CurvatureOrder", "3"
.Set "CurvatureOrderPolicy", "fixedorder"
```

该证据确证 token 的原生拼写，不是从界面文字猜测；automatic 另有上述官方模板。
原会话报告参数、端口、实体和 DS 禁用状态保持；维护侧未独立核验这些工程属性，
未进行原生调用。只提取这三句，不照抄 UI 生成的整份全局网格配置。
固定策略+阶数2的实际网格生效仍待新任务验证，不从 Fixed3 的语法取证直接推定。

## 强制边界

整批先校验，order 请求要求实际 worker 能力 `hf-tet-curvature-order-v1`，policy
请求要求 `hf-tet-curvature-policy-v1`，组合请求同时要求二者；提交与执行双重检查。
既有 `content-bound-settings-history-v1`、`mesh-settings-no-rebuild-v1` 要求保持。
纯设置批次读消息并保存，不 Rebuild、不求解；混合几何批次按原规则执行，故保持
单独设置批次。标题绑定完整命令内容，不因后续稀疏 Snap 更新丢失曲率历史。
旧 worker 不自动升级，已运行求解不受安装影响，空闲后由所属会话受控交接。

readback_verified/mesh_verified/solver_verified 仍为 False；没有新增专用 getter。
离线用例只验证范围/枚举、命令、批次拒绝、独立能力门槛、无重建路径及历史替身重放。
真实 CST 生效和保存重开由所属会话另行验收，原失败 EM 与数值目标保持。
