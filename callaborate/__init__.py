import os

if 'APP_SETTINGS' in os.environ and os.path.isfile(os.environ['APP_SETTINGS']):
    from app import app
    from views import *
else:
    from init_error import *


def main():
    app.run(threaded=True, host=app.config['BIND_HOST'], port=app.config['BIND_PORT'])


if __name__ == "__main__":
    main()
