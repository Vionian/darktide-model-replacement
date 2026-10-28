"""Read a finite set of declarative EFMI commands; never execute shaders/code.

The draw manifest records the exact active index ranges and resource bindings.
Unknown expression nodes fail explicitly instead of silently merging variants.
"""
import ast,copy,json,re
from pathlib import Path

def sections(file):
    out={};name=None
    for line in file.read_text(encoding='utf-8-sig',errors='replace').splitlines():
        line=line.split(';',1)[0].strip()
        if not line:continue
        if line.startswith('[') and line.endswith(']'):
            name=line[1:-1];out.setdefault(name,[])
        elif name:out[name].append(line)
    return out

class Reader:
    def __init__(self,file,overrides=None):
        self.file=Path(file);self.root=self.file.parent;self.blocks=sections(self.file)
        self.resources={n.casefold():{a.strip().casefold():z.strip() for a,z in
                        (line.split('=',1) for line in lines if '=' in line)}
                        for n,lines in self.blocks.items() if n.casefold().startswith('resource')}
        self.lookup={n.casefold():n for n in self.blocks}
        self.variables={};self.state={};self.draws=[];self.warnings=[]
        self.variables.update(lod_level=0,mod_enabled=1,object_detected=1,mod_id=1)
        self.execute(self.blocks.get('Constants',[]),initial=True)
        self.variables.update(overrides or {})
        self.variables['lod_level']=0
        self.variables['mod_enabled']=1
        self.variables['mod_id']=1
        if 'CommandListProcessToggles' in self.blocks:self.run('CommandListProcessToggles')
    def expr(self,text):
        text=text.strip()
        text=re.sub(r'\$([\w\\.]+)',lambda m:'VAR('+repr(m[1].lower())+')',text)
        text=text.replace('&&',' and ').replace('||',' or ')
        text=re.sub(r'!(?!=)',' not ',text).strip()
        text=re.sub(r'\btrue\b','True',text,flags=re.I);text=re.sub(r'\bfalse\b','False',text,flags=re.I)
        tree=ast.parse(text,mode='eval')
        ops={ast.Add:lambda a,b:a+b,ast.Sub:lambda a,b:a-b,ast.Mult:lambda a,b:a*b,
             ast.Div:lambda a,b:a/b if b else 0,ast.Mod:lambda a,b:a%b if b else 0,
             ast.Eq:lambda a,b:a==b,ast.NotEq:lambda a,b:a!=b,ast.Gt:lambda a,b:a>b,
             ast.GtE:lambda a,b:a>=b,ast.Lt:lambda a,b:a<b,ast.LtE:lambda a,b:a<=b}
        def visit(node):
            if isinstance(node,ast.Expression):return visit(node.body)
            if isinstance(node,ast.Constant):return node.value
            if isinstance(node,ast.Name):return dict(DRAW_TYPE=4,INSTANCE_COUNT=1,FIRST_INSTANCE=0,ps=200,vs=200,rt_width=1920,rt_height=1080).get(node.id,0)
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='VAR':return self.variables.get(visit(node.args[0]),0)
            if isinstance(node,ast.UnaryOp):
                value=visit(node.operand)
                if isinstance(node.op,ast.Not):return not value
                if isinstance(node.op,ast.USub):return -value
                if isinstance(node.op,ast.UAdd):return value
            if isinstance(node,ast.BinOp) and type(node.op) in ops:return ops[type(node.op)](visit(node.left),visit(node.right))
            if isinstance(node,ast.BoolOp):return all(visit(v) for v in node.values) if isinstance(node.op,ast.And) else any(visit(v) for v in node.values)
            if isinstance(node,ast.Compare):
                a=visit(node.left)
                for op,right in zip(node.ops,node.comparators):
                    b=visit(right)
                    if not ops[type(op)](a,b):return False
                    a=b
                return True
            raise ValueError(('Unsupported EFMI expression',ast.dump(node),text))
        return visit(tree)
    def run(self,name,depth=0):
        if depth>20:raise ValueError('Recursive source command list')
        if 'drawinstances' in name.casefold():
            callback=next((v for k,v in self.state.items()if k.endswith('callback_component_drawcustom')),None)
            if callback:self.run(callback,depth+1)
            return
        actual=self.lookup.get(name.casefold())
        if actual:self.execute(self.blocks[actual],section=actual,depth=depth+1)
    def resource(self,value):
        value=re.sub(r'^(ref|reference|copy)\s+','',value.strip(),flags=re.I)
        for _ in range(8):
            nxt=self.state.get(value.casefold())
            if not nxt or nxt.casefold()==value.casefold():break
            value=nxt
        return value
    def execute(self,lines,section='',depth=0,initial=False):
        stack=[];active=True
        for line in lines:
            lower=line.lower()
            if lower.startswith('if '):
                result=bool(self.expr(line[3:])) if active else False
                stack.append([active,result]);active=active and result;continue
            if lower.startswith('elif '):
                parent,taken=stack[-1];result=bool(self.expr(line[5:])) if parent and not taken else False
                stack[-1][1]|=result;active=parent and result;continue
            if lower=='else':
                parent,taken=stack[-1];active=parent and not taken;stack[-1][1]=True;continue
            if lower=='endif':
                parent,_=stack.pop();active=parent;continue
            if not active or '=' not in line:continue
            key,value=(s.strip() for s in line.split('=',1));key=re.sub(r'^(global\s+)?(persist\s+)?','',key,flags=re.I)
            if key.startswith('$'):
                if not key.startswith('$Pool'):
                    try:self.variables[key[1:].lower()]=self.expr(value)
                    except (SyntaxError,ValueError):
                        if initial:raise
                continue
            if initial:continue
            key=key.casefold()
            if key=='run':
                self.run(value,depth);continue
            if key in ('drawindexed','drawindexedinstanced'):
                values=[self.expr(s) for s in value.split(',')]
                count,start,base=(values[0],values[2],values[3]) if key.endswith('instanced') else values[:3]
                if count:
                    self.draws.append(dict(section=section,count=int(count),start=int(start),base_vertex=int(base),
                         bindings={k:self.resource(v) for k,v in self.state.items()},variables=copy.copy(self.variables)))
                continue
            if key in ('ib','vb0','vb1','vb2','vb3') or key.startswith(('ps-t','resource')) or 'callback_component_drawcustom' in key:
                self.state[key]=self.resource(value)
        assert not stack, ('Unclosed EFMI condition',section)
    def collect(self):
        entries=[n for n,lines in self.blocks.items()if n.casefold().startswith('textureoverride')
                 and not any(s in n.casefold()for s in ('lod1','lod2','lod3'))
                 and (any('callback_component_drawcustom' in l.casefold()for l in lines)
                      or any(l.casefold().startswith(('drawindexed =','drawindexedinstanced ='))for l in lines))]
        if entries:
            for name in entries:self.state={};self.run(name)
            return self.draws
        for name in self.blocks:
            if name.casefold().startswith('commandlist_draw_') and not any(s in name.lower()for s in ('lod1','lod2','_lod')):
                self.state={};self.run(name)
        return self.draws
    def path(self,resource):
        row=self.resources.get(resource.casefold(),{})
        file=row.get('filename')
        return self.root/file.replace(chr(92),'/') if file else None

if __name__=='__main__':
    import sys
    from skins_sources import SOURCES,OUT,source
    for key in sys.argv[1:] or SOURCES:
        row=source(key)
        if key=='si_ink_wash':continue
        try:
            r=Reader(row['ini']);draws=r.collect()
            folder=OUT/key;folder.mkdir(exist_ok=True)
            payload=dict(source=str(row['ini']),defaults=r.variables,draws=draws,
                         resources=r.resources,source_file_sizes={str(p.relative_to(r.root)):p.stat().st_size for p in r.root.rglob('*')if p.is_file()})
            (folder/'draws.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
            print('EFMI_DRAWS',key,len(draws),sum(d['count']//3 for d in draws),flush=True)
        except Exception as e:print('EFMI_FAILED',key,repr(e),flush=True)
