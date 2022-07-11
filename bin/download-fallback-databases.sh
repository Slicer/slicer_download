#!/bin/bash

set -e

script_dir=$(cd $(dirname $0) || exit 1; pwd)

ROOT_DIR=$(realpath "${script_dir}/..")
FALLBACK_DIR=${ROOT_DIR}/etc/fallback

VERSION=2022.07.11
GIRDER_SHA256=871002b6fdb5d9263a12cabc9b39d66e20e8aaa45570f73ba84f84531f64d759
MIDAS_SHA256=NA

DATABASE_BACKUPS_GITHUB_REPO=slicer_download_database_backups

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
source ${script_dir}/download-github-release-executable.sh

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