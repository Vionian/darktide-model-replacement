from pathlib import Path
import urllib.request, re, json, zipfile
ROOT = Path(__file__).resolve().parents[1]
url = 'https://github.com/fviuff/darktide-sdk/releases'
request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(request, timeout=25).read().decode()
(ROOT/'build/sdk_releases.html').write_text(html, encoding='utf-8')
links = re.findall(r'''(?:href|src)=["']([^"']+)''', html)
releases = sorted(set(x for x in links if '/releases/tag/' in x or '/releases/expanded_assets/' in x or '/releases/download/' in x))
print(json.dumps(releases, indent=2), flush=True)
for expanded in [x for x in releases if '/releases/expanded_assets/' in x][:1]:
    page = urllib.request.urlopen(expanded if expanded.startswith('https:') else 'https://github.com'+expanded, timeout=25).read().decode()
    assets = re.findall(r'''href=["']([^"']+)''', page)
    print(json.dumps(assets, indent=2), flush=True)
    for path in assets:
        if '/releases/download/' in path and path.endswith('.zip') and ('Compiler' in path or 'compiler' in path):
            target=ROOT/'tools'/path.rsplit('/',1)[1]
            with urllib.request.urlopen('https://github.com'+path, timeout=45) as response:
                target.write_bytes(response.read())
            zipfile.ZipFile(target).extractall(ROOT/'tools/compiler')
            print('EXTRACTED', target, flush=True)
            break
