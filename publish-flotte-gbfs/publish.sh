#!/bin/sh
# This script regularly publishes the fLotte GBFS to the bbnavi open data portal.

set -e

if [ -z "$GBFS_TMP_DIR" ]; then
	1>&2 echo 'missing/empty $GBFS_TMP_DIR'
	exit 1
fi
echo 1 "$1"
if [ -z "$1" ]; then
	1>&2 echo 'missing/empty 1st argument'
	exit 1
fi
bucket="$1"

set -x

python cbToGBFS.py \
	--baseUrl 'https://opendata.bbnavi.de/flotte' \
	--outputDir "$GBFS_TMP_DIR" \

tree -sh "$GBFS_TMP_DIR"

mc cp -q -r $GBFS_TMP_DIR/* "$bucket/"
