# fLotte GBFS publishing

This directory contains [a script](main.sh) that
1. uses `cb2gbfs` to generate three [fLotte](https://flotte-berlin.de) GBFS feeds (`flotte-berlin`, `flotte-brandenburg` & `flotte-potsdam`)
2. copies the feeds into the `flotte` bucket within the [bbnavi](https://bbnavi.de) [open data portal](https://opendata.bbnavi.de)
3. repeats this process every 15 minutes.

## Docker

To build a Docker image for this publishing tool, run the following command *within this directory*:

```shell
docker build -t publish-flotte-gbfs .
```

*Note:* The [`Dockerfile`](Dockerfile) assumes that you have built the [commonsbooking2gbfs](..) Docker image as `commonsbooking2gbfs`.

Run a container as follows:

```shell
docker run -it --rm \
	-e MINIO_ACCESS_KEY=… -e MINIO_SECRET_KEY=… \
	publish-flotte-gbfs
```