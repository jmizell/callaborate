"""
Utils to interact with the redis DB
"""
import os
import httplib2
import json
import redis
from datetime import datetime
from apiclient import discovery
from oauth2client.service_account import ServiceAccountCredentials
from app import app

LOCAL_REDIS = 'redis://localhost:6379/0'
REDIS_URL = os.environ.get('REDISCLOUD_URL', LOCAL_REDIS)
CALLEE_COUNTER_KEY = 'callee_counter'
EVENTS_KEY = 'events'
CALLED_NUMBERS_SET_KEY = 'called_numbers_set'
redis = redis.from_url(REDIS_URL)


class CallSheet:
    def __init__(self, key_file_dict, spreadsheet_id):
        self.key_file_dict = key_file_dict
        self.spreadsheet_id = spreadsheet_id
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets']
        self.letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        self.credentials = ServiceAccountCredentials.from_json_keyfile_dict(
            keyfile_dict=app.config['GOOGLE_KEY_FILE_DICT'],
            scopes=self.scopes)
        self.calls = []
        self.headers = []
        self._load_callees()

    def _get_sheet_service(self):
        http = self.credentials.authorize(httplib2.Http())
        return discovery.build('sheets', 'v4', http=http)

    def _sheet_to_dict(self, rows):
        calls = []
        self.headers = rows[0]
        for row in rows[1:]:
            row = (row + [''] * len(rows[0]))[:len(rows[0])]  # pad rows to match column headers
            calls.append(dict(zip(self.headers, row)))
        return calls

    def _load_callees(self):
        result = self._get_sheet_service().spreadsheets().values().get(
            spreadsheetId=app.config['SPREADSHEET_ID'],
            range='A:ZZ').execute()
        values = result.get('values', [])
        if values:
            self.calls = self._sheet_to_dict(values)

    def get_cell_range(self, row, column_name):
        column = self.headers.index(column_name) + 1
        result = []
        while column:
            column, remainder = divmod(column - 1, 26)
            result[:0] = self.letters[remainder]
        return ''.join(result) + str(row + 2)

    def get(self, index):
        return self.calls[index]

    def write_cell(self, column_name, row, value):
        body = {'values': [[value]]}
        self._get_sheet_service().spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id, range=self.get_cell_range(row, column_name),
            valueInputOption="RAW", body=body).execute()


callees = CallSheet(app.config['GOOGLE_KEY_FILE_DICT'], app.config['SPREADSHEET_ID'])


def store_event(event_name, data):
    event = dict(
        name=event_name,
        timestamp=datetime.utcnow().isoformat(),
        data=data,
    )
    redis.rpush(EVENTS_KEY, json.dumps(event))


def count_calls():
    return redis.get(CALLEE_COUNTER_KEY)


def get_next_callee():
    """
    # TODO Testing, fix before commit
    """
    index = redis.incr(CALLEE_COUNTER_KEY) - 1
    callee = callees.get(index)
    redis.sadd(CALLED_NUMBERS_SET_KEY, callee['phone'])
    if redis.sismember(CALLED_NUMBERS_SET_KEY, callee['phone']):
        store_event('skipped_repeat_number', callee)
        return get_next_callee()
    else:
        redis.sadd(CALLED_NUMBERS_SET_KEY, callee['phone'])
        return index, callee


def get_events():
    events = {}
    for e in redis.lrange("events", 0, -1):
        e = json.loads(e)
        events.setdefault(e['name'], []).append(e)
    return events


def coalesce_dicts(signins):
    user = {}
    keys = set()
    keys.update(*signins)
    for k in keys:
        for s in signins:
            if s.get(k):
                user[k] = s.get(k)
    return user


def sort_dicts_by_key(items, sort_key, mutate=lambda k, v: k):
    retval = {}
    for i in items:
        key = mutate(i.get(sort_key), i)
        retval.setdefault(key, []).append(i)
    return retval


def get_calls_by_phone():
    events = get_events()
    caller_data = [e['data']['raw_data']['caller'] for e in events['save_call']]

    def remove_dashes(k, v):
        if k:
            return k.replace('-', '')
        else:
            return k

    return sort_dicts_by_key(caller_data, 'phoneNumber', mutate=remove_dashes)


def get_full_leaderboard():
    calls_by_phone = get_calls_by_phone()
    leaders = sorted([(len(v), k) for k,v in calls_by_phone.items()], reverse=True)
    users = [coalesce_dicts(calls_by_phone[k]) for v,k in leaders]
    full_leaderboard = [dict(calls=v, **u) for u, (v,k) in zip(users, leaders)]
    for l in full_leaderboard: del l['sessionId']
    return full_leaderboard


def get_leaderboard():
    users = get_full_leaderboard()
    names = ['{} {}.'.format(u.get('firstName', 'Anonymous').title(), u.get('lastName', 'Badger')[:1].upper()) for u in users]
    return [{'name': n, 'calls': u['calls']} for n, u in zip(names, users)]

# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4
