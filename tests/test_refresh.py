import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from refresh import ripe,peering,collect,valid_asn

class RefreshTests(unittest.TestCase):
    def test_asn_bounds_and_boolean_rejection(self):
        self.assertTrue(valid_asn(4294967294));self.assertFalse(valid_asn(True));self.assertFalse(valid_asn(0));self.assertFalse(valid_asn(4294967295))
    def test_bgp_source_must_match_resource_and_validate_counts(self):
        body={'status':'ok','data':{'resource':'123456','query_starttime':'2026-11-24T00:00:00','neighbours':[{'asn':852,'type':'left','v4_peers':2,'v6_peers':0}]}}
        self.assertEqual(ripe(body,123456)['data']['neighbours'][0]['asn'],852)
        with self.assertRaises(ValueError):ripe(body,1)
        body['data']['neighbours'][0]['v4_peers']=-1
        with self.assertRaises(ValueError):ripe(body,123456)
    def test_directory_drops_contact_and_unneeded_fields(self):
        body={'data':[{'id':1,'asn':1,'name':'Example','poc_set':[{'email':'private@example.com'}],'notes':'unneeded','netfac_set':[],'netixlan_set':[]}]}
        safe=peering(body,1)
        self.assertNotIn('private',json.dumps(safe));self.assertNotIn('notes',safe['data'][0]);self.assertEqual(peering({'data':[]},1),{'data':[]})
        with self.assertRaises(ValueError):peering({'data':[{'asn':1,'id':1}]},1)
    def test_expand_watchlist_and_abort_failed_source(self):
        config={'asns':[123456,654321],'default_pair':[123456,654321],'max_saved_pairs':20,'request_timeout_seconds':75,'request_interval_seconds':3.1,'peering_api_base':'https://www.peeringdb.com/api'}
        calls=[];waits=[]
        def fetch(url,timeout=75):
            calls.append(url)
            if 'peeringdb' in url:return {'data':[]}
            number=int(url.rsplit('AS',1)[1]);return {'status':'ok','data':{'resource':str(number),'neighbours':[]}}
        result=collect(config,fetcher=fetch,sleep=waits.append,now='2026-11-25T01:00:00Z')
        self.assertEqual(len(result['networks']),2);self.assertEqual(waits,[3.1]);self.assertEqual(len(calls),4)
        def fail(*args,**kwargs):raise OSError('unavailable')
        with self.assertRaises(OSError):collect(config,fetcher=fail)
