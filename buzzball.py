import arrow
import csv
import requests
import slack

from slack import files
from tokens import BING_MAPS_API_KEY, SLACK_API_KEY

IAMGROUND_ENDPOINT = 'https://iamground.kr/futsal/s/_f.php?&load=2000'
IAMGROUND_URL_TEMPLATE = 'https://iamground.kr/futsal/detail/{}?offset=0'
IAMGROUND_PICTURE_TEMPLATE = 'http://iamground.kr/img/facility/fut/72aa8bc014c2652944a3e0b3a6cb2361/{}.jpg'
BING_MAPS_ENDPOINT = 'http://dev.virtualearth.net/REST/v1/Routes'

DEFAULT_TIMEOUT = 3 * 60
BUZZVIL_LOCATION = {'latitude': 37.510449, 'longitude': 127.106566}
PREFERENCE = ['726', '728', '729']

CSV_HEADERS = [
    'Name',
    'Address',
    'Driving distance (km)',
    'Driving time (min)',
    'Floor',
    'Indoor',
    'Lighting',
    'Size',
    'Capacity',
    'Parking',
    'Shower',
    'Ball rent',
    'Shoes rent',
    'Vest rent',
    'Temperature controller',
    'Available time | Cost',
    'Reservation link',
    'Pictures',
]
CSV_BODY = []


def get_distance_matrix(latitude, longitude):
    params = {
        'wayPoint.0': '{},{} [Point]'.format(BUZZVIL_LOCATION['latitude'], BUZZVIL_LOCATION['longitude']),
        'wayPoint.1': '{},{} [Point]'.format(latitude, longitude),
        'optimize': 'timeWithTraffic',
        'routeAttributes': 'excludeItinerary',
        'travelMode': 'Driving',
        'key': BING_MAPS_API_KEY,
    }
    response = requests.get(url=BING_MAPS_ENDPOINT, params=params, timeout=DEFAULT_TIMEOUT)
    data = response.json()['resourceSets'][0]['resources'][0]
    return data['travelDistance'], data['travelDuration'] / 60.0


def is_valid_option(option):
    if option['time'] > 30.0 or option['size2'] < '4' or option['size2'] > '7':
        return False

    return True


def get_available_time(option):
    time_slots = []
    time_options = option['reserv']
    for time_option in time_options:
        today = arrow.utcnow().to('+09:00').format('YYYY-MM-DD')
        date = arrow.get(time_option['start_date'], 'YYYY-MM-DD')
        if time_option['start_date'] > today and date.weekday() < 5 and time_option['start_time'] >= '18:00' and '01:00' <= time_option['end_time'] <= '23:00':
            # time_option['time_length'], time_option['unit_price']
            time_slots.append('{}({}) {}-{} | {}'.format(time_option['start_date'], date.format('dddd', locale='en_GB'), time_option['start_time'], time_option['end_time'], time_option['unit_price']))

    return time_slots


if __name__ == '__main__':
    data = {'from': 'full_info'}
    response = requests.post(url=IAMGROUND_ENDPOINT, data=data, timeout=DEFAULT_TIMEOUT)
    data = response.json()

    OPTIONS = data['reserv']
    PICTURES = data['pic']

    for option in OPTIONS:
        option['distance'], option['time'] = get_distance_matrix(option['latitude'], option['longitude'])
        if not is_valid_option(option):
            continue
        available_time = get_available_time(option)
        if not available_time:
            continue

        pictures = [IAMGROUND_PICTURE_TEMPLATE.format(picture['pName'])
                    for picture in PICTURES if picture['fNum'] == option['fNum']]

        info = [
            option['fName'],
            option['fAddress'],
            option['distance'],
            option['time'],
            option['floor'],
            option['indoor'],
            option['lighting'],
            option['size'],
            option['size2'],
            option['parking'],
            option['shower'],
            option['ballrent'],
            option['shoesrent'],
            option['vestrent'],
            option['temp'],
            '\n'.join(available_time),
            IAMGROUND_URL_TEMPLATE.format(option['fNum']),
            '\n'.join(pictures),
        ]
        if option['fNum'] in PREFERENCE:
            CSV_BODY.insert(0, info)
        else:
            CSV_BODY.append(info)

    with open('buzzball.csv', 'w') as writeFile:
        writer = csv.writer(writeFile)
        writer.writerow(CSV_HEADERS)
        writer.writerows(CSV_BODY)
    writeFile.close()

    today = arrow.utcnow().to('+09:00').format('YYYY-MM-DD')
    slack.api_token = SLACK_API_KEY
    files.upload(
        channels='#buzzball',
        filename='buzzball_{}.csv'.format(today),
        content=open('buzzball.csv', 'r').read(),
    )
