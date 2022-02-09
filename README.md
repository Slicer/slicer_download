# Slicer Download

Site for listing the installers associated with the latest Stable and Preview Slicer releases.

## Current deployments

_The following deployments are hosted and maintained by Kitware._

| URL | Description |
|-----|-------------|
| https://download.slicer.org/ | Production server |
| https://download-staging.slicer.org/ | Testing server |

## Repository layout

This section describes main files and directories available in this repository.

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
    | `download-fallback-databases.sh` | Download latest database backups from [database-backups][https://github.com/Slicer/slicer_download_database_backups/releases/tag/database-backups] release associated with `Slicer/slicer_download_database_backups` repository. |
    | `download-flask-templates-and-assets.sh` | Download up-to-date flask templates from [Slicer/slicer.org@download-slicer-org][branch-download-slicer-org] branch. |
    | `geoipupdate`                     | Download GeoIP Binary Databases into `etc/geoip/db` directory. |
    | `kill`                            | Shell script for killing the download Flask web application. |
    | `start`                           | Shell script for starting the download Flask web application. |
    | `stop`                            | Shell script for stopping the download Flask web application. |

[branch-download-slicer-org]: https://github.com/Slicer/slicer.org/tree/download-slicer-org

* [etc](https://github.com/Slicer/slicer_download/tree/main/etc)

    | Name                   | Description |
    |------------------------|-------------|
    | `slicer_getbuildinfo`  | Python application for retrieving application package information from https://slicer-packages.kitware.com/ and creating `slicer-girder-records.sqlite` file.
    | `slicer_parselogs`     | Python application for parsing Nginx access logs, updating `download-stats.sqlite` and generating `slicer-download-data.json` |

## Getting started with development

1. Create a virtual environment and install prerequisites

    ```
    cd slicer_download
    python -m venv env
    ./env/bin/python -m pip install -r requirements.txt -r requirements-dev.txt
    ```

2. Download up-to-date flask templates from [Slicer/slicer.org@download-slicer-org][branch-download-slicer-org] branch.


    ```
    ./bin/download-flask-templates-and-assets.sh
    ```

3. If it applies, post a message on the 3D Slicer forum requesting access to https://github.com/Slicer/slicer_download_database_backups

    Go to https://discourse.slicer.org

4. Download latest database backups from [database-backups](https://github.com/Slicer/slicer_download_database_backups/releases/tag/database-backups) release associated with `Slicer/slicer_download_database_backups` repository.

    ```
    export SLICER_BACKUP_DATABASE_GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz0123456789
    ./bin/download-fallback-databases.sh
    ```
    _:warning: GitHub token specified in the previous command is a placeholder that should be replaced with a valid one._

5. Setup startup environment

    ```
    echo "export SLICER_DOWNLOAD_DB_FALLBACK=True" >> ./bin/.start_environment
    ```

6. Start the server

    ```
    ./bin/start
    ```

## Startup environment

These variables may be exported in the file `./bin/.start_environment` to customize environment
associated with the `./bin/start` script.

| Variable Name | Description | Default |
|---------------|-------------|---------|
| `UWSGI_HTTP_HOST` | Host associated with the uWSGI server running the Flask application. | `127.0.0.1` |
| `UWSGI_HTTP_PORT` | Port associated with the uWSGI server running the Flask application. | `53683` |
| `SLICER_DOWNLOAD_DEBUG` | If `True`, show unhandled exceptions and reload server when code changes. For more details, see [here](https://flask.palletsprojects.com/en/2.0.x/config/#DEBUG). | `False` |
| `SLICER_DOWNLOAD_DB_FALLBACK` | If `True`, lookup the fallback database. | `False` |
| `SLICER_DOWNLOAD_DB_FILE` | Path to the database file containing download records. | `./var/slicer-<server_api>-records.sqlite` or `./etc/fallback/slicer-<SLICER_DOWNLOAD_SERVER_API>-records.sqlite` if `SLICER_DOWNLOAD_DB_FALLBACK` is `True`. |
| `SLICER_DOWNLOAD_URL` | URL of the Slicer download server. | `http://${UWSGI_HTTP_HOST}:<UWSGI_HTTP_PORT>` |
| `SLICER_DOWNLOAD_SERVER_API` | Supported values are `Girder_v1` or `Midas_v1`. | `Midas_v1` |

## History

The original implementation was created by Mike Halle ([@mhalle](https://github.com/mhalle), BWH) in 2011 and hosted on a server maintained within the Surgical Planning Laboratory (SPL) at Harvard University.

In 2014, Mike Halle added source code to GitHub (see archive [here](https://github.com/mhalle/slicer4-download_deprecated)) and set up the server using WebFaction.

In December 2020, Mike transitioned the hosting from WebFaction to opalstack.

Then, in May 2021, Jean-Christophe Fillion-Robin ([@jcfr](https://github.com/jcfr), Kitware) worked with Mike to transition the GitHub project to its current [home](https://github.com/Slicer/slicer_download). J-Christophe also updated the implementation so that it can be deployed in arbitrary environments and added support to integrate with the new backend infrastructure built on Girder for managing Slicer application and extension packages.

In July 2021, the production server was migrated to a server hosted and maintained by Kitware. Additionally, the landing page
was updated to match the style of the `slicer.org` website.


## License

It is covered by the Apache License, Version 2.0:

https://www.apache.org/licenses/LICENSE-2.0

The license file was added at revision [24bfe91][24bfe91] on 2021-07-20, but you may
consider that the license applies to all prior revisions as well.

[24bfe91]: https://github.com/Slicer/slicer_download/commit/24bfe91574221f90122415cda5d5d0c4177a2e45
