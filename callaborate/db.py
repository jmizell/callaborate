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


class NoAvailableNumber(Exception):
    """
    No un-called numbers remain in list
    """
    def __str__(self):
        return repr("No un-called numbers remain in list")


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
        self.load_callees()

    def _get_sheet_service(self):
        http = self.credentials.authorize(httplib2.Http())
        return discovery.build('sheets', 'v4', http=http)

    def _sheet_to_dict(self, rows):
        """
        Convert api response values to a list of dictionaries, assuming first row is column headers

        :param rows: api response values, list of list
        :return: a list of containing dictionary rows
        """
        calls = []
        self.headers = rows[0]
        for row in rows[1:]:
            row = (row + [''] * len(rows[0]))[:len(rows[0])]  # pad rows to match column headers
            calls.append(dict(zip(self.headers, row)))
        return calls

    def load_callees(self):
        """
        Retrieves the constituent list from the Google Sheet

        :return: None
        """
        result = self._get_sheet_service().spreadsheets().values().get(
            spreadsheetId=app.config['SPREADSHEET_ID'],
            range='A:ZZ').execute()
        values = result.get('values', [])
        if values:
            self.calls = self._sheet_to_dict(values)

    def get_cell_range(self, row, column_name):
        """
        Converts column names, and rows values to Sheets API cell ranges

        :param row: zero indexed sheet row, zero starting from row 2 in Google Sheet
        :param column_name: string name of column from Google Sheet
        :return: Sheets cell range
        """
        column = self.headers.index(column_name) + 1
        result = []
        while column:
            column, remainder = divmod(column - 1, 26)
            result[:0] = self.letters[remainder]
        return ''.join(result) + str(row + 2)

    def get(self, index):
        """
        Retrieve a single row from the Google Sheet

        :param row: zero indexed sheet row, zero starting from row 2 in Google Sheet
        :return: dictionary of cell values
        """
        return self.calls[index]

    def length(self):
        return len(self.calls)

    def write_cell(self, row, column_name, value):
        """
        Writes a single cell value to Google Sheet

        :param row: zero indexed sheet row, zero starting from row 2 in Google Sheet
        :param column_name: string name of column from Google Sheet
        :param value: cell value
        :return: None
        """
        body = {'values': [[value]]}
        self._get_sheet_service().spreadsheets().values().update(
            spreadsheetId=self.spreadsheet_id, range=self.get_cell_range(row=row, column_name=column_name),
            valueInputOption="RAW", body=body).execute()

    def _format_batch_data(self, values):
        """
        Formats a list of cell values with column names, and rows to Sheets API data values

        :param values: a list of lists, containing individual cell values, with the format of
            [
              [
                COLUMN_NAME,
                ROW,
                CELL_VALUE
              ],
              ...
            ]
        :return: a list of dictionaries containing Sheets data
        """
        data = []
        for value in values:
            column_name = value[0]
            row = value[1]
            cell_value = value[2]
            data.append(
                {
                    'range': self.get_cell_range(row=row, column_name=column_name),
                    'values': [[cell_value]]
                }
            )
        return data

    def write_call_ranges(self, values):
        """
        Takes a list of cell values, and batch inserts them into the Google Sheet

        :param values: a list of lists, containing individual cell values, with the format of
            [
              [
                COLUMN_NAME,
                ROW,
                CELL_VALUE
              ],
              ...
            ]
        :return: None
        """
        body = {
            'valueInputOption': "RAW",
            'data': self._format_batch_data(values)
        }
        self._get_sheet_service().spreadsheets().values().batchUpdate(
            spreadsheetId=self.spreadsheet_id, body=body).execute()


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


def set_called_list():
    """
    Iterates through the call list, and adds numbers to the called_number_set that have been recorded as contacted

    :return: None
    """
    pipe = redis.pipeline()
    for callee in callees.calls:
        if callee['call_status'] != '':
            redis.sadd(CALLED_NUMBERS_SET_KEY, callee['phone'])
    pipe.execute()


def get_unique_number_count():
    return len(set(map(lambda x: x['phone'], callees.calls)))


def get_next_callee():
    """
    Pulls the next number in the record that has not been contacted,
    or reloads the list if the end of the records has been met.

    :return: integer index, dictionary callee data
    """
    index = int(redis.incr(CALLEE_COUNTER_KEY)) - 1

    # if index is passed last record, reload data from sheets
    if index > callees.length() - 1:
        callees.load_callees()
        redis.delete(CALLEE_COUNTER_KEY, CALLED_NUMBERS_SET_KEY)
        return get_next_callee()

    # if the called number set has no records, set them with recorded values from sheet
    if redis.scard(CALLED_NUMBERS_SET_KEY) == 0:
        set_called_list()

        # if the total number of unique numbers is the same as the number called, signal complete
        if get_unique_number_count() <= redis.scard(CALLED_NUMBERS_SET_KEY):
            raise NoAvailableNumber

    callee = callees.get(index)

    # if record shows the number has been contacted, skip calleee
    if callee['call_status'] != '' or redis.sismember(CALLED_NUMBERS_SET_KEY, callee['phone']):
        store_event('skipped_repeat_number', callee)
        return get_next_callee()

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
