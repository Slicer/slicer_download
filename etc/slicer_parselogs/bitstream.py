from slicer_download import (
    getServerAPI,
    progress,
    progress_end,
    ServerAPI
)


COLUMNS = [
    'bitstream_id',
    'filename',
    'os',
    'arch',
    'product_name',
    'codebase',
    'release',
    'revision',
    'creation_date',
    'checkout_date',
    'size'
]


def create_bitstream_table(db):
    print("creating 'bsinfo' table")
    with db as c:
        c.execute(
            'create table if not exists '
            'bsinfo ({primary_key} primary key, {columns})'.format(
                primary_key=COLUMNS[0],
                columns=','.join(COLUMNS[1:]))
        )


def get_cleaned_up_record(record):
    if getServerAPI() == ServerAPI.Midas_v1:
        bs = record['bitstreams'][0]
        return {
            'bitstream_id': bs['bitstream_id'],
            'filename': bs['name'],
            'os': record['os'],
            'arch': record['arch'],
            'product_name': record['productname'],
            'codebase': record['codebase'],
            'release': record.get('release', ''),
            'revision': record['revision'],
            'creation_date': record['date_creation'],
            'checkout_date': record['checkoutdate'],
            'size': bs['size']
        }

    if getServerAPI() == ServerAPI.Girder_v1:
        extension = {
            "linux": ".tar.gz",
            "macosx": ".dmg",
            "win": ".exe",
        }.get(record["meta"]["os"], "")
        return {
            'bitstream_id': record['_id'],
            'filename': (
                f'{record["meta"]["baseName"]}-{record["meta"]["version"]}'
                f'-{record["meta"]["os"]}-{record["meta"]["arch"]}{extension}'),
            'os': record['meta']['os'],
            'arch': record['meta']['arch'],
            'product_name': record['meta']['baseName'],
            'codebase': '',  # Not supported
            'release': record['meta'].get('release', ''),
            'revision': record['meta']['revision'],
            'creation_date': record['meta']['build_date'],
            'checkout_date': '',  # Not supported
            'size': record['size']
        }


def add_bitstream_info(db, records):
    print("populating 'bsinfo' table")
    for index, record in enumerate(records, start=1):
        progress(index, len(records))
        cleaned = get_cleaned_up_record(record)
        db.execute(
            'insert or replace into bsinfo({columns}) '
            'values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'.format(columns=','.join(COLUMNS)),
            [cleaned[column] for column in COLUMNS])
        db.commit()

    progress_end()
