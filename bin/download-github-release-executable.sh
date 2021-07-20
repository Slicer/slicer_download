#!/bin/bash

set -e

script_dir=$(cd $(dirname $0) || exit 1; pwd)

GITHUB_RELEASE_EXECUTABLE=${script_dir}/github-release

# Display summary
echo
echo "[download_github_release_executable] Using these executables"
echo "  GITHUB_RELEASE_EXECUTABLE : ${GITHUB_RELEASE_EXECUTABLE}"

executable_name=linux-amd64-github-release
filename=${executable_name}.bz2
url=https://github.com/github-release/github-release/releases/download/v0.10.0/${filename}
sha256=b360af98188c5988314d672bb604efd1e99daae3abfb64d04051ee17c77f84b6

echo
if [[ ! -f ${script_dir}/${filename} ]]; then
  echo "[download_github_release_executable] Downloading ${filename}"
  curl -o ${script_dir}/${filename} -# -SL ${url}
else
  echo "[download_github_release_executable] Skipping download: Found ${filename}"
fi

echo
echo "[download_github_release_executable] Checking"
echo "${sha256}  ${script_dir}/${filename}" > ${script_dir}/${filename}.sha256
sha256sum -c ${script_dir}/${filename}.sha256
rm -f ${script_dir}/${filename}.sha256

echo
echo "[download_github_release_executable] Extracting"
bunzip2 -f ${script_dir}/${filename} -c > ${GITHUB_RELEASE_EXECUTABLE}
chmod u+x ${GITHUB_RELEASE_EXECUTABLE}

echo
echo "[download_github_release_executable] Executing"
${GITHUB_RELEASE_EXECUTABLE} --version