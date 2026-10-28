# Contributing

欢迎可复现修复、适配 profile 和有证据的经验。描述输入、游戏/Blender/SDK 版本、变化原因及完成的证据等级；不要将单个模型经验升级为通用规则。

提交前运行 `python tools/validate_repository.py` 与 `python -m unittest discover -s tests -v`。涉及编译时，用自己的合法安装完成 smoke 或等价候选检查，不上传生成资源。

不提交模型/贴图、游戏资源、Oodle、二进制依赖、私有配置、token、日志、转储和个人绝对路径。测试用合成数据。新增骨架/武器路线保留原生装备所有权及安全生命周期，并补充适当回归。最终 mod 发行者负责模型作者署名和授权。原创贡献按 GPL-3.0 分发。
