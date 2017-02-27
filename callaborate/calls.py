import json
import requests
from app import app

JSON_HEADERS = {'Content-type': 'application/json', 'Accept': 'application/json'}


def make_call(number):
    url = 'https://api.tropo.com/1.0/sessions'
    data = {
        'token': app.config['TROPO_VOICE_API_KEY'],
        'number': number,
    }
    r = requests.post(url, data=json.dumps(data), headers=JSON_HEADERS)
    return r.json['id']  # session_id


def send_signal(session_id, signal):
    session_id = session_id.strip()
    url = 'https://api.tropo.com/1.0/sessions/{}/signals'.format(session_id)
    data = {'signal': signal}
    r = requests.post(url, data=json.dumps(data), headers=JSON_HEADERS)

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
