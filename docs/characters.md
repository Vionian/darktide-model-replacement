# 人物流程

1. 检查可见 mesh、骨架、权重、贴图及材质，排除碰撞体、展示底座和辅助对象。
2. 填 `meshes`、可选 `armature`、`bone_map`（源骨 → native 骨）和材质覆盖。空 meshes 选择所有可见且有材质的网格；多骨架应显式选择。
3. 基线用 SDK human skeleton preset、原生参考和 auto-map，再应用覆盖映射并检查必需骨骼。保留比例选项会影响拟合和接触，需要预览。
4. 编译 3P 身体；按 native 手臂权重筛出 1P 网格。`first_person_meshes` 只限制筛选对象，不跳过权重筛选。手臂基线沿用 human 身体 bind，以 1P 节点名链接，须实测武器接触。
5. 检查 UNIT 材质绑定/资源闭包并生成模组。基线支持 human/cryptic，原生装备和骨架保留游戏所有权；欧格林不支持。

`materials` 以源材质名为键，可设 `double_sided` 和 SDK material `intent`。Toon/专用 shader 需先转换或烘焙，不能认为 Blender 显示正确就等于 native 支持全部通道。

源长度手指、静止轴及动作校准需读取源手部和 MMR 实际报告；默认构建记录 `source_hand_mmr_executed: false`。Daniya/Qianxia/Aemeath 等历史模板仅供对照，不随仓库提供，也非通用默认输入。

衣摆剔除、辅助骨、matched-motion、眼白/角/尾巴分类、多服装、HUD 和菜单预览见 [专题索引](knowledge-index.md)。`toolbox/runtime/character` 是高级集成参考，不要直接覆盖基础模板。离线通过不代替实机人物和武器动作、切关与资源生命周期检查。
