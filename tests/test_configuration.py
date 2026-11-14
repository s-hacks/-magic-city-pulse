import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import app
from config import load_env
import geocoding
import pulse


class Configuration(unittest.TestCase):
    def test_env_loader_precedence_quotes_and_no_execution(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'GROQ_API_KEY':'existing'}, clear=True):
            path=Path(tmp)/'.env'
            path.write_text('GROQ_API_KEY=local\nexport GEMINI_API_KEY="test value" # comment\nGOOGLE_MAPS_API_KEY=maps-test\nLITERAL=$(do-not-run)\nINVALID NAME=no\nBROKEN="unclosed\n')
            load_env(path)
            self.assertEqual(os.environ['GROQ_API_KEY'],'existing')
            self.assertEqual(os.environ['GEMINI_API_KEY'],'test value')
            self.assertEqual(os.environ['GOOGLE_MAPS_API_KEY'],'maps-test')
            self.assertEqual(os.environ['LITERAL'],'$(do-not-run)')
            self.assertNotIn('BROKEN',os.environ)
            load_env(Path(tmp)/'absent')
    def test_both_llm_modes_use_provider_and_groq_precedence(self):
        cases=[({'GROQ_API_KEY':'test-groq','GEMINI_API_KEY':'test-gemini'},'https://api.groq.com/openai/v1/chat/completions','llama-3.3-70b-versatile','test-groq'),({'GEMINI_API_KEY':'test-gemini'},'https://generativelanguage.googleapis.com/v1beta/openai/chat/completions','gemini-2.5-flash','test-gemini')]
        for env,url,model,key in cases:
            for parser in (True,False):
                content='{"name":"Ada"}' if parser else 'A grounded reply'
                response={'choices':[{'message':{'content':content}}]}
                with patch.dict(os.environ,env,clear=True),patch('pulse.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as mocked:
                    result=pulse.llm('instructions',{'data':1},parser)
                req=mocked.call_args.args[0];payload=json.loads(req.data)
                self.assertEqual(req.get_header('User-agent'),'MagicCityPulse/1.0')
                self.assertEqual(req.get_header('Accept'),'application/json')
                self.assertEqual(req.full_url,url);self.assertEqual(payload['model'],model)
                self.assertEqual(req.get_header('Authorization'),'Bearer '+key)
                self.assertEqual(result,{'name':'Ada'} if parser else content)
                self.assertNotIn(key,req.full_url)
    def test_groq_model_override(self):
        response={'choices':[{'message':{'content':'OK'}}]}
        with patch.dict(os.environ,{'GROQ_API_KEY':'test','GROQ_MODEL':'openai/gpt-oss-120b'},clear=True),patch('pulse.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as mocked:
            self.assertEqual(pulse.llm('test',[]),'OK')
        self.assertEqual(json.loads(mocked.call_args.args[0].data)['model'],'openai/gpt-oss-120b')

    def test_llm_offline_and_failure(self):
        with patch.dict(os.environ,{},clear=True),patch('pulse.urllib.request.urlopen') as mocked:
            self.assertIsNone(pulse.llm('x',[]));mocked.assert_not_called()
        with patch.dict(os.environ,{'GROQ_API_KEY':'test'},clear=True),patch('pulse.urllib.request.urlopen',side_effect=OSError('network down')):
            self.assertIsNone(pulse.llm('x',[]))
    def test_safe_diagnostics_for_missing_and_rejected_key(self):
        import urllib.error
        with patch.dict(os.environ,{},clear=True):
            code,result=app.dispatch('GET','/api/status',{},None)
            self.assertEqual(code,200);self.assertFalse(result['configured'])
            pulse.llm('test',[])
            self.assertEqual(pulse.provider_status()['last_call']['reason'],'missing_key')
        with patch.dict(os.environ,{'GROQ_API_KEY':'fake-secret-not-for-output'},clear=True),patch('pulse.urllib.request.urlopen',side_effect=urllib.error.HTTPError('https://example.test',401,'secret body',{},None)):
            pulse.llm('test',[])
            status=pulse.provider_status()
            self.assertEqual(status['last_call']['reason'],'invalid_key')
            self.assertNotIn('fake-secret',json.dumps(status))
            self.assertNotIn('secret body',json.dumps(status))

    def test_blocked_signature_has_safe_specific_reason(self):
        import urllib.error
        error=urllib.error.HTTPError('https://example.test',403,'Forbidden',{},io.BytesIO(b'error code: 1010'))
        with patch.dict(os.environ,{'GROQ_API_KEY':'test'},clear=True),patch('pulse.urllib.request.urlopen',side_effect=error):
            self.assertIsNone(pulse.llm('test',[]))
            self.assertEqual(pulse.provider_status()['last_call']['reason'],'request_signature_blocked')

    def test_geocoding_request_and_coordinates(self):
        response={'status':'OK','results':[{'geometry':{'location':{'lat':33.538,'lng':-86.747},'location_type':'ROOFTOP'},'address_components':[{'types':['postal_code'],'short_name':'35212'}]}]}
        with patch.dict(os.environ,{'GOOGLE_MAPS_API_KEY':'test-only'},clear=True),patch('geocoding.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(response).encode())) as mocked:
            result=geocoding.geocode('5804 1st Ave S')
        from urllib.parse import parse_qs,urlparse
        args=parse_qs(urlparse(mocked.call_args.args[0]).query)
        self.assertEqual(args['key'],['test-only']);self.assertEqual(args['address'],['5804 1st Ave S, Birmingham, AL, USA'])
        self.assertEqual(result['lat'],33.538);self.assertEqual(result['zip_code'],'35212');self.assertNotIn('test-only',json.dumps(result))
    def test_geocoding_failure_and_outside_city(self):
        for payload in [{'status':'REQUEST_DENIED'},{'status':'ZERO_RESULTS'},{'status':'OK','results':[{'geometry':{'location':{'lat':40,'lng':-70}}}]},{'status':'OK','results':[{'geometry':{'location':{'lat':'NaN','lng':-86.8}}}]}]:
            with patch.dict(os.environ,{'GOOGLE_MAPS_API_KEY':'test'},clear=True),patch('geocoding.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(payload).encode())):
                self.assertIsNone(geocoding.geocode('Ensley'))
        with patch.dict(os.environ,{'GOOGLE_MAPS_API_KEY':'test'},clear=True),patch('geocoding.urllib.request.urlopen',side_effect=TimeoutError):
            self.assertIsNone(geocoding.geocode('Ensley'))
        with patch.dict(os.environ,{},clear=True),patch('geocoding.urllib.request.urlopen') as mocked:
            self.assertIsNone(geocoding.geocode('Ensley'));mocked.assert_not_called()
    def test_street_and_neighborhood_resolution(self):
        self.assertEqual(geocoding.street_address("I'm Ada near 5804 1st Ave S, need food"),'5804 1st Ave S')
        with patch('geocoding.geocode',return_value=None) as mocked:
            geocoding.resolve('food near Woodlawn',{})
        mocked.assert_called_once_with('Woodlawn')
    def test_legacy_search_uses_geocoded_origin_and_shared_llm(self):
        rows=[dict(id='a',category='food',status='open',lat=33.5,lon=-86.9,name='A',address='A',hours_today='daily',what_to_bring='bag',nearest_max_stop='Route'),dict(id='b',category='food',status='open',lat=33.54,lon=-86.75,name='B',address='B',hours_today='daily',what_to_bring='bag',nearest_max_stop='Route')]
        with patch.object(app,'load',return_value=rows),patch('geocoding.resolve',return_value={'lat':33.54,'lon':-86.75}),patch.object(pulse,'llm',return_value=None):
            result=app.ask('food near Woodlawn')
        self.assertEqual(result['matches'][0]['id'],'b')

if __name__=='__main__':unittest.main()
