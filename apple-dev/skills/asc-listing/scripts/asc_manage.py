#!/usr/bin/env python3
"""Scoped ASC draft metadata and append-only screenshots: read/prepare/apply/readback.
Credentials are process-local ASC_KEY_* variables, never part of manifests/plans.
"""
import argparse
import hashlib
import http.client
import json
import os
import time
import subprocess
import tempfile
import functools
import atexit
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
import asc_readback as auth

INFO = {'name', 'subtitle', 'privacyPolicyUrl'}
VERSION = {'description', 'keywords', 'promotionalText', 'supportUrl', 'marketingUrl', 'whatsNew'}
MAC_SIZES = {(1280,800),(1440,900),(2560,1600),(2880,1800)}
MAC_GROUP = 'MAC_PROFILE'
SCREENSHOT = 'APP_SCREENSHOT'
IMAGE_CATEGORY = 'APP_SCREENSHOTS_AND_PREVIEWS'
READY_IMAGE_STATES = {'COMPLETE', 'PREPARE_FOR_SUBMISSION', 'READY_FOR_REVIEW', 'WAITING_FOR_REVIEW',
                      'IN_REVIEW', 'ACCEPTED', 'APPROVED'}
_IMAGE_WORKSPACES=[]

def cleanup_image_decoders():
    for workspace in _IMAGE_WORKSPACES:workspace.cleanup()
    _IMAGE_WORKSPACES.clear()

atexit.register(cleanup_image_decoders)

@functools.lru_cache(maxsize=1)
def image_decoder():
    """One ImageIO helper per process; binary/cache are temporary, not user config."""
    helper=Path(__file__).with_name('asc_image_probe.swift')
    if not Path('/usr/bin/swiftc').exists() or not helper.is_file():
        raise ValueError('Mac screenshot validation requires installed Swift and asc_image_probe.swift')
    workspace=tempfile.TemporaryDirectory(prefix='asc-image-probe-')
    binary=Path(workspace.name)/'asc-image-probe'
    try:
        result=subprocess.run(['/usr/bin/swiftc','-module-cache-path',workspace.name,
                               str(helper),'-o',str(binary)],capture_output=True,text=True,timeout=90)
        if result.returncode or not binary.is_file():raise ValueError('System image decoder build failed; no upload allowed')
    except (OSError,subprocess.TimeoutExpired,ValueError):
        workspace.cleanup()
        raise ValueError('System image decoder unavailable; no upload allowed') from None
    _IMAGE_WORKSPACES.append(workspace)
    return binary,workspace

def probe_image(path):
    """Fully decode with installed macOS ImageIO; no Pillow dependency."""
    binary,_=image_decoder()
    try:
        result=subprocess.run([str(binary),str(path)],capture_output=True,text=True,timeout=60)
    except (OSError,subprocess.TimeoutExpired):
        raise ValueError('System image decoder failed or timed out; no upload allowed') from None
    try:record=json.loads(result.stdout)
    except (ValueError,TypeError):raise ValueError('System image decoder did not return validated JSON') from None
    if result.returncode or record.get('valid') is not True:
        raise ValueError('System image decoder rejected the image')
    return record

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

