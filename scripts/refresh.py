#!/usr/bin/env python3
"""Fetch an allowlisted public ASN baseline; publish only after all sources validate."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import time
from urllib.parse import urlsplit, urlencode
from urllib.request import Request, build_opener, HTTPRedirectHandler
ROOT=Path(__file__).resolve().parents[1]
AGENT='BackboneCompare/1.0 (+https://github.com/jsdyer/backbonecompare/issues)'

def valid_asn(value):return type(value) is int and 1<=value<=4294967294

class SameHostRedirect(HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
        if urlsplit(request.full_url).hostname != urlsplit(newurl).hostname:
            raise ValueError('Source redirected to another host')
        return super().redirect_request(request,fp,code,msg,headers,newurl)

def fetch(url,timeout=75):
    headers={'User-Agent':AGENT,'Accept':'application/json'}
    # Credentials go only to the fixed official API host, never config-driven URLs.
    if urlsplit(url).hostname=='www.peeringdb.com' and os.environ.get('PEERINGDB_API_KEY'):
        headers['Authorization']='Api-Key '+os.environ['PEERINGDB_API_KEY']
    with build_opener(SameHostRedirect()).open(Request(url,headers=headers),timeout=timeout) as response:
        raw=response.read(8_000_001)
        if response.status!=200 or not raw or len(raw)>8_000_000:raise ValueError('Invalid source response')
        return json.loads(raw)

def ripe(body,asn):
    if not isinstance(body,dict) or body.get('status')!='ok' or not isinstance(body.get('data'),dict):raise ValueError('Invalid RIPEstat response')
    data=body['data']
    if str(data.get('resource','')).upper().removeprefix('AS')!=str(asn):raise ValueError('RIPEstat returned another ASN')
    rows=data.get('neighbours')
    if not isinstance(rows,list) or len(rows)>100000:raise ValueError('Invalid neighbour evidence')
    output=[]
    for row in rows:
        if not isinstance(row,dict) or not valid_asn(row.get('asn')) or row.get('type') not in ('left','right','uncertain'):raise ValueError('Invalid BGP neighbour')
        item={key:row[key] for key in ('asn','type')}
        for key in ('power','v4_peers','v6_peers'):
            value=row.get(key)
            if value is not None and (type(value) not in (int,float) or value<0):raise ValueError('Invalid BGP observation count')
            item[key]=value
        output.append(item)
    for key in ('query_starttime','query_endtime'):
        if data.get(key):datetime.fromisoformat(data[key].replace('Z','+00:00'))
    return {'status':'ok','data':{'resource':str(asn),'query_starttime':data.get('query_starttime'),'query_endtime':data.get('query_endtime'),'neighbours':output}}

def peering(body,asn):
    if not isinstance(body,dict) or not isinstance(body.get('data'),list) or len(body['data'])>1:raise ValueError('Invalid PeeringDB response')
    if not body['data']:return {'data':[]}
    source=body['data'][0]
    if source.get('asn')!=asn or type(source.get('id')) is not int:raise ValueError('PeeringDB returned another ASN')
    record={key:source.get(key) for key in ('id','asn','name','updated','netixlan_updated','netfac_updated')}
    for kind,fields,identifier in [('netfac_set',('fac_id','name','city','country','updated','status'),'fac_id'),('netixlan_set',('ix_id','ixlan_id','name','ipaddr4','ipaddr6','updated','status','operational'),'ix_id')]:
        rows=source.get(kind)
        if not isinstance(rows,list) or len(rows)>10000:raise ValueError('Missing or invalid PeeringDB memberships')
        if any(not isinstance(row,dict) or type(row.get(identifier)) is not int or row[identifier]<1 for row in rows):raise ValueError('Invalid PeeringDB membership')
        record[kind]=[{key:row.get(key) for key in fields} for row in rows if row.get('status')=='ok']
    return {'data':[record]}

def provider_directory(body,expected):
    if not isinstance(body,dict) or not isinstance(body.get('data'),list) or len(body['data'])>100:raise ValueError('Invalid provider directory')
    rows=[];seen=set()
    for row in body['data']:
        if not isinstance(row,dict) or not valid_asn(row.get('asn')) or row['asn'] not in expected or row['asn'] in seen or type(row.get('id')) is not int or row['id']<1:raise ValueError('Unexpected provider directory entry')
        if not isinstance(row.get('name'),str) or not row['name'].strip():raise ValueError('Missing provider name')
        seen.add(row['asn'])
        rows.append({key:str(row.get(key) or '')[:500] for key in ('name','aka','name_long','updated')}|{'id':row['id'],'asn':row['asn']})
    if not rows:raise ValueError('Empty configured provider directory')
    return rows

def collect(config,fetcher=fetch,sleep=time.sleep,now=None):
    asns=config['asns']
    if not isinstance(asns,list) or not asns or len(asns)>50 or len(set(asns))!=len(asns) or not all(valid_asn(asn) for asn in asns):raise ValueError('Invalid configured ASN watchlist')
    if not isinstance(config.get('default_pair'),list) or len(config['default_pair'])!=2 or len(set(config['default_pair']))!=2 or any(asn not in asns for asn in config['default_pair']):raise ValueError('Invalid default ASN pair')
    now=now or datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00','Z')
    networks={}
    for index,asn in enumerate(asns):
        if index:sleep(max(3.1,float(config.get('request_interval_seconds',3.1))))
        bgp=ripe(fetcher(f'https://stat.ripe.net/data/asn-neighbours/data.json?resource=AS{asn}',timeout=config.get('request_timeout_seconds',75)),asn)
        pdb=peering(fetcher(f'https://www.peeringdb.com/api/net?asn={asn}&depth=2',timeout=config.get('request_timeout_seconds',75)),asn)
        networks[str(asn)]={'asn':asn,'checked_at':now,'ripe':bgp,'peering':pdb}
        print(f'Validated AS{asn}: {len(bgp["data"]["neighbours"])} observation rows',flush=True)
    providers=[]
    if config.get('directory_asns'):
        numbers=config['directory_asns']
        if not isinstance(numbers,list) or len(numbers)>100 or len(set(numbers))!=len(numbers) or not all(valid_asn(n) for n in numbers):raise ValueError('Invalid directory ASN list')
        sleep(max(3.1,float(config.get('request_interval_seconds',3.1))))
        query=urlencode({'asn__in':','.join(map(str,numbers)),'fields':'id,asn,name,aka,name_long,updated','limit':100})
        providers=provider_directory(fetcher('https://www.peeringdb.com/api/net?'+query,timeout=config.get('request_timeout_seconds',75)),numbers)
    return {'schema':1,'checked_at':now,'networks':networks,'providers':providers,'config':{k:config[k] for k in ('default_pair','max_saved_pairs','request_timeout_seconds','peering_api_base')}}

def write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',dir=path.parent,delete=False,encoding='utf-8') as file:json.dump(data,file,ensure_ascii=False,indent=2);file.write('\n');temp=Path(file.name)
    temp.replace(path)

def main():
    capture=collect(json.loads((ROOT/'config/watchlist.json').read_text()))
    encoded=(json.dumps(capture,ensure_ascii=False,indent=2)+'\n').encode()
    write(ROOT/'web/data/networks.json',capture)
    write(ROOT/'web/data/status.json',{'checked_at':capture['checked_at'],'count':len(capture['networks']),'sha256':sha256(encoded).hexdigest()})
    print('Published complete validated network capture')
if __name__=='__main__':main()
