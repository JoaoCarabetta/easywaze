from sqlalchemy import  Table, Column, Integer, String, MetaData, ForeignKey, BigInteger, DATETIME, JSON
import sqlalchemy as sa
import yaml
import requests
import json
import datetime
from dateutil import tz
import fire
import urllib.parse as urlparse
from urllib.parse import urlencode

# Local imports
from utils import create_mysql_engine


def create_engine():
    return sa.create_engine("mysql+pymysql://root:root@easywaze-mysql:3306")


def create_tables(engine):

    try:
        engine.execute("CREATE DATABASE waze") #create db
    except:
        pass
    engine.execute("USE waze")

    # Try to create table if not exist
    metadata = MetaData()
    tables = {}
    for table in ['jams', 'irregularities', 'alerts']:
        
        tables[table] = Table(table, metadata,
            Column("id",                  Integer, primary_key=True),
            Column("start_time_millis",   BigInteger),
            Column("end_time_millis",     BigInteger),
            Column("start_time",          DATETIME),
            Column("end_time",            DATETIME),
            Column("timezone",            String(255)),
            Column("raw_json",            JSON)
            )

    metadata.create_all(engine)

    return tables


def get_timezone(url):
    
    data = request_url(url)
    lng, lat = data['alerts'][0]['location'].values()
    geourl = 'http://api.geonames.org/timezoneJSON?lat={lat}&lng={lng}&username=easywaze'.format(lat=lat ,lng=lng)
    
    return json.loads(requests.get(geourl).text)['timezoneId']

def improve_url(url):
    
    needed_items = {'acotu': 'true',
             'format': 'JSON',
             'irmie': 'true',
             'types': 'traffic,alerts,irregularities'}
    
    url, polygon = url.split('&polygon=')
    
    url_parts = list(urlparse.urlparse(url))
    current_items = dict(urlparse.parse_qsl(url_parts[4]))
    
    final_items = dict(needed_items, **current_items)

    url_parts[4] = urlencode(final_items)

    return urlparse.urlunparse(url_parts) + '&polygon=' + polygon

def load_yaml():

    res = yaml.load(open('config.yaml', 'r'))

    for i, city in enumerate(res['cities']):

        if 'acotu=true&irmie=true' not in city['endpoint']:
            res['cities'][i]['endpoint'] = improve_url(city['endpoint'])
            yaml.dump(res, open('config.yaml', 'w'))
        
        if 'timezone' not in city.keys():
            res['cities'][i]['timezone'] = get_timezone(city['endpoint'])
            yaml.dump(res, open('config.yaml', 'w'))

    return res['cities']


def request_url(url):

    headers = {'user-agent': "Mozilla/5.0 (X11; Fedora; Linux x86_64; rv:38.0) Gecko/20100101 Firefox/38.0",}

    response = requests.get(url, headers=headers)

    return json.loads(response.text)


def insert_data(data, city, tables, engine):

    from_zone = tz.tzutc()
    to_zone = tz.gettz(city['timezone'])

    for table, meta in tables.items():
        engine.execute("USE waze")
        try:
            ins = meta.insert().values(
                start_time_millis=data['startTimeMillis'],
                end_time_millis=data['endTimeMillis'],
                start_time=(datetime.datetime.
                            strptime(data['startTime'],'%Y-%m-%d %H:%M:%S:%f').
                            replace(tzinfo=from_zone).
                            astimezone(to_zone)),
                end_time=(datetime.datetime.
                            strptime(data['endTime'],'%Y-%m-%d %H:%M:%S:%f').
                            replace(tzinfo=from_zone).
                            astimezone(to_zone)),
                timezone=city['timezone'],
                raw_json=data[table])
            conn = engine.connect()
            conn.execute(ins)
            
        except KeyError:
            print('[FAIL] MySQL Insertion Failed!')
            continue
           
        print('[SUCESS] Data inserted!')


def main():
    
    # Create engine
    engine = create_mysql_engine()
    tables = create_tables(engine)

    cities = load_yaml()
    for city in cities:
        data = request_url(city['endpoint'])
        insert_data(data, city, tables, engine)


if __name__ == '__main__':
    fire.Fire(main)
