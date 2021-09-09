#!/bin/bash

set -e

script_dir=$(cd $(dirname $0) || exit 1; pwd)

ROOT_DIR=$(realpath "${script_dir}/..")
ASSETS_DIR=${ROOT_DIR}/slicer_download_server/assets
TEMPLATES_DIR=${ROOT_DIR}/slicer_download_server/templates

BRANCH=download-slicer-org
FILENAME=${BRANCH}.zip
DOWNLOAD_URL="https://github.com/Slicer/slicer.org/archive/refs/heads/${FILENAME}"

# Display summary
echo
echo "[download_flask_templates_and_assets] Settings"
echo "  DOWNLOAD_URL  : ${DOWNLOAD_URL}"
echo "  ROOT_DIR      : ${ROOT_DIR}"
echo "  ASSETS_DIR    : ${ASSETS_DIR}"
echo "  TEMPLATES_DIR : ${TEMPLATES_DIR}"

# Temporary directory
TEMP_DIR=`mktemp -d -p "/tmp"`
if [[ ! "${TEMP_DIR}" || ! -d "${TEMP_DIR}" ]]; then
  echo "[download_flask_templates_and_assets] Could not create temporary directory"
  exit 1
fi

# Deletes the temp directory
function cleanup {
  echo
  echo "[download_flask_templates_and_assets] Deleting temporary directory ${TEMP_DIR}"
  rm -rf "${TEMP_DIR}"
}

# Register the cleanup function to be called on the EXIT signal
trap cleanup EXIT

# Download
echo
echo "[download_flask_templates_and_assets] Downloading ${FILENAME}"
rm -f
curl -o ${TEMP_DIR}/${FILENAME} -# -SL ${DOWNLOAD_URL}

# Extracting
echo
echo "[download_flask_templates_and_assets] Extracting ${FILENAME}"
unzip -d ${TEMP_DIR}/ ${TEMP_DIR}/${FILENAME}

# Extracted directory is specific to the downloaded archive
site_dir=${TEMP_DIR}/slicer.org-${BRANCH}

# Clear target directories
echo
echo "[download_flask_templates_and_assets] Cleaning directories"
for directory in ${ASSETS_DIR} ${TEMPLATES_DIR}; do
  subdir=$(basename ${directory})
  echo "  ${directory}"
  find ${directory} ! -name '.keep' -type f -exec rm -f {} +
  find ${directory} ! -name "${subdir}" -type d -exec rm -rf {} +
done

# Copy file
echo
echo "[download_flask_templates_and_assets] Copying"

TEMPLATES_FILENAMES="download.html download_40x.html"

echo "  ${site_dir}/assets/* -> ${ASSETS_DIR}/"
cp -r ${site_dir}/assets/* ${ASSETS_DIR}/

for template_filename in ${TEMPLATES_FILENAMES};
do
  echo "  ${site_dir}/${template_filename} -> ${TEMPLATES_DIR}/${template_filename}"
  cp -r ${site_dir}/${template_filename} ${TEMPLATES_DIR}/${template_filename}
done

# Post process
# - Replace "%7B%7B" and "%7D%7D" with "{{" and "}}". This is required because the plugin
#   "jekyll-target-blank" systematically convert the content to html.
echo
echo "[download_flask_templates_and_assets] Postprocessing"
for template_filename in ${TEMPLATES_FILENAMES};
do
  sed -i "s/%7B%7B/{{/g" "${TEMPLATES_DIR}/${template_filename}"
  sed -i "s/%7D%7D/}}/g" "${TEMPLATES_DIR}/${template_filename}"
done
