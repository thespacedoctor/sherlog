#!/usr/bin/env bash
#
# RE-DOWNLOAD ALADIN LITE AND VENDOR IT UNDER static/vendor/aladin/.
#
# WE SERVE ALADIN OURSELVES INSTEAD OF LOADING IT FROM aladin.cds.unistra.fr
# BECAUSE THAT CDN SENDS Cache-Control: no-store ON THE 1.8 MB BUNDLE, SO A
# BROWSER RE-DOWNLOADS IT ON EVERY PAGE VIEW. CDS ALSO PUBLISHES NO WORKING
# PINNED-VERSION URL, SO THIS SCRIPT ALWAYS FETCHES "latest" AND EXTRACTS THE
# VERSION STRING BAKED INTO THE BUNDLE ITSELF TO NAME THE VENDORED FILE.
#
# USAGE:
#     bash scripts/vendor_aladin.sh
#
# AFTER RUNNING, UPDATE THE {% static %} PATH IN
# apps/transients/templates/transients/molecules/sky_view_scripts.html AND
# THE ASSERTION IN tests/test_transients.py TO POINT AT THE NEW FILENAME, AND
# DELETE THE OLD VERSIONED FILE.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_URL="https://aladin.cds.unistra.fr/AladinLite/api/v3/latest/aladin.js"
DEST_DIR="${REPO_ROOT}/static/vendor/aladin"
TMP_FILE="$(mktemp)"
trap 'rm -f "${TMP_FILE}"' EXIT

echo "Downloading ${SOURCE_URL} ..."
curl -fsSL "${SOURCE_URL}" -o "${TMP_FILE}"

VERSION="$(grep -oE '"[0-9]+\.[0-9]+\.[0-9]+"' "${TMP_FILE}" | head -1 | tr -d '"')"
if [[ -z "${VERSION}" ]]; then
    echo "Could not find a version string in the downloaded bundle — aborting." >&2
    exit 1
fi

DEST_FILE="${DEST_DIR}/aladin-${VERSION}.js"
mkdir -p "${DEST_DIR}"
cp "${TMP_FILE}" "${DEST_FILE}"

echo "Vendored Aladin Lite ${VERSION} to ${DEST_FILE}"
echo "Remember to update the {% static %} path in sky_view_scripts.html and the"
echo "test in tests/test_transients.py, and remove any old aladin-*.js file."
