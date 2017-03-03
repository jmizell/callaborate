FROM python:2.7

COPY static /app/callaborate/static
COPY templates /app/callaborate/templates
COPY app_settings.py.example /app/callaborate/app_settings.py.example
COPY setup.py /app/callaborate/setup.py
COPY callaborate /app/callaborate/callaborate
COPY tropo_call_script.py /app/callaborate/tropo_call_script.py

RUN cd /app/callaborate && \
    python setup.py install

ENV APP_SETTINGS /app/config/app_settings.py

EXPOSE 5000

CMD /usr/local/bin/callaborate