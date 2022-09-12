import json
import time
from flask import Flask, request, render_template, Response, stream_with_context
from influxdb_client import InfluxDBClient
from os import environ
from datetime import datetime, timedelta


app = Flask(__name__)

client = InfluxDBClient(
    url=environ.get('IFX_URL'),
    token=environ.get('IFX_TOKEN'),
    org=environ.get('IFX_ORG')
)


query_api = client.query_api()


@app.route("/")
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
    
    print('qp', query_param)

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

    response = Response(stream_with_context(generate_random_data()), mimetype="text/event-stream")
    return response



@app.route("/notif", methods=['POST'])
def notif():
    print("===================================")
    print(request.data.decode("UTF-8"))
    return {'result': 'OK'}, 200



if __name__ == "__main__":
    app.run(host='0.0.0.0', port=6784, debug=True, threaded=True)
