# 武器流程

先明确目标 native template 和 attachment family，再检查源 mesh/LOD、材质、握点、长轴和比例。不能依据名称或外观猜测坐标。`target_templates` 列出已确认的目标，`attachment_prefix` 是被替换附件的资源前缀。基础模板适用 `grip/hilt/blade/pommel` 剑类结构；枪械、链锯或盾牌需审核其实际附件。

对齐矩阵为：

```text
T(target_grip) × R_XYZ(rotation_degrees) × S(uniform_scale) × T(-source_grip) × source_matrix_world
```

source_grip 是源场景坐标，target_grip 是目标原生附件坐标。与提取的 native 参考比较，测量后才设 `coordinate_frame_reviewed: true`；设置 true 本身不证明测量正确。工具拒绝未审核坐标的构建。

编译后检查 UNIT 材质槽的非零资源 ID、纹理/材质闭包与比例。基础 runtime 保留原生装备所有权，按 profile 应用外观，包含双 equipment root、1P viewmodel 和延迟删除机制，不自动创建源粒子或刀身 cover。

高级粒子、cover、职业/武器/外观独立设置和生命周期见 [武器专题](../skills/darktide-model-replacement/references/weapon-model-replacement.md)。助手可从 `toolbox/weapon` 与 `toolbox/runtime/weapon` 适配所需实现。至少实测拔收、轻重击、格挡、特殊动作、瞄准（适用时）、1P/3P、切换武器及地图卸载。
