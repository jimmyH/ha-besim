### Changes v0.3
 - Now supports multiple Thermostats
 - Previously if you set the thermostat temperature it only changed Comfort/T3 setpoint.
   Now it will try to work out if the thermostat is using T1/T2/T3 and set the correct setpoint.
   This may not always work as expected..
 - Note that if a thermostat card controls the low/high temperature settings:
   - target_temp_low always controls T2/Eco
   - target_temp_high always controls T3/Comfort 

** Your configuration MUST be updated  - see example below with 2 rooms/thermostats **
```yaml
climate:
  - platform: besmart
    url: http://<your BeSim server>/api/v1.0/
    device_id: <your device id>
    rooms:
      - name: Landing
        room_id: <room id>
      - name: Kitchen
        room_id: <room id>
    scan_interval: 10
```

### Changes v0.2
 - fix bug where T1 and T2 temperatures were mixed up
 - reduce delay fetching updates from BeSim server
 - Use roomId as HA unique_id which allows you to modify entity settings in GUI

