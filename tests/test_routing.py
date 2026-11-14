import io
import json
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs,urlparse
import routing


class Routing(unittest.TestCase):
    def setUp(self):
        routing._CACHE.clear();routing._LAST_REQUEST=0
        self.resource={'id':'local','name':'Local pantry','lat':33.5165,'lon':-86.8091,'is_demo':False}
        self.origin=(33.512,-86.82)
        self.payload={'code':'Ok','routes':[{'geometry':{'type':'LineString','coordinates':[[-86.82,33.512],[-86.8091,33.5165]]},'distance':1300,'duration':1000,'legs':[{'steps':[{'distance':30,'name':'2nd Ave N','maneuver':{'type':'turn','modifier':'right'}}]}]}]}
    def test_walking_uses_foot_instance_and_returns_real_geometry(self):
        with patch('routing.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(self.payload).encode())) as mocked:
            result=routing.route(self.origin,self.resource)
        self.assertTrue(result['available']);self.assertEqual(result['geometry'],self.payload['routes'][0]['geometry'])
        url=mocked.call_args.args[0].full_url
        self.assertIn('/routed-foot/route/v1/foot/',url);self.assertNotIn('driving',url)
        self.assertEqual(result['duration_s'],1000)
        self.assertEqual(parse_qs(urlparse(result['links']['transit']).query)['travelmode'],['transit'])
    def test_timeout_does_not_invent_route(self):
        with patch('routing.urllib.request.urlopen',side_effect=TimeoutError): result=routing.route(self.origin,self.resource)
        self.assertFalse(result['available']);self.assertNotIn('geometry',result);self.assertIn('walking',result['links'])
    def test_synthetic_destination_never_routes(self):
        with patch('routing.urllib.request.urlopen') as mocked: result=routing.route(self.origin,{**self.resource,'is_demo':True})
        self.assertFalse(result['available']);mocked.assert_not_called();self.assertNotIn('links',result)
    def test_cache_and_throttle(self):
        with patch('routing.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(self.payload).encode())) as mocked:
            first=routing.route(self.origin,self.resource)
            self.assertEqual(first,routing.route(self.origin,self.resource))
            throttled=routing.route((33.513,-86.821),self.resource)
        mocked.assert_called_once();self.assertFalse(throttled['available'])
    def test_location_validation(self):
        for value in [None,{}, {'lat':True,'lon':-86.8},{'lat':float('nan'),'lon':-86.8},{'lat':42,'lon':-86.8},{'lat':'33.5','lon':-86.8}]:
            with self.assertRaises(ValueError):routing.location(value)
    def test_invalid_geometry_is_unavailable(self):
        self.payload['routes'][0]['geometry']['coordinates']=[[0,0],[1,1]]
        with patch('routing.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(self.payload).encode())):
            self.assertFalse(routing.route(self.origin,self.resource)['available'])

if __name__=='__main__':unittest.main()
