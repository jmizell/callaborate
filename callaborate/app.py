import logging
from flask import Flask

app = Flask(__name__, static_url_path='')
app.config.from_envvar('APP_SETTINGS')
app.template_folder = app.config['TEMPLATE_FOLDER']
app.static_folder = app.config['STATIC_FOLDER']
app.logger.addHandler(logging.StreamHandler())
app.logger.setLevel(logging.INFO)
SECRET = app.config['SECRET_KEY']
