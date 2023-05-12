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


def getRecordsFromDB(dbfile):
    """Get the records from a SQLite 3.0 database file.

    Returns a list of dictionaries where each dictionary contains the fields
    and values of a record in the database.
    """
    with sqlite3.connect(dbfile) as db:
        cursor = db.cursor()
        cursor.execute("select record from _")
        return [json.loads(row[0]) for row in cursor.fetchall()]


def midasRecordToDb(r):
    """Convert a Midas record to a list of fields to insert in a database.

    Returns a list of fields in the order that they should be inserted into
    the database. The Midas fields include the id (``item_id``), the
    revision (``revision``), the checkout date (``checkoutdate``),
    the build date (``date_creation``) and the entire record as a JSON string.
    """
    try:
        return [int(r['item_id']),
                int(r['revision']),
                r['checkoutdate'],
                r['date_creation'],
                json.dumps(r)]
    except ValueError:
        return None


def girderRecordToDb(r):
    """Convert a Girder record to a list of fields to insert in a database.

    Returns a list of fields in the order that they should be inserted
    into the database. The Girder fields include the id (``_id``), the
    revision (``meta.revsion``), the checkout date (``created``), the
    build date (``meta.build_date``) and the entire record as a JSON string.
    """
    return [r['_id'],
            int(r['meta']['revision']),
            r['created'],
            r['meta']['build_date'],
            json.dumps(r)]


def recordToDb(r):
    """Convert a record to a list of fields to insert in a database.

    Returns a list of fields in the order that they should be inserted into
    the database. The specific conversion function depends on the server API
    being used (see :func:`getServerAPI`).
    """
    return {
        ServerAPI.Midas_v1: midasRecordToDb,
        ServerAPI.Girder_v1: girderRecordToDb,
    }[getServerAPI()](r)


def applicationPackageToIDs(records):
    """Return a dictionnary of ``<revision>-<os>-<arch>`` (uniquely identifying an application package)
    to list of ``(itemId, folderId)`` tuples.

    This function returns a dictionary containing keys that are uniquely
    identifying an application package, and values that are a list of tuples
    containing the itemId and folderId of the corresponding records from a
    Girder database (see :const:`ServerAPI.Girder_v1`).
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

    return {key: item_ids for key, item_ids in packages.items()}


def computeContentChecksum(algo, content):
    """Compute digest of ``content`` using ``algo``.

    Supported hashing algorithms are SHA256, SHA512, and MD5.

    :raises ValueError: if algo is unknown.
    """
    import hashlib

    if algo not in ['SHA256', 'SHA512', 'MD5']:
        msg = f"unsupported hashing algorithm {algo}"
        raise ValueError(msg)

    digest = hashlib.new(algo)
    digest.update(content)
    return digest.hexdigest()


def displayDuplicateDrafts(records):
    """Display table of duplicate ``<revision>-<os>-<arch>`` and correponding draft folder URLs
    and draft item IDS.

    Entries of the table are organized using the headers `<revision>-<os>-<arch>`, `release`, `itemId`
    and `folderId` where `release` is displayed as `<DRAFT>` if no matching release was found.

    The matching with a release is done by checking if the `folderId` associated with the
    `<revision>-<os>-<arch>` item is found in the list of releases returned using
    https://slicer-packages.kitware.com/api/v1/app/5f4474d0e1d8c75dfc705482/release?limit=0.
    """
    assert getServerAPI() == ServerAPI.Girder_v1

    duplicates = {key: item_ids for key, item_ids in applicationPackageToIDs(records).items() if len(item_ids) > 1}

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
    argparser.add_argument("--skip-db-insert-or-update", action="store_true", help="skip database insert or update of rows")
    argparser.add_argument("dbfile", metavar="DB_FILE", nargs="?")
    args = argparser.parse_args()
    dbfile = args.dbfile

    print("ServerAPI is {0}: {1}".format(getServerAPI().name, getServerAPIUrl()))

    if args.display_duplicate_drafts:
        records = getRecordsFromURL()
        displayDuplicateDrafts(getRecordsFromURL())
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

    if not args.skip_db_insert_or_update:
        primary_key_type = "INTEGER" if getServerAPI() == ServerAPI.Midas_v1 else "TEXT"

        with sqlite3.connect(dbfile) as db:
            print("")
            db.execute('''create table if not exists
            _(item_id {primary_key_type} primary key,
                        revision INTEGER,
                        checkout_date TEXT,
                        build_date TEXT,
                        record TEXT)'''.format(primary_key_type=primary_key_type))

            # Since when using the `insert or replace into` statement below, all records are effectively
            # replaced independently of their value, the `cursor.rowcount` property does not allow to
            # know the number of records effectively updated.
            #
            # To address this, we compute the checksum of all records before and after and use that to
            # infer the number of record added and updated.
            cursor = db.cursor()
            cursor.execute("select item_id, record from _")
            checksumOfRecordsBefore = {row[0]: computeContentChecksum("SHA256", row[1].encode()) for row in cursor.fetchall()}
            numberOfRowsBefore = len(checksumOfRecordsBefore)

            cursor = db.cursor()
            cursor.executemany('''insert or replace into _
                (item_id, revision, checkout_date, build_date, record)
                values(?,?,?,?,?)''',
                            [_f for _f in (recordToDb(r) for r in records) if _f])

            cursor = db.cursor()
            cursor.execute("select count(*) from _")
            numberOfRowsAfter = cursor.fetchone()[0]

            cursor = db.cursor()
            cursor.execute("select item_id, record from _")
            recordsChecksumAfter= {
                row[0]: computeContentChecksum("SHA256", row[1].encode()) for row in cursor.fetchall()
                if row[0] in checksumOfRecordsBefore
            }
            numberOfRowsModified = len(set(recordsChecksumAfter.values()) - set(checksumOfRecordsBefore.values()))

            print(f"Added {numberOfRowsAfter - numberOfRowsBefore} rows")
            print(f"Updated {numberOfRowsModified} rows")

            db.commit()

        print("Saved {0}".format(dbfile))

    if len(itemIdsToRemove) > 0:
        print("")
        packages = applicationPackageToIDs(getRecordsFromDB(dbfile))
        packagesByItemId = {}
        for key, ids in packages.items():
            for itemId, _ in ids:
                packagesByItemId[itemId] = key

        with sqlite3.connect(dbfile) as db:
            print(f"Removing {len(itemIdsToRemove)} rows")
            for itemId in itemIdsToRemove:
                if itemId not in packagesByItemId:
                    print(f"  {itemId} (not found)")
                    continue
                db.execute("delete from _ where item_id=?", (itemId, ))
                print(f"  {itemId} ({packagesByItemId[itemId]})")
            db.commit()
            print(f"Removed {db.total_changes} rows")

        print("Saved {0}".format(dbfile))

if __name__ == '__main__':
    main()
