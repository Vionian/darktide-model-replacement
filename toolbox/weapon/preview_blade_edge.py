from pathlib import Path
import json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'build/blade_edge'
fig,axes=plt.subplots(1,3,figsize=(14,9),facecolor='#151c27')
for ax in axes:
    ax.set_facecolor('#151c27');ax.tick_params(colors='#aebdd0');ax.set_aspect('equal');ax.grid(color='#293443',linewidth=.5)
    for s in ax.spines.values():s.set_color('#455264')
def draw(ax,v,f,offset=0,color='#626e82',alpha=1):
    p=v[f][:,:,[1,2]].copy();p[:,:,0]+=offset
    ax.add_collection(PolyCollection(p,facecolors=color,edgecolors='none',alpha=alpha))
ax=axes[0]
for name,filename,x,color in [('Force greatsword','2h_force_sword_blade_01_assembled.npz',-.48,'#6f88a3'),('Relic sword','2h_power_sword_blade_01_assembled.npz',-.16,'#947e6e')]:
    n=np.load(OUT/filename)
    for k in n.files:
        if not k.endswith('_faces'):draw(ax,n[k],n[k+'_faces'],x,color)
    ax.text(x,-.37,name,color='#dae4ef',ha='center',fontsize=8,rotation=12)
n=np.load(ROOT/'build/target_mesh.npz');draw(ax,n['vertices'],n['faces'],.16,'#7e748d')
ax.text(.16,-.37,'Khravengger before',color='#dae4ef',ha='center',fontsize=8,rotation=12)
n=np.load(OUT/'khravengger_compiled.npz');draw(ax,n['vertices'],n['faces'],.48,'#9cdafa')
ax.text(.48,-.37,'Khravengger -12%',color='#dae4ef',ha='center',fontsize=8,rotation=12)
ax.set_xlim(-.66,.66);ax.set_ylim(-.49,1.22);ax.set_title('Native size comparison (m)',color='white')
for ax,name,title,color in zip(axes[1:],['khravengger','langzhifei'],['Ice-blue: both cutting edges','Blue-violet: single cutting edge'],['#65d6ff','#9475ff']):
    n=np.load(OUT/(name+'_compiled.npz'));draw(ax,n['vertices'],n['faces'],color='#5c6779')
    n=np.load(OUT/(name+'_compiled_b.npz'));draw(ax,n['vertices'],n['faces'],color=color)
    edge=json.loads((OUT/(name+'_edge.json')).read_text());ep=np.array(edge['envelope'])
    for side in edge['sides']:
        zs=np.linspace(edge['start_z']+.009,ep[-1,0]-.012,23 if name=='khravengger' else 19)
        ys=np.interp(zs,ep[:,0],ep[:,2 if side==1 else 1])-side*.0015
        ax.scatter(ys,zs,s=6,color='#e9ecff',alpha=.9)
    ax.set_xlim(-.19,.19);ax.set_ylim(-.3,1.08);ax.set_title(title,color='white');ax.set_xlabel('Y (m)',color='#aebdd0')
fig.suptitle('Compiled UNIT geometry / edge-emitter placement - offline preview',color='white',fontsize=13)
fig.tight_layout(rect=(0,0,1,.96));fig.savefig(OUT/'blade_edge_comparison.png',dpi=150,facecolor=fig.get_facecolor())
print('BLADE_EDGE_PREVIEW_READY')
