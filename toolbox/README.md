# 历史适配工具

这里归档人物/武器项目的建模、材质、权重、姿态、证据和运行集成源码：263 份适配脚本及 32 份 Lua 运行参考。逐文件来源和状态见 [inventory.json](inventory.json) 与 [完整目录](../docs/toolbox-catalog.md)。

这些是供助手改写的模型专用参考。部分依赖旧布局、模型名、未公开 reports、需另行授权的模型模板或插件，没有逐个在新机器执行验证，不属于通用一键入口。

```powershell
python tools/darktide.py materialize-toolbox --output work/expert-adapters
```

这会替换路径占位符并创建工作副本。之后仍需重建 profile/reports、核对输入与导入依赖。不要在原模型/已部署安装批量运行历史脚本。标准任务优先使用 tools 入口。运行参考不包含第三方角色 provider 或复制的 CustomAssets；高级 controller/registry 需要与新模型清单和生命周期集成。