class API:
    def __init__(self):
        self.token = auth._token()
    def request(self, method, path, body=None):
        req = urllib.request.Request(auth.API + path, method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={'Authorization':'Bearer '+self.token, 'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raise ValueError(f'ASC HTTP {error.code}; operation stopped, inspect non-secret receipt') from None
    def all(self, path):
        rows = []
        while path:
            page = self.request('GET', path)
            rows.extend(page['data'])
            link = page.get('links', {}).get('next')
            if link and not link.startswith(auth.API + '/'):
                raise ValueError('Unexpected pagination origin')
            path = link[len(auth.API):] if link else None
        return rows

def mac_placements(api, localization_id):
    query = urllib.parse.urlencode({'limit': 200, 'include': 'image', 'sort': 'placementGroupPosition',
                                   'filter[placementGroup]': MAC_GROUP})
    rows = api.all('/v1/appStoreVersionLocalizations/'+localization_id+'/placements?'+query)
    placements = []
    for row in rows:
        attributes = row['attributes']
        if attributes['placementGroup'] != MAC_GROUP:
            continue
        image = row.get('relationships', {}).get('image', {}).get('data')
        media = api.request('GET', '/v1/appAssetLibraryImages/'+image['id'])['data']['attributes'] if image else {}
        placements.append({'id': row['id'], 'type': attributes['placementType'], 'state': attributes['state'],
                           'image_id': image['id'] if image else None,
                           'image': {key: media.get(key) for key in ('fileName', 'fileSize', 'referenceName', 'state')}})
    return placements


def snapshot(api, scope, *, media=False):
    app = api.request('GET', '/v1/apps/'+scope['app_id'])['data']
    if app['attributes']['bundleId'] != scope['bundle_id']:
        raise ValueError('App bundle mismatch')
    versions = api.all('/v1/apps/'+scope['app_id']+'/appStoreVersions?limit=200')
    matches = [v for v in versions if v['attributes']['platform']==scope['platform'] and v['attributes']['versionString']==scope['version']]
    if len(matches)!=1:
        raise ValueError('Exact version missing or ambiguous')
    version = matches[0]
    infos = api.all('/v1/apps/'+scope['app_id']+'/appInfos?limit=200')
    infos = [i for i in infos if i['attributes'].get('appStoreState')=='PREPARE_FOR_SUBMISSION']
    if len(infos)!=1 or auth.ver_state(version['attributes'])!='PREPARE_FOR_SUBMISSION':
        raise ValueError('Only an unambiguous Prepare for Submission draft is writable')
    info = infos[0]
    il = api.all('/v1/appInfos/'+info['id']+'/appInfoLocalizations?limit=200')
    vl = api.all('/v1/appStoreVersions/'+version['id']+'/appStoreVersionLocalizations?limit=200')
    locales = {}
    for locale in scope['locales']:
        i = next((x for x in il if x['attributes']['locale']==locale),None)
        v = next((x for x in vl if x['attributes']['locale']==locale),None)
        locales[locale] = {'info': i, 'version': v}
        if media:
            locales[locale]['mac_placements'] = mac_placements(api, v['id']) if v else []
    return {'scope':scope,'version_id':version['id'],'info_id':info['id'],'state':'PREPARE_FOR_SUBMISSION','locales':locales}

def image_record(item, base, platform):
    if set(item)-{'approved','display_type','locale','path','sha256','size','file_name','width','height','format'}:
        raise ValueError('Unsupported screenshot fields')
    if item.get('approved') is not True:
        raise ValueError('Every screenshot needs explicit approved=true after visual review')
    if platform!='MAC_OS' or item.get('display_type')!='APP_DESKTOP':
        raise ValueError('Bundled screenshot validator supports reviewed Mac APP_DESKTOP assets only')
    p = (base/item['path']).resolve()
    info=probe_image(p)
    if info.get('format') not in ('PNG','JPEG') or (info.get('width'),info.get('height')) not in MAC_SIZES:
        raise ValueError('Unsupported Mac screenshot format/dimensions')
    if info.get('has_alpha') is not False:
        raise ValueError('App Store screenshot must have no alpha/transparency')
    data = p.read_bytes()
    return dict(item, path=str(p), sha256=hashlib.sha256(data).hexdigest(), size=len(data),
                file_name=p.name, width=info['width'], height=info['height'], format=info['format'])


def image_reference(image):
    return 'asc-manage-sha256-' + image['sha256']


def same_image(asset, image):
    return (asset.get('referenceName') == image_reference(image)
            and asset.get('fileName') == image['file_name']
            and asset.get('fileSize') == image['size'])

def prepare(manifest, before, base):
    if set(manifest)!= {'scope','locales','screenshots'}:
        raise ValueError('Manifest contains missing/unsupported top-level fields')
    scope=manifest['scope']
    if set(scope)!={'app_id','bundle_id','platform','version','locales'} or not scope['locales'] or len(set(scope['locales']))!=len(scope['locales']):
        raise ValueError('Explicit app ID, bundle, platform, version and unique locales required')
    if before['scope']!=scope or before['state']!='PREPARE_FOR_SUBMISSION':
        raise ValueError('Snapshot scope/state mismatch')
    if set(manifest['locales'])!=set(scope['locales']):
        raise ValueError('Locale scope mismatch')
    expected_fields=[]
    for locale in scope['locales']:
        fields = manifest['locales'][locale]
        if not isinstance(fields, dict) or set(fields)-(INFO|VERSION):
            raise ValueError('Unsupported metadata fields')
        if not fields:
            continue
        prior = before['locales'][locale]
        if not all(prior[kind] or (fields.keys() & names) for kind, names in [('info', INFO), ('version', VERSION)]):
            raise ValueError(f'{locale}: changes must leave both app info and version localizations present')
        for field,value in fields.items():
            if not isinstance(value,str): raise ValueError('Metadata must be strings')
            limit={'name':30,'subtitle':30,'description':4000,'promotionalText':170,'whatsNew':4000}.get(field)
            if limit and len(value)>limit: raise ValueError('Metadata length limit exceeded')
            if field=='keywords' and len(value.encode())>100: raise ValueError('Keywords exceed 100 UTF-8 bytes')
            if field.endswith('Url') and (not value.startswith('https://') or not urllib.parse.urlparse(value).netloc):
                raise ValueError('URLs must be reviewed public HTTPS URLs')
            resource=before['locales'][locale]['info' if field in INFO else 'version']
            old=None if not resource else resource['attributes'].get(field)
            expected_fields.append({'locale':locale,'field':field,'before':old,'after':value})
    images=[image_record(i,base,scope['platform']) for i in manifest['screenshots']]
    if not expected_fields and not images:
        raise ValueError('Provide at least one metadata field or screenshot')
    if len({(i['locale'],i['display_type'],i['sha256']) for i in images})!=len(images):
        raise ValueError('Duplicate screenshot in manifest')
    for i in images:
        if i['locale'] not in scope['locales']: raise ValueError('Screenshot locale outside scope')
        prior=before['locales'][i['locale']]
        if not prior['version'] and not (manifest['locales'][i['locale']].keys() & VERSION):
            raise ValueError('New screenshot locale requires version metadata')
        if 'mac_placements' not in prior:
            raise ValueError('Read a fresh Mac snapshot with screenshot placements before preparing screenshot changes')
        if any(p['type'] == SCREENSHOT and p['image'].get('referenceName') == image_reference(i)
               for p in prior['mac_placements']):
            raise ValueError('Screenshot already present; no duplication allowed')
    if not images:
        before = dict(before, locales={locale: {key: value[key] for key in ('info', 'version')}
                                       for locale, value in before['locales'].items()})
    changes = [field for field in expected_fields if field['before'] != field['after']]
    return {'scope':scope, 'before':before, 'before_hash':digest(before), 'changes':changes,
            'expected_fields':expected_fields, 'images':images}

def localization_body(kind, parent, locale, attributes):
    # Fastlane 2.232.2 incorrectly uses appStoreVersion on appInfoLocalizations.
    relation,parent_type=('appInfo','appInfos') if kind=='appInfoLocalizations' else ('appStoreVersion','appStoreVersions')
    return {'data':{'type':kind,'attributes':dict(attributes,locale=locale),
                    'relationships':{relation:{'data':{'type':parent_type,'id':parent}}}}}

def verify(plan, actual):
    results = [{'draft_identity': True, 'match': all(actual[key] == plan['before'][key]
                for key in ('scope', 'version_id', 'info_id', 'state'))}]
    for locale in dict.fromkeys(field['locale'] for field in plan['expected_fields']):
        records = actual['locales'][locale]
        results.append({'locale': locale, 'localizations_present': True, 'match': bool(records['info'] and records['version'])})
    for c in plan['expected_fields']:
        resource=actual['locales'][c['locale']]['info' if c['field'] in INFO else 'version']
        observed=None if resource is None else resource['attributes'].get(c['field'])
        results.append(dict(c,observed=observed,match=observed==c['after']))
    for locale in dict.fromkeys(image['locale'] for image in plan['images']):
        prior = plan['before']['locales'][locale]
        old = prior['mac_placements']
        placements = actual['locales'][locale]['mac_placements']
        version = actual['locales'][locale]['version']
        images = [image for image in plan['images'] if image['locale'] == locale]
        def identity(placement):
            return (placement['id'], placement['image_id'], placement['type'])
        appended = placements[len(old):]
        match = (bool(version) and (not prior['version'] or prior['version']['id'] == version['id'])
                 and list(map(identity, placements[:len(old)])) == list(map(identity, old))
                 and len(appended) == len(images))
        results.append({'locale': locale, 'placement_group': MAC_GROUP, 'placement_ids': [p['id'] for p in placements],
                        'order_and_existing_preserved': True, 'match': match})
        for index, image in enumerate(images):
            placement = appended[index] if index < len(appended) else None
            match = (placement is not None and placement['type'] == SCREENSHOT
                     and placement['state'].startswith('PARENT_')
                     and placement['image']['state'] in READY_IMAGE_STATES and same_image(placement['image'], image))
            results.append({'locale': locale, 'file_name': image['file_name'],
                            'placement_id': placement['id'] if placement else None, 'match': match})
    return results


def linkage(kind, resource_id):
    return {'data': {'type': kind, 'id': resource_id}}


def asset_catalog(api, plan):
    query = urllib.parse.urlencode({'filter[features]': 'APP_STORE_VERSIONS'})
    rows = api.all('/v1/appAssetLibraryRefData?'+query)
    matching_specs = set()
    specs = {}
    limits = set()
    for row in rows:
        attributes = row['attributes']
        specs.update((spec['specId'], spec) for spec in attributes['imageSpecs'])
        for entry in attributes['placementTypes']:
            if entry['placementTypeId'] == SCREENSHOT and IMAGE_CATEGORY in entry['acceptsAssetCategories']:
                for mapping in entry['specMappings']:
                    if mapping['placementGroupId'] == MAC_GROUP:
                        matching_specs.update(mapping['specs'])
        for feature in attributes['features']:
            if feature['featureId'] == 'APP_STORE_VERSIONS':
                for policy in feature['placementPolicies']:
                    if policy['placementType'] == SCREENSHOT:
                        limits.update(rule['maxCount'] for rule in policy['groupLimits'] if MAC_GROUP in rule['groupIds'])
    if len(limits) != 1 or not matching_specs:
        raise ValueError('Apple did not return an unambiguous Mac screenshot specification and limit')
    limit = limits.pop()
    for locale in plan['scope']['locales']:
        images = [image for image in plan['images'] if image['locale'] == locale]
        existing = plan['before']['locales'][locale]['mac_placements']
        if images and sum(p['type'] == SCREENSHOT for p in existing) + len(images) > limit:
            raise ValueError(f'{locale}: screenshot count would exceed Apple’s Mac placement limit ({limit})')
    for image in plan['images']:
        mime = 'image/png' if image['format'] == 'PNG' else 'image/jpeg'
        extension = Path(image['file_name']).suffix.lower()
        allowed = set()
        for spec_id in matching_specs:
            spec = specs[spec_id]
            dimensions = spec['dimensions']
            if (dimensions['minWidth'] <= image['width'] <= dimensions['maxWidth']
                    and dimensions['minHeight'] <= image['height'] <= dimensions['maxHeight']
                    and mime in spec['mimeTypes'] and extension in spec['fileExtensions']
                    and image['size'] <= spec['maxFileSize']):
                allowed.add(spec_id)
        if not allowed:
            raise ValueError(f"{image['file_name']}: image does not match Apple’s Mac screenshot specifications")
        yield allowed


def upload_image(api, library_id, image, record):
    query = urllib.parse.urlencode({'filter[referenceName]': image_reference(image)})
    rows = api.all('/v1/appAssetLibraries/'+library_id+'/images?'+query)
    candidates = [row for row in rows if same_image(row['attributes'], image)
                  and row['attributes']['category'] == IMAGE_CATEGORY]
    if len(candidates) > 1:
        raise ValueError('Multiple library images match the prepared screenshot; inspect the library before retrying')
    if candidates:
        shot = candidates[0]
        state = shot['attributes']['state']
        record({'image_id': shot['id'], 'status': state})
        if state == 'UPLOAD_COMPLETE' or state in READY_IMAGE_STATES:
            return shot['id']
        raise ValueError(f"Matching library image is {state}; inspect its saved ID before retrying")
    data = Path(image['path']).read_bytes()
    if hashlib.sha256(data).hexdigest() != image['sha256']:
        raise ValueError('Screenshot changed after prepare')
    kind = 'appAssetLibraryImages'
    payload = {'type': kind, 'attributes': {'fileName': image['file_name'], 'fileSize': len(data),
               'referenceName': image_reference(image), 'category': IMAGE_CATEGORY},
               'relationships': {'assetLibrary': linkage('appAssetLibraries', library_id)}}
    shot = api.request('POST', '/v1/'+kind, {'data': payload})['data']
    image_id = shot['id']
    record({'image_id': image_id, 'status': 'reserved'})
    for operation in shot['attributes']['uploadOperations']:
        if urllib.parse.urlparse(operation['url']).scheme != 'https':
            raise ValueError('Non-HTTPS upload operation')
        offset, length = operation['offset'], operation['length']
        if offset < 0 or length <= 0 or offset+length > len(data):
            raise ValueError('Invalid upload range')
        try:
            request = urllib.request.Request(operation['url'], data=data[offset:offset+length],
                        method=operation['method'], headers={h['name']: h['value'] for h in operation['requestHeaders']})
            with urllib.request.urlopen(request, timeout=60) as response:
                response.read()
        except (OSError, ValueError, http.client.HTTPException):
            raise ValueError('Screenshot transfer failed; reserved image ID retained in receipt') from None
    api.request('PATCH', '/v1/'+kind+'/'+image_id,
                {'data': {'type': kind, 'id': image_id, 'attributes': {'uploaded': True}}})
    record({'image_id': image_id, 'status': 'uploaded'})
    return image_id


def wait_for_images(api, image_specs):
    deadline = time.monotonic() + 60
    pending = dict(image_specs)
    while pending:
        for image_id, allowed in list(pending.items()):
            image = api.request('GET', '/v1/appAssetLibraryImages/'+image_id)['data']['attributes']
            if image['state'] in READY_IMAGE_STATES:
                if image['specId'] not in allowed:
                    raise ValueError(f'{image_id}: Apple matched an incompatible screenshot specification')
                del pending[image_id]
            elif image['state'] != 'UPLOAD_COMPLETE':
                raise ValueError(f"{image_id}: image processing state is {image['state']}; inspect the receipt")
        if pending:
            if time.monotonic() >= deadline:
                raise ValueError('Images are still processing; use the receipt and reprepare from a fresh read before continuing')
            time.sleep(2)


def place_images(api, plan, current, image_ids, record):
    for locale in dict.fromkeys(image['locale'] for image in plan['images']):
        current_locale = current['locales'][locale]
        prior = plan['before']['locales'][locale]
        localization = current_locale['version']
        if not localization or (prior['version'] and prior['version']['id'] != localization['id']):
            raise ValueError(f'{locale}: version localization changed or is missing; inspect the receipt')
        localization_id = localization['id']
        version = linkage('appStoreVersionLocalizations', localization_id)
        existing = prior['mac_placements']
        if current_locale['mac_placements'] != existing:
            raise ValueError(f'{locale}: Mac placements changed during apply; inspect the receipt')
        current_ids = [row['id'] for row in existing]
        ordered = current_ids.copy()
        for image, image_id in zip(plan['images'], image_ids):
            if image['locale'] != locale:
                continue
            if any(row['image_id'] == image_id and row['type'] == SCREENSHOT for row in existing):
                raise ValueError(f'{locale}: image is already placed; inspect the receipt')
            payload = {'type': 'appAssetLibraryPlacements',
                       'attributes': {'placementType': SCREENSHOT, 'placementGroup': MAC_GROUP},
                       'relationships': {'appStoreVersionLocalization': version,
                                         'image': linkage('appAssetLibraryImages', image_id)}}
            placement = api.request('POST', '/v1/appAssetLibraryPlacements', {'data': payload})['data']
            ordered.append(placement['id'])
            record({'locale': locale, 'image_id': image_id, 'placement_id': placement['id'], 'status': 'placed'})
        observed = [row['id'] for row in mac_placements(api, localization_id)]
        if observed == ordered:
            continue
        if set(observed) != set(ordered) or [pid for pid in observed if pid in current_ids] != current_ids:
            raise ValueError(f'{locale}: Mac placements changed during apply; inspect the receipt')
        ordering = {'type': 'appAssetLibraryPlacementOrderingRequests', 'attributes': {'placementGroup': MAC_GROUP},
                    'relationships': {'appStoreVersionLocalization': version, 'orderedPlacements':
                                      {'data': [linkage('appAssetLibraryPlacements', pid)['data'] for pid in ordered]}}}
        api.request('POST', '/v1/appAssetLibraryPlacementOrderingRequests', {'data': ordering})
        record({'locale': locale, 'placement_ids': ordered, 'status': 'ordered'})


def validate_plan_schema(plan):
    if 'expected_fields' not in plan:
        raise ValueError('This plan predates full readback validation; prepare it again from the original manifest')


def apply(api, plan, receipt_path):
    validate_plan_schema(plan)
    if digest(plan['before'])!=plan['before_hash']:raise ValueError('Prepared snapshot integrity mismatch')
    manifest={'scope':plan['scope'],'locales':{l:{} for l in plan['scope']['locales']},'screenshots':plan['images']}
    for c in plan['expected_fields']:manifest['locales'][c['locale']][c['field']]=c['after']
    validated=prepare(manifest,plan['before'],Path('.'))
    if any(validated[key] != plan[key] for key in ('changes', 'expected_fields', 'images')):
        raise ValueError('Plan changed or invalid; prepare again')
    has_images = bool(plan['images'])
    current=snapshot(api,plan['scope'],media=True) if has_images else snapshot(api,plan['scope'])
    if digest(current)!=plan['before_hash']: raise ValueError('Draft changed since prepare; prepare a new diff')
    if has_images:
        specifications = list(asset_catalog(api, plan))
        library_id = api.request('GET', '/v1/apps/'+plan['scope']['app_id']+'/assetLibrary')['data']['id']
    receipt={'scope':plan['scope'],'operations':[],'complete':False}
    def record(operation):
        receipt['operations'].append(operation);receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    record({'stage':'preflight','before_hash':plan['before_hash']})
    for locale in plan['scope']['locales']:
        for section,allowed,kind,parent in [('info',INFO,'appInfoLocalizations',current['info_id']),('version',VERSION,'appStoreVersionLocalizations',current['version_id'])]:
            attrs={c['field']:c['after'] for c in plan['changes'] if c['locale']==locale and c['field'] in allowed}
            if not attrs: continue
            resource=current['locales'][locale][section]
            if resource:
                api.request('PATCH','/v1/'+kind+'/'+resource['id'],{'data':{'type':kind,'id':resource['id'],'attributes':attrs}})
            else:
                api.request('POST','/v1/'+kind,localization_body(kind,parent,locale,attrs))
            record({'locale':locale,'fields':sorted(attrs),'status':'written'})
    if has_images:
        image_ids = []
        by_reference = {}
        image_specs = {}
        for image, allowed in zip(plan['images'], specifications):
            key = (image['sha256'], image['file_name'])
            if key not in by_reference:
                by_reference[key] = upload_image(api, library_id, image, record)
            image_id = by_reference[key]
            image_ids.append(image_id)
            image_specs[image_id] = allowed
        wait_for_images(api, image_specs)
        current = snapshot(api, plan['scope'], media=True)
        if any(current[key] != plan['before'][key] for key in ('version_id', 'info_id')):
            raise ValueError('Draft identity changed during apply; inspect the receipt')
        place_images(api, plan, current, image_ids, record)
    actual=snapshot(api,plan['scope'],media=True) if has_images else snapshot(api,plan['scope'])
    checks=verify(plan,actual)
    receipt.update(after=actual,checks=checks,complete=all(c['match'] for c in checks))
    receipt_path.write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    return receipt

def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='mode',required=True)
    read=sub.add_parser('read');read.add_argument('--scope',required=True);read.add_argument('--output',required=True)
    read.add_argument('--metadata-only', action='store_true', help='Skip Mac Asset Library placements')
    prep=sub.add_parser('prepare');prep.add_argument('--manifest',required=True);prep.add_argument('--before',required=True);prep.add_argument('--output',required=True)
    for mode in ['apply','readback']:
        cmd=sub.add_parser(mode);cmd.add_argument('--plan',required=True);cmd.add_argument('--output',required=True)
        if mode=='apply':cmd.add_argument('--authorized',action='store_true',help='Use only for an explicitly authorized scope')
    a=p.parse_args();load=lambda path:json.loads(Path(path).read_text())
    if a.mode=='prepare':
        result=prepare(load(a.manifest),load(a.before),Path(a.manifest).resolve().parent)
    elif a.mode=='read':
        scope = load(a.scope)
        result = snapshot(API(), scope, media=scope['platform']=='MAC_OS' and not a.metadata_only)
    else:
        plan=load(a.plan)
        validate_plan_schema(plan)
        if a.mode=='apply':
            if not a.authorized:p.error('apply requires explicit authorization and --authorized')
            result=apply(API(),plan,Path(a.output))
        else:
            actual=snapshot(API(),plan['scope'],media=bool(plan['images']));checks=verify(plan,actual)
            result={'after':actual,'checks':checks,'complete':all(c['match'] for c in checks)}
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({'mode':a.mode,'complete':result.get('complete'),'changes':len(result.get('changes',[]))}))
    if result.get('complete') is False:raise SystemExit('Readback pending/mismatch; no further writes. Run readback again after processing.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError) as error:raise SystemExit(str(error))
