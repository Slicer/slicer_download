import flask
from flask import json

import dateutil.parser
import os
import re

from itertools import groupby, islice

from slicer_download import (
    getServerAPI,
    ServerAPI,
    openDb,
    toBool
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
    download_host_url = os.environ.get('SLICER_DOWNLOAD_URL', flask.request.host_url).strip('/')
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
        return record

    if error_code in (400, 404):
        return _render_error_page(error_code, error_message), error_code

    flask.abort(error_code)


@app.route('/findall')
def recordFindAllRequest():
    """Render as JSON document the list of matching records for all OS (see :const:`SUPPORTED_OS_CHOICES`)
    and stability (see :const:`STABILITY_CHOICES`)

    See :func:`recordsMatchingAllOSAndStability` and :func:`getBestMatching`.
    """
    allRecords, error_message, error_code = recordsMatchingAllOSAndStability()

    if allRecords:
        return allRecords

    if error_code in (400, 404):
        return _render_error_page(error_code, error_message), error_code

    flask.abort(error_code)


def getRecordField(record, key):
    """Return the value of a specific field in the record.

    Given a record and the field key, this function returns the value of the requested field.
    Depending on the server API used, the key is mapped to a field in the database record.
    See :func:`recordsMatchingAllOSAndStability` and :func:`getBestMatching`.

    :param record: A dictionary with fields and values.
    :param key: The field key.

    :return: The value of the field in the record, or None if the field is not present.
    """
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
        elif key == 'pre_release':
            return record['meta'].get('pre_release', 'False')
        elif key == 'submissiontype':
            return 'release' if record['meta'].get('release') else 'nightly'
        elif key == 'bitstream_id':
            return record['_id']


def getCleanedUpRecord(record):
    """Return a dictionary with, organized, cleaned up and standardized fields.

    Given a raw database record and depending on the server API used, this function
    returns a cleaned-up dictionary that includes new fields and more
    consistent names.

    The fields included in the cleaned-up dictionary are the following:
    * 'arch'
    * 'revision'
    * 'os'
    * 'codebase'
    * 'name'
    * 'package'
    * 'build_date'
    * 'build_date_ymd'
    * 'checkout_date'
    * 'checkout_date_ymd'
    * 'product_name'
    * 'stability'
    * 'size'
    * 'md5'
    * 'sha512'
    * 'version' (see :func:`getVersion`)
    * 'download_url' (see :func:`getLocalBitstreamURL`)
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
        cleaned['sha512'] = record['meta'].get('sha512', None)
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
    ``"date", "9999-12-31"``.

    If more than one mode parameter was found (see :const:`MODE_CHOICES`), it returns
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
    """Return the best record that matches specific criteria.

    Given the parameters in the HTTP request (``flask.request``), this function gets revision records from
    the database (see :func:`getRecordsFromDb`) and returns the best record that matches the provided criteria.

    The criteria depend on the values of the `os`, `offset`, `stability`, and `mode`
    parameters passed in the HTTP request and are used to filter the database records using :func:`getBestMatching`.

    :return: A tuple with three elements:
            - The best record matching the criteria, if one exists.
            - An error message, if applicable.
            - An HTTP status code.
    """
    request = flask.request
    revisionRecords = getRecordsFromDb()

    operatingSystem = request.args.get('os')  # may generate BadRequest if not present
    if operatingSystem not in SUPPORTED_OS_CHOICES:
        return None, 'unknown os "{0}": should be one of {1}'.format(operatingSystem, SUPPORTED_OS_CHOICES), 400

    offset_arg = request.args.get('offset', '0')
    try:
        offset = int(offset_arg)
    except ValueError:
        return None, 'bad offset "{0}": should be specified as an integer'.format(offset_arg), 400

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
    """Return all records that match the search criteria, for all OS and stability choices.

    Given the parameters in the HTTP request (``flask.request``), this function gets revision records from
    the database (see :func:`getRecordsFromDb`) and returns all records that match the provided criteria.

    The criteria depend on the values of the `os`, `offset`, `stability`, and `mode`
    parameters passed in the HTTP request. If any of these parameters are not specified, the default
    values are:
    - `os`: all :const:`SUPPORTED_OS_CHOICES`.
    - `offset`: 0.
    - `stability`: all :const:`STABILITY_CHOICES`.
    - `mode`: See :func:`getSupportedMode` and :func:`getMode`.

    :return: A tuple with three elements:
             - All records matching the criteria, if any exist.
             - An error message, if applicable.
             - An HTTP status code.
    """

    request = flask.request
    revisionRecords = getRecordsFromDb()

    offset_arg = request.args.get('offset', '0')
    try:
        offset = int(offset_arg)
    except ValueError:
        return None, 'bad offset "{0}": should be specified as an integer'.format(offset_arg), 400

    modeName, value = getMode()
    if modeName is None:
        return None, "invalid or ambiguous mode: should be one of {0}".format(MODE_CHOICES), 400
    if modeName not in getSupportedMode():
        return None, "unsupported mode: should be one of {0}".format(getSupportedMode()), 400

    if "os" in request.args:
        if request.args['os'] not in SUPPORTED_OS_CHOICES:
            return None, 'unknown os "{0}": should be one of {1}'.format(request.args['os'], SUPPORTED_OS_CHOICES), 400
        operatingSystems = [request.args['os']]
    else:
        operatingSystems = SUPPORTED_OS_CHOICES

    if "stability" in request.args:
        if request.args['stability'] not in STABILITY_CHOICES:
            return None, "bad stability {0}: should be one of {1}".format(request.args['stability'], STABILITY_CHOICES), 400
        stabilities = [request.args['stability']]
    else:
        stabilities = list(set(STABILITY_CHOICES) - set(['any']))

    results = {}
    for operatingSystem in operatingSystems:
        osResult = {}
        for stability in stabilities:
            record = getBestMatching(revisionRecords, operatingSystem, stability, modeName, value, offset)
            osResult[stability] = getCleanedUpRecord(record)
        results[operatingSystem] = osResult

    return results, None, 200


def matchOS(operatingSystem):
    """Return a lambda function that expects a record as a parameter and returns True if the record
    matches the provided operating system.

    :param operatingSystem: operating system to be matched. It should be one :const:`SUPPORTED_OS_CHOICES`.

    :return: a callable lambda function
    """
    return lambda record: getRecordField(record, 'os') == operatingSystem


def matchExactRevision(rev):
    """Return a lambda function that expects a record as a parameter and returns True if the
    record matches the provided revision exactly.

    The lambda function is used as a predicate when the mode passed to :func:`getBestMatching`
    is "revision" (see :const:`MODE_CHOICES`).

    :param rev: revision to be matched

    :return: a callable lambda function
    """
    def match(record):
        return int(rev) == int(getRecordField(record, 'revision'))
    return match


def matchClosestRevision(rev):
    """Return a lambda function that expects a record as a parameter and returns True if the
    provided revision is greater than or equal to the one associated with the record.

    The lambda function is used as a predicate when the mode passed to :func:`getBestMatching`
    is "closest-revision" (see :const:`MODE_CHOICES`).

    :param rev: revision to be matched

    :return: a callable lambda function
    """
    def match(record):
        return int(rev) >= int(getRecordField(record, 'revision'))
    return match


def matchDate(dt, dateType):
    """Return a lambda function that expects a record as a parameter and returns True if the
    provided date is greater than the record date of the specified date type.

    :param dt: date to be matched
    :param dateType: type of the date to be matched. It should be one of the date mode in :const:`MODE_CHOICES`.

    :return: a callable lambda function
    """
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
    """Return a lambda function that expects a record as a parameter and returns True if
    the record version matches the provided one.

    The record version is retrieved using :func:`getVersion`.

    The lambda function is used as a predicate when the mode passed to :func:`getBestMatching`
    is "version" (see :const:`MODE_CHOICES`).

    :param version: version to be matched

    :return: a callable lambda function
    """
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
    """Return a lambda function that expects a record as a parameter and returns True if the provided
    stability matches the provided stability.

    A given record matches the "nightly" stability if its submissiontype is "nightly".

    A given record matches the "release" stability under these two conditions:
    * its "release" field has been set
    * its "pre_release" field does not evaluate to True

    A record is considered to be a pre-release only if its "pre_release" has been set and evaluates
    to True (see :func:`slicer_download.toBool`).

    :param stability: stability to be matched. It should be one of the supported choices in :const:`STABILITY_CHOICES`.

    :return: a callable lambda function
    """
    if stability == 'nightly':
        return lambda record: getRecordField(record, 'submissiontype') == 'nightly'
    if stability == 'release':
        return lambda record: getRecordField(record, 'release') != "" and not toBool(getRecordField(record, 'pre_release'))

    return lambda record: True

# regex patterns for extracting version information.
# this looks ugly because we need to be able to accept versions like:
# 4.5.0, 4.5.0-1, 4.5.0-rc2, 4.5.0-gamma, and so forth
VersionWithDateRE = re.compile(r'^[A-z]+-([-\d.a-z]+)-(\d{4}-\d{2}-\d{2})')
VersionRE = re.compile(r'^[A-z]+-([-\d.a-z]+)-(macosx|linux|win+)')
VersionFullRE = re.compile(r'^([-\d.a-z]+)-(\d{4}-\d{2}-\d{2})')
VersionXyzRE = re.compile(r'^(\d+\.\d+\.\d+)$')


def getVersion(record):
    """Extract version information from the given record.

    If the ``release`` key is found, returns the associated value.

    Otherwise, it returns the version extracted from the value associated
    with the ``name`` key for :const:`ServerAPI.Midas_v1` or the ``meta.version``
    key for :const:`ServerAPI.Girder_v1`.

    For :const:`ServerAPI.Midas_v1`, version extraction is attempted using
    first the :const:`VersionWithDateRE` pattern and then the :const:`VersionRE`
    pattern.

    For :const:`ServerAPI.Girder_v1`, version extraction is attempted using
    first the :const:`VersionFullRE` pattern and then the :const:`VersionXyzRE`
    pattern.

    If the value associated with the selected key does not match any of the
    regular expressions, it returns ``None``.

    See :func:`getRecordField`.
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
            match = VersionXyzRE.match(record['meta']['version'])

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
    """Return the best matching record based on the provided criteria.

    Given a set of revision records, this function returns the best matching record for the provided
    operating system, stability, mode, mode argument, and offset.

    The parameters that control the matching process are:
    * `operatingSystem`: the name of the operating system to match (see :const:`SUPPORTED_OS_CHOICES` and :func:`matchOS`).
    * `stability`: the stability level to match (see :const:`STABILITY_CHOICES` and :func:`matchStability`).
    * `mode`: the matching mode to use (see :const:`MODE_CHOICES`).
    * `modeArg`: the argument to use for the selected matching mode (e.g., the version string or revision number).
    * `offset`: the offset to use when selecting a matching record (e.g., to choose a different revision based on its order).

    The matching process is performed by creating a list of predicate functions based on the provided criteria
    using various functions, which are listed below along with their associated modes:

    +------------------------------+---------------------------+
    | Predicate function           | Modes                     |
    +==============================+===========================+
    | :func:`matchOS`              | `version`,                |
    |                              | `closest-revision`,       |
    |                              | `revision`,               |
    |                              | `date`,                   |
    |                              | `checkout-date`           |
    +------------------------------+---------------------------+
    | :func:`matchStability`       | `version`,                |
    |                              | `closest-revision`,       |
    |                              | `revision`,               |
    |                              | `date`,                   |
    |                              | `checkout-date`           |
    +------------------------------+---------------------------+
    | :func:`matchVersion`         | `version`                 |
    +------------------------------+---------------------------+
    | :func:`matchExactRevision`   | `revision`                |
    +------------------------------+---------------------------+
    | :func:`matchClosestRevision` | `closest-revision`        |
    +------------------------------+---------------------------+
    | :func:`matchDate`            | `date`, `checkout-date`   |
    +------------------------------+---------------------------+

    The predicate functions are combined into a single matcher function using :func:`allPass`, which is used to discard irrelevant records.

    Returns the best matching record, or None if no record matches the provided criteria.
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
