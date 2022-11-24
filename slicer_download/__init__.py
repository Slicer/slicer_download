import json
import os
import requests
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

from enum import Enum


class ServerAPI(Enum):
    Midas_v1 = 1
    Girder_v1 = 2


def getServerAPI():
    return ServerAPI[os.getenv("SLICER_DOWNLOAD_SERVER_API", ServerAPI.Midas_v1.name)]


def getServerAPIUrl():
    return {
        ServerAPI.Midas_v1: "http://slicer.kitware.com/midas3/api/json",
        ServerAPI.Girder_v1: "https://slicer-packages.kitware.com/api/v1",
    }[getServerAPI()]


def getMidasRecordsFromURL():
    InfoURLMethod = 'midas.slicerpackages.get.packages'

    infoURL = '{0}?productname=Slicer&method={1}'.format(getServerAPIUrl(), InfoURLMethod)

    fp = urllib.request.urlopen(infoURL)
    info = fp.read()
    fp.close()

    return json.loads(info)['data']


def getGirderRecordsFromURL():
    result = requests.get("{0}/app/5f4474d0e1d8c75dfc705482/package?limit=0".format(getServerAPIUrl()))
    return result.json()


def getRecordsFromURL():
    return {
        ServerAPI.Midas_v1: getMidasRecordsFromURL,
        ServerAPI.Girder_v1: getGirderRecordsFromURL,
    }[getServerAPI()]()


def openDb(database_filepath):
    """Return opened database connection."""
    database_connection = sqlite3.connect(database_filepath)
    database_connection.row_factory = sqlite3.Row
    return database_connection


def progress(count, total, status=''):
    """Adapted from https://gist.github.com/vladignatyev/06860ec2040cb497f0f3
    """
    if not sys.stdout.isatty():
        return
    bar_len = 60
    filled_len = int(round(bar_len * count / float(total)))

    percents = round(100.0 * count / float(total), 1)
    bar = '=' * filled_len + '-' * (bar_len - filled_len)

    sys.stdout.write('\r[{0}] {1}%  {2}'.format(bar, percents, status))
    sys.stdout.flush()


def progress_end():
    if not sys.stdout.isatty():
        return
    print("")


def toBool(val):
    """
    Coerce a string value to a bool. Meant to be used to parse HTTP
    parameters, which are always sent as strings. The following string
    values will be interpreted as True:

      - ``'true'``
      - ``'on'``
      - ``'1'``
      - ``'yes'``

    All other strings will be interpreted as False. If the given param
    is not passed at all, returns the value specified by the default arg.
    This function is case-insensitive.

    :param val: The value to coerce to a bool.
    :type val: str
    """
    if isinstance(val, bool):
        return val

    return val.lower().strip() in ('true', 'on', '1', 'yes')
