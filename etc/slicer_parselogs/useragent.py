from slicer_download import (
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
    if family == 'Other':
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
