"""Replace the Play Store screenshots for every listing language.

    python3 marketing/store-screenshots/upload_play.py            # dry run: list what would change
    python3 marketing/store-screenshots/upload_play.py --commit   # upload and commit the edit

Phone screenshots come from out/android/<lang>/, 7" and 10" tablet screenshots from
out/ipad/<lang>/. The icon and feature graphic (from feature_graphic.py) go up only when asked:

    python3 marketing/store-screenshots/upload_play.py --types icon,featureGraphic --commit

Uses the same service account as mobile/scripts/release-android.cjs.
"""
import argparse
import json
import os
import time
from pathlib import Path

import jwt
import requests

PACKAGE = 'pro.birdr.app'
API = f'https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{PACKAGE}'
UPLOAD = f'https://androidpublisher.googleapis.com/upload/androidpublisher/v3/applications/{PACKAGE}'
OUT = Path(__file__).resolve().parent / 'out'
SETS = {'phoneScreenshots': 'android', 'sevenInchScreenshots': 'ipad', 'tenInchScreenshots': 'ipad'}
SINGLES = ('icon', 'featureGraphic')


def image_files(image_type, lang):
    if image_type == 'icon':
        return [OUT / 'play' / 'icon-512.png']
    if image_type == 'featureGraphic':
        f = OUT / 'play' / f'feature-{lang}.png'
        return [f if f.exists() else OUT / 'play' / 'feature-en.png']
    return sorted((OUT / SETS[image_type] / lang).glob('*.png'))


def credentials():
    path = os.environ.get('PLAY_SERVICE_ACCOUNT_JSON_PATH') or Path.home() / '.config/birdr/play-service-account.json'
    return json.loads(Path(path).read_text())


def access_token(creds):
    now = int(time.time())
    assertion = jwt.encode(
        {
            'iss': creds['client_email'],
            'scope': 'https://www.googleapis.com/auth/androidpublisher',
            'aud': 'https://oauth2.googleapis.com/token',
            'iat': now,
            'exp': now + 3600,
        },
        creds['private_key'],
        algorithm='RS256',
    )
    res = requests.post(
        'https://oauth2.googleapis.com/token',
        data={'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer', 'assertion': assertion},
    )
    res.raise_for_status()
    return res.json()['access_token']


def caption_lang(play_language):
    """Play listing language (nl-NL, es-419, pt-BR ...) to a captions.json key."""
    if play_language == 'pt-BR':
        return 'pt-BR'
    base = play_language.split('-')[0]
    return base if (OUT / 'android' / base).is_dir() else 'en'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', action='store_true')
    parser.add_argument('--language', help='only this listing language, e.g. nl-NL')
    parser.add_argument('--types', default=','.join(SETS), help='comma-separated image types')
    args = parser.parse_args()

    session = requests.Session()
    session.headers['Authorization'] = f'Bearer {access_token(credentials())}'

    edit = session.post(f'{API}/edits').json()['id']
    try:
        listings = session.get(f'{API}/edits/{edit}/listings').json().get('listings', [])
        for listing in listings:
            language = listing['language']
            if args.language and language != args.language:
                continue
            lang = caption_lang(language)
            for image_type in (*SETS, *SINGLES):
                if image_type not in args.types.split(','):
                    continue
                files = image_files(image_type, lang)
                print(f'{language}: {image_type} <- {", ".join(f.relative_to(OUT).as_posix() for f in files)}')
                if not args.commit:
                    continue
                session.delete(f'{API}/edits/{edit}/listings/{language}/{image_type}').raise_for_status()
                for f in files:
                    res = session.post(
                        f'{UPLOAD}/edits/{edit}/listings/{language}/{image_type}',
                        params={'uploadType': 'media'},
                        data=f.read_bytes(),
                        headers={'Content-Type': 'image/png'},
                    )
                    res.raise_for_status()
        if args.commit:
            res = session.post(f'{API}/edits/{edit}:commit')
            if res.status_code >= 400:
                raise SystemExit(f'commit failed: {res.status_code} {res.text}')
            print('committed edit', edit)
        else:
            session.delete(f'{API}/edits/{edit}')
            print('dry run, nothing changed (pass --commit to upload)')
    except Exception:
        session.delete(f'{API}/edits/{edit}')
        raise


if __name__ == '__main__':
    main()
