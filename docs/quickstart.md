# 从一个 Blender 模型开始

## 安装与输入

按根 README 克隆、安装 skill 并运行 setup。安装器记录仓库位置；移动仓库后重新安装。只复制 skill 而不保留工具仓库，不会得到构建工具。其他支持 Markdown skill 的助手也可使用，但需具备文件和命令执行能力。

`setup` 校验下载 SDK、limn、MMR，配置 SDK Oodle，从自己的游戏提取 human 1P/3P UNIT/BONES；不会部署模组。缓存位于 `.cache`，本机路径在 `.local/config.json`，两者不提交。基础入口仅使用 Python 标准库。

人物需要可用骨架和权重；武器需明确目标原版武器。贴图应打包或有有效路径。原游戏动作、截图和材质说明如有请提供，便于助手校准。

## 候选构建

可直接用自然语言让助手执行，也可手动运行：

```powershell
python tools/darktide.py inspect "model.blend" --output work/inspection
```

助手依据 `source-inspection.json` 选择 mesh、armature、骨骼映射、材质和握点，参考 `profiles/*.example.json` 写入 `work/profile.json`；不能把示例坐标当成已测量坐标。

```powershell
python tools/darktide.py build "model.blend" --profile work/profile.json --output work/candidate-001
python tools/scaffold_mod.py work/candidate-001 --mod-id MyReplacement --output work/runtime-001
python tools/darktide.py package work/candidate-001 --runtime work/runtime-001 --output dist/candidate-001
```

每次使用新目录。候选含 blend、GLB/native 资源和审计报告；本地 job/inspection 含本机路径，不随 mod 分发。复杂模型需先补充材质转换、源手部/MMR、服装剔除或运行集成，再重建。

## 安装与实机

安装原作者 DML、DMF 和 Custom Assets。关闭游戏，备份将修改的注册信息、bundle database 及目标 bundle/stream，按对应发行版说明注册。生成目录含 INSTALL.txt；CustomAssets API 必须先加载，内嵌 API 的旧安装也需满足这一点。

核对 patcher 计划和执行结果，完成一次无变更验证后重启游戏。基础模板建议新游戏会话，不宣称已存在角色热加载可靠。检查 1P/3P、持握动作、切装、切关/重生、开关模组、返回菜单和所需预览，见 [validation.md](validation.md)。只在任务包含部署时执行部署。
