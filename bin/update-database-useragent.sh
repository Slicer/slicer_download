#!/bin/bash

set -e

script_dir=$(cd $(dirname $0) || exit 1; pwd)

ROOT_DIR=$(realpath "${script_dir}/..")
VIRTUALENV_DIR=$(realpath -m "${ROOT_DIR}/env")
PYTHON_EXECUTABLE=${VIRTUALENV_DIR}/bin/python

# Customizing environment
echo -n "[slicer_getbuildinfo] Looking for ${ROOT_DIR}/bin/.start_environment "
if [ -e "${ROOT_DIR}/bin/.start_environment" ]; then
  source "${ROOT_DIR}/bin/.start_environment"
  echo "[ok]"
else
  echo "[not found]"
fi

SLICER_DOWNLOAD_SERVER_API=$(PYTHONPATH=${ROOT_DIR} ${PYTHON_EXECUTABLE} -c "import slicer_download as sd; print(sd.getServerAPI().name)")

SLICER_DOWNLOAD_STATS_DB_FILE="${ROOT_DIR}/var/download-stats.sqlite"

SITE_LOG_DIR=${SITE_LOG_DIR:-$(realpath -m "${ROOT_DIR}/../logs/sites/slicer_download_org")}
mkdir -p ${SITE_LOG_DIR}

# Display summary
echo
echo "[slicer_parselogs] Using this config"
echo "  SLICER_DOWNLOAD_SERVER_API       : ${SLICER_DOWNLOAD_SERVER_API}"
echo "  SLICER_DOWNLOAD_STATS_DB_FILE    : ${SLICER_DOWNLOAD_STATS_DB_FILE}"
echo
echo "[slicer_parselogs] Using these directories"
echo "  ROOT_DIR       : ${ROOT_DIR}"
echo "  SITE_LOG_DIR   : ${SITE_LOG_DIR}"

echo
export PYTHONPATH=${ROOT_DIR}:${ROOT_DIR}/etc
exec "${PYTHON_EXECUTABLE}" "${ROOT_DIR}/etc/slicer_parselogs" \
    --db ${SLICER_DOWNLOAD_STATS_DB_FILE} \
    --update-useragent-table \
    $*
