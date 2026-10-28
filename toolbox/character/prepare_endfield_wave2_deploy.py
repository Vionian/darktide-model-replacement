"""Parameterize the existing backup/hash/patch/dry-run deployment procedure."""
import pathlib,re
from endfield_wave2 import PROFILES
here=pathlib.Path(__file__).parent
text=(here/'deploy_endfield_batch.ps1').read_text(encoding='utf-8-sig')
entries=',\n'.join("    @{ Asset='%s'; Provider='%s' }"%(key,p['provider'])for key,p in PROFILES.items())
text,count=re.subn(r'\$models = @\(.*?\n\)',lambda m:'$models = @(\n'+entries+'\n)',text,count=1,flags=re.S)
assert count==1
text=text.replace("endfield_batch\\deployment_backup_","endfield_batch\\wave2_deployment_backup_")
text=text.replace("endfield_batch\\deployment_latest.json","endfield_batch\\wave2_deployment_latest.json")
text=text.replace('ENDFIELD_DEPLOYED','ENDFIELD_WAVE2_DEPLOYED')
path=here/'deploy_endfield_wave2.ps1';path.write_text(text,encoding='utf-8-sig')
print(path)
