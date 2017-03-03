import logging
from flask import render_template, make_response
from flask import Flask

app = Flask(__name__, static_url_path='')
app.logger.addHandler(logging.StreamHandler())
app.logger.setLevel(logging.INFO)
app.config['BIND_HOST'] = "0.0.0.0"
app.config['BIND_PORT'] = "5000"


@app.route('/')
def root():
    return render_template('init_error.html'), 500
