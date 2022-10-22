import json
import time
from flask import Flask, request, render_template, Response, stream_with_context
from influxdb_client import InfluxDBClient
from os import environ
from datetime import datetime, timedelta
from influxdb_client.service.checks_service import ChecksService
from influxdb_client.service.notification_rules_service import NotificationRulesService
from influxdb_client.service.notification_endpoints_service import NotificationEndpointsService


app = Flask(__name__)

with open('config.json') as f:
    config = json.load(f)

app.config.update(config)


client = InfluxDBClient(url=app.config["IFX_URL"],token=app.config["IFX_TOKEN"],org=app.config["IFX_ORG"])


query_api = client.query_api()


@app.route("/")
@app.route("/index")
def index():
    return render_template('index.html')


@app.route("/data")
def data():
    nganu = request.values

    query_param = {
        "_start": int(nganu['start']),
        "_stop": int(nganu['stop']),
        "_every": timedelta(minutes=int(nganu['every']))
    }

    query = query_api.query('''
        from(bucket: "tasmota")
            |> range(start: _start, stop: _stop)
            |> filter(fn: (r) => r["_measurement"] == "temperature" or r["_measurement"] == "humidity")
            |> filter(fn: (r) => r["_field"] == "value")
            |> filter(fn: (r) => r["sensor"] == "am2301")
            |> aggregateWindow(every: _every, fn: mean, createEmpty: false)
            |> keep(columns: ["table", "_time", "_value", "_measurement"])
        ''', params=query_param)

    return query.to_json()


@app.route("/last2mintemp")
def last2mintemp():
    def generate_random_data():
        while True:
            tables = query_api.query("""
            from(bucket: "tasmota")
                |> range(start: -2m)
                |> filter(fn: (r) => r["_measurement"] == "temperature" or r["_measurement"] == "humidity")
                |> filter(fn: (r) => r["_field"] == "value")
                |> filter(fn: (r) => r["device"] == "tasmota_4E3B70")
                |> filter(fn: (r) => r["sensor"] == "am2301")
                |> aggregateWindow(every: 2m, fn: last, createEmpty: false)
                |> yield(name: "last")
            """)
            data = tables.to_json(indent=None)
            yield f"data:{data}\n\n"
            time.sleep(120)

    response = Response(stream_with_context(
        generate_random_data()), mimetype="text/event-stream")
    return response


@app.route("/notif", methods=['POST'])
def notif():
    import requests
    SEND_URL = f'https://api.telegram.org/bot{app.config["TELE_TOKEN"]}/sendMessage'

    print("===================================")
    data = json.loads(request.data.decode("UTF-8"))
    print(data)
    # text = f"{data['_message']} {data['device']} {data['sensor']} {data['value']}"
    requests.post(SEND_URL, json={'chat_id': app.config["TELE_CHAT_PRIVATE"], 'text': data })
    return {'result': 'OK'}, 200


@app.route("/check")
def check():
    """
    Find Organization ID by Organization API.
    """
    org = client.organizations_api().find_organizations(org=app.config["IFX_ORG"])[0]


    checks_service = ChecksService(api_client=client.api_client)
    notification_endpoint_service = NotificationEndpointsService(api_client=client.api_client)
    notification_rules_service = NotificationRulesService(api_client=client.api_client)

    """
    List all Checks
    """
    print(f"\n------- Checks: -------\n")
    checks = checks_service.get_checks(org_id=org.id).checks
    print("\n".join([f" ---\n ID: {it.id}\n Name: {it.name}\n Type: {type(it)}\n Detail: {it.to_dict()}" for it in checks]))
    print("---")

    """
    List all Endpoints
    """
    print(f"\n------- Notification Endpoints: -------\n")
    notification_endpoints = notification_endpoint_service.get_notification_endpoints(org_id=org.id).notification_endpoints
    print("\n".join([f" ---\n ID: {it.id}\n Name: {it.name}\n Type: {type(it)}\n Detail: {it.to_dict()}" for it in notification_endpoints]))
    print("---")

    """
    List all Notification Rules
    """
    print(f"\n------- Notification Rules: -------\n")
    notification_rules = notification_rules_service.get_notification_rules(org_id=org.id).notification_rules
    print("\n".join([f" ---\n ID: {it.id}\n Name: {it.name}\n Type: {type(it)}\n Detail: {it.to_dict()}" for it in notification_rules]))
    return render_template('check.html', checks=checks, endpoints=notification_endpoints, notif_rules=notification_rules)



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=6784, debug=True, threaded=True)
