import re

from . import countries

''' bitstream[id] = {
     os: {mac,win,linux}
     arch: {amd64,arm64,i386}
     bits: {32,64} as integers
     version: (e.g., "4.1.0")
     stable: {0,1}
     checkout: (date time)
 }

 countryCodeData[countryCode] = [country_name, country_subregion, country_region]

 access = [
   [bitstreamId, access_date+time, country_code, locationIndex]
   ...
 ]
 location[locationIndex] = locationCoords
 '''


CountryCodeQuery = """
    select distinct country_code, country_name
    from ipinfo order by country_code
"""

BitstreamQuery = """
    select * from bsinfo order by bitstream_id
"""

AccessQuery =  """
    select bsinfo.bitstream_id, ipinfo.country_code, 
    ipinfo.latitude, ipinfo.longitude, 
    access.ts 
    from access 
        join bsinfo on access.bitstream_id = bsinfo.bitstream_id 
        join ipinfo on access.ip = ipinfo.ip 
        join uainfo on access.useragent = uainfo.useragent 
    where uainfo.browser_type = 'Browser' 
    group by access.ip, bsinfo.bitstream_id 
    order by access.ts
"""

EUCountryInfo = ['European Union', 'Western Europe', 'Europe']

BitTable = {
    'i386': 32,
    'amd64': 64,
    'arm64': 64
}


def get_download_stats_data(db):
    bitstream = build_bitstream_table(db)
    access, location = build_access_table(db)
    country_code = build_country_code_table(db)

    return {
        'bitstream': bitstream,
        'access': access,
        'location': location,
        'countryCode': country_code,
        '_formatVersion': '1.0'
    }


def build_bitstream_table(db):
    versionRE = re.compile(r'^\w*-([0-9.\w]*)(?:-|$)')
    bitstream_table = {}

    with db as cur:
        print("executing 'BitstreamQuery'")
        for row in cur.execute(BitstreamQuery):
            bitstream_id = row['bitstream_id']
            name = row['filename']
            match = versionRE.match(name)
            if match:
                version = '.'.join(match.group(1).split('.')[0:3])
            else:
                version = ''
            checkout = row['checkout_date']
            creation = row['creation_date']
            if checkout:
                event_date = checkout
            elif creation:
                event_date = creation
            else:
                event_date = ''

            bitstream_table[bitstream_id] = {
                'os': row['os'],
                'arch': row['arch'],
                'bits': BitTable[row['arch']],
                'version': version,
                'stable': 1 if row['release'] else 0,
                'checkout': event_date
            }
    return bitstream_table


def build_access_table(db):
    access_table = []
    location_cache = []
    location_lookup = {}
    location_id = 0
    
    with db as cur:
        print("executing 'AccessQuery'")
        for row in cur.execute(AccessQuery):
            locs = format_latlng(row['latitude'], row['longitude'])
            try:
                loci = location_lookup[locs]
            except KeyError:
                loci = location_id
                location_id += 1
                location_lookup[locs] = loci
                location_cache.append(locs)
            access_table.append((row['bitstream_id'],
                    row['ts'][0:16],
                    row['country_code'],
                    loci))
    return (access_table, location_cache)


def build_country_code_table(db):
    all_country_info = countries_by_isocode()
    country_table = {}
    with db as cur:
        print("executing 'CountryCodeQuery'")
        for row in cur.execute(CountryCodeQuery):
            country_isocode = row['country_code']
            country_info = all_country_info.get(country_isocode, None)
            if country_info:
                country_table[country_isocode] = (
                        country_info['name'],
                        country_info['subregion'],
                        country_info['region']
                        )
            elif country_isocode == 'EU':
                country_table[country_isocode] = EUCountryInfo
            else:
                country_table[country_isocode] = (country_isocode, "unknown", "unknown")
    return country_table


def countries_by_isocode():
    index = {}
    for c in countries.country_data:
        index[c['cca2']] = c
    return index


def format_latlng(lat, lng):
    return '{:f},{:f}'.format(lat, lng)
