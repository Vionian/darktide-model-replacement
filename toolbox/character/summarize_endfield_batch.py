import pathlib,json
from PIL import Image,ImageDraw,ImageFont,ImageChops
from integrate_endfield_batch import PROFILES,ROOT,HERE
out=HERE/'endfield_batch'
font=ImageFont.truetype('<WINDOWS_FONTS>/msyh.ttc',24)

def subject(path):
    im=Image.open(path).convert('RGB')
    bg=Image.new('RGB',im.size,im.getpixel((0,0)))
    mask=ImageChops.difference(im,bg).convert('L').point(lambda x:255 if x>8 else 0)
    box=mask.getbbox()
    if box:
        x,y,r,t=box;pad=20
        im=im.crop((max(0,x-pad),max(0,y-pad),min(im.width,r+pad),min(im.height,t+pad)))
    return im

body=Image.new('RGB',(1080,1760),'#20262e');draw=ImageDraw.Draw(body)
hands=Image.new('RGB',(1200,1360),'#20262e');hd=ImageDraw.Draw(hands)
summary={}
for row,(key,(label,provider)) in enumerate(PROFILES.items()):
    draw.text((10,row*440+6),label+'  正面 / 侧面 / 背面',font=font,fill='white')
    for col,view in enumerate(('front','side','back')):
        im=subject(out/key/'preview'/f'roshia_preunit_matrix_hand_rigid_{view}_preview.png')
        im.thumbnail((345,395));body.paste(im,(col*360+(360-im.width)//2,row*440+40))
    hd.text((10,row*340+5),label+'  第一人称原生静止姿态：左手 / 右手',font=font,fill='white')
    for col,side in enumerate(('left','right')):
        im=subject(out/key/'preview_rest_hands'/f'roshia_preunit_matrix_hand_rigid_first_person_hands_closeup_{side}_front_preview.png')
        im.thumbnail((580,295));hands.paste(im,(col*600+(600-im.width)//2,row*340+42))
    compiled=[json.loads((ROOT/'Custom'/asset/'compile_manifest.json').read_text(encoding='utf-8')) for asset in (key,key+'_arms')]
    contact=json.loads((out/key/'contact_runtime_audit.json').read_text())
    mmr=json.loads((out/key/'source_hand_audit.json').read_text())
    mapping=json.loads((out/key/'Custom'/(key+'_source_mapping.json')).read_text(encoding='utf-8'))
    summary[key]={'name':label,'provider':provider,'scale':compiled[0]['asset_scale'],
                  'body_triangles':compiled[0]['geometry']['triangles'],'arms_triangles':compiled[1]['geometry']['triangles'],
                  'helper_reduction':mapping['reductions'],'mmr_nodes':mmr['mmr']['mapping_count'],
                  'mmr_max_joint_error_m':mmr['mmr']['max_joint_position_error_m'],
                  'synthetic_cases':len(contact['arms']['synthetic_cases']),'frames_per_unit':contact['arms']['frames'],
                  'native_hand_contract':True,'deployed_to_game':False,'gameplay_verified':False}
body.save(out/'body_overview.png');hands.save(out/'hands_overview.png')
(out/'adaptation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
rows='\n'.join(f"| {v['name']} | `{key}` / `{key}_arms` | {v['scale']:.4f} | {v['body_triangles']:,} / {v['arms_triangles']:,} |" for key,v in summary.items())
text='''# 终末地四模型暗潮适配记录

已构建并接入此工作区的二次元模型替换菜单；未写入游戏目录，未启动游戏验证。

| 模型 | 全身 / 第一人称资源 | 源比例缩放 | 全身 / 手臂三角面 |
| --- | --- | --- | --- |
'''+rows+'''

## 已完成

- 使用用户提供的四份 `.blend` 读取源网格、权重、UV、贴图和关节；源文件未保存覆盖。
- 独立角色配置，按各自脚底与肩高计算缩放；复用洛茜已验证的躯干比例 FK、肩部支持骨和原生动画驱动方案。
- 为各材质输出独立 BC/BCA 原生贴图、平直法线与 ORM；按材质名区分透明槽，眼睛/眼白/眉睫保持不透明，排除 MMD 影层和表情图集。
- 根据各角色真实骨骼链，减少密集服装/头发控制点到 50 发骨、105 衣饰骨的模板预算。未保留的控制点映射到已保留祖先；不导入 MMD 刚体。
- 第一人称保留原角色手部网格/UV/贴图和源权重，离线适配原生手指接触跨度和参考手指截面。手指绝对尺寸有适配，不能称为整手刚体无缩放。
- 手腕/手指使用原生名称与引擎链接，不逐帧写入手指、不移动武器。祀的落地长袖片保留在第三人称动态链，第一人称移除长悬挂片，保留贴臂袖口/护腕。
- 新增李织烟、女管理员、祀、提弗洛斯四个菜单选项；六个人类职业可选，排除欧格林。现有职业默认选择未改动。

## 检查与证据

- `integration_audit.json`：八个资源目录、482 个清单产物及工作区/候选 SHA256 一致性；Lua 语法、模块路径、六职业菜单路由、欧格林排除。
- 各角色 `asset_audit.json`：序列化骨骼/逆绑定矩阵、切线空间、包围体和材质/贴图流依赖。
- 各角色 `contact_runtime_audit.json`：生产 Lua 22 组模拟动作 × 每组 20 帧（全身和手臂分别检查），含施法、盾牌、双刀、换弹和快速相机变换；这些不是从游戏采集的武器动画。
- 各角色 `source_hand_audit.json` 与 `*_source_hand_mmr.blend`：实际 MMR 40 节点、7 组合成动作的离线转移检查。源文件未提供原游戏手势动画。
- `reference_hand_contract.json`：达妮娅蓝/红、千咲、爱弥斯的 40 个手部节点原始世界绑定一致；本批和洛茜一致，严格匹配本构建使用的千咲全身模板。全身与手臂模板的跨文件量化差异为最大矩阵分量约 9.60e-6、位置分量约 2.74e-6 m，报告中单独记录。
- 预览读取编译贴图并逐字节核对 `.unit` 网格流。`body_overview.png` 为全身三视图，`hands_overview.png` 为原生静止姿态左右手。各目录也保留合成握拳/动作特写。

静态预览、MMR 和数值检查不能保证所有实机武器无穿模。仍需大厅/训练场检查明暗、衣饰摆动、武器表面接触及快速转向。

## 文件与复现

正式工作区资源位于 `Custom/<资源ID>` 与 `Custom/<资源ID>_arms`；运行模块位于 `scripts/mods/<Provider>`。
统一入口为 `AnimeModelReplacement.mod`，选择菜单位于 `scripts/mods/AnimeModelReplacement/model_definitions.lua`。

使用 `tools/model-work/build_endfield_native.py -- <资源ID>` 构建（由 Blender 的 `--python` 调用，脚本参数置于 Blender 的 `--` 后）。
使用 `audit_endfield_native.py -- assets <资源ID>` / `-- mmr <资源ID>` 进行 Blender 检查；普通 Python 使用 `audit_endfield_native.py lua <资源ID>`。
预览脚本使用 `--model-profile <资源ID>`，全身 `--asset-dir Custom/<资源ID>`，手臂额外指定 `--first-person` 并使用对应 `_arms` 目录。

本次集成备份位于此目录的 `integration_backup_*`；洛茜现有资源及运行模块未被替换。
后续安装到游戏时须同时复制统一入口、菜单、四个 Provider 和八个 Custom 目录，并通过 Custom Assets 插件或离线 patcher 注册资源。
'''
(out/'README_适配说明.md').write_text(text,encoding='utf-8')
print('ENDFIELD_SUMMARY_WRITTEN',summary)
