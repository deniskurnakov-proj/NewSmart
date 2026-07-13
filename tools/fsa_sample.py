#!/usr/bin/env python3
import json
import urllib.request
import urllib.error
from pathlib import Path

BASE='https://tourism.fsa.gov.ru'
ID='019e647f-5683-72f4-b20f-6ecca8868794'
paths={
 'main':f'/api/v1/resorts/hotels/{ID}/main',
 'additional':f'/api/v1/resorts/common/{ID}/additional-info',
 'drawer':f'/api/v1/resorts/hotels/{ID}/drawer',
}
out={}
for name,path in paths.items():
    url=BASE+path
    try:
        req=urllib.request.Request(url,headers={'Accept':'application/json, text/plain, */*','User-Agent':'Mozilla/5.0','Referer':BASE+'/ru/resorts/showcase/hotels'})
        with urllib.request.urlopen(req,timeout=30) as r:
            raw=r.read().decode('utf-8')
        out[name]={'ok':True,'data':json.loads(raw)}
    except Exception as e:
        out[name]={'ok':False,'error':repr(e)}
Path('sample').mkdir(exist_ok=True)
Path('sample/endpoints.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(out,ensure_ascii=False)[:5000])
