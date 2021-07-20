# Slicer Download

## Current deployments

_The following deployments are hosted and maintained by Kitware._

| URL | Description |
|-----|-------------|
| https://download.slicer.org/ | Production server |
| https://download-staging.slicer.org/ | Testing server |

## Repository layout

This section desribes main files and directories available in this repository.

* [slicer_download_server](https://github.com/Slicer/slicer_download/tree/main/slicer_download_server)

    Flask web application served using uWSGI and expected to be proxied through Nginx.

* [slicer_download](https://github.com/Slicer/slicer_download/tree/main/slicer_download)

    Python package implementing utility functions useful independently of the Flask web application.

* [bin](https://github.com/Slicer/slicer_download/tree/main/bin)

    This directory contains shell scripts for starting/stopping the flask web application and for setting up the
    relevant environments.

    | Name                              | Description |
    |-----------------------------------|-------------|
    | `backup-databases.sh`             | Archive databases as release assets associated with the [Slicer/slicer_download_database_backups](https://github.com/Slicer/slicer_download_database_backups/releases/tag/database-backups) private repository. |
    | `cron-getbuildinfo.sh`            | Invoke `etc/slicer_getbuildinfo` python application. |
    | `cron-parselogs.sh`               | Invoke `etc/slicer_parselogs` python application. |
    | `geoipupdate`                     | Download GeoIP Binary Databases into `etc/geoip/db` directory. |
    | `kill`                            | Shell script for killing the download Flask web application. |
    | `start`                           | Shell script for starting the download Flask web application. |
    | `stop`                            | Shell script for stopping the download Flask web application. |

* [etc](https://github.com/Slicer/slicer_download/tree/main/etc)

    | Name                   | Description |
    |------------------------|-------------|
    | `slicer_getbuildinfo`  | Python application for retrieving application package information from https://slicer-packages.kitware.com/ and creating `slicer-girder-records.sqlite` file.
    | `slicer_parselogs`     | Python application for parsing Nginx access logs, updating `download-stats.sqlite` and generating `slicer-download-data.json` |


## History

The original implementation was created by Mike Halle ([@mhalle](https://github.com/mhalle), BWH) in 2011 and hosted on a server maintained within the Surgical Planning Laboratory (SPL) at Harvard University.

In 2014, Mike Halle added source code to GitHub (see archive [here](https://github.com/mhalle/slicer4-download_deprecated)) and set up the server using WebFaction.

In December 2020, Mike transitioned the hosting from WebFaction to opalstack.

Then, in May 2021, J-Christophhe Fillion-Robin ([@jcfr](https://github.com/jcfr), Kitware) worked with Mike to transition the GitHub project to its current [home](https://github.com/Slicer/slicer_download). J-Christophe also updated the implementation so that it can be deployed in arbitrary environments and added support to integrate with the new backend infrastructure built on Girder for managing Slicer application and extension packages.

In July 2021, the production server was migrated to a server hosted and maintained by Kitware.


## License

It is covered by the Apache License, Version 2.0:

http://www.apache.org/licenses/LICENSE-2.0

The license file was added at revision 1b53566 on 2021-07-14, but you may
consider that the license applies to all prior revisions as well.
