import argparse
import json
import sys

from slicer_download import (
    openDb,
    getRecordsFromURL
)

from slicer_parselogs import (
    access,
    bitstream,
    geoip,
    useragent,
    slicerstats
)


def generate_slicer_stats(db, slicer_stats_data_file):
    slicer_stats_data = slicerstats.get_download_stats_data(db)
    with open(slicer_stats_data_file, 'w+') as statsfp:
        print('writing %s' % slicer_stats_data_file)
        json.dump(slicer_stats_data, statsfp, separators=(',', ':'), indent=2)


def main():
    argparser = argparse.ArgumentParser(description='Process Slicer4 download information.')
    argparser.add_argument('--db', required=True, help="sqlite stats database")
    argparser.add_argument('--geoip', required=False, help="geoip data file")
    argparser.add_argument('--statsdata', required=False, help="slicer stats output")
    argparser.add_argument('--only-statsdata', action='store_true', help="skip database update and only generate stats output")
    argparser.add_argument('--skip-records-fetch', action='store_true', help="skip fetching of records from packages server")
    argparser.add_argument('--update-useragent-table', action='store_true', help="update useragent table entries")
    argparser.add_argument('--dry-run', action='store_true', help="simulate database update")
    argparser.add_argument('filenames', nargs="*")
    args = argparser.parse_args()
    dbname = args.db
    geoip_filename = args.geoip
    filenames = args.filenames
    statsdata = args.statsdata

    if args.only_statsdata:
        if statsdata is None:
            argparser.error('with --only-statsdata, the following arguments are required: --statsdata')

        with openDb(dbname) as db:
            generate_slicer_stats(db, statsdata)
        sys.exit(0)

    if args.update_useragent_table:
        useragent.update_useragent_info(dbname, dry_run=args.dry_run)
        sys.exit(0)

    required_args = [
        "--geoip",
        "--statsdata",
    ]

    if any([vars(args).get(arg[2:]) is None for arg in required_args]):
        argparser.error(f"the following arguments are required: {', '.join(required_args)}")

    with openDb(dbname) as db:

        access.create_access_table(db)
        bitstream.create_bitstream_table(db)
        geoip.create_geoip_table(db)
        useragent.create_useragent_table(db)

        # parse apache logs, if they exist, and add them to db
        access.add_access_info(db, filenames)

        # each of these items depends on the access table
        geoip.add_geoip_info(db, geoip_filename)
        useragent.add_useragent_info(db)
        if not args.skip_records_fetch:
            bitstream.add_bitstream_info(db, getRecordsFromURL())

        # then write out slicer json
        generate_slicer_stats(db, statsdata)

    sys.exit(0)


if __name__ == '__main__':
    main()
