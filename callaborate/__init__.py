import os
from app import app
from views import *


def main():
    app.run(threaded=True, host=app.config['BIND_HOST'], port=app.config['BIND_PORT'])


if __name__ == "__main__":
    main()
