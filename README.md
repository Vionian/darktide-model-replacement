# 暗潮模型替换知识库 / Darktide Model Replacement

面向《Warhammer 40,000: Darktide》人物与武器模型替换的工作流、排错记录和可安装 AI skill。

[English](README.en.md) · [快速开始](docs/quickstart.md) · [工具清单](docs/tools.md) · [知识库](docs/knowledge-index.md)

把自己的 Blender 模型交给 AI 助手，完成暗潮人物或武器外观替换。本仓库包含可移植构建工具、基础 Lua 运行模板、263 份历史适配脚本和 32 份运行参考源码。

## 开始使用

需要 Windows、Python 3.12+、Git、Blender 和本机合法安装的暗潮。已在 Python 3.12.7 / Blender 5.2.3 LTS 上完成合成模型离线构建。游戏运行还需原作者发布的 DML、DMF 和 Custom Assets，见[依赖说明](docs/tools.md)。

```powershell
git clone https://github.com/Vionian/darktide-model-replacement.git
cd darktide-model-replacement
python tools/darktide.py install-skill
python tools/darktide.py setup
python tools/darktide.py doctor
```

自动发现失败时，给 `setup` 添加 `--game "游戏安装目录" --blender "blender.exe完整路径"`。已有同名 skill 时使用 `install-skill --replace`，旧版本会备份。重新加载助手的 skill 后，在该仓库打开任务并告诉它：

> 使用 darktide-model-replacement。我提供了角色.blend，请检查模型、贴图和骨架，生成含第三人称身体和第一人称手臂的暗潮替换候选，完成原生资源检查后打包。

> 使用 darktide-model-replacement。将武器.blend 适配到指定原版武器，请检查握点、坐标和附件族，生成候选并打包。

贴图应打包进 blend，或一起提供有效的相对路径贴图。助手先检查实际模型，再生成 profile 和所需适配代码。**不承诺任意骨架、材质和武器都无需调整即可一键替换。**

## 内容与边界

| 目录 | 内容 |
| --- | --- |
| `skills/darktide-model-replacement` | 可安装 skill 与专题知识库 |
| `tools` | 依赖校验下载、模型检查、拟合/对齐、编译、原生回读、生成模组和打包 |
| `profiles` / `templates` | 配置示例和基础人物/武器 DMF 运行模板 |
| `toolbox` | 模型专用历史脚本与高级运行集成参考，需按输入重新适配 |
| `docs` / `tests` | 使用文档、完整工具索引与离线回归检查 |

- 人物基线使用 SDK human 原生骨架拟合；欧格林、菜单预览、HUD、多服装和源长度手指需额外适配。
- 武器基线覆盖剑类 `grip/hilt/blade/pommel` 附件族；其他附件结构、粒子和刀身 cover 需额外适配。
- 默认构建不执行 MMR 源手部校准。离线编译和资源审计不等于实机视觉验收。
- 不分发原模型、贴图、游戏提取资源、Oodle DLL 和未经授权的插件。上游工具校验下载到本机缓存，骨架从使用者自己的游戏提取。源 blend 保持不变。

原创代码、模板和文档采用 [GPL-3.0](LICENSE)。上游及模型授权独立，见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 和 [CONTRIBUTING.md](CONTRIBUTING.md)。
