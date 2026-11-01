"""Replace the App Store screenshots of the editable version for every localization.

    ASC_ISSUER_ID=... python3 marketing/store-screenshots/upload_appstore.py            # dry run
    ASC_ISSUER_ID=... python3 marketing/store-screenshots/upload_appstore.py --commit   # upload

iPhone 6.9" screenshots come from out/iphone/<lang>/, iPad 13" from out/ipad/<lang>/.
The key is read from ASC_PRIVATE_KEY_PATH, else ~/.config/birdr/AuthKey_<ASC_KEY_ID>.p8.
Screenshots can only change on a version that is not live yet (Prepare for Submission).
"""
import argparse
import hashlib
import os
import time
from pathlib import Path

import jwt
import requests

API = 'https://api.appstoreconnect.apple.com/v1'
BUNDLE_ID = 'pro.birdr.app'
OUT = Path(__file__).resolve().parent / 'out'
SETS = {'APP_IPHONE_67': 'iphone', 'APP_IPAD_PRO_3GEN_129': 'ipad'}
EDITABLE = {'PREPARE_FOR_SUBMISSION', 'DEVELOPER_REJECTED', 'REJECTED', 'METADATA_REJECTED', 'INVALID_BINARY'}


def token():
    key_id = os.environ.get('ASC_KEY_ID', 'LP2D34WCR7')
    issuer = os.environ['ASC_ISSUER_ID']
    key_path = os.environ.get('ASC_PRIVATE_KEY_PATH') or Path.home() / f'.config/birdr/AuthKey_{key_id}.p8'
    now = int(time.time())
    return jwt.encode(
        {'iss': issuer, 'iat': now, 'exp': now + 1200, 'aud': 'appstoreconnect-v1'},
        Path(key_path).read_text(),
        algorithm='ES256',
        headers={'kid': key_id, 'typ': 'JWT'},
    )


def caption_lang(locale):
    """App Store locale (en-US, nl-NL, es-MX, pt-BR, ja ...) to a captions.json key."""
    if locale == 'pt-BR':
        return 'pt-BR'
    base = locale.split('-')[0]
    return base if (OUT / 'iphone' / base).is_dir() else 'en'


class ASC:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers['Authorization'] = f'Bearer {token()}'

    def call(self, method, path, **kw):
        url = path if path.startswith('http') else API + path
        res = self.s.request(method, url, **kw)
        if res.status_code >= 400:
            raise RuntimeError(f'{method} {path}: {res.status_code} {res.text[:500]}')
        return res.json() if res.content else {}

    def upload(self, set_id, f):
        data = f.read_bytes()
        shot = self.call('POST', '/appScreenshots', json={'data': {
            'type': 'appScreenshots',
            'attributes': {'fileName': f.name, 'fileSize': len(data)},
            'relationships': {'appScreenshotSet': {'data': {'type': 'appScreenshotSets', 'id': set_id}}},
        }})['data']
        for op in shot['attributes']['uploadOperations']:
            chunk = data[op['offset']:op['offset'] + op['length']]
            headers = {h['name']: h['value'] for h in op['requestHeaders']}
            requests.request(op['method'], op['url'], data=chunk, headers=headers).raise_for_status()
        self.call('PATCH', f"/appScreenshots/{shot['id']}", json={'data': {
            'type': 'appScreenshots', 'id': shot['id'],
            'attributes': {'uploaded': True, 'sourceFileChecksum': hashlib.md5(data).hexdigest()},
        }})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', action='store_true')
    args = parser.parse_args()
    asc = ASC()

    app = asc.call('GET', '/apps', params={'filter[bundleId]': BUNDLE_ID})['data'][0]
    versions = asc.call('GET', f"/apps/{app['id']}/appStoreVersions",
                        params={'filter[platform]': 'IOS', 'limit': 10})['data']
    editable = [v for v in versions if v['attributes']['appStoreState'] in EDITABLE]
    if not editable:
        states = ', '.join(f"{v['attributes']['versionString']}={v['attributes']['appStoreState']}" for v in versions)
        raise SystemExit(f'No editable version; screenshots can only change on a new version. Versions: {states}')
    version = editable[0]
    print('version', version['attributes']['versionString'], version['attributes']['appStoreState'])

    locs = asc.call('GET', f"/appStoreVersions/{version['id']}/appStoreVersionLocalizations")['data']
    for loc in locs:
        locale = loc['attributes']['locale']
        lang = caption_lang(locale)
        sets = {s['attributes']['screenshotDisplayType']: s for s in
                asc.call('GET', f"/appStoreVersionLocalizations/{loc['id']}/appScreenshotSets")['data']}
        for display_type, device in SETS.items():
            files = sorted((OUT / device / lang).glob('*.png'))
            print(f'{locale}: {display_type} <- {device}/{lang} ({len(files)} images)')
            if not args.commit:
                continue
            if display_type in sets:
                set_id = sets[display_type]['id']
                for old in asc.call('GET', f'/appScreenshotSets/{set_id}/appScreenshots')['data']:
                    asc.call('DELETE', f"/appScreenshots/{old['id']}")
            else:
                set_id = asc.call('POST', '/appScreenshotSets', json={'data': {
                    'type': 'appScreenshotSets',
                    'attributes': {'screenshotDisplayType': display_type},
                    'relationships': {'appStoreVersionLocalization': {
                        'data': {'type': 'appStoreVersionLocalizations', 'id': loc['id']}}},
                }})['data']['id']
            for f in files:
                asc.upload(set_id, f)
    print('done' if args.commit else 'dry run, nothing changed (pass --commit to upload)')


if __name__ == '__main__':
    main()
