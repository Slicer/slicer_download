import flask
from flask import json

import dateutil.parser
import os
import re

from itertools import groupby, islice

from slicer_download import (
    getServerAPI,
    ServerAPI,
    openDb
)

SUPPORTED_OS_CHOICES = (
    'macosx',
    'win',
    'linux'
)
STABILITY_CHOICES = (
    'release',
    'nightly',
    'any'
)
MODE_CHOICES = (
    'revision',
    'closest-revision',
    'version',
    'checkout-date',
    'date'
)

LOCAL_BITSTREAM_PATH = '/bitstream'

app = flask.Flask(__name__, static_folder='assets')
app.config.from_envvar('SLICER_DOWNLOAD_SERVER_CONF')


def getSourceDownloadURL(package_identifier):
    """Return package download URL for the current server API.

    +-------------+--------------------------------------------------------------------------------+
    | Server API  | Download URL                                                                   |
    +=============+================================================================================+
    | Midas_v1    | https://slicer.kitware.com/midas3/download?bitstream=<package_identifier>      |
    +-------------+--------------------------------------------------------------------------------+
    | Girder_v1   | https://slicer-packages.kitware.com/api/v1/item/<package_identifier>/download  |
    +-------------+--------------------------------------------------------------------------------+

    See :func:`getServerAPI`.
    """
    return {
        ServerAPI.Midas_v1: "https://slicer.kitware.com/midas3/download?bitstream={0}",
        ServerAPI.Girder_v1: "https://slicer-packages.kitware.com/api/v1/item/{0}/download"
    }[getServerAPI()].format(package_identifier)


def _render_error_page(error_code, error_message):
    return flask.render_template(
        'download_40x.html', error_code=error_code, error_title={
            400: "Bad Request",
            404: "Not Found"
        }[error_code], error_message=error_message
    )


@app.route('/')
def downloadPage():
    """Render download page .

    See :func:`recordsMatchingAllOSAndStability`.
    """
    allRecords, error_message, error_code = recordsMatchingAllOSAndStability()
    download_host_url = os.environ.get('SLICER_DOWNLOAD_HOSTNAME', flask.request.host_url).strip('/')
    download_stats_url = '/'.join([download_host_url, 'download-stats'])

    if allRecords:
        return flask.render_template('download.html', R=allRecords, download_stats_url=download_stats_url)

    if error_code in (400, 404):
        return _render_error_page(error_code, error_message), error_code

    flask.abort(error_code)


@app.route('/bitstream/<bitstreamId>')
def redirectToSourceBitstream(bitstreamId):
    """Redirect to package download URL.

    See :func:`getSourceDownloadURL`.
    """
    return flask.redirect(getSourceDownloadURL(bitstreamId))


@app.route('/download')
def redirectToLocalBitstream():
    """Lookup ``bitstreamId`` based on matching criteria and redirect to ``download_url``
    associated with the retrieved matching record.

    The ``download_url`` value is set in :func:`getCleanedUpRecord`.

    If no record is found, render ``404`` page.

    If one of the matching criteria is incorrectly specified, render the ``400`` page
    along with details about the issue.

    See :func:`recordMatching`.
    """
    record, error_message, error_code = recordMatching()

    if record:
        return flask.redirect(record['download_url'])

    if error_code in (400, 404):
        return _render_error_page(error_code, error_message), error_code

    flask.abort(error_code)


@app.route('/find')
def recordFindRequest():
    """Render as JSON document the record matching specific criteria.

    If no record is found, render ``404`` page.

    If one of the matching criteria is incorrectly specified, render the ``400`` page
    along with details about the issue.

    See :func:`recordMatching`.
    """
    record, error_message, error_code = recordMatching()

    if record:
        return json.dumps(record)

    if error_code in (400, 404):
        return _render_error_page(error_code, error_message), error_code

    flask.abort(error_code)


@app.route('/findall')
def recordFindAllRequest():
    """Render as JSON document the list of matching records for all OS (see :const:`SUPPORTED_OS_CHOICES`)
    and stability (see :const:`STABILITY_CHOICES`)

    See :func:`recordsMatchingAllOSAndStability` and :func:`recordMatching`.
    """
    allRecords, error_message, error_code = recordsMatchingAllOSAndStability()

    if allRecords:
        return json.dumps(allRecords)

    if error_code in (400, 404):
        return _render_error_page(error_code, error_message), error_code

    flask.abort(error_code)


