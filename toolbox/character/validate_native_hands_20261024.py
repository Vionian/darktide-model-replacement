"""Validate one consistent repair pipeline, never equate this with gameplay."""
from pathlib import Path
import concurrent.futures, datetime, json, subprocess, sys, time
from repair_native_hands_20261024 import ROOT,HERE,OUT,REPAIR,BLENDER,LEGACY,fingerprints

def call(tag,folder,label,script,args,blender):
    cmd=([BLENDER,'-b','--threads','2','--python-exit-code','1','--python',str(HERE/script),'--'] if blender else [sys.executable,'-X','utf8',str(HERE/script)])+list(map(str,args))
    log=folder/('native_repair_'+label+'.log')
    with log.open('w',encoding='utf8') as stream:r=subprocess.run(cmd,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT)
    value=log.read_text(encoding='utf8',errors='replace')
    if r.returncode or 'Traceback' in value:raise ValueError((tag,label,str(log),value[-2200:]))

def validate(tag):
    legacy=tag in LEGACY;folder=REPAIR/tag if legacy else OUT/tag
    status=folder/'native_repair_status.json'
    deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        if status.exists():
            try:
                built=json.loads(status.read_text(encoding='utf8'))
                if built.get('pipeline_sha256')==fingerprints() and built.get('pipeline_unchanged_during_build'):
                    if not built['ok']:raise ValueError(('Build failed',tag,built['log']))
                    break
            except json.JSONDecodeError:pass
        time.sleep(3)
    else:raise TimeoutError(('Current pipeline candidate not ready',tag))
    print('AUDIT_START',tag,flush=True)
    if legacy:
        call(tag,folder,'resources','audit_endfield_native.py',['assets',tag,'--output',folder],True)
        call(tag,folder,'contacts','audit_endfield_native.py',['lua',tag,'--output',folder],False)
    else:
        call(tag,folder,'resources','audit_new_skin.py',[tag],True)
        call(tag,folder,'contacts','test_new_skin_contacts.py',[tag],False)
    authoring=folder if legacy else folder/'native'
    details=[]
    for mode in ('body','arms'):
        seg=json.loads((authoring/('native_arm_segment_'+mode+'.json')).read_text(encoding='utf8'))
        geom=json.loads((authoring/('export_geometry_'+mode+'.json')).read_text(encoding='utf8'))
        assert len(seg['rows'])==4,(tag,'missing arm segment')
        max_error=max(r['fitted_endpoint_error_mm'] for r in seg['rows'])
        assert max_error<.002,(tag,max_error)
        if mode=='body':
            assert len(seg['shoulder_supports'])==2,(tag,'Actual upper-arm supports missing')
            assert max(r['fitted_endpoint_error_mm']for r in seg['shoulder_supports'])<.002,tag
        hands=[r for r in geom['materials'] if r['source_high_hand_weight_triangles']]
        assert hands,(tag,'No source hand surface')
        assert all(r['source_high_hand_weight_triangles']==r['exported_high_hand_weight_triangles'] for r in hands)
        details.append(dict(mode=mode,maximum_fitted_endpoint_error_mm=max_error,
            previous_maximum_endpoint_error_mm=max(r['previous_endpoint_error_mm'] for r in seg['rows']),
            source_high_hand_weight_triangles=sum(r['source_high_hand_weight_triangles'] for r in hands),
            all_high_hand_weight_triangles_exported=True,rigid_accessories=geom['rigid_accessories'],
            zero_area_front_triangles=sum(r['zero_area_front_triangles'] for r in geom['materials'])))
    mmr=json.loads((authoring/'mmr_hand_authoring_arms.json').read_text(encoding='utf8'))
    assert mmr['MMR_mappings']==32 and mmr['max_MMR_matrix_error']<1e-4
    result=dict(profile=tag,folder=str(folder),checked_at=datetime.datetime.now().isoformat(),
        pipeline_sha256=fingerprints(),offline_checks_passed=True,
        serialized_resources_and_native_hand_contact_checks=True,production_lua_stress_cases=True,
        MMR_source_character_mappings=mmr['MMR_mappings'],max_MMR_matrix_error=mmr['max_MMR_matrix_error'],
        source_game_animation_available=False,geometry=details,gameplay_verified=False)
    (folder/'native_repair_checks.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print('AUDIT_DONE',tag,flush=True)
    return result

if __name__=='__main__':
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(validate,t):t for t in sys.argv[1:]}
        for future in concurrent.futures.as_completed(futures):
            tag=futures[future]
            try:rows.append(future.result())
            except Exception as ex:
                print('AUDIT_FAILED',tag,str(ex),flush=True)
                rows.append(dict(profile=tag,offline_checks_passed=False,error=str(ex),gameplay_verified=False))
    (REPAIR/'validation_results.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    if not all(r['offline_checks_passed'] for r in rows):sys.exit(1)
