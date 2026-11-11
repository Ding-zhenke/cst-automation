# HF Tet 低频稳定化与 Direct 精度许可

用于已审阅的 general-purpose tetrahedral frequency-domain 工程，只配置保存，
不求解、不重建。由原会话使用既有 model_api 路由：

```json
{
  "method": "configure_fd_linear_solver",
  "kwargs": {
    "settings": {
      "low_frequency_stabilization": true,
      "allow_float_direct_solver": false
    }
  }
}
```

所属会话仍须提供 project_id、stage_id 和完整 calls 的 preview_digest，遵守原
工作流及当前保存基线审阅。MCP 使用 submit_cst_session_operation，没有新增旁路。
本例只下发两个明确字段；不改变 Direct/Second、AccuracyTet、端口或几何。
两字段可单独提供，必须是真布尔值；字符串、0/1、null 拒绝，省略项不写默认值。

| 字段 | 官方命令 | 边界 |
|---|---|---|
| low_frequency_stabilization | FDSolver.LowFrequencyStabilization | general-purpose HF Tet 接近零频的稳定化，可能改善收敛；不保证低频解通过 |
| allow_float_direct_solver | FDSolver.SetAllowFloatDirectSolver | 仅 AccuracyTet 严格大于 1e-6（更宽松）时可允许 float Direct；false 不代表已独立核实实际精度 |

1e-7 目标不满足官方 float 许可生效条件，不为启用功能放宽该目标。
FDSolver.UseDoublePrecision 文档针对积分方程求解器，不用于认证 HF Tet。
没有已确认的 Direct defect-correction setter/getter，不把 MaxIterations 当作其次数上限。
默认示例值不证明当前工程设置；本版没有对应专用 getter。

整批参数先校验，已有 worker 的提交入口与执行入口均要求
`hf-tet-lf-controls-v1`。新能力与原 solver-settings-no-rebuild-v1 等能力共同使用；
仅设置批次读消息并保存，不 Rebuild；混合几何批次仍按原规则重建，因此保持分开。
仍使依赖 EM/HB 证据失效，不允许沿用旧输入资格。配置回执 readback_verified=False，
不把历史命令当作有效设置读回、双精度或结果保留证据。

插件安装不会热更新当前 worker。是否交接由所属会话依现有授权、空闲和已保存审阅
决定；本次维护不接触主 DE、不启动新夹具或求解。后续实际验证仍须检查完整频率和
每激励残差、矩阵与真实日志，不能因设置调用成功放行 DC/HB。

官方本机依据（相对 CST 2026 安装根目录）：

- Online Help/mergedProjects/VBA_3D/special_vbasolver/special_vbasolver_fdsolver_object.htm：LowFrequencyStabilization、SetAllowFloatDirectSolver、UseDoublePrecision。
- Online Help/mergedProjects/3D/special_solvopt/special_solvopt_w3d_specials.htm：Low frequency stabilization 与 Allow single precision。
- Library/Python/lib/cstapps/_impl/eda/emag/_impl/vba_snippets.py：HF Tet 示例的 LowFrequencyStabilization True。
