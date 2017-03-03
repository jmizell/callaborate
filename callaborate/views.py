import hashlib
from multiprocessing.dummy import Pool as ThreadPool
from datetime import datetime, timedelta
from functools import wraps
from flask import jsonify, request, send_from_directory, render_template
from flask.ext.cors import cross_origin
import calls
import db
from db import store_event, get_next_callee, callees
from app import app
from app import SECRET


def create_key(index):
    """Hash a secret to create a key signature for an index"""
    s = hashlib.sha1()
    s.update('{}:{}'.format(SECRET, index))
    return s.hexdigest()


def check_key(index, key):
    return create_key(index) == key


def insert_record(parameters):
    column_name = parameters[0]
    callee_id = parameters[1]
    value = parameters[2]
    callees.write_cell(column_name=column_name, row=callee_id, value=value)


def timeblock(inner_fn):
    @wraps(inner_fn)
    def outer_fn(*args, **kwargs):
        utc_offset_hours = int(app.config['TIMEZONE_UTC_OFFSET'])
        utc_offset = timedelta(seconds=60 * 60 * utc_offset_hours)
        hour = (datetime.utcnow() + utc_offset).time().hour
        call_time_start = int(app.config['CALL_TIME_START'])
        call_time_end = int(app.config['CALL_TIME_END'])
        if hour < call_time_end and hour >= call_time_start:
            return inner_fn(*args, **kwargs)
        try:
            request_data = request.get_json()
        except:
            request_data = {}
        event_data = {
            'path': request.path,
            'endpoint': request.endpoint,
            'request_data': request_data
        }
        store_event('after_hours', event_data)
        return jsonify(error='after_hours')

    return outer_fn


def build_callee(raw_callee):
    r = lambda x: x
    t = lambda x: x.title()
    mapping = {
        'first_name': ('firstName', t),
        'last_name': ('lastName', t),
        'residential_city': ('residentialCity', r),
    }
    return dict((k_out, l(raw_callee[k_in])) for k_in, (k_out, l) in mapping.iteritems())


def get_callee():
    index, raw_callee = get_next_callee()
    callee = build_callee(raw_callee)
    callee['id'] = index
    callee['key'] = create_key(index)
    return callee, raw_callee['phone']


@app.route('/<path:path>')
def send_js(path):
    return send_from_directory(app.config['STATIC_FOLDER'], path)


@app.route('/')
def root():
    return render_template(
        'index.html',
        CALL_SCRIPT=app.config['CALL_SCRIPT'],
        CALL_FORM_FIELDS=app.config['CALL_FORM_FIELDS'])


@app.route('/call_count')
@cross_origin()
def call_count():
    return db.count_calls()


@app.route('/leaderboard')
@cross_origin()
def leaderboard():
    return jsonify(leaderboard=db.get_leaderboard(), total_called=db.count_calls())


@app.route('/sign_in', methods=['POST'])
@timeblock
def sign_in():
    # log signin
    data = request.get_json()

    if data:
        store_event('sign_in', data)
    return 'sign_in success'
    # TODO return failure message if calling out of hours
    # add time-ban decorator to all methods


@app.route('/connect_caller', methods=['POST'])
@timeblock
def connect_caller():
    data = request.get_json()
    data['session_id'] = calls.make_call(data['phoneNumber'])
    store_event('connect_caller', data)
    return jsonify(sessionId=data['session_id'])


@app.route('/connect_callee', methods=['POST'])
@timeblock
def connect_callee():
    data = request.get_json()
    callee, phone = get_callee()
    calls.send_signal(data['sessionId'], phone)

    event_data = {'caller': data, 'callee': callee, 'phone': phone}
    store_event('connect_callee', event_data)
    return jsonify(callee)


@app.route('/save_call', methods=['POST'])
def save_call():
    raw_data = request.get_json()

    # check key
    callee_id = raw_data['callee']['id']
    callee_key = raw_data['callee']['key']
    if not check_key(callee_id, callee_key):
        return 'failed'

    # match raw data to form fields
    inserts = []
    for section, values in raw_data.items():
        if section in app.config['CALL_FORM_FIELDS']:
            for field_name, value in values.items():
                if field_name in app.config['CALL_FORM_FIELDS'][section]:
                    column_name = app.config['CALL_FORM_FIELDS'][section][field_name]['column_name']
                    inserts.append([column_name, callee_id, value])

    # insert the records in parallel into the sheet
    pool = ThreadPool(4)
    pool.map(insert_record, inserts)
    pool.close()
    pool.join()
    pool.terminate()

    store_event('save_call', {'raw_data': raw_data})
    return 'saved'
