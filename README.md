# commonsbooking2gbfs

commonsbooking2gbfs is a small python script, which generates a GBFS feed from CommonsBookings's fLotte map plugin API.

To generate a feed for e.g. fLotte Berlin network, execute

```sh
python cbToGBFS.py -t <secret> -b https://myportal/gbfs/ -c flotte-berlin
```

To generate feeds for every operator in config.json, just run (without specifying the config, which in this case defaults to `all`)

```sh
python cbToGBFS.py -t <secret> -b https://myportal/gbfs/
```

Note: Not every GBFS information can be retrieved from the API. The content of system_information and system_pricing_plans is hard coded in config.json and needs to be updated, if this information changes.

## Using Docker

```sh
docker build -t mfdz/commonsboooking2gbfs .
docker run --rm -v $PWD/out:/usr/src/app/out mfdz/commonsboooking2gbfs cbToGBFS.py -t <secret> -b https://data.mfdz.de/gbfs/
```







