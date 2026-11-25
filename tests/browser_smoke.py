"""Browser behavior at a project subpath; mocks arbitrary live ASN source responses."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import json
import os
import shutil
import tempfile
import threading
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    shots=ROOT/'browser-checks';shots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        shutil.copytree(ROOT/'dist',Path(temporary)/'backbonecompare')
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=temporary));threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_PATH'),args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1360,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                def ripe(route):
                    number=int(route.request.url.rsplit('AS',1)[1]);route.fulfill(json={'status':'ok','data':{'resource':str(number),'query_starttime':'2026-11-20T00:00:00','neighbours':[{'asn':13335,'type':'left','v4_peers':10,'v6_peers':0},{'asn':15169,'type':'right','v4_peers':0,'v6_peers':5}]}})
                def peering(route):
                    from urllib.parse import urlparse,parse_qs
                    query=parse_qs(urlparse(route.request.url).query)
                    if 'asn' not in query:
                        route.fulfill(json={'data':[{'asn':123456,'id':9876,'name':'<img src=x> Remote provider','aka':'Remote alias'}]});return
                    number=int(query['asn'][0]);route.fulfill(json={'data':[{'asn':number,'id':number,'name':'<img src=x> Example network','updated':'2026-11-10T00:00:00Z','netixlan_set':[{'ix_id':10,'ixlan_id':10,'name':'Test IX','status':'ok','ipaddr4':'192.0.2.1','ipaddr6':'2001:db8::1','updated':'2026-11-01T00:00:00Z'}],'netfac_set':[{'fac_id':10,'name':'Test facility','city':'Ottawa','country':'CA','status':'ok','updated':'2026-11-01T00:00:00Z'}]}]})
                page.route('https://stat.ripe.net/data/**',ripe);page.route('https://www.peeringdb.com/api/**',peering)
                page.goto(f'http://127.0.0.1:{server.server_port}/backbonecompare/');page.locator('#workspace').wait_for(state='visible')
                page.locator('#provider-query').fill('Bragg');assert 'Eastlink' in page.locator('#provider-results').inner_text();page.get_by_role('button',name='Use Eastlink AS11260 as A',exact=True).click();assert page.locator('#asn-a').input_value()=='11260'
                page.locator('#compare').click();page.wait_for_function("document.getElementById('network-cards').textContent.includes('AS11260')")
                page.locator('#provider-query').fill('Remote');page.locator('#provider-search').click();page.wait_for_function("!document.getElementById('provider-search').disabled");assert 'Remote provider' in page.locator('#provider-results').inner_text();assert page.locator('img').count()==0
                page.get_by_role('button',name='Use <img src=x> Remote provider AS123456 as A',exact=True).click();assert page.locator('#asn-a').input_value()=='123456'
                page.locator('#asn-a').fill('AS123456');page.locator('#asn-b').fill('654321');page.locator('#compare').click();page.wait_for_function("document.getElementById('network-cards').textContent.includes('AS123456')")
                assert page.locator('img').count()==0;assert 'AS13335' in page.locator('#evidence-list').inner_text();assert 'AS15169' in page.locator('#evidence-list').inner_text()
                page.locator('#family').select_option('v6');assert 'AS13335' not in page.locator('#evidence-list').inner_text();assert 'AS15169' in page.locator('#evidence-list').inner_text()
                page.locator('#tab-exchanges').click();assert 'Test IX' in page.locator('#evidence-list').inner_text()
                page.locator('#pair-label').fill('My backup comparison');page.locator('#notes').fill('Ask about shared ducts');page.locator('#save').click();page.locator('#notes').fill('changed');page.get_by_role('button',name='My backup comparison',exact=True).click();assert page.locator('#notes').input_value()=='Ask about shared ducts'
                with page.expect_download() as download:page.locator('#export').click()
                value=json.loads(Path(download.value.path()).read_text());assert value['networks'][0]['asn']==123456;assert value['networks'][0]['bgp']['observed_at']=='2026-11-20T00:00:00Z'
                page.route('https://www.peeringdb.com/api/**',lambda route:route.fulfill(status=503,json={'error':'unavailable'}))
                page.locator('#provider-query').fill('Missing');page.locator('#provider-search').click();page.wait_for_function("!document.getElementById('provider-search').disabled");assert 'Search incomplete' in page.locator('#provider-status').inner_text()
                page.locator('#refresh').click();page.wait_for_function("!document.getElementById('refresh').disabled");assert 'previous evidence retained' in page.locator('#network-cards').inner_text();assert 'Test IX' in page.locator('#evidence-list').inner_text()
                page.screenshot(path=str(shots/'desktop.png'),full_page=True);page.set_viewport_size({'width':390,'height':844});assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth');page.screenshot(path=str(shots/'mobile.png'),full_page=True)
                assert not errors,errors;browser.close()
            print('Browser checks passed: arbitrary pair, safe text, IPv6 filter, saved evidence, export, partial-source failure and mobile layout')
        finally:server.shutdown()
if __name__=='__main__':main()
