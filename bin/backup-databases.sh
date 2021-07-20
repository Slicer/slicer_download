#!/bin/bash

set -e

script_dir=$(cd $(dirname $0) || exit 1; pwd)

ROOT_DIR=$(realpath "${script_dir}/..")
VIRTUALENV_DIR=$(realpath -m "${ROOT_DIR}/env")
PYTHON_EXECUTABLE=${VIRTUALENV_DIR}/bin/python

DATABASE_BACKUPS_GITHUB_REPO=slicer_download_database_backups

# Customizing environment
echo -n "[backup_database] Looking for ${script_dir}/.start_environment "
if [ -e "${script_dir}/.start_environment" ]; then
  source "${script_dir}/.start_environment"
  echo "[ok]"
else
  echo "[not found]"
fi

# Backup working directory
BACKUP_WORK_DIR=`mktemp -d -p "/tmp"`
if [[ ! "${BACKUP_WORK_DIR}" || ! -d "${BACKUP_WORK_DIR}" ]]; then
  echo "[backup_database] Could not create backup working directory"
  exit 1
fi

# Deletes the temp directory
function cleanup {
  echo
  echo "[backup_database] Deleting backup working directory ${BACKUP_WORK_DIR}"
  rm -rf "${BACKUP_WORK_DIR}"
}

# Register the cleanup function to be called on the EXIT signal
trap cleanup EXIT

# Configuration
export SLICER_DOWNLOAD_SERVER_CONF="${SLICER_DOWNLOAD_SERVER_CONF:-${ROOT_DIR}/etc/conf/config.py}"
if [ ! -e "${SLICER_DOWNLOAD_SERVER_CONF}" ]; then
  echo "SLICER_DOWNLOAD_SERVER_CONF set to an nonexistent file: ${SLICER_DOWNLOAD_SERVER_CONF}"
  exit 99
fi

# Variables
SLICER_DOWNLOAD_SERVER_API=$(PYTHONPATH=${ROOT_DIR} ${PYTHON_EXECUTABLE} -c "import slicer_download as sd; print(sd.getServerAPI().name)")
SLICER_DOWNLOAD_DB_FILE=$(PYTHONPATH=${ROOT_DIR} ${PYTHON_EXECUTABLE} -c "import slicer_download_server as sds; print(sds.dbFilePath())")
SLICER_DOWNLOAD_STATS_DB_FILE="${ROOT_DIR}/var/download-stats.sqlite"
SLICER_DOWNLOAD_STATS_DATA_FILE="${ROOT_DIR}/var/slicer-download-data.json"

# Display summary
echo
echo "[backup_database] Using this config"
echo "  SLICER_DOWNLOAD_SERVER_CONF     : ${SLICER_DOWNLOAD_SERVER_CONF}"
echo "  SLICER_DOWNLOAD_SERVER_API      : ${SLICER_DOWNLOAD_SERVER_API}"
echo "  DATABASE_BACKUPS_GITHUB_REPO    : ${DATABASE_BACKUPS_GITHUB_REPO}"
echo
echo "[backup_database] Database files"
echo "  SLICER_DOWNLOAD_DB_FILE         : ${SLICER_DOWNLOAD_DB_FILE}"
echo "  SLICER_DOWNLOAD_STATS_DB_FILE   : ${SLICER_DOWNLOAD_STATS_DB_FILE}"
echo "  SLICER_DOWNLOAD_STATS_DATA_FILE : ${SLICER_DOWNLOAD_STATS_DATA_FILE}"
echo
echo "[backup_database] Using these directories"
echo "  ROOT_DIR        : ${ROOT_DIR}"
echo "  BACKUP_WORK_DIR : ${BACKUP_WORK_DIR}"
echo
echo "[backup_database] Using these executables"
echo "  PYTHON_EXECUTABLE         : ${PYTHON_EXECUTABLE}"

#
# Download github-release executable
#
source ${script_dir}/download-github-release-executable.sh


#
# Prepare backup
#

# Prefix used to uniquely identify backups
BACKUP_PREFIX=$(date '+%Y.%m.%d')
echo
echo "[backup_database] Using backup_prefix: ${BACKUP_PREFIX}"


