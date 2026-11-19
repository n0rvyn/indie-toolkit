import copy
import json
import os
import tempfile
import struct
import zlib
import unittest
import sys
import urllib.parse
from pathlib import Path
from unittest.mock import patch
import asc_manage as m
import asc_readback as auth

def png(path,width=1280,height=800,alpha=False):
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
    pixel=b'\xff\xff\xff\xff' if alpha else b'\xff\xff\xff'
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,6 if alpha else 2,0,0,0))+chunk(b'IDAT',zlib.compress((b'\0'+pixel*width)*height))+chunk(b'IEND',b''))

SCOPE={'app_id':'123','bundle_id':'test.app','platform':'MAC_OS','version':'1.0','locales':['en-US','zh-Hans']}
def before():
    return {'scope':SCOPE,'version_id':'v','info_id':'i','state':'PREPARE_FOR_SUBMISSION','locales':{
        'en-US':{'info':{'id':'il','attributes':{'locale':'en-US','name':'Old','subtitle':'Keep'}},'version':{'id':'vl','attributes':{'locale':'en-US','description':'Old','whatsNew':'Keep release notes'}}},
        'zh-Hans':{'info':None,'version':None}}}
def manifest():
    return {'scope':SCOPE,'locales':{'en-US':{'name':'New','description':'New description'},'zh-Hans':{'name':'测试','description':'说明'}},'screenshots':[]}

class Fake:
    def __init__(self):self.state=before();self.calls=[];self.fail_at=None
    def request(self,method,path,body):
        self.calls.append((method,path,body))
        if len(self.calls)==self.fail_at:raise ValueError('ASC HTTP 403')
        data=body['data'];kind=data['type'];section='info' if kind=='appInfoLocalizations' else 'version'
        if method=='POST':
            relation='appInfo' if section=='info' else 'appStoreVersion'
            assert set(data['relationships'])=={relation}
            locale=data['attributes']['locale'];resource={'id':locale+section,'attributes':copy.deepcopy(data['attributes'])}
            self.state['locales'][locale][section]=resource
        else:
            for item in self.state['locales'].values():
                resource=item[section]
                if resource and resource['id']==data['id']:resource['attributes'].update(data['attributes'])
        return {}

