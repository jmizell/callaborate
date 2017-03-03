import logging
from logging.handlers import RotatingFileHandler
from logging import Formatter
from flask import Flask

app = Flask(__name__, static_url_path='')
app.config.from_envvar('APP_SETTINGS')
app.template_folder = app.config['TEMPLATE_FOLDER']
app.static_folder = app.config['STATIC_FOLDER']

app.logger.addHandler(logging.StreamHandler())
app.logger.setLevel(logging.INFO)
handler = RotatingFileHandler(app.config['LOG_FILE'], maxBytes=50000000, backupCount=4)
handler.setFormatter(Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
handler.setLevel(logging.INFO)
if app.config['LOG_LEVEL'] == "DEBUG":
    handler.setLevel(logging.DEBUG)
elif app.config['LOG_LEVEL'] == "WARNING":
    handler.setLevel(logging.WARNING)
elif app.config['LOG_LEVEL'] == "CRITICAL":
    handler.setLevel(logging.CRITICAL)
logger = logging.getLogger('werkzeug')
logger.addHandler(handler)
app.logger.addHandler(handler)

SECRET = app.config['SECRET_KEY']
