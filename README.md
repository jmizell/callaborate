
_Call-aborate_ lets volunteers sign in to call potential supporters. It presents callers with a script and embedded questions, then calls their phone and connects them to the next call recipient. When the call is complete, the caller records the outcome and they are connected to the next number. All detailed info is logged in Redis, and completed call results are stored in a Google Spreadsheet via a Form for easy access.


Google Service Account
-----------

TODO: document service account creation


Callee Data
-----------

Callaborate stores it's call data to a Google Drive Sheet. You'll need to give read, and write permissions to your service account, using the client_email provided to you in your service account key file.

Required fields:

`first_name`, `middle_name`, `last_name`, `residential_city`, `residential_zip5`, `phone`, `call_status`


Tropo
-----

The outbound calling uses [Tropo](https://www.tropo.com), so you'll need to create an account there.

Create a new app. We want our call script to run on Tropo's server, so for "type of application", select "Scripting API". Press "New Script" to open their in-browser editor, copy the contents of the `tropo_call_script.py` file (in this directory), and paste it into Tropo. Give it some file name and save.

Add a phone number in whichever area you want (likely the area in which you're going to be calling), then click "Create App"

Once the app is created, Tropo will redirect you to your App Details page. At the bottom of the page, you'll find your voice API key.


Testing with Tropo is free, but if you're doing any significant volume, you'll likely want to move your Tropo app into "Production" mode before starting the call campaign. Once in production, calls will cost $0.03/minute.


Config
------

TODO: document configuration file


Run 
---

A docker image is provided for easy deployment. You'll need to mount your configuration file to /app/config/app_settings.py in the container. The default application log directory is /app/config/log

If using a cloud based redis provider, you can specify the location in the Callaborate container using the REDISCLOUD_URL environment variable. Otherwise for small local deployments, we'll link the redis container to the callaborate container.

Start the redis container.

```
docker run -it --rm \
  --name callaborte-redis \
  redis
```

Start the Callaborate app container, assuming a configuration file stored at /srv/callaborate/app_settings.py

```
docker run -it --rm \
  --name callaborate \
  --link callaborte-redis:redis \
  -e REDISCLOUD_URL="redis://redis:6379/0" \
  -p 80:80 \
  -v /srv/callaborate/app_settings.py:/app/config/app_settings.py \
  -v /srv/callaborate/log:/app/config/log \
  jmizell/callaborate
```

