"""Put the product page header (from app_store_header.py) on every localization of the editable version.

    ASC_ISSUER_ID=... python3 marketing/store-screenshots/upload_appstore_header.py            # dry run
    ASC_ISSUER_ID=... python3 marketing/store-screenshots/upload_appstore_header.py --commit   # upload

The image goes into the app's asset library once, then gets a PRODUCT_PAGE_HEADER_ASSET
placement per localization. Placements cannot be edited, so an existing one is deleted first.
"""
import argparse
import time

import requests

from upload_appstore import ASC, BUNDLE_ID, EDITABLE, OUT

HEADER = OUT / 'appstore' / 'header-3840x1646.png'
PLACEMENT = 'PRODUCT_PAGE_HEADER_ASSET'


def upload_image(asc, library_id):
    data = HEADER.read_bytes()
    image = asc.call('POST', '/appAssetLibraryImages', json={'data': {
        'type': 'appAssetLibraryImages',
        'attributes': {'category': 'CREATIVE_ASSETS', 'fileName': HEADER.name, 'fileSize': len(data)},
        'relationships': {'assetLibrary': {'data': {'type': 'appAssetLibraries', 'id': library_id}}},
    }})['data']
    for op in image['attributes']['uploadOperations']:
        chunk = data[op['offset']:op['offset'] + op['length']]
        headers = {h['name']: h['value'] for h in op['requestHeaders']}
        requests.request(op['method'], op['url'], data=chunk, headers=headers).raise_for_status()
    asc.call('PATCH', f"/appAssetLibraryImages/{image['id']}", json={'data': {
        'type': 'appAssetLibraryImages', 'id': image['id'], 'attributes': {'uploaded': True},
    }})
    for _ in range(60):  # processed once Apple has rendered the image
        attrs = asc.call('GET', f"/appAssetLibraryImages/{image['id']}")['data']['attributes']
        if attrs.get('imageAsset') or attrs.get('stateDetails'):
            break
        time.sleep(5)
    if not attrs.get('imageAsset'):
        raise SystemExit(f"image {image['id']} not processed: {attrs.get('state')} {attrs.get('stateDetails')}")
    return image['id']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', action='store_true')
    parser.add_argument('--image-id', help='place an image already in the asset library instead of uploading')
    args = parser.parse_args()
    asc = ASC()

    app = asc.call('GET', '/apps', params={'filter[bundleId]': BUNDLE_ID})['data'][0]
    versions = asc.call('GET', f"/apps/{app['id']}/appStoreVersions",
                        params={'filter[platform]': 'IOS', 'limit': 10})['data']
    editable = [v for v in versions if v['attributes']['appStoreState'] in EDITABLE]
    if not editable:
        raise SystemExit('No editable version; the header can only change on a new version.')
    version = editable[0]
    locs = asc.call('GET', f"/appStoreVersions/{version['id']}/appStoreVersionLocalizations")['data']
    print('version', version['attributes']['versionString'], '->', ', '.join(l['attributes']['locale'] for l in locs))
    if not args.commit:
        print('dry run, nothing changed (pass --commit to upload)')
        return

    if args.image_id:
        image_id = args.image_id
    else:
        library_id = asc.call('GET', f"/apps/{app['id']}/assetLibrary")['data']['id']
        image_id = upload_image(asc, library_id)
        print('uploaded image', image_id)
    for loc in locs:
        existing = asc.call('GET', f"/appStoreVersionLocalizations/{loc['id']}/placements")['data']
        for p in existing:
            if p['attributes'].get('placementType') == PLACEMENT:
                asc.call('DELETE', f"/appAssetLibraryPlacements/{p['id']}")
        asc.call('POST', '/appAssetLibraryPlacements', json={'data': {
            'type': 'appAssetLibraryPlacements',
            'attributes': {'placementType': PLACEMENT},
            'relationships': {
                'appStoreVersionLocalization': {'data': {'type': 'appStoreVersionLocalizations', 'id': loc['id']}},
                'image': {'data': {'type': 'appAssetLibraryImages', 'id': image_id}},
            },
        }})
        print(loc['attributes']['locale'], 'header placed')
    print('done')


if __name__ == '__main__':
    main()
