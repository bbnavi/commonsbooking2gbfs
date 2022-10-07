#!/bin/sh
# This script regularly publishes the fLotte GBFS to the bbnavi open data portal.

set -e

if [ -z "$MINIO_ACCESS_KEY" ]; then
	1>&2 echo 'missing/empty $MINIO_ACCESS_KEY'
	exit 1
fi
if [ -z "$MINIO_SECRET_KEY" ]; then
	1>&2 echo 'missing/empty $MINIO_SECRET_KEY'
	exit 1
fi

# default: 15 minutes
PUBLISH_INTERVAL="${PUBLISH_INTERVAL:-900}"

export MC_HOST_bbnavi="https://$MINIO_ACCESS_KEY:$MINIO_SECRET_KEY@opendata.bbnavi.de"

dir="$(mktemp -d -t flotte-gbfs.XXXXXX)"

set -x

mc cp -q index.html flotte-*-logo.png bbnavi/flotte/

while true; do
	# We sleep first so that, if the GBFS generation fails constantly, we don't DOS the fLotte API.
	sleep "$PUBLISH_INTERVAL"

	python cbToGBFS.py \
		--baseUrl 'https://opendata.bbnavi.de/flotte' \
		--outputDir "$dir" \

	tree -sh "$dir"

	mc cp -q -r $dir/* bbnavi/flotte/
done