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

# Configuration
export SLICER_DOWNLOAD_SERVER_CONF="${SLICER_DOWNLOAD_SERVER_CONF:-${ROOT_DIR}/etc/conf/config.py}"
if [ ! -e "${SLICER_DOWNLOAD_SERVER_CONF}" ]; then
  echo "SLICER_DOWNLOAD_SERVER_CONF set to an nonexistent file: ${SLICER_DOWNLOAD_SERVER_CONF}"
  exit 99
fi

# Set variables
SLICER_DOWNLOAD_DB_FALLBACK=$(PYTHONPATH=${ROOT_DIR} ${PYTHON_EXECUTABLE} -c "import slicer_download_server as sds; print(sds.app.config['DB_FALLBACK'])")
SLICER_DOWNLOAD_DB_FILE=$(PYTHONPATH=${ROOT_DIR} ${PYTHON_EXECUTABLE} -c "import slicer_download_server as sds; print(sds.dbFilePath())")
SLICER_DOWNLOAD_DEBUG=$(PYTHONPATH=${ROOT_DIR} ${PYTHON_EXECUTABLE} -c "import slicer_download_server as sds; print(sds.app.config['DEBUG'])")
SLICER_DOWNLOAD_SERVER_API=$(PYTHONPATH=${ROOT_DIR} ${PYTHON_EXECUTABLE} -c "import slicer_download as sd; print(sd.getServerAPI().name)")

# Display summary
echo
echo "[slicer_getbuildinfo] Using this config"
echo "  SLICER_DOWNLOAD_SERVER_CONF: ${SLICER_DOWNLOAD_SERVER_CONF}"
echo "  SLICER_DOWNLOAD_DEBUG      : ${SLICER_DOWNLOAD_DEBUG}"
echo "  SLICER_DOWNLOAD_DB_FALLBACK: ${SLICER_DOWNLOAD_DB_FALLBACK}"
echo "  SLICER_DOWNLOAD_DB_FILE    : ${SLICER_DOWNLOAD_DB_FILE}"
echo "  SLICER_DOWNLOAD_SERVER_API : ${SLICER_DOWNLOAD_SERVER_API}"
echo
echo "[slicer_getbuildinfo] Using these directories"
echo "  ROOT_DIR       : ${ROOT_DIR}"

echo
PYTHONPATH=${ROOT_DIR} "${PYTHON_EXECUTABLE}" "${ROOT_DIR}/etc/slicer_getbuildinfo" $* ${SLICER_DOWNLOAD_DB_FILE}
