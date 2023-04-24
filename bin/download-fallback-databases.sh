#!/bin/bash

set -e

script_dir=$(cd $(dirname $0) || exit 1; pwd)

ROOT_DIR=$(realpath "${script_dir}/..")
FALLBACK_DIR=${ROOT_DIR}/etc/fallback

# slicer-(girder|midas)-records.sqlite
VERSION=2022.11.23
GIRDER_SHA256=f0cd84c3b307cf14b5371d6796577b7a0a39c0a838830dfd8a3788f899b958a9
MIDAS_SHA256=NA

DATABASE_BACKUPS_GITHUB_REPO=slicer_download_database_backups

# Customizing environment
echo -n "[download_fallback_databases] Looking for ${ROOT_DIR}/bin/.start_environment "
if [ -e "${ROOT_DIR}/bin/.start_environment" ]; then
  source "${ROOT_DIR}/bin/.start_environment"
  echo "[ok]"
else
  echo "[not found]"
fi

# Display summary
echo
echo "[download_fallback_databases] Settings"
echo "  VERSION        : ${VERSION}"
echo "  GIRDER_SHA256  : ${GIRDER_SHA256}"
echo "  MIDAS_SHA256   : ${MIDAS_SHA256}"
echo "  ROOT_DIR       : ${ROOT_DIR}"
echo "  FALLBACK_DIR   : ${FALLBACK_DIR}"
echo "  DATABASE_BACKUPS_GITHUB_REPO : ${DATABASE_BACKUPS_GITHUB_REPO}"

#
# Download github-release executable
#
source ${ROOT_DIR}/bin/download-github-release-executable.sh

#
# Download databases
#
mkdir -p ${FALLBACK_DIR}

for server_api in girder midas; do

  sha5256_varname=${server_api^^}_SHA256
  sha256=${!sha5256_varname}

  filename=slicer-${server_api}-records.sqlite

  if [[ $sha256 == "NA" ]]; then
    echo
    echo "[download_fallback_databases] Skipping ${VERSION}_${filename} download: SHA256 not specified"
    continue
  fi

  echo
  echo "[download_fallback_databases] Downloading ${filename}"
  ${GITHUB_RELEASE_EXECUTABLE} \
    download \
      --security-token "${SLICER_BACKUP_DATABASE_GITHUB_TOKEN}" \
      --user Slicer \
      --repo ${DATABASE_BACKUPS_GITHUB_REPO} \
      --tag database-backups \
      --name ${VERSION}_${filename} > ${FALLBACK_DIR}/${filename}

  echo
  echo "[download_fallback_databases] Checking"
  echo "${sha256}  ${FALLBACK_DIR}/${filename}" > ${FALLBACK_DIR}/${filename}.sha256
  sha256sum -c ${FALLBACK_DIR}/${filename}.sha256
  rm -f ${FALLBACK_DIR}/${filename}.sha256
done