class Tests(unittest.TestCase):
    def plan(self):return m.prepare(manifest(),before(),Path('.'))
    def test_individual_claims_omit_issuer(self):
        self.assertEqual(auth.token_claims(None,100),{'sub':'user','iat':100,'exp':1300,'aud':'appstoreconnect-v1'})
    def test_team_claims_retained(self):self.assertEqual(auth.token_claims('issuer',100)['iss'],'issuer')
    def test_explicit_individual_ignores_stale_team_issuer(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'opaque.p8';p.touch()
            with patch.dict(os.environ,{'ASC_KEY_PATH':str(p),'ASC_KEY_ID':'id','ASC_KEY_TYPE':'individual','ASC_ISSUER_ID':'stale'},clear=True):
                self.assertEqual(auth._find_key(),(p,'id',None))
    def test_team_credentials_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'AuthKey_test.p8';p.touch();(Path(d)/'key.info').write_text('Key ID: id\nIssuer ID: issuer')
            with patch.dict(os.environ,{'ASC_KEY_PATH':str(p)},clear=True):self.assertEqual(auth._find_key(),(p,'id','issuer'))
    def test_individual_requires_explicit_key_id_even_with_standard_filename(self):
        with tempfile.TemporaryDirectory() as d:
            key = Path(d)/'AuthKey_test.p8'
            key.touch()
            environment = {'ASC_KEY_TYPE': 'individual', 'ASC_KEY_PATH': str(key)}
            with patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(SystemExit, 'explicit ASC_KEY_PATH and ASC_KEY_ID'):
                    auth._find_key()
    def test_prepare_no_api_calls(self):self.assertEqual(len(self.plan()['changes']),4)
    def test_unknown_and_out_of_scope_fields_rejected(self):
        for key in ['price','submitted','copyright']:
            x=manifest();x['locales']['en-US'][key]='x'
            with self.assertRaises(ValueError):m.prepare(x,before(),Path('.'))
    def test_scope_mismatch_rejected(self):
        x=manifest();x['scope']=dict(SCOPE,version='2.0')
        with self.assertRaises(ValueError):m.prepare(x,before(),Path('.'))
    def test_keyword_byte_limit(self):
        x=manifest();x['locales']['en-US']['keywords']='字'*34
        with self.assertRaises(ValueError):m.prepare(x,before(),Path('.'))
    def test_unsafe_url_rejected(self):
        x=manifest();x['locales']['en-US']['supportUrl']='http://example.test'
        with self.assertRaises(ValueError):m.prepare(x,before(),Path('.'))
    def test_localization_relationship_regression(self):
        b=m.localization_body('appInfoLocalizations','parent','zh-Hans',{'name':'测试'})
        self.assertEqual(b['data']['relationships'],{'appInfo':{'data':{'type':'appInfos','id':'parent'}}})
    def test_apply_and_readback_preserve_unrelated(self):
        fake=Fake()
        with tempfile.TemporaryDirectory() as d,patch.object(m,'snapshot',side_effect=lambda api,scope:copy.deepcopy(api.state)):
            r=m.apply(fake,self.plan(),Path(d)/'receipt.json')
            self.assertTrue(r['complete']);self.assertEqual(len([check for check in r['checks'] if 'field' in check]),4)
            self.assertEqual(fake.state['locales']['en-US']['info']['attributes']['subtitle'],'Keep')
            self.assertEqual(fake.state['locales']['en-US']['version']['attributes']['whatsNew'],'Keep release notes')
            self.assertFalse(any('reviewSubmission' in c[1] for c in fake.calls))
    def test_stale_snapshot_no_writes(self):
        fake=Fake();fake.state['locales']['en-US']['info']['attributes']['name']='Changed'
        with tempfile.TemporaryDirectory() as d,patch.object(m,'snapshot',side_effect=lambda api,scope:copy.deepcopy(api.state)):
            with self.assertRaises(ValueError):m.apply(fake,self.plan(),Path(d)/'receipt.json')
        self.assertEqual(fake.calls,[])
    def test_partial_failure_receipt_is_retained(self):
        fake=Fake();fake.fail_at=2
        with tempfile.TemporaryDirectory() as d,patch.object(m,'snapshot',side_effect=lambda api,scope:copy.deepcopy(api.state)):
            p=Path(d)/'receipt.json'
            with self.assertRaises(ValueError):m.apply(fake,self.plan(),p)
            r=json.loads(p.read_text());self.assertFalse(r['complete']);self.assertEqual(r['operations'][-1]['status'],'written')
    def test_readback_mismatch_not_passed(self):self.assertFalse(all(c['match'] for c in m.verify(self.plan(),before())))
    def test_one_sided_new_locale_is_rejected_and_existing_half_can_be_repaired(self):
        for fields, existing, missing in [({'name':'测试'}, 'version', 'info'),
                                          ({'description':'说明'}, 'info', 'version')]:
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as d:
                request = manifest()
                request['locales']['zh-Hans'] = fields
                with self.assertRaisesRegex(ValueError, 'both app info and version'):
                    m.prepare(request, before(), Path('.'))
                fake = Fake()
                fake.state['locales']['zh-Hans'][existing] = {
                    'id': 'existing', 'attributes': {'locale': 'zh-Hans'}}
                plan = m.prepare(request, fake.state, Path('.'))
                with patch.object(m, 'snapshot', side_effect=lambda api, scope: copy.deepcopy(api.state)):
                    result = m.apply(fake, plan, Path(d)/'receipt.json')
                self.assertTrue(result['complete'])
                self.assertIsNotNone(fake.state['locales']['zh-Hans'][missing])
                actual = copy.deepcopy(fake.state)
                actual['locales']['zh-Hans'][existing] = None
                self.assertFalse(all(check['match'] for check in m.verify(plan, actual)))

    def test_already_matching_field_is_verified_without_writing_it(self):
        request = manifest()
        request['locales'] = {'zh-Hans': {}, 'en-US': {'name': 'Old', 'description': 'Updated'}}
        fake = Fake()
        plan = m.prepare(request, fake.state, Path('.'))
        self.assertEqual([c['field'] for c in plan['changes']], ['description'])
        def snapshots(api, scope):
            state = copy.deepcopy(api.state)
            if api.calls:
                state['locales']['en-US']['info']['attributes']['name'] = 'Concurrent edit'
            return state
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'snapshot', side_effect=snapshots):
            result = m.apply(fake, plan, Path(d)/'receipt.json')
        self.assertFalse(result['complete'])
        self.assertEqual(len(fake.calls), 1)
        check = next(c for c in result['checks'] if c.get('field') == 'name')
        self.assertEqual(check['observed'], 'Concurrent edit')
        self.assertFalse(check['match'])
    def test_unapproved_image_rejected_before_open(self):
        with self.assertRaises(ValueError):m.image_record({'approved':False},Path('.'),'MAC_OS')
    def test_duplicate_and_missing_version_image_preflight(self):
        record={'locale':'zh-Hans','display_type':'APP_DESKTOP','file_name':'a.png','sha256':'same','size':1}
        x=manifest();x['locales']['zh-Hans']={'name':'测试'};x['screenshots']=[record]
        with patch.object(m,'image_record',return_value=record):
            with self.assertRaises(ValueError):m.prepare(x,before(),Path('.'))
        x=manifest();record=dict(record,locale='en-US');x['screenshots']=[record]
        baseline=before()
        baseline['locales']['en-US']['mac_placements'] = [
            {'type': m.SCREENSHOT, 'image': {'referenceName': m.image_reference(record)}}]
        with patch.object(m,'image_record',return_value=record):
            with self.assertRaises(ValueError):m.prepare(x,baseline,Path('.'))
    def test_mac_image_dimensions_alpha_and_changed_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'screen.png';item={'approved':True,'display_type':'APP_DESKTOP','locale':'en-US','path':str(p)}
            png(p);r=m.image_record(item,Path('.'),'MAC_OS');self.assertEqual(r['sha256'],__import__('hashlib').sha256(p.read_bytes()).hexdigest())
            png(p,alpha=True)
            with self.assertRaises(ValueError):m.image_record(item,Path('.'),'MAC_OS')
            png(p,100,100)
            with self.assertRaises(ValueError):m.image_record(item,Path('.'),'MAC_OS')
            p.write_bytes(b'not an image')
            with self.assertRaises(ValueError):m.image_record(item,Path('.'),'MAC_OS')

    def test_system_jpeg_preflight_and_truncated_image(self):
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'source.png';png(source)
            target=Path(d)/'screen.jpg'
            result=subprocess.run(['/usr/bin/sips','-s','format','jpeg',str(source),'--out',str(target)],capture_output=True)
            self.assertEqual(result.returncode,0)
            item={'approved':True,'display_type':'APP_DESKTOP','locale':'en-US','path':str(target)}
            self.assertEqual(m.probe_image(target)['format'],'JPEG')
            self.assertEqual(m.image_record(item,Path('.'),'MAC_OS')['size'],target.stat().st_size)
            source.write_bytes(source.read_bytes()[:30])
            with self.assertRaises(ValueError):m.probe_image(source)

    def test_system_decoder_unavailable_blocks_without_upload(self):
        m.image_decoder.cache_clear()
        with patch.object(m.subprocess,'run',side_effect=OSError('missing compiler')):
            with self.assertRaises(ValueError):m.image_decoder()
        m.image_decoder.cache_clear()

    def test_screenshot_only_cli_places_asset_and_verifies_actual_order(self):
        class ScreenshotAPI:
            def __init__(self):
                self.calls = []
                self.images = {'prior-image': {'fileName': 'prior.png', 'state': 'APPROVED'}}
                self.placements = [('prior-placement', 'prior-image')]
                self.processing_reads = 0

            def all(self, path):
                route, _, query = path.partition('?')
                parameters = urllib.parse.parse_qs(query)
                state = before()
                english = state['locales']['en-US']
                if route == '/v1/apps/123/appStoreVersions':
                    return [{'id': 'v', 'attributes': {'platform': 'MAC_OS', 'versionString': '1.0',
                                                       'appVersionState': 'PREPARE_FOR_SUBMISSION'}}]
                if route == '/v1/apps/123/appInfos':
                    return [{'id': 'i', 'attributes': {'appStoreState': 'PREPARE_FOR_SUBMISSION'}}]
                if route == '/v1/appInfos/i/appInfoLocalizations':
                    return [english['info']]
                if route == '/v1/appStoreVersions/v/appStoreVersionLocalizations':
                    return [english['version']]
                if route == '/v1/appStoreVersionLocalizations/vl/placements':
                    self_test.assertEqual(parameters['sort'], ['placementGroupPosition'])
                    self_test.assertEqual(parameters['filter[placementGroup]'], ['MAC_PROFILE'])
                    return [{'id': placement, 'attributes': {'placementType': 'APP_SCREENSHOT',
                             'placementGroup': 'MAC_PROFILE', 'state': 'PARENT_PREPARE_FOR_SUBMISSION'},
                             'relationships': {'image': m.linkage('appAssetLibraryImages', image)}}
                            for placement, image in self.placements]
                if route == '/v1/appAssetLibraries/library/images':
                    return [{'id': key, 'attributes': attrs} for key, attrs in self.images.items()
                            if attrs.get('referenceName') in parameters['filter[referenceName]']]
                if route == '/v1/appAssetLibraryRefData':
                    return [{'attributes': {
                        'imageSpecs': [{'specId': 'mac-1280', 'dimensions': {
                            'minWidth': 1280, 'maxWidth': 1280, 'minHeight': 800, 'maxHeight': 800},
                            'mimeTypes': ['image/png'], 'fileExtensions': ['.png'], 'maxFileSize': 500000}],
                        'features': [{'featureId': 'APP_STORE_VERSIONS', 'placementPolicies': [{
                            'placementType': 'APP_SCREENSHOT', 'groupLimits': [{'groupIds': ['MAC_PROFILE'], 'maxCount': 10}]}]}],
                        'placementTypes': [{'placementTypeId': 'APP_SCREENSHOT',
                            'acceptsAssetCategories': ['APP_SCREENSHOTS_AND_PREVIEWS'],
                            'specMappings': [{'placementGroupId': 'MAC_PROFILE', 'specs': ['mac-1280']}]}],
                    }}]
                raise AssertionError(path)

            def request(self, method, path, body=None):
                if method == 'GET':
                    if path == '/v1/apps/123':
                        return {'data': {'attributes': {'bundleId': SCOPE['bundle_id']}}}
                    if path == '/v1/apps/123/assetLibrary':
                        return {'data': {'id': 'library'}}
                    if path.startswith('/v1/appAssetLibraryImages/'):
                        image_id = path.rsplit('/', 1)[-1]
                        image = self.images[image_id]
                        if image['state'] == 'UPLOAD_COMPLETE':
                            self.processing_reads += 1
                            if self.processing_reads == 2:
                                image.update(state='PREPARE_FOR_SUBMISSION', specId='mac-1280')
                        return {'data': {'id': image_id, 'attributes': copy.deepcopy(image)}}
                    raise AssertionError(path)
                self.calls.append((method, path))
                data = body['data']
                if (method, path) == ('POST', '/v1/appAssetLibraryImages'):
                    self_test.assertEqual(data['relationships']['assetLibrary']['data']['id'], 'library')
                    self.images['new-image'] = dict(data['attributes'], state='AWAITING_UPLOAD')
                    return {'data': {'id': 'new-image', 'attributes': {'uploadOperations': [{
                        'url': 'https://upload.example.test/signed', 'method': 'PUT', 'offset': 0,
                        'length': data['attributes']['fileSize'], 'requestHeaders': []}]}}}
                if (method, path) == ('PATCH', '/v1/appAssetLibraryImages/new-image'):
                    self_test.assertEqual(data['attributes'], {'uploaded': True})
                    self.images['new-image']['state'] = 'UPLOAD_COMPLETE'
                    return {}
                if (method, path) == ('POST', '/v1/appAssetLibraryPlacements'):
                    self_test.assertEqual(data['attributes'], {'placementType': 'APP_SCREENSHOT',
                                                               'placementGroup': 'MAC_PROFILE'})
                    self_test.assertEqual(data['relationships']['appStoreVersionLocalization']['data']['id'], 'vl')
                    self_test.assertEqual(data['relationships']['image']['data']['id'], 'new-image')
                    self_test.assertEqual(self.images['new-image']['state'], 'PREPARE_FOR_SUBMISSION')
                    self.placements.insert(0, ('new-placement', 'new-image'))
                    return {'data': {'id': 'new-placement'}}
                if (method, path) == ('POST', '/v1/appAssetLibraryPlacementOrderingRequests'):
                    ids = [row['id'] for row in data['relationships']['orderedPlacements']['data']]
                    self_test.assertEqual(ids, ['prior-placement', 'new-placement'])
                    self_test.assertEqual(data['attributes'], {'placementGroup': 'MAC_PROFILE'})
                    images = dict(self.placements)
                    self.placements = [(pid, images[pid]) for pid in ids]
                    return {}
                raise AssertionError((method, path))

        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b''

        self_test = self
        api = ScreenshotAPI()
        scope = dict(SCOPE, locales=['en-US'])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            screenshot = root/'screen.png'
            png(screenshot)
            (root/'scope.json').write_text(json.dumps(scope))
            (root/'manifest.json').write_text(json.dumps({
                'scope': scope, 'locales': {'en-US': {}}, 'screenshots': [{
                    'locale': 'en-US', 'display_type': 'APP_DESKTOP', 'path': 'screen.png', 'approved': True}]}))

            def run_cli(action, *args, output):
                with patch.object(sys, 'argv', ['asc_manage.py', action, *args, '--output', str(root/output)]):
                    m.main()
                return json.loads((root/output).read_text())

            with patch.object(m, 'API', return_value=api), patch.object(m.time, 'sleep'), patch.object(
                    m.urllib.request, 'urlopen', return_value=Response()) as upload:
                run_cli('read', '--scope', str(root/'scope.json'), output='before.json')
                plan = run_cli('prepare', '--manifest', str(root/'manifest.json'), '--before', str(root/'before.json'),
                               output='plan.json')
                self.assertEqual(plan['changes'], [])
                receipt = run_cli('apply', '--plan', str(root/'plan.json'), '--authorized', output='receipt.json')
                self.assertTrue(receipt['complete'])
                self.assertEqual(upload.call_args[0][0].data, screenshot.read_bytes())
                self.assertNotIn('signed', json.dumps(receipt))
                result = run_cli('readback', '--plan', str(root/'plan.json'), output='readback.json')
                self.assertTrue(result['complete'])
                self.assertEqual(api.calls, [
                    ('POST', '/v1/appAssetLibraryImages'), ('PATCH', '/v1/appAssetLibraryImages/new-image'),
                    ('POST', '/v1/appAssetLibraryPlacements'), ('POST', '/v1/appAssetLibraryPlacementOrderingRequests')])
                reordered = list(reversed(api.placements))
                for placements in [[('prior-placement', 'prior-image')],
                                   reordered, [('new-placement', 'new-image')]]:
                    api.placements = placements
                    with self.assertRaisesRegex(SystemExit, 'Readback pending/mismatch'):
                        run_cli('readback', '--plan', str(root/'plan.json'), output='readback.json')
                    self.assertFalse(json.loads((root/'readback.json').read_text())['complete'])
                self.assertIn('new-image', api.images)

if __name__=='__main__':unittest.main()
