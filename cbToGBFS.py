# Run as: ENV_SOURCE=<path to source .geojson> ENV_DEST=<path to destination folder> python geojsonToStatus.py
from argparse import ArgumentParser
import requests
import copy
from xml.etree import ElementTree as ET
import json
import os
from datetime import datetime, timedelta
import requests
import logging
from pathlib import Path
import urllib.parse

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
logger = logging.getLogger("cbToGBFS")

DEFAULT_MAX_RANGE_METERS = 30000
USER_AGENT = 'cb2GTFS'

class CommonsBookingDataSource():
	api = "commons-booking"

	feature_map = {
		11: "Cargo Trike",
		15: "Cargo Bike",
		18: "Kindertransport",
        75: "Elektro",
		90: "Deckel",
		94: "Ladefläche",
		149: "Regenverdeck",
		206: "Rikscha",
		216: "2. Kinderbank", 
	}
	
	def get_stations(self, cb_map_settings):
		data = {
			"nonce": cb_map_settings["nonce"],
			"cb_map_id": cb_map_settings["cb_map_id"],
			"action": "cb_map_locations"
		}

		res = requests.post(cb_map_settings["data_url"], data=data, headers={'User-Agent': USER_AGENT, "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
		return res.json()

	def get_data(self, url):
		if url.startswith('file://'):
			with open(url[7:]) as f:
				return json.load(f)
		else:
			res = requests.get(url, headers = {'User-Agent': USER_AGENT})
			if res.status_code == 200:
				response = res.text
				cb_settings_assignment = "cb_map.settings = "
				first_idx = response.find(cb_settings_assignment) + len(cb_settings_assignment)
				last_idx = response.find("};", first_idx) + 1

				cb_map_settings = json.loads(response[first_idx:last_idx])
				return self.get_stations(cb_map_settings)

	def as_timestamp(self, timestamp_or_datestring):
		if type(timestamp_or_datestring) == int:
			return timestamp_or_datestring
		else:
			return int(datetime.strptime(timestamp_or_datestring, '%Y-%m-%d').timestamp())

	def current_timeframe(self, item, current_timestamp):
		timeframes = item.get('timeframes')

		if len(timeframes) > 0:
			is_in_timeframe = False
			for timeframe in timeframes:
				date_start = self.as_timestamp(timeframe['date_start'])
				date_end = self.as_timestamp(timeframe['date_end']) + (24*60*60 if type(timeframe['date_end'])== 'str' else 0)
				if current_timestamp >= date_start and current_timestamp <= date_end:
					return [date_start, date_end]
		return None

	def todays_cb_availability(self, item):
		current_date = datetime.now().strftime('%Y-%m-%d')
		availability = item.get('availability')
		if availability:
			for d in availability:
				if d['date'] ==  current_date:
					return d['status']
		else:
			return 'available'
		
	def is_available(self, item, current_timestamp):
		if item['status'] != "publish":
			return False

		if not self.current_timeframe(item, current_timestamp):
			return False

		if "available" != self.todays_cb_availability(item):
			return False

		return True

	def is_available_until(self, item, current_timestamp):
		timeframe = self.current_timeframe(item, current_timestamp)
		min_timeframe = timeframe[1] if timeframe else None
		min_availability_date = None

		availability = item.get('availability')
		if availability:
			for d in availability[1:]:
				if "available" != d['status']:
					return min(self.as_timestamp(d['date']), min_timeframe)
		
		return timeframe[1] if timeframe else None
	
	def extract_from_item(self, item, station_id, current_timestamp):
		vehicle_type_id = item['short_desc'].strip() if len(item['short_desc'])>0 else item['name']
		vehicle_type = {
			'vehicle_type_id': vehicle_type_id,
			'name': item['name'],
			'form_factor': 'cargo_bicycle', # Note: other for GBFS 2.2
			'wheel_count': 3 if 11 in item['terms'] or 'Trike' in item['short_desc'] else 2,
			'propulsion_type': 'electric_assist' if 90 in item['terms'] else 'human',
			'name': item['short_desc'].strip(),
			'return_type': 'roundtrip',
			'default_pricing_plan_id': 'kostenfrei',
			'vehicle_image': urllib.parse.quote(item['thumbnail']) if 'thumbnail' in item and item['thumbnail'] else None,
		}
		
		vehicle_id = '{}_{}'.format(item['id'], item['name'])
		is_available = self.is_available(item, current_timestamp)
		vehicle = {
			'bike_id': vehicle_id,
			'is_reserved': not is_available,
			'is_disabled': item['status'] != 'publish',
			'vehicle_type_id': vehicle_type_id,
			'station_id': station_id,
			'rental_uris': {
				'web': item['link']
			},
			'pricing_plan_id': 'kostenfrei'
		}

		# Note: We have no range information available. 
		# GBFS spec says for current_range_meters:
		# REQUIRED if the corresponding vehicle_type definition for this 
		# vehicle has a motor. This value represents the furthest distance 
		# in meters that the vehicle can travel with the vehicle's current
		# charge or fuel (without recharging or refueling). 
		# Note that in the case of carsharing, the given range is indicative
		# and can be different from the one displayed on the vehicle's dashboard.
		if vehicle_type['propulsion_type'] == 'electric_assist':
			vehicle_type['max_range_meters'] = DEFAULT_MAX_RANGE_METERS
			vehicle['current_range_meters'] = DEFAULT_MAX_RANGE_METERS

		if is_available:
			until = self.is_available_until(item, current_timestamp)
			if until:
				vehicle['availabe_until'] = until
		
		return vehicle, vehicle_type

	def extract_from_vehicles(self, items, station_id, current_timestamp):
		vehicles = {}
		vehicle_types = {}

		for item in items:
			vehicle, vehicle_type = self.extract_from_item(item, station_id, current_timestamp)
			vehicle_types[vehicle_type['vehicle_type_id']] = vehicle_type
			vehicles[vehicle['bike_id']] = vehicle
		
		return vehicles, vehicle_types

	def extract_opening_hours(self, closed_days):
		WEEKDAYS = ['mo','tu','we','th','fr','sa', 'su']
		if not closed_days:
			return
		if type(closed_days) == 'str':
			quote = '"'
		else:
			quote = ''

		opening_days = []
		for weekday in range(1,7):
			if not quote+str(weekday)+quote in closed_days:
				opening_days.append(WEEKDAYS[weekday-1])

		# Assume public holidays are handled like sundays
		opening_days.append('ph off' if (quote+"7"+quote) in closed_days else "ph")

		return ','.join(opening_days)

	def update_availability_status(data, stations, vehicles):
		stations_status = {}
		for vehicle in vehicles:
			vehicle_id = vehicle['bike_id']
			
		
			station_id = vehicle['station_id']
			status = stations_status.get(station_id)
			if not status:
				status = {}
				stations_status[station_id] = status

			vehicle_type_id = vehicle['vehicle_type_id']
			if not status.get(vehicle_type_id):
				status[vehicle_type_id] = 0
			if not vehicle['is_reserved'] and not vehicle['is_disabled']:
				status[vehicle_type_id] += 1
				stations[station_id]["num_bikes_available"] += 1
			
		for station_id in stations:
			if station_id in stations_status:
				status = stations_status[station_id] if station_id in stations_status else {}	
			stations[station_id]['vehicle_types_available'] = [ {"vehicle_type_id": x, "count": status[x]} for x in status]
			else:
				stations[station_id]['vehicle_types_available'] = []

	def load_stations(self, datasource):
		infos = {}
		status = {}
		vehicles = {}
		vehicle_types = {}

		default_last_reported = int(datetime.timestamp(datetime.now()))

		stations = self.get_data(datasource)
        
		for elem in stations:
			station_id = elem['location_name']
			station = {
				"lat": round(elem['lat'], 6),
				"lon": round(elem['lon'], 6),
				'name': elem['location_name'],
				'station_id': station_id,
				'addresss': elem['address']['street'],
				'post_code': elem['address']['zip'],
				'city': elem['address']['city'], # Non-standard
			}

			# station_opening_hours is GBFS 3.0, we include it anyway
			# Note & TODO: opening _hours_ are currently not part of the commons-booking API
			station_opening_hours = self.extract_opening_hours(elem['closed_days'])
			if station_opening_hours:
				station['station_opening_hours'] = station_opening_hours

			station_link = elem.get('location_link')
			if station_link:
				station['rental_uris'] = {
					'web': station_link
				}

			infos[station_id] = station

			station_vehicles, station_vehicle_types = self.extract_from_vehicles(elem['items'], station_id, default_last_reported)

			vehicles = vehicles | station_vehicles
			vehicle_types = vehicle_types | station_vehicle_types

			status[station_id] = {
				"num_bikes_available": 0,
				"vehicle_types_available": [],
				"is_renting": True,
				"is_installed": True,
				"is_returning": True,
				'station_id': station_id,
				'last_reported': default_last_reported
			}

		self.update_availability_status(status, vehicles.values())

		
		return list(infos.values()), list(status.values()), vehicle_types, vehicles

class GbfsWriter():

	def write_gbfs_file(self, filename, data, timestamp, ttl=1800 ):
		with open(filename, "w") as dest:
			content = {
				"data": data,
				"last_updated": timestamp,
				"ttl": ttl,
				"version": "2.3"
			}
			json.dump(content, dest, indent=2)

	def gbfs_data(self, base_url):
		gbfs_data = { "de": {
			  "feeds": [
				{
				  "name": "system_information",
				  "url": base_url+"/system_information.json"
				},
				{
				  "name": "station_information",
				  "url": base_url+"/station_information.json"
				},
				{
				  "name": "station_status",
				  "url": base_url+"/station_status.json"
				},
				{
				  "name": "free_bike_status",
				  "url": base_url+"/free_bike_status.json"
				},
				{
				  "name": "vehicle_types",
				  "url": base_url+"/vehicle_types.json"
				},
				{
				  "name": "system_pricing_plans",
				  "url": base_url+"/system_pricing_plans.json"
				},
				
			  ]
			}}
		return gbfs_data

	def write_gbfs_feed(self, config, destFolder, info, status, vehicle_types, vehicles, base_url):
		base_url = base_url or config['publication_base_url']
		pricing_plans = config.get('pricing_plans')
		system_information = copy.deepcopy(config['system_information_data'])
		Path(destFolder).mkdir(parents=True, exist_ok=True)
		
		timestamp = int(datetime.timestamp(datetime.now()))
		self.write_gbfs_file(destFolder + "/gbfs.json", self.gbfs_data(base_url) , timestamp)
		self.write_gbfs_file(destFolder + "/station_information.json", {"stations": info} , timestamp)
		self.write_gbfs_file(destFolder + "/station_status.json", {"stations": status}, timestamp)
		self.write_gbfs_file(destFolder + "/free_bike_status.json", {"bikes": list(vehicles.values())}, timestamp)
		self.write_gbfs_file(destFolder + "/system_information.json", system_information, timestamp)
		self.write_gbfs_file(destFolder + "/vehicle_types.json", {"vehicle_types": list(vehicle_types.values())}, timestamp)
		if pricing_plans:
			self.write_gbfs_file(destFolder + "/system_pricing_plans.json", {"plans": pricing_plans}, timestamp)


def generate_feed(destFolder, config, baseUrl):
	(info, status, vehicle_types, vehicles) = CommonsBookingDataSource().load_stations(config['datasource'])
	GbfsWriter().write_gbfs_feed(config, destFolder, info, status, vehicle_types, vehicles, baseUrl)
	
def main(args):
	destFolder = args.outputDir
	config_name = args.config
	
	with open("config.json") as f:
		configs = json.load(f)

	if config_name == "all":
		for name in configs:
			generate_feed(destFolder+"/"+name, configs[name], args.baseUrl+"/"+name if args.baseUrl else None)
	else:
		generate_feed(destFolder, configs[config_name], args.baseUrl)

		
if __name__ == '__main__':
	parser = ArgumentParser()
	parser.add_argument("-o", "--outputDir", help="output directory the transformed files are written to", default="out")
	parser.add_argument("-t", "--token", required=False, help="token for service")
	parser.add_argument("-c", "--config", required=False, help="service provider", default="all")
	parser.add_argument("-b", "--baseUrl", required=False, help="baseUrl this/these feed(s) will be published under")
	
	args = parser.parse_args()

	main(args)
