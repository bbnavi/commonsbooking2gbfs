# This Dockerfile builds a service that regularly publishes the fLotte GBFS feeds to the bbnavi open data portal.
FROM minio/mc as mc

FROM ghcr.io/bbnavi/commonsbooking2gbfs

ENV MINIO_ACCESS_KEY="" MINIO_SECRET_KEY=""
ENV PUBLISH_INTERVAL=""

RUN apk add --no-cache --update tree

# install MinIO client a.k.a. mc
COPY --from=mc /usr/bin/mc /usr/bin/mc

COPY *.sh ./
COPY index.html flotte-*-logo.png ./

# prevent inheriting `python` as entrypoint
ENTRYPOINT []

CMD ["/bin/sh", "main.sh"]
