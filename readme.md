
# HA Riello's Besmart thermostats 

Support for Riello's Besmart thermostats.
Be aware the thermostat may require more then 3 minute to refresh its states.

The thermostats support the season switch however this control will be managed with a 
different control.

tested with home-assistant >= 0.113

Hacked version of https://github.com/muchasuerte/ha-besmart to connect to BeSim server instead of Riello's cloud servers.

Configuration example:

```yaml
climate:
  - platform: besmart
    name: Besmart Thermostat
    url: http://<your BeSim server>/api/v1.0/
    device_id: <your device id>
    room_id: <your room id>
    room: Soggiorno
    scan_interval: 10

logging options:

logger:
  default: info
  logs:
    custom_components.climate.besmart: debug
```

## Contribute

Contributions are always welcome!

## License

[![CC0](https://licensebuttons.net/p/zero/1.0/88x31.png)](https://creativecommons.org/publicdomain/zero/1.0/)
