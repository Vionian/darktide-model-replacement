"""Read back installed repair files, command uniqueness, and retired assets."""
from pathlib import Path
import datetime, hashlib, json, re, sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'python-deps'))
from lupa.luajit21 import LuaRuntime

def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def main():
    out=HERE/'issue_fixes_20261023'
    report=json.loads((HERE/'skins_20261023/deployment_latest.json').read_text(encoding='utf8'))
    mod=Path(report['installed_root'])
    for row in report['files']:
        assert sha(mod/row['path'])==row['sha256']==sha(ROOT/row['path']),row['path']
    commands={};lua=LuaRuntime(unpack_returned_tuples=True)
    parse=lua.eval('function(s)local f,e=loadstring(s);assert(f,e)end')
    files=list((mod/'scripts').rglob('*.lua'))
    for file in files:
        text=file.read_text(encoding='utf-8-sig');parse(text)
        for name in re.findall(r'mod:command\(\s*"([^"]+)"',text):
            assert name not in commands,('Duplicate command',name,commands.get(name),str(file))
            commands[name]=file.relative_to(mod).as_posix()
    assert commands['si']=='scripts/mods/SiReplacement/SiReplacement.lua'
    retired=['Custom/perlica_jk','Custom/perlica_jk_arms',
             'scripts/mods/PerlicaReplacement/perlica_jk_jiggle_bones.lua',
             'scripts/mods/PerlicaReplacement/perlica_jk_proportion_bones.lua']
    for name in retired:assert not (mod/name).exists(),name
    for name in ['costume_catalog.lua','AnimeModelReplacement_data.lua','AnimeModelReplacement_localization.lua']:
        assert 'perlica_jk' not in (mod/'scripts/mods/AnimeModelReplacement'/name).read_text(encoding='utf8'),name
    for relative in ['tools/custom-assets-manifest.json','tools/custom-assets-manifest.lua']:
        file=mod.parents[1]/relative
        if file.exists():
            text=file.read_text(encoding='utf8')
            for name in ('perlica_jk','perlica_jk_arms'):
                assert 'content/mods/'+name+'/' not in text,file
    dry_run=Path(report['patcher_logs']['dry_run']).read_text(encoding='utf8')
    assert dry_run.strip(), 'Missing patcher dry-run output'
    result=dict(checked_at=datetime.datetime.now().isoformat(),installed_root=str(mod),
                files_hash_verified=len(report['files']),lua_files_parsed=len(files),
                unique_chat_commands=commands,jk_removed=True,
                deployment_backup=report['backup'],
                unrelated_original_assets_unchanged=report['unrelated_original_assets_unchanged'],
                game_launched=False,gameplay_verified=False,passed=True)
    (out/'installed_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print('INSTALLED_REPAIRS_VERIFIED',len(report['files']),'files',len(files),'Lua files')

if __name__=='__main__':main()
