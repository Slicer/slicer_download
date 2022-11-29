import argparse
import json
import requests
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


def collectDuplicates(records):
    """Return a dictionnary of ``<revision>-<os>-<arch>`` to folderIDs.

    .. note:: Each ``<revision>-<os>-<arch>`` key may be associated with two or more folderIDs.
    """
    assert getServerAPI() == ServerAPI.Girder_v1
    packages = {}
    for record in records:
        key = "%s-%s-%s" % (record["meta"]["revision"], record["meta"]["os"], record["meta"]["arch"])
        itemId = record["_id"]
        folderId = record["folderId"]
        if key not in packages:
            packages[key] = [(itemId, folderId)]
        else:
            packages[key].append((itemId, folderId))

    return {key: item_ids for key, item_ids in packages.items() if len(item_ids) > 1}


def displayDuplicateDrafts(duplicates):
    """Display table of duplicate ``<revision>-<os>-<arch>`` and correponding draft folder URLs
    and draft item IDS.

    Entries of the table are organized using the headers `<revision>-<os>-<arch>`, `release`, `itemId`
    and `folderId` where `release` is displayed as `<DRAFT>` if no matching release was found.

    The matching with a release is done by checking if the `folderId` associated with the
    `<revision>-<os>-<arch>` item is found in the list of releases returned using
    https://slicer-packages.kitware.com/api/v1/app/5f4474d0e1d8c75dfc705482/release?limit=0.
    """
    assert getServerAPI() == ServerAPI.Girder_v1
    if len(duplicates) == 0:
        print("")
        print("No duplicate identified")
        return

    result = requests.get("{0}/app/5f4474d0e1d8c75dfc705482/release?limit=0".format(getServerAPIUrl()))
    releases = {release["_id"]: release["name"] for release in result.json()}

    draftItemIds = []
    draftFolderIds = set()
    print("")
    print("|{:^24}|{:^9}|{:^26}|{:^26}|".format("`<revision>-<os>-<arch>`", "release", "itemId", "folderId"))
    print(f"|{'-'*24}|{'-'*9}|{'-'*26}|{'-'*26}|")
    for key, ids in duplicates.items():
        for itemId, folderId in ids:
            release  = releases.get(folderId, "`<DRAFT>`")
            if folderId not in releases:
                draftItemIds.append(itemId)
                draftFolderIds.add(folderId)
            print(f"|{key:<24}|{release:<9}|{itemId:<26}|{folderId:<26}|")

    print("")
    print("Duplicate draft folder URLs")
    for folderId in draftFolderIds:
        print(f"{getServerAPIUrl()[0:-len('api/v1/')]}/#folder/{folderId}")

    print("")
    print(f"Duplicate draft item IDs:\n{','.join(draftItemIds)}")


def main():
    argparser = argparse.ArgumentParser(description="Download Slicer application package metadata and update sqlite database")
    argparser.add_argument("--display-duplicate-drafts", action="store_true", help="Display duplicate draft folders & items and exit")
    argparser.add_argument("--remove-itemids", help="comma separated list of itemid to remove from the database")
    argparser.add_argument("dbfile", metavar="DB_FILE", nargs="?")
    args = argparser.parse_args()
    dbfile = args.dbfile

    print("ServerAPI is {0}: {1}".format(getServerAPI().name, getServerAPIUrl()))

    if args.display_duplicate_drafts:
        records = getRecordsFromURL()
        duplicates = collectDuplicates(records)
        displayDuplicateDrafts(duplicates)
        sys.exit(0)

    itemIdsToRemove = set()
    if args.remove_itemids:
        for itemId in args.remove_itemids.split(","):
            if len(itemId) != 24:
                argparser.error("ID of item to eclude is expected to be 24 characters")
            itemIdsToRemove.add(itemId)

    if dbfile is None:
        argparser.error("No action requested, specify --display-duplicate-drafts or DB_FILE")

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

    if len(itemIdsToRemove) > 0:
        print("")
        duplicatesByItemId = {}
        for key, ids in collectDuplicates(records).items():
            for itemId, _ in ids:
                duplicatesByItemId[itemId] = key

        with sqlite3.connect(dbfile) as db:
            print(f"Removed {len(itemIdsToRemove)} rows")
            for itemId in itemIdsToRemove:
                db.execute("delete from _ where item_id=?", (itemId, ))
                print(f"  {itemId} ({duplicatesByItemId[itemId]})")
            db.commit()

        print("Saved {0}".format(dbfile))

if __name__ == '__main__':
    main()
