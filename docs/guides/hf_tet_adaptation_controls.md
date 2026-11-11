# HF Tet 奇异边细化与几何投影

`configure_tetrahedral_mesh` 的稀疏设置示例：

```python
settings = {
    "adaptation": {
        "refinement_type": "automatic",
        "singular_edge_refinement": 3,
        "snap_to_geometry": True,
    }
}
```

通过原会话 `model_api` 的 `configure_tetrahedral_mesh` 调用提交；CLI 和
`submit_cst_session_operation` MCP 工具共用该校验入口。仍需原有审阅摘要及工程身份。
这段配置不改变频段、采样行、适配点、轮数、Delta-S 门槛或适配开关。需要改变这些
设置时应在已批准范围内显式提交，不能把本例当作完整求解规格。

对应原生命令依次为：

```vb
MeshAdaption3D.SetType "HighFrequencyTet"
MeshAdaption3D.RefinementType "Automatic"
MeshAdaption3D.SingularEdgeRefinement "3"
MeshAdaption3D.SnapToGeometry True
```

`singular_edge_refinement` 只接受整数 0..3，拒绝布尔、字符串和浮点数；提供该项时
必须同时声明 `refinement_type="automatic"`，避免依赖未知继承值。
0 关闭额外奇异边细化，1/2 采用不同误差阈值，3 考虑全部可能的奇异导体边。
`snap_to_geometry` 只接受布尔值，可独立配置，控制新界面节点向原几何投影。

这些是频域四面体自适应控制，不是低质量网格优化迭代上限。奇异边额外细化可能
超过 RefThetaFactor 或线性增长限制；不保证修复所有低质量单元、曲率降阶或收敛。
回执保持 readback_verified/mesh_verified/solver_verified=false。实机命令生效、
保存重开、网格变化与收敛分别验收。

## worker 可用性和升级边界

实际 worker 必须宣告 `hf-tet-adaptation-controls-v1`。旧活跃 worker 在排队与
启动前被拒绝，包括新设置与其他调用混合的批次。纯设置批次仍要求已有的
mesh-settings-no-rebuild-v1；不全量 Rebuild，但结果兼容性弹窗仍可能出现。

安装插件/更新源码不会刷新已加载的 worker。已有 `begin_worker_upgrade` /
`finish_worker_upgrade` 仅支持无活原生 DE 的已确认空闲会话；仍拒绝活 DE。
本次未移除该限制，未重启任何 worker。

### 保留活 DE 的受控交接：待实现、待实机验证

不能仅删除 live-DE 拒绝分支。最低协议与验收应覆盖：

1. 原任务、后处理和 SDK 均已返回；无排队任务、未决写入或弹窗。原会话保存并
   核验项目摘要、精确 DE 启动身份、全部已开标签和原生空闲状态。
2. 在 registry/state 锁内冻结新提交，记录旧 worker/DE 身份、工程摘要和所需能力。
   原 worker 在其执行循环空闲边界确认协作退出；不从外部终止进程。
3. 旧 worker 退出后必须实测原 DE 仍为同一进程、原标签仍存在。仅凭 Python 代码
   没有 close()，不能证明原生 SDK 句柄析构不会关闭 DE。
4. 新 worker 只允许借用同一 DE 的已开工程；此交接模式禁止创建 DE、重开缺失标签、
   保存、重建或重放任务。不能直接复用允许恢复/创建环境的普通 fallback 路径。
5. 新 worker 读回身份、标签、原生空闲及保存基线，证明目标能力已加载后才解除冻结。
   任何进程消失、身份/摘要变化、读回失败或新 worker 启动失败均保持冻结，不自动另建。
6. 先在隔离测试工程上验证旧 worker → 新 worker 的真实交接，包含升级中断恢复；
   再由工程所属会话在批准条件下验收。离线替身只能验证协议，不能证明 DE 存续。

## 官方来源

本机 CST 2026 帮助：
`Online Help/mergedProjects/VBA_3D/special_vbamesh/special_vbamesh_meshadaption3d_object.htm`
中的 SetType、RefinementType、SingularEdgeRefinement、SnapToGeometry。
命令存在和适用条件由文档核对；本功能未操作实际工程验收。
