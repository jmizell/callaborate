FROM python:2.7

COPY data /app/config/data
COPY static /app/config/static
COPY templates /app/config/templates
COPY app_settings.py /app/config/app_settings.py
COPY setup.py /app/setup.py
COPY callaborate /app/callaborate/

RUN cd /app && \
    python setup.py install

ENV APP_SETTINGS /app/config/app_settings.py

CMD /bin/bash