import json
import sqlite3
import sys
import textwrap

from slicer_download import (
    getServerAPI,
    ServerAPI,
    getRecordsFromURL,
    getServerAPIUrl
)


def midasRecordToDb(r):
    try:
        return [int(r['item_id']),
                int(r['revision']),
                r['checkoutdate'],
                r['date_creation'],
                json.dumps(r)]
    except ValueError:
        return None


def girderRecordToDb(r):
    return [r['_id'],
            int(r['meta']['revision']),
            r['created'],
            r['meta']['build_date'],
            json.dumps(r)]


def recordToDb(r):
    return {
        ServerAPI.Midas_v1: midasRecordToDb,
        ServerAPI.Girder_v1: girderRecordToDb,
    }[getServerAPI()](r)


def main(dbfile):

    print("ServerAPI is {0}: {1}".format(getServerAPI().name, getServerAPIUrl()))

    records = getRecordsFromURL()

    primary_key_type = "INTEGER" if getServerAPI() == ServerAPI.Midas_v1 else "TEXT"

    with sqlite3.connect(dbfile) as db:
        db.execute('''create table if not exists
        _(item_id {primary_key_type} primary key,
                    revision INTEGER,
                    checkout_date TEXT,
                    build_date TEXT,
                    record TEXT)'''.format(primary_key_type=primary_key_type))

        cursor = db.cursor()
        cursor.executemany('''insert or replace into _
            (item_id, revision, checkout_date, build_date, record)
            values(?,?,?,?,?)''',
                           [_f for _f in (recordToDb(r) for r in records) if _f])
        db.commit()

    print("Retrieved {0} records".format(len(records)))
    print("Saved {0}".format(dbfile))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(textwrap.dedent("""
        Usage: %s DB_FILE

          Download Slicer application package metadata and update sqlite database

        """ % sys.argv[0]), file=sys.stderr)
        sys.exit(1)

    main(sys.argv[1])
