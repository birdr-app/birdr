import csv
import re

import requests
from django.conf import settings

from jizz.models import Species, Country, CountrySpecies, SpeciesImage, SpeciesSound, SpeciesVideo, Language, \
    SpeciesName, TaxonomicOrder, TaxonomicFamily, TaxonomicGenus
from jizz.services.taxonomy_texts import fetch_ebird_taxonomy, EBIRD_LOCALE_EN
from jizz.taxonomy_parse import parse_genus_from_sci_name

SERVER_NAME = 'api.ebird.org'
API_VERSION = 'v2'

# Status and Trends download API (regional stats CSV)
ST_DOWNLOAD_BASE = 'https://st-download.ebird.org/v1'

# GBIF API (https://techdocs.gbif.org/en/openapi/)
GBIF_API_BASE = 'https://api.gbif.org/v1'
# Set User-Agent so GBIF can contact us if there are issues (recommended in their docs)
GBIF_HEADERS = {
    'User-Agent': 'JizzBirdApp/1.0 (https://github.com/jizz-bird)',
}


def gbif_species_match(scientific_name):
    """
    Resolve a scientific name to GBIF usageKey (taxonKey) via the Species API.
    Returns the usageKey (int) or None if no match or on error.
    """
    if not scientific_name or not str(scientific_name).strip():
        return None
    url = f'{GBIF_API_BASE}/species/match'
    try:
        r = requests.get(
            url,
            params={'name': scientific_name.strip()},
            headers=GBIF_HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        # Prefer species-level key; usageKey can be genus etc. for fuzzy matches
        key = data.get('speciesKey') or data.get('usageKey')
        if key is not None and data.get('matchType') != 'NONE':
            return int(key)
        return None
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def gbif_occurrence_count(country_code, taxon_key):
    """
    Return the number of occurrence records in GBIF for the given country and taxon.
    Uses occurrence search with limit=0 to get only the count.
    """
    if not country_code or taxon_key is None:
        return 0
    url = f'{GBIF_API_BASE}/occurrence/search'
    try:
        r = requests.get(
            url,
            params={
                'country': country_code.upper(),
                'taxonKey': taxon_key,
                'limit': 0,
            },
            headers=GBIF_HEADERS,
            timeout=60,
        )
        r.raise_for_status()
        return int(r.json().get('count', 0))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return 0


def ebird_st_list_files(species_code, access_key, version_year=2023):
    """
    List available files for a species from eBird Status and Trends API.
    Returns list of object paths (e.g. ['2023/woothr/regional_stats.csv', ...]).
    See https://ebird.github.io/ebirdst/articles/api.html
    """
    url = f'{ST_DOWNLOAD_BASE}/list-obj/{version_year}/{species_code}'
    res = requests.get(url, params={'key': access_key}, timeout=60)
    res.raise_for_status()
    return res.json()


def ebird_st_download_regional_stats(species_code, access_key, version_year=2023):
    """
    Download the regional_stats.csv for a species from eBird Status and Trends.
    Returns CSV content as string, or None if no regional_stats.csv is available.
    """
    paths = ebird_st_list_files(species_code, access_key, version_year)
    obj_key = None
    for p in paths:
        if isinstance(p, str) and p.endswith('regional_stats.csv'):
            obj_key = p
            break
    if not obj_key:
        return None
    url = f'{ST_DOWNLOAD_BASE}/fetch'
    r = requests.get(url, params={'objKey': obj_key, 'key': access_key}, timeout=120)
    r.raise_for_status()
    return r.text


def download_ebird_regional_zip(url):
    """
    Fetch URL; if response is a ZIP, extract the first .csv and return its content as string.
    If response is already CSV (text), return as-is.
    """
    import io
    import zipfile
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    content_type = (r.headers.get('Content-Type') or '').lower()
    if 'zip' in content_type or r.content[:4] == b'PK\x03\x04':
        with zipfile.ZipFile(io.BytesIO(r.content), 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith('.csv'):
                    return zf.read(name).decode('utf-8', errors='replace')
        raise ValueError('ZIP contains no CSV file')
    return r.text


def sync_species():
    results = fetch_ebird_taxonomy(locale=EBIRD_LOCALE_EN, categories='species')
    for row in results:
        if row['category'] != 'species':
            continue
        order, _ = TaxonomicOrder.objects.update_or_create(
            name_latin=row['order'],
            defaults={'name_en': row['order'], 'name_nl': row['order']},
        )
        family, _ = TaxonomicFamily.objects.update_or_create(
            name_latin=row['familySciName'],
            defaults={
                'name_en': row['familyComName'],
                'name_nl': row['familyComName'],
                'taxonomic_order': order,
            },
        )
        genus = None
        genus_name = parse_genus_from_sci_name(row['sciName'])
        if genus_name:
            genus, _ = TaxonomicGenus.objects.update_or_create(
                name_latin=genus_name,
                defaults={
                    'name_en': genus_name,
                    'name_nl': genus_name,
                    'taxonomic_family': family,
                },
            )
        tax_ordering = row.get('taxonOrder')
        Species.objects.update_or_create(
            code=row['speciesCode'],
            defaults={
                'name': row['comName'],
                'name_latin': row['sciName'],
                'taxonomic_order': order,
                'taxonomic_family': family,
                'taxonomic_genus': genus,
                'tax_ordering': tax_ordering,
            },
        )

    results_nl = fetch_ebird_taxonomy(locale='nl', categories='species')
    for row in results_nl:
        if row['category'] != 'species':
            continue
        Species.objects.update_or_create(
            code=row['speciesCode'],
            defaults={
                'name_nl': row['comName'],
            },
        )
    print("Done syncing species")


def sync_names():

    for lang in Language.objects.all():
        print(f'getting names for {lang.name}')
        data = requests.get(
            f'https://{SERVER_NAME}/{API_VERSION}/ref/taxonomy/ebird?locale={lang.code}&fmt=json',
            headers={'x-ebirdapitoken': settings.EBIRD_API_TOKEN}
        )
        results = data.json()
        for row in results:
            species = Species.objects.filter(code=row['speciesCode']).first()
            if species:
                SpeciesName.objects.update_or_create(
                    language=lang,
                    species=species,
                    defaults={
                        'name': row['comName'],
                    }
                )
    print("Done syncing names")


def sync_languages():
    data = requests.get(
        f'https://{SERVER_NAME}/{API_VERSION}/ref/taxa-locales/ebird',
        headers={'x-ebirdapitoken': settings.EBIRD_API_TOKEN}
    )
    results = data.json()
    for row in results:
        country, created = Language.objects.update_or_create(
            code=row['code'],
            defaults={
                'name': row['name'],
            }
        )
    print("Done syncing languages")


def sync_regions(country, code):
    data = requests.get(
        f'https://{SERVER_NAME}/{API_VERSION}/product/spplist/{code}',
        headers={'X-eBirdApiToken': settings.EBIRD_API_TOKEN},
        timeout=90,
    )
    data.raise_for_status()
    codes = data.json()
    if not isinstance(codes, list):
        raise ValueError(f'eBird spplist for {code} did not return a species list')

    ids = list(Species.objects.filter(code__in=codes).values_list('id', flat=True))
    parent_attrs = {}
    parent_id = getattr(country, 'parent_id', None)
    if parent_id and ids:
        parent_attrs = {
            species_id: (status, frequency, frequency_pct)
            for species_id, status, frequency, frequency_pct in CountrySpecies.objects.filter(
                country_id=parent_id,
                species_id__in=ids,
            ).values_list('species_id', 'status', 'frequency', 'frequency_pct')
        }
    specs = []
    for species_id in ids:
        parent_row = parent_attrs.get(species_id)
        status = 'native'
        frequency = None
        frequency_pct = None
        if parent_row:
            parent_status, parent_frequency, parent_frequency_pct = parent_row
            if parent_status and parent_status != 'unknown':
                status = parent_status
            if parent_frequency:
                frequency = parent_frequency
                frequency_pct = parent_frequency_pct
        specs.append(
            CountrySpecies(
                country_id=country.code,
                species_id=species_id,
                status=status,
                frequency=frequency,
                frequency_pct=frequency_pct,
            )
        )
    print('Got some work to do ', len(specs))
    CountrySpecies.objects.bulk_create(specs, ignore_conflicts=True)


def sync_country(code='ZNZ'):
    if code == 'world':
        sync_world()
        return
    country = Country.objects.get(code=code)
    if country.codes:
        for code in country.codes.split(','):
            sync_regions(country, code)
    else:
        sync_regions(country, country.code)


def sync_world():
    country = Country.objects.get(code='world')
    for spec in Species.objects.all():
        CountrySpecies.objects.update_or_create(
            country=country,
            species=spec,
            defaults={'status': 'native'}
        )


def get_media(id=1, media='photo'):
    species = Species.objects.get(id=id)
    data = requests.get(
        f'https://media.ebird.org/catalog?taxonCode={species.code}&mediaType={media}&sort=rating_rank_desc'
    )
    pattern = r'assetId:(\d+)'
    matches = re.findall(pattern, data.text)
    print(f'found {len(matches)} matches')
    for match in matches[0:10]:
        if media == 'photo':
            SpeciesImage.objects.get_or_create(
                url=f'https://cdn.download.ams.birds.cornell.edu/api/v2/asset/{match}/1800',
                species=species
            )
        elif media == 'audio':
            SpeciesSound.objects.get_or_create(
                url=f'https://cdn.download.ams.birds.cornell.edu/api/v2/asset/{match}/mp3',
                species=species
            )
        elif media == 'video':
           SpeciesVideo.objects.get_or_create(
                url=f'https://cdn.download.ams.birds.cornell.edu/api/v2/asset/{match}/mp4/1280',
                species=species
            )



def get_images(id=1, save=True):
    species = Species.objects.get(id=id)
    data = requests.get(
        f'https://ebird.org/species/{species.code}'
    )
    pattern = r'https://cdn\.download\.ams\.birds\.cornell\.edu/api/v1/asset/(\d+)/1800'
    matches = re.findall(pattern, data.text)


    for match in matches:
        SpeciesImage.objects.get_or_create(
            url=f'https://cdn.download.ams.birds.cornell.edu/api/v1/asset/{match}/1800',
            species=species
        )


def get_sounds(id=1, save=True):
    species = Species.objects.get(id=id)
    data = requests.get(
        f'https://media.ebird.org/catalog?taxonCode={species.code}&mediaType=audio&sort=rating_rank_desc'
    )
    pattern = r'assetId:(\d+)'
    matches = re.findall(pattern, data.text)
    for match in matches[0:5]:
        SpeciesSound.objects.get_or_create(
            url=f'https://cdn.download.ams.birds.cornell.edu/api/v2/asset/{match}/mp3',
            species=species
        )


def get_videos(id=1):
    species = Species.objects.get(id=id)
    data = requests.get(
        f'https://media.ebird.org/catalog?taxonCode={species.code}&mediaType=video&sort=rating_rank_desc'
    )
    pattern = r'assetId:(\d+)'
    matches = re.findall(pattern, data.text)
    for match in matches[0:5]:
        SpeciesVideo.objects.get_or_create(
            url=f'https://cdn.download.ams.birds.cornell.edu/api/v2/asset/{match}/mp4/1280',
            species=species
        )


def get_country_images(code='TZ-15'):
    country = Country.objects.get(code=code)
    nr = 0
    count = CountrySpecies.objects.filter(country=country).count()
    print (f'{country.name} {count} species')
    count = CountrySpecies.objects.filter(country=country, species__images=None).count()
    print (f'{count} still need to retrieve images')
    for species in CountrySpecies.objects.filter(country=country, species__images=None):
        nr += 1
        if species.species.images.count() == 0:
            print(f'🔎 [{nr}/{count}] {species.species.name}' , end='\r')
            get_images(species.species.id)
            print(f'☑️ [{nr}/{count}] images {species.species.name}')
        else:
            print(f'☑️ [{nr}/{count}] images {species.species.name}')

    nr = 0
    count = CountrySpecies.objects.filter(country=country, species__sounds=None).count()
    print (f'{count} still need to retrieve sounds')
    for species in CountrySpecies.objects.filter(country=country, species__sounds=None):
        nr += 1
        if species.species.sounds.count() == 0:
            print(f'🔎 [{nr}/{count}] {species.species.name}' , end='\r')
            get_sounds(species.species.id)
            print(f'☑️ [{nr}/{count}] sounds {species.species.name}')
        else:
            print(f'☑️ [{nr}/{count}] sounds {species.species.name}')

    nr = 0
    count = CountrySpecies.objects.filter(country=country, species__videos=None).count()
    print (f'{count} still need to retrieve videos')
    for species in CountrySpecies.objects.filter(country=country, species__videos=None):
        nr += 1
        if species.species.videos.count() == 0:
            print(f'🔎 [{nr}/{count}] {species.species.name}' , end='\r')
            get_videos(species.species.id)
            print(f'☑️ [{nr}/{count}] sounds {species.species.name}')
        else:
            print(f'☑️ [{nr}/{count}] sounds {species.species.name}')



def get_country_media(code='NL'):
    country = Country.objects.get(code=code)
    count = CountrySpecies.objects.filter(country=country).count()
    print (f'{country.name} {count} species')

    species = CountrySpecies.objects.filter(country=country, species__images=None)
    print (f'{species.count()} still need to retrieve images')
    nr = 0
    media = []
    for spec in species:
        nr += 1
        print(f'🔎 [{nr}/{species.count()}] {spec.species.name}' , end='\r\n')
        get_media(spec.species.id, 'photo')

    species = CountrySpecies.objects.filter(country=country, species__sounds=None)
    print (f'{species.count()} still need to retrieve sounds')
    nr = 0
    for spec in species:
        nr += 1
        print(f'🔎 [{nr}/{species.count()}] {spec.species.name}' , end='\r\n')
        get_media(spec.species.id, 'audio')

    species = CountrySpecies.objects.filter(country=country, species__videos=None)
    print (f'{species.count()} still need to retrieve videos')
    nr = 0
    for spec in species:
        nr += 1
        print(f'🔎 [{nr}/{species.count()}] {spec.species.name}' , end='\r\n')
        get_media(spec.species.id, 'video')


def get_all_species():
    species = Species.objects.filter(images=None)
    print (f'{species.count()} still need to retrieve images')
    nr = 0
    for spec in species:
        nr += 1
        print(f'🔎 [{nr}/{species.count()}] {spec.name}' , end='\r\n')
        get_media(spec.id, 'photo')

    species = Species.objects.filter(sounds=None)
    print (f'{species.count()} still need to retrieve sounds')
    nr = 0
    for spec in species:
        nr += 1
        print(f'🔎 [{nr}/{species.count()}] {spec.name}' , end='\r\n')
        get_media(spec.id, 'audio')

    species = Species.objects.filter(videos=None)
    print (f'{species.count()} still need to retrieve videos')
    nr = 0
    for spec in species:
        nr += 1
        print(f'🔎 [{nr}/{species.count()}] {spec.name}' , end='\r\n')
        get_media(spec.id, 'video')


def get_all_countries():
    countries = Country.objects.filter(countryspecies=None).all()
    count = countries.count()
    nr = 0
    print (f'{count} still need to retrieve species')
    for country in countries:
        nr += 1
        print(f'☑️ [{nr}/{count}] {country.name}')
        sync_country(country.code)


def get_all_images():
    count = Species.objects.filter(images=None).count()
    nr = 0
    print (f'{count} still need to retrieve images')
    for species in Species.objects.filter(images=None):
        nr += 1
        print(f'☑️ [{nr}/{count}] {species.name}')
        get_media(species.id, 'photo')


def get_all_sounds():
    count = Species.objects.filter(sounds=None).count()
    nr = 0
    print (f'{count} still need to retrieve sounds')
    for species in Species.objects.filter(sounds=None):
        nr += 1
        print(f'☑️ [{nr}/{count}] {species.name}')
        get_media(species.id, 'audio')


def get_all_videos():
    count = Species.objects.filter(videos=None).count()
    nr = 0
    print (f'{count} still need to retrieve videos')
    for species in Species.objects.filter(videos=None):
        nr += 1
        print(f'☑️ [{nr}/{count}] {species.name}')
        get_media(species.id, 'video')


def get_country_status(country_code='NL'):
    country = Country.objects.get(code=country_code)
    species = CountrySpecies.objects.filter(country=country, status='unknown')
    print (f'{country.name} {species.count()} species')
    code, sub_code = country_code.split('-')
    if code == 'GB':
        code = 'UK'
    url = f'https://avibase.bsc-eoc.org/checklist.jsp??lang=EN&p2=1&list=ebird&region={code}&version=text&lifelist=&highlight=0'

    data = requests.get(url)
    if data.status_code != 200:
        print(f'Error: {data.status_code}')
        return

    pattern = r"<tr class='highlight1'>.*?<i>(.*?)<\/i>.*?<td>(.*?)<\/td>\s*<\/tr>"
    matches = re.findall(pattern, data.text, re.DOTALL)

    def clean_status(status):
        clean = re.sub(r'<.*?>', '', status)
        return clean.strip()

    result = [(latin_name, clean_status(status)) for latin_name, status in matches]
    count = 0
    for latin_name, status in result:
        spec = species.filter(species__name_latin=latin_name).first()
        if spec:
            count += 1
            if 'Rare/Accidental' in status:
                spec.status = 'rare'
                spec.save()
            elif 'Introduced species' in status:
                spec.status = 'introduced'
                spec.save()
            elif 'Uncertain origin' in status:
                spec.status = 'uncertain'
                spec.save()
            elif 'Endemic' in status:
                spec.status = 'endemic'
                spec.save()
            elif 'Extirpated' in status:
                spec.status = 'extirpated'
                spec.save()
            else:
                spec.status = 'native'
                spec.save()
    print(f'{count} species updated')

def get_all_country_status():
    countries = Country.objects.all()
    for country in countries:
        get_country_status(country.code)


def get_media_citation(model):
    if isinstance(model, SpeciesVideo):
        asset_id = model.url.split('/')[-3]
    else:
        asset_id = model.url.split('/')[-2]
    url = f'https://macaulaylibrary.org/asset/{asset_id}'
    data = requests.get(url)
    if data.status_code != 200:
        print(f'Error: {data.status_code}')
        return
    pattern = r'<span\s+class="main"[^>]*>(.*?)</span>'
    match = re.search(pattern, data.text)

    if match:
        name = match.group(1)
        model.contributor = name
        print(name)
    model.link = url
    model.save()


def get_all_citations():
    for species in Species.objects.all():
        print(species.name)
        print('> Images')
        for image in species.images.filter(contributor__isnull=True).all():
            get_media_citation(image)
        print('> Sounds')
        for sound in species.sounds.filter(contributor__isnull=True).all():
            get_media_citation(sound)
        print('> Videos')
        for video in species.videos.filter(contributor__isnull=True).all():
            get_media_citation(video)