def getRecordField(record, key):
    if getServerAPI() == ServerAPI.Midas_v1:
        if key == 'bitstream_id':
            return record['bitstreams'][0]['bitstream_id']
        else:
            return record[key]

    elif getServerAPI() == ServerAPI.Girder_v1:
        if key == 'os':
            return record['meta']['os']
        elif key == 'revision':
            return record['meta']['revision']
        elif key == 'date_creation':
            return record['meta']['build_date']
        elif key == 'checkoutdate':
            return None  # Not supported
        elif key == 'release':
            return record['meta'].get('release', '')
        elif key == 'submissiontype':
            return 'release' if record['meta'].get('release') else 'nightly'
        elif key == 'bitstream_id':
            return record['_id']


def getCleanedUpRecord(record):
    """Return a dictionary generated from a raw database record.

    It includes new fields and more consistent names.

    See :func:`getVersion` and :func:`getLocalBitstreamURL`.
    """
    if not record:
        return None

    cleaned = {}

    if getServerAPI() == ServerAPI.Midas_v1:

        for field in (
            'arch',
            'revision',
            'os',
            'codebase',
            'name',
            'package'
        ):
            cleaned[field] = record[field]

        cleaned['build_date'] = record['date_creation']
        cleaned['build_date_ymd'] = cleaned['build_date'].split(' ')[0]
        cleaned['checkout_date'] = record['checkoutdate']
        cleaned['checkout_date_ymd'] = cleaned['checkout_date'].split(' ')[0]

        cleaned['product_name'] = record['productname']
        cleaned['stability'] = 'release' if record['release'] else 'nightly'
        cleaned['size'] = record['bitstreams'][0]['size']
        cleaned['md5'] = record['bitstreams'][0]['md5']
        cleaned['version'] = getVersion(record)
        cleaned['download_url'] = getLocalBitstreamURL(record)

    if getServerAPI() == ServerAPI.Girder_v1:

        cleaned['arch'] = record['meta']['arch']
        cleaned['revision'] = record['meta']['revision']
        cleaned['os'] = record['meta']['os']
        cleaned['codebase'] = None  # Not supported
        cleaned['name'] = record['name']
        cleaned['package'] = None  # Not supported

        cleaned['build_date'] = record['meta']['build_date']
        cleaned['build_date_ymd'] = dateutil.parser.parse(record['meta']['build_date']).strftime("%Y-%m-%d")
        cleaned['checkout_date'] = None  # Not supported
        cleaned['checkout_date_ymd'] = None  # Not supported

        cleaned['product_name'] = record['meta']['baseName']
        cleaned['stability'] = 'release' if getRecordField(record, 'release') else 'nightly'
        cleaned['size'] = record['size']
        cleaned['md5'] = None  # Not supported
        cleaned['version'] = getVersion(record)
        cleaned['download_url'] = getLocalBitstreamURL(record)

    return cleaned


def getLocalBitstreamURL(record):
    """Given a record, return the URL of the local bitstream
    (e.g., https://download.slicer.org/bitstream/XXXXX )"""
    bitstreamId = getRecordField(record, 'bitstream_id')

    downloadURL = '{0}/{1}'.format(LOCAL_BITSTREAM_PATH, bitstreamId)
    return downloadURL


def getMode():
    """Convenience function returning the mode name and value extracted
    from ``flask.request``.

    If no mode parameter was found (see :const:`MODE_CHOICES`), it returns
    ``None, None``.
    """
    request = flask.request

    modeDict = {}
    for name in MODE_CHOICES:
        value = request.args.get(name, None)
        if value is not None:
            modeDict[name] = value

    if len(list(modeDict.keys())) == 0:
        modeName = 'date'
        value = '9999-12-31'  # distant date to force last record
    elif len(list(modeDict.keys())) == 1:
        modeName, value = list(modeDict.items())[0]
    else:
        return None, None

    return modeName, value


def getSupportedMode():
    """Return list of mode supported by the current server API."""
    return {
        ServerAPI.Midas_v1: MODE_CHOICES,
        ServerAPI.Girder_v1: list(set(MODE_CHOICES) - set(['checkout-date']))
    }[getServerAPI()]


def recordMatching():
    """High level function for getting the best record matching specific criteria including OS."""
    request = flask.request
    revisionRecords = getRecordsFromDb()

    operatingSystem = request.args.get('os')  # may generate BadRequest if not present
    if operatingSystem not in SUPPORTED_OS_CHOICES:
        return None, 'unknown os "{0}": should be one of {1}'.format(operatingSystem, SUPPORTED_OS_CHOICES), 400

    offset = int(request.args.get('offset', '0'))

    modeName, value = getMode()
    if modeName is None:
        return None, "invalid or ambiguous mode: should be one of {0}".format(MODE_CHOICES), 400
    if modeName not in getSupportedMode():
        return None, "unsupported mode: should be one of {0}".format(getSupportedMode()), 400

    defaultStability = 'any' if modeName == 'revision' else 'release'
    stability = request.args.get('stability', defaultStability)

    if stability not in STABILITY_CHOICES:
        return None, "bad stability {0}: should be one of {1}".format(stability, STABILITY_CHOICES), 400

    record = getBestMatching(revisionRecords, operatingSystem, stability, modeName, value, offset)
    cleaned = getCleanedUpRecord(record)

    if not cleaned:
        return None, "no matching revision for given parameters", 404

    return cleaned, None, 200


