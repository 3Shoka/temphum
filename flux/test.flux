from(bucket: "tasmota")
    |> range(start: -20m)
    |> filter(fn: (r) => r["_measurement"]=="temperature" or r["_measurement"] == "humidity")
    |> filter(fn: (r) => r["_field"] == "value")
    |> filter(fn: (r) => r["sensor"] == "am2301")
    |> aggregateWindow(every: 5m, fn: mean, createEmpty: false)
    |> keep(columns: ["_start","_stop","_time", "_value", "_measurement"])
    
    
    