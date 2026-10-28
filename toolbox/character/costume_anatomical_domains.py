"""Nearest actual anatomical bone segment domains, in the supplied world frame."""
import re
import numpy as np
TORSO={'腰','下半身','上半身','上半身1','上半身2','上半身3'}
UPPER_BODY=TORSO|{'肩.L','肩.R','腕.L','腕.R','ひじ.L','ひじ.R','肘.L','肘.R'}
def is_arm(name):
    return bool(re.fullmatch(r'(肩|腕|ひじ|肘|手首|親指[０１２３0123]|人指[１２３123]|中指[１２３123]|薬指[１２３123]|小指[１２３123])\.[LR]',name))
def nearest(points,bones):
    selected=[];distances=[]
    for row in bones:
        name=row['name']
        if name not in TORSO|{'首','頭'} and not re.fullmatch(r'(肩|腕|ひじ|肘|手首|足|ひざ|足首|つま先|親指[０１２３0123]|人指[１２３123]|中指[１２３123]|薬指[１２３123]|小指[１２３123])\.[LR]',name):continue
        a,z=np.asarray(row['head'],float),np.asarray(row['tail'],float)
        axis=z-a;length=axis@axis
        if length<1e-12:continue
        t=np.clip((points-a)@axis/length,0,1)
        distances.append(np.sum((points-a-t[:,None]*axis)**2,axis=1));selected.append(name)
    assert distances,'Missing anatomical source bones'
    matrix=np.stack(distances,axis=1)
    return np.array(selected)[np.argmin(matrix,axis=1)]
def from_armature(arm):
    return [dict(name=b.name,head=list(arm.matrix_world@b.head_local),tail=list(arm.matrix_world@b.tail_local))for b in arm.data.bones]