def recordsMatchingAllOSAndStability():
    """High level function returning all records matching search criteria,
    for all OS and stability choices."""

    request = flask.request
    revisionRecords = getRecordsFromDb()

    offset = int(request.args.get('offset', '0'))

    modeName, value = getMode()
    if modeName is None:
        return None, "invalid or ambiguous mode: should be one of {0}".format(MODE_CHOICES), 400
    if modeName not in getSupportedMode():
        return None, "unsupported mode: should be one of {0}".format(getSupportedMode()), 400

    results = {}
    for operatingSystem in SUPPORTED_OS_CHOICES:
        osResult = {}
        for stability in ('release', 'nightly'):
            record = getBestMatching(revisionRecords, operatingSystem, stability, modeName, value, offset)
            osResult[stability] = getCleanedUpRecord(record)
        results[operatingSystem] = osResult

    return results, None, 200


# query matching functions
def matchOS(operatingSystem):
    return lambda record: getRecordField(record, 'os') == operatingSystem


def matchExactRevision(rev):
    def match(record):
        return int(rev) == int(getRecordField(record, 'revision'))
    return match


def matchClosestRevision(rev):
    def match(record):
        return int(rev) >= int(getRecordField(record, 'revision'))
    return match


def matchDate(dt, dateType):
    def match(record):
        if dateType == 'date':
            dateString = getRecordField(record, 'date_creation')
        elif dateType == 'checkout-date':
            dateString = getRecordField(record, 'checkoutdate')
        if not dateString:
            return False
        justDateString = dateString.split(' ')[0]  # drop time
        return dt >= justDateString
    return match


def matchVersion(version):
    def match(record):
        record_version = getVersion(record)
        if not record_version:
            return False
        record_version_parts = record_version.split('.')
        version_parts = version.split('.')
        for index in range(0, len(version_parts)):
            if record_version_parts[index] != version_parts[index]:
                return False
        return True
    return match


def matchStability(stability):
    if stability == 'nightly':
        return lambda record: getRecordField(record, 'submissiontype') == 'nightly'
    if stability == 'release':
        return lambda record: getRecordField(record, 'release') != ""

    return lambda record: True

# composite field getters

# this looks ugly because we need to be able to accept versions like:
# 4.5.0, 4.5.0-1, 4.5.0-rc2, 4.5.0-gamma, and so forth


VersionWithDateRE = re.compile(r'^[A-z]+-([-\d.a-z]+)-(\d{4}-\d{2}-\d{2})')
VersionRE = re.compile(r'^[A-z]+-([-\d.a-z]+)-(macosx|linux|win+)')
VersionFullRE = re.compile(r'^([-\d.a-z]+)-(\d{4}-\d{2}-\d{2})')


def getVersion(record):
    """Extract version information from record.

    If ``release`` key is found, returns associated value.

    Otherwise it returns the version extracted from the value associated
    with the ``name`` key for :const:`ServerAPI.Midas_v1` or the ``meta.version`
    key for :const:`ServerAPI.Girder_v1`.

    For :const:`ServerAPI.Midas_v1`, extraction of the version is attempted using
    first :const:`VersionWithDateRE` and then :const:`VersionRE`.

    For :const:`ServerAPI.Girder_v1`, extraction of the version is attempted using
    first :const:`VersionFullRE`.

    If value associated with the selected key does not match any of the regular
    expressions, it returns ``None``.
    """
    if getRecordField(record, 'release'):
        return getRecordField(record, 'release')

    match = None

    if getServerAPI() == ServerAPI.Midas_v1:
        match = VersionWithDateRE.match(record['name'])
        if not match:
            match = VersionRE.match(record['name'])

    elif getServerAPI() == ServerAPI.Girder_v1:
        match = VersionFullRE.match(record['meta']['version'])

    if not match:
        return None
    return match.group(1)


def allPass(predlist):
    """Returns a function that evaluates each predicate in a list given an argument,
    and returns True if all pass, otherwise False."""
    def evaluate(x):
        for pred in predlist:
            if not pred(x):
                return False
        return True
    return evaluate


