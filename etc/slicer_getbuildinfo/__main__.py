import argparse
import json
import sqlite3
import sys

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



def main():
    argparser = argparse.ArgumentParser(description="Download Slicer application package metadata and update sqlite database")
    argparser.add_argument("dbfile", metavar="DB_FILE")
    args = argparser.parse_args()
    dbfile = args.dbfile

    print("ServerAPI is {0}: {1}".format(getServerAPI().name, getServerAPIUrl()))

    records = getRecordsFromURL()
    print("Retrieved {0} records".format(len(records)))

    primary_key_type = "INTEGER" if getServerAPI() == ServerAPI.Midas_v1 else "TEXT"

    with sqlite3.connect(dbfile) as db:
        print("")
        db.execute('''create table if not exists
        _(item_id {primary_key_type} primary key,
                    revision INTEGER,
                    checkout_date TEXT,
                    build_date TEXT,
                    record TEXT)'''.format(primary_key_type=primary_key_type))

        cursor = db.cursor()
        cursor.execute("select count(*) from _")
        numberOfRowsBefore = cursor.fetchone()[0]

        cursor = db.cursor()
        cursor.executemany('''insert or replace into _
            (item_id, revision, checkout_date, build_date, record)
            values(?,?,?,?,?)''',
                           [_f for _f in (recordToDb(r) for r in records) if _f])

        cursor = db.cursor()
        cursor.execute("select count(*) from _")
        numberOfRowsAfter = cursor.fetchone()[0]

        print(f"Added {numberOfRowsAfter - numberOfRowsBefore} rows")

        db.commit()

    print("Saved {0}".format(dbfile))


if __name__ == '__main__':
    main()
