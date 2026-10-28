# 验证与交付证据

| 等级 | 能说明什么 | 不能说明什么 |
| --- | --- | --- |
| 离线 | 语法/mock、合成模型编译、CRC/依赖闭包、native 材质绑定、源文件哈希 | 实机画面、持握、全部动画、运行 API 完全兼容 |
| 注册 | Custom Assets patcher 的计划、应用、资源注册和最终无变更检查 | 镜头和动作中的表现 |
| 实机 | 指定游戏 build、模组版本、日志/截图对应的行为 | 未测试职业、武器、场景及后续版本 |

构建报告默认 `in_game_visual_verified: false`；不以编译退出码或 Blender 渲染改成 true。`source_hand_mmr_executed: false` 表示未执行源手部 MMR，不能将 SDK fit 冒充校准。历史笔记中的验收仅适用于原案例。

```powershell
python tools/validate_repository.py
python -m unittest discover -s tests -v
python tools/smoke_test.py
```

前两条无需游戏；完整 Lua 语法/mock 检查需 `lupa==2.8`。smoke 需 setup 后的 Windows/Blender/本地游戏参考，生成无第三方艺术的合成人物与武器。CI 不分发或提取游戏资源。

交付检查：源 blend SHA256 不变；每次独立候选；manifest 尺寸/CRC/依赖完整；UNIT 材质槽非零且绑定存在；包中只含审阅过的 runtime 和 manifest 资源；不带源模型、配置、日志或提取缓存；ZIP 顶层唯一模组目录，SHA256SUMS 可复核。发行者应补齐模型/贴图署名及授权。部署有恢复点，实机验收单独记录。

## 首次整理的本机验证记录（2026-10-28）

Windows、Python 3.12.7、Blender 5.2.3 LTS；上游版本与归档校验值见根目录 dependencies.lock.json。

- 23 项离线回归通过，包括 Lua 5.1 语法、人物/武器生命周期、共享设置表快照、延迟资源释放、manifest 和打包校验。
- 六阶段 Blender smoke 通过：生成合成模型、分别检查/构建人物与武器，再用真实 SDK reader 做损坏绑定测试。
- 三份 UNIT（身体、手臂、武器）编译并回读通过；在内存中将材质绑定置零后均被拒绝，原文件保持不变。
- 两种候选均生成独立运行模组与 ZIP。没有部署或验证新基础模板在真实游戏中的画面，实机标记保持 false。