def getBestMatching(revisionRecords, operatingSystem, stability, mode, modeArg, offset):
    """Return best matching record.
    """
    osRecords = list(filter(matchOS(operatingSystem), revisionRecords))

    selectors = [matchStability(stability)]

    # now, do either version, date, or revision
    if mode == 'version':
        selectors.append(matchVersion(modeArg))
    elif mode == 'revision':
        selectors.append(matchExactRevision(modeArg))
    elif mode == 'closest-revision':
        selectors.append(matchClosestRevision(modeArg))
    elif mode == 'date':
        selectors.append(matchDate(modeArg, 'date'))
    elif mode == 'checkout-date':
        selectors.append(matchDate(modeArg, 'checkout-date'))
    else:
        app.logger.error("unknown mode {0}".format(mode))
        return None

    matcher = allPass(selectors)

    matchingRecordIndex = -1
    for index, osRecord in enumerate(osRecords):
        if matcher(osRecord):
            matchingRecordIndex = index
            break

    if matchingRecordIndex == -1:
        matchingRecord = None
    else:
        if offset < 0:
            # an offset < 0 looks backward in time, or forward in the list
            g = groupby(osRecords[matchingRecordIndex:], key=lambda record: int(getRecordField(record, 'revision')))
            try:
                o = next(islice(g, -offset, -offset + 1))
                matchingRecord = list(o[1])[0]
            except StopIteration:  # no match or stepped off the end of the list
                matchingRecord = None
        elif offset > 0:
            # look forward in time for the latest build of a particular rev, so
            # flip list
            g = groupby(osRecords[matchingRecordIndex:0:-1], key=lambda record: int(getRecordField(record, 'revision')))
            try:
                o = next(islice(g, offset, offset + 1))
                matchingRecord = list(o[1])[-1]
            except StopIteration:  # no match of stepped off the end of the list
                matchingRecord = None
        else:
            matchingRecord = osRecords[matchingRecordIndex]
    return matchingRecord


def dbFilePath():
    """Return database filepath.

    If a relative path is associated with either configuration entry or the environment
    variable, ``app.root_path`` is prepended.

    The filepath is set following these steps:

    1. If set, returns value associated  with ``DB_FILE`` configuration entry.

    2. If set, returns value associated with ``SLICER_DOWNLOAD_DB_FILE`` environment variable.

    3. If ``DB_FALLBACK`` configuration entry is set to True, returns
       ``<app.root_path>/etc/fallback/slicer-<server_api>-records.sqlite``
       otherwise returns ``<app.root_path>/var/slicer-<server_api>-records.sqlite``
       where ``<server_api>`` is set to ``midas`` or ``girder`` based on :func:`getServerAPI()`.
    """

    if 'DB_FILE' in app.config:
        db_file = app.config['DB_FILE']
    elif 'SLICER_DOWNLOAD_DB_FILE' in os.environ:
        db_file = os.environ["SLICER_DOWNLOAD_DB_FILE"]
    else:
        fallback = app.config.get('DB_FALLBACK', False)
        subdir = '../var' if not fallback else '../etc/fallback'
        db_file = os.path.join(
            subdir,
            {
                ServerAPI.Midas_v1: 'slicer-midas-records.sqlite',
                ServerAPI.Girder_v1: 'slicer-girder-records.sqlite'
            }[getServerAPI()]
        )

    if not os.path.isabs(db_file):
        return os.path.join(app.root_path, db_file)
    else:
        return db_file


def getRecordsFromDb():
    """Return all records found in the database associated with :func:`dbFilePath()`.

    List of records are cached using an application configuration entry identified
    by ``_CACHED_RECORDS`` key.

    See also :func:`openDb`.
    """
    try:
        records = flask.current_app.config["_CACHED_RECORDS"]
    except KeyError:
        records = None

    database_filepath = dbFilePath()
    app.logger.info("database_filepath: %s" % database_filepath)
    if not os.path.isfile(database_filepath):
        raise IOError(2, 'Database file %s does not exist', database_filepath)
    database_connection = openDb(database_filepath)
    cursor = database_connection.cursor()

    # get record count
    cursor.execute('select count(1) from _')
    count = int(cursor.fetchone()[0])

    # load db if needed or count has changed
    if records is None or count != len(records):
        cursor.execute('select record from _ order by revision desc,build_date desc')
        records = [json.loads(record[0]) for record in cursor.fetchall()]
        flask.current_app.config["_CACHED_RECORDS"] = records

    database_connection.close()

    return records


@app.teardown_appcontext
def closeDb(error):
    pass


if __name__ == '__main__':
    app.run()