# Copy database files
for path in \
  ${SLICER_DOWNLOAD_DB_FILE} \
  ${SLICER_DOWNLOAD_STATS_DB_FILE} \
  ${SLICER_DOWNLOAD_STATS_DATA_FILE}
  do
  filename=$(basename ${path})
  backup_filename=${BACKUP_PREFIX}_${filename}
  dest_path=${BACKUP_WORK_DIR}/${backup_filename}
  echo
  echo "[backup_database] Copying ${path} -> ${dest_path}"
  cp ${path} ${dest_path}
done

#
# Retrieve database backups
#

echo
CURRENT_DATABASE_BACKUPS_JSON=${BACKUP_WORK_DIR}/database-backups-assets.json
${GITHUB_RELEASE_EXECUTABLE} \
  info \
    --security-token "${SLICER_BACKUP_DATABASE_GITHUB_TOKEN}" \
    --json \
    --user Slicer \
    --repo ${DATABASE_BACKUPS_GITHUB_REPO} \
    --tag database-backups \
    | jq '.Releases[] | select(.tag_name == "database-backups") | .assets[] | {name,size}' > ${CURRENT_DATABASE_BACKUPS_JSON}


DATABASE_BACKUPS_MARKDOWN=$(${GITHUB_RELEASE_EXECUTABLE} \
  info \
    --security-token "${SLICER_BACKUP_DATABASE_GITHUB_TOKEN}" \
    --json \
    --user Slicer \
    --repo ${DATABASE_BACKUPS_GITHUB_REPO} \
    --tag database-backups \
    | jq -r '.Releases[] | select(.tag_name == "database-backups") | .body')

#
# Perform backup
#

for path in \
  ${SLICER_DOWNLOAD_DB_FILE} \
  ${SLICER_DOWNLOAD_STATS_DB_FILE} \
  ${SLICER_DOWNLOAD_STATS_DATA_FILE}
  do
  filename=$(basename ${path})
  backup_filename=${BACKUP_PREFIX}_${filename}
  backup_filepath=${BACKUP_WORK_DIR}/${backup_filename}

  # If local asset has been uploaded but its size does not match, exit and report the issue
  asset_json=$(cat ${CURRENT_DATABASE_BACKUPS_JSON} | jq '. | select(.name == "'${backup_filename}'")')
  if [[ "${asset_json}" != "" ]]; then
    remote_asset_size=$(echo ${asset_json} | jq '. | .size')
    local_asset_size=$(wc -c ${backup_filepath} | cut -f1 -d" ")
    if [[ "${remote_asset_size}" != "${local_asset_size}" ]]; then
      echo "[backup_database] Asset '${backup_filename}' already uploaded by size does not match !"
      echo "                  remote_asset_size: ${remote_asset_size}"
      echo "                  local_asset_size: ${local_asset_size}"
      exit 1
    else
      echo "[backup_database] Asset '${backup_filename}' already uploaded: skipping"
      continue
    fi
  fi

  echo
  echo "[backup_database] Uploading ${backup_filepath}"

  echo
  ${GITHUB_RELEASE_EXECUTABLE} \
    upload \
      --security-token "${SLICER_BACKUP_DATABASE_GITHUB_TOKEN}" \
      --user Slicer \
      --repo ${DATABASE_BACKUPS_GITHUB_REPO} \
      --tag database-backups \
      --name ${backup_filename} \
      --file ${backup_filepath}

  asset_sha256=$(sha256sum ${backup_filepath} | cut -d " " -f1)
  asset_download_base_url="https://github.com/Slicer/${DATABASE_BACKUPS_GITHUB_REPO}/releases/download/database-backups/"
  asset_markdown="* [${backup_filename}](${asset_download_base_url}/${backup_filename})
  - SHA256: \`${asset_sha256}\`"
  DATABASE_BACKUPS_MARKDOWN="${DATABASE_BACKUPS_MARKDOWN}
${asset_markdown}"

  echo
  echo "[backup_database] Updating release description adding ${backup_filename} (${asset_sha256})"
  echo
  ${GITHUB_RELEASE_EXECUTABLE} \
    edit \
      --security-token "${SLICER_BACKUP_DATABASE_GITHUB_TOKEN}" \
      --user Slicer \
      --repo ${DATABASE_BACKUPS_GITHUB_REPO} \
      --tag database-backups \
      --description "${DATABASE_BACKUPS_MARKDOWN}"
done