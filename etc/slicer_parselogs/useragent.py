import json
import os
from datetime import date

from slicer_download import (
    openDb,
    progress,
    progress_end
)
from ua_parser import user_agent_parser


def create_useragent_table(db):
    print("creating 'uainfo' table")
    with db as c:
        c.execute('''create table if not exists
            uainfo (useragent primary key, 
                    browser_type, ua_name, os_name, os_family)
        ''')


def get_browser_type_compat(rec):
    family = rec['device']['family']

    if family == 'Spider':
        return 'Robot'
    if family == 'Other' or family == "Mac":
        return 'Browser'
    return 'MobileBrowser'


def pretty_os(rec):
    os = rec['os']
    return user_agent_parser.PrettyOS(os['family'],
                                      os['major'],
                                      os['minor'],
                                      os['patch'])


def parse_useragent(user_agent):
    ua_rec = user_agent_parser.Parse(user_agent)
    if not ua_rec:
        return None
    return {
        "useragent": user_agent,
        "browser_type": get_browser_type_compat(ua_rec),
        "ua_name": ua_rec['user_agent']['family'],
        "os_name": pretty_os(ua_rec),
        "os_family": ua_rec['os']['family']}


def add_useragent_info_row(db, fields):
    db.execute("""insert or replace into uainfo(useragent,
                browser_type, ua_name, os_name, os_family)
                values(:useragent, :browser_type, :ua_name, :os_name, :os_family)""",
                fields)


def add_useragent_info(db):
    print("populating 'uainfo' table")
    ua_completed = set()
    uas = list(db.execute("select useragent from access except select useragent from uainfo"))
    for index, ua in enumerate(uas, start=1):
        progress(index, len(uas))
        user_agent = ua[0]
        if user_agent in ua_completed:
            continue
        ua_fields = parse_useragent(user_agent);
        if ua_fields is None:
            continue
        add_useragent_info_row(db, ua_fields)
        ua_completed.add(user_agent)
        db.commit() # commit per record in case we exit
    progress_end()


def update_useragent_info(dbfile, dry_run=True):

    if not os.path.isfile(dbfile):
        print(f"Database file {dbfile} does not exist")
        return

    updated_rows_file = os.path.join(os.path.dirname(dbfile), f"download-stats-useragent-updates-{date.today()}.json")

    with openDb(dbfile) as db:
        print("update 'uainfo' table")

        updatedRows = []

        uas = list(db.execute("select useragent, browser_type, ua_name, os_name, os_family from uainfo"))
        for index, ua in enumerate(uas, start=1):
            progress(index, len(uas))
            ua_fields = {key: ua[key] for key in ua.keys()}
            updated_ua_fields = parse_useragent(ua[0]);
            if updated_ua_fields is None:
                continue

            if ua_fields != updated_ua_fields:
                updatedRows.append((ua_fields, updated_ua_fields))

            if not dry_run:
                add_useragent_info_row(db, updated_ua_fields)

        progress_end()

        if not dry_run:
            db.commit()
            print("Saved {0}".format(dbfile))

        print(f"\nProcessed {index}/{len(uas)} rows")

        with open(updated_rows_file, 'w+') as fp:
            json.dump(updatedRows, fp, separators=(',', ':'), indent=2)

        print(f"Written {updated_rows_file}")

        if dry_run:
            print("Dry-run successful! No actual changes were made.")

        update_stats = read_useragent_info_update_stats(updated_rows_file)
        display_useragent_info_update_stats(update_stats, field_details=True, useragent_details=False)


def read_useragent_info_update_stats(update_file):
    if not os.path.isfile(update_file):
        print(f"Update file {update_file} does not exist")
        return

    per_field = {
        "browser_type": [],
        "ua_name": [],
        "os_name": [],
        "os_family": [],
    }

    with open(update_file) as fp:
        update_data = json.load(fp)

        for ua_fields, updated_ua_fields in update_data:
            for field in per_field.keys():
                value = ua_fields[field]
                updated_value = updated_ua_fields[field]
                if value != updated_value:
                    per_field[field].append((value, updated_value, ua_fields["useragent"]))

    per_field_count = {field: len(per_field[field]) for field in per_field}

    per_field_changes = {}
    for field in per_field.keys():
        per_field_changes[field]= {}
        for value, updated_value, useragent in per_field[field]:
            per_field_changes[field].setdefault(value, []).append((updated_value, useragent))

    return {"all": len(update_data), "count": {**per_field_count}, "changes": {**per_field_changes}}


def display_useragent_info_update_stats(stats, field_details=False, useragent_details=False):

    print(f"\nUpdated {stats['all']} rows")
    for field in stats['count']:
        print(f"- {stats['count'][field]} with `{field}` updated")

    if field_details:

        print("\n## Field updates")

        for field in stats['changes']:
            changes = stats['changes'][field]
            print(f"\n<!-- {field} -->")

            print(f"\n<details><summary>{field}</summary><pre>")
            for value in changes:
                updated_values = [value for value, _ in changes[value]]
                updated_uas = [useragent for _, useragent in changes[value]]
                for updated_value in set(updated_values):
                    print(f"{value} -> {updated_value}: {updated_values.count(updated_value)}")
            print("</pre></details>")

    if useragent_details:

        print("\n## User-agent updates")

        selected_fields = ["browser_type"]

        for field in stats['changes']:
            changes = stats['changes'][field]
            if field not in selected_fields:
                continue

            print(f"\n### {field}")

            for value in changes:
                updated_values = [value for value, _ in changes[value]]
                updated_uas = [useragent for _, useragent in changes[value]]
                for updated_value in set(updated_values):
                    if field in selected_fields:
                        section = f"{value} -> {updated_value}: {updated_values.count(updated_value)}"
                        print(f"\n<!-- {section} -->")
                        print(f"\n<details><summary>{section}</summary><pre>")
                        for updated_ua in updated_uas:
                            print(f"{updated_ua}")
                        print("</pre></details>")
