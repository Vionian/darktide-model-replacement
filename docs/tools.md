# 工具与依赖

| 入口 | 用途 |
| --- | --- |
| `tools/darktide.py setup / doctor` | 校验下载、环境发现、原生骨架提取和依赖检查 |
| `inspect / build / validate` | 读取 blend、拟合/对齐、编译、manifest 闭包/CRC |
| `tools/blender/worker.py` | Blender 后台执行，不原位保存源 blend |
| `tools/native_audit.py` | UNIT 材质槽回读，拒绝零 ID 和缺失绑定 |
| `tools/scaffold_mod.py` | 生成人物/武器基础运行模组 |
| `tools/package_mod.py` | 审计资源与 runtime 打包及 SHA256 清单 |
| `install-skill / materialize-toolbox` | 安装 skill、生成历史工具本机工作副本 |
| `tools/smoke_test.py` | 合成角色/武器的本机 Blender 冒烟测试 |
| `tools/validate_repository.py` | 发布文件语法、链接与敏感内容检查 |

## 校验下载

版本、提交和 SHA256 见 [dependencies.lock.json](../dependencies.lock.json)，不使用浮动 latest。

- [Darktide SDK](https://github.com/fviuff/Darktide-SDK)：编译器、Blender addon 和原生 reader，GPL-3.0。
- [limn](https://github.com/manshanko/limn)：提取用户本机游戏资源，MIT OR Apache-2.0。
- [MikuMikuRig](https://github.com/XiaoFFGe/MikuMikuRig)：源手部和动作校准，GPL-3.0。setup 缓存源码，不自动执行校准；不是游戏运行依赖。

## 自行安装

- [Blender](https://www.blender.org/)，已验证 5.2.3 LTS。
- [DML](https://github.com/Darktide-Mod-Framework/Darktide-Mod-Loader)（[Nexus 19](https://www.nexusmods.com/warhammer40kdarktide/mods/19)）和 [DMF](https://github.com/Darktide-Mod-Framework/Darktide-Mod-Framework)（[Nexus 8](https://www.nexusmods.com/warhammer40kdarktide/mods/8)）。
- [Custom Assets / Nexus 1200](https://www.nexusmods.com/warhammer40kdarktide/mods/1200)，[API/patcher 源码](https://github.com/fviuff/darktide-mods/tree/main/Custom-Assets-patcher)。插件版和 bat 版状态文件位置不同，按对应发行版说明安装；本仓库不重新分发。
- Oodle DLL 仅从用户暗潮 binaries 本地使用，不随仓库发布。

## 专题可选工具

[Bitsquid Blender Tools](https://gitlab.com/qasikfwn/bitsquid-blender-tools) 用于部分历史导入/导出；[MMD Tools](https://github.com/MMD-Blender/blender_mmd_tools) 用于 MMD 源模型。Character Material Bridge 等源模型插件需使用者自行取得授权；默认基础路线不依赖专有插件。

历史工具可能使用 [requirements-optional.txt](../requirements-optional.txt) 的 Pillow、numpy、scipy、lupa、psutil、pywin32。按实际需要安装；Blender Python 的包应单独配置。源码查询可参考 [Darktide-Source-Code](https://github.com/Aussiemon/Darktide-Source-Code)。

历史工具需重建源 reports、核对模型参数和导入依赖，见 [完整目录](toolbox-catalog.md)，不要批量执行全部脚本。
