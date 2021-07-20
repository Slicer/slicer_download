#!/bin/bash

set -e

script_dir=$(cd $(dirname $0) || exit 1; pwd)

ROOT_DIR=$(realpath "${script_dir}/..")
FALLBACK_DIR=${ROOT_DIR}/etc/fallback

VERSION=2021.06.23
GIRDER_SHA256=a8aa2b52e022fdee2f0ca8b882fd7744f622dad9a85e4f3c1792ca5bdd915ed3
MIDAS_SHA256=39569792b939c270ad1e21e9e35f74da2490e10b59a2b507ad63cf551550a920

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

  filename=slicer-${server_api}-records.sqlite
  echo
  echo "[download_fallback_databases] Downloading ${filename}"
  ${GITHUB_RELEASE_EXECUTABLE} \
    download \
      --security-token "${SLICER_BACKUP_DATABASE_GITHUB_TOKEN}" \
      --user Slicer \
      --repo ${DATABASE_BACKUPS_GITHUB_REPO} \
      --tag database-backups \
      --name ${VERSION}_${filename} > ${FALLBACK_DIR}/${filename}

  sha5256_varname=${server_api^^}_SHA256
  sha256=${!sha5256_varname}
  echo
  echo "[download_fallback_databases] Checking"
  echo "${sha256}  ${FALLBACK_DIR}/${filename}" > ${FALLBACK_DIR}/${filename}.sha256
  sha256sum -c ${FALLBACK_DIR}/${filename}.sha256
  rm -f ${FALLBACK_DIR}/${filename}.sha256
done