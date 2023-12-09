# -*- coding: utf-8 -*-
"""
Support for Riello's Besmart thermostats.
Be aware the thermostat may require more then 3 minute to refresh its states.

The thermostats support the season switch however this control will be managed with a 
different control.

version: 2
tested with home-assistant >= 0.96

Configuration example:

climate:
  - platform: Besmart
    name: Besmart Thermostat
    url: http://besim-api.kagisoft.co.uk/api/v1.0/
    device_id: 1675843714
    room_id: 40499877
    room: Soggiorno
    scan_interval: 10

logging options:

logger:
  default: info
  logs:
    custom_components.climate.besim: debug
"""
import logging
from datetime import datetime, timedelta

import homeassistant.helpers.config_validation as cv
import requests
import voluptuous as vol
from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_LOW,
    PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import (
    ATTR_STATE,
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_URL,
    CONF_DEVICE_ID,
    CONF_ROOM,
    STATE_OFF,
    STATE_ON,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)

CONF_ROOM_ID = "room_id"

_LOGGER = logging.getLogger(__name__)
DEPENDENCIES = ["switch", "sensor"]
REQUIREMENTS = ["requests"]

DEFAULT_NAME = "Besmart Thermostat"
DEFAULT_TIMEOUT = 3

ATTR_MODE = "mode"
STATE_UNKNOWN = "unknown"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_URL): cv.string,
        vol.Required(CONF_DEVICE_ID): cv.string,
        vol.Required(CONF_ROOM_ID): cv.string,
        vol.Required(CONF_ROOM): cv.string,
    }
)

SUPPORT_FLAGS = (
    SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE_RANGE | SUPPORT_TARGET_TEMPERATURE
)


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the Besmart thermostats."""
    client = Besmart(config.get(CONF_URL),config.get(CONF_DEVICE_ID))
    client.rooms()  # force init
    add_devices([Thermostat(config.get(CONF_NAME), config.get(CONF_ROOM_ID), config.get(CONF_ROOM), client)])


# pylint: disable=abstract-method
# pylint: disable=too-many-instance-attributes
class Besmart(object):
    """Representation of a Besmart thermostat."""

    ROOM_MODE = "devices/{0}/rooms/{1}/mode"
    ROOM_DATA = "devices/{0}"
    ROOM_ECON_TEMP = "devices/{0}/rooms/{1}/t1"
    ROOM_FROST_TEMP = "devices/{0}/rooms/{1}/t2"
    ROOM_CONF_TEMP = "devices/{0}/rooms/{1}/t3"
    GET_SETTINGS = "getSetting.php"
    SET_SETTINGS = "setSetting.php"

    CONTENT_HDRS = { 'Content-Type' : 'application/json' }

    def __init__(self, url,deviceId):
        """Initialize the thermostat."""
        self._lastupdate = None
        self._url = url
        self._deviceId = deviceId
        self._rooms = None
        self._data = None
        self._timeout = 30
        self._s = requests.Session()

    def _fahToCent(self, temp):
        return round((temp - 32.0) / 1.8, 1)

    def _centToFah(self, temp):
        return round(32.0 + (temp * 1.8), 1)

    def rooms(self):
        try:
            _LOGGER.debug(self._url + self.ROOM_DATA.format(self._deviceId))
            resp = self._s.get(
                self._url + self.ROOM_DATA.format(self._deviceId),
                timeout=self._timeout,
            )
            if resp.ok:
                self._lastupdate = datetime.now()
                self._data = resp.json()
                self._rooms = self._data.get('rooms',{}).keys()
                _LOGGER.debug("rooms: {}".format(self._rooms))
                if len(self._rooms) == 0:
                    self._lastupdate = None
                    return None

                return self._rooms
            else:
                _LOGGER.debug("get rooms failed!")
        except Exception as ex:
            _LOGGER.warning(ex)
            self._device = None

        return None

    def roomdata(self, room):
        if self._data is not None:
            return self._data["rooms"][room]

        return None

    '''
    @todo program()
    def program(self, room):
        self.login()
        try:
            resp = self._s.get(
                self.BASE_URL + self.ROOM_PROGRAM.format(room.get("id")),
                timeout=self._timeout,
            )
            if resp.ok:
                return resp.json()
        except Exception as ex:
            _LOGGER.warning(ex)
            self._device = None
        return None
    '''

    def roomById(self, roomId):
        if self._lastupdate is None or datetime.now() - self._lastupdate > timedelta(
            seconds=120
        ):
            _LOGGER.debug("refresh rooms state")
            self.rooms()

        if self._rooms and roomId in self._rooms:
            return self.roomdata(roomId)
        return None

    def setRoomMode(self, roomId, mode):
        room = self.roomById(roomId)

        if room:
            url = self._url + self.ROOM_MODE.format(self._deviceId, roomId)
            data = str(mode)
            _LOGGER.debug("setRoomMode: {} {}".format(url,data))
          
            resp = self._s.put(url, headers=self.CONTENT_HDRS, data=data, timeout=self._timeout)
            _LOGGER.debug("setRoomMode resp: {}".format(resp))

            if resp.ok:
                msg = resp.json()
                return True

        return None

    def setRoomConfortTemp(self, roomId, new_temp):
        return self.setRoomTemp(roomId, new_temp, self.ROOM_CONF_TEMP)

    def setRoomECOTemp(self, roomId, new_temp):
        return self.setRoomTemp(roomId, new_temp, self.ROOM_ECON_TEMP)

    def setRoomFrostTemp(self, roomId, new_temp):
        return self.setRoomTemp(roomId, new_temp, self.ROOM_FROST_TEMP)

    def setRoomTemp(self, roomId, new_temp, url=None):
        ''' new_temp must be degC*10 '''
        url = url or self.ROOM_CONF_TEMP
        room = self.roomById(roomId)
        if room:
            _LOGGER.debug("room: {}".format(room))

            _LOGGER.debug(
                "setRoomTemp: {}".format(new_temp)
            )

            data = str(new_temp)

            url = self._url + url.format(self._deviceId,roomId)
            _LOGGER.debug("setRoomTemp: {} {}".format(url,data))
            resp = self._s.put(url, headers=self.CONTENT_HDRS, data=data, timeout=self._timeout)
            _LOGGER.debug("setRoomTemp resp: {}".format(resp))
            if resp.ok:
                msg = resp.json()
                return True
        else:
            _LOGGER.warning("error on get the room by name: {}".format(room_name))

        return None

    def getSettings(self, room_name):
        # @todo fix this
        room = self.roomByName(room_name)

        if self._device and room:
            data = {
                "deviceId": self._device.get("deviceId"),
                "therId": room.get("roomMark"),
            }

            resp = self._s.post(
                self.BASE_URL + self.GET_SETTINGS, data=data, timeout=self._timeout
            )
            if resp.ok:
                msg = resp.json()
                _LOGGER.debug("resp: {}".format(msg))
                if msg.get("error") == 0:
                    return msg

        return None

    def setSettings(self, room_name, season):
        # @todo fix this
        room = self.roomByName(room_name)

        if self._device and room:
            old_data = self.getSettings(room_name)
            if old_data.get("error") == 0:
                min_temp_set_point_ip, min_temp_set_point_fp = str(
                    old_data.get("minTempSetPoint", "30.0")
                ).split(".")
                max_temp_set_point_ip, max_temp_set_point_fp = str(
                    old_data.get("maxTempSetPoint", "30.0")
                ).split(".")
                temp_curver_ip, temp_curver_fp = str(
                    old_data.get("tempCurver", "0.0")
                ).split(".")
                data = {
                    "deviceId": self._device.get("deviceId"),
                    "therId": room.get("roomMark"),
                    "minTempSetPointIP": min_temp_set_point_ip,
                    "minTempSetPointFP": min_temp_set_point_fp,
                    "maxTempSetPointIP": max_temp_set_point_ip,
                    "maxTempSetPointFP": max_temp_set_point_fp,
                    "sensorInfluence": old_data.get("sensorInfluence", "0"),
                    "tempCurveIP": temp_curver_ip,
                    "tempCurveFP": temp_curver_fp,
                    "unit": old_data.get("unit", "0"),
                    "season": season,
                    "boilerIsOnline": old_data.get("boilerIsOnline", "0"),
                }

                resp = self._s.post(
                    self.BASE_URL + self.SET_SETTINGS, data=data, timeout=self._timeout
                )
                if resp.ok:
                    msg = resp.json()
                    _LOGGER.debug("resp: {}".format(msg))
                    if msg.get("error") == 0:
                        return msg
        return None


# pylint: disable=abstract-method
# pylint: disable=too-many-instance-attributes
class Thermostat(ClimateEntity):
    """Representation of a Besmart thermostat."""

    # BeSmart thModel = 5
    # BeSmart WorkMode
    AUTO = 0  # 'Auto'
    MANUAL = 1  # 'Manuale - Confort'
    ECONOMY = 2  # 'Holiday - Economy'
    PARTY = 3  # 'Party - Confort'
    IDLE = 4  # 'Spento - Antigelo'
    DHW = 5 # 'Sanitario - Domestic hot water only'

    PRESET_HA_TO_BESMART = {
        "AUTO": AUTO,
        "MANUAL": MANUAL,
        "ECO": ECONOMY,
        "PARTY": PARTY,
        "IDLE": IDLE,
        "DHW": DHW,
    }

    PRESET_BESMART_TO_HA = {
        AUTO: "AUTO",
        MANUAL: "MANUAL",
        ECONOMY: "ECO",
        PARTY: "PARTY",
        IDLE: "IDLE",
        DHW: "DHW",
    }
    PRESET_MODE_LIST = list(PRESET_HA_TO_BESMART)

    HVAC_MODE_LIST = (HVAC_MODE_COOL, HVAC_MODE_HEAT)
    HVAC_MODE_BESMART_TO_HA = {1: HVAC_MODE_HEAT, 0: HVAC_MODE_COOL}

    # BeSmart Season
    HVAC_MODE_HA_BESMART = {HVAC_MODE_HEAT: 1, HVAC_MODE_COOL: 0}

    def __init__(self, name, roomId, room, client):
        """Initialize the thermostat."""
        self._name = name
        self._roomId = roomId
        self._room_name = room
        self._cl = client
        self._current_temp = 0
        self._current_state = self.IDLE
        self._current_operation = 0
        self._current_unit = 0
        self._tempSetMark = 0
        self._heating_state = False
        self._battery = 0
        self._frostT = 0
        self._saveT = 0
        self._comfT = 0
        self._season = 1
        self.update()

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._comfT

    @property
    def target_temperature_high(self):
        return self._comfT

    @property
    def target_temperature_low(self):
        return self._saveT

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.2

    @property
    def should_poll(self):
        """Polling needed for thermostat."""
        _LOGGER.debug("Should_Poll called")
        return True

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    def convertReadingToCurrentUnits(self,temp):
        if self._current_unit==0:
            return float(temp)/10
        else:
            return self._cl._centToFah(float(temp)/10)

    def convertTemp(self,temp):
        if self._current_unit==0:
            return int(temp*10)
        else:
            return int(self._cl._fahToCent(temp)*10)

    def update(self):
        """Update the data from the thermostat."""
        _LOGGER.debug("Update called")
        data = self._cl.roomById(self._roomId)
        _LOGGER.debug(data)
        if data:
            '''
            @todo Handle program
            try:
                # from Sunday (0) to Saturday (6)
                today = datetime.today().isoweekday() % 7
                # 48 slot per day
                index = datetime.today().hour * 2 + (
                    1 if datetime.today().minute > 30 else 0
                )
                programWeek = data["programWeek"]
                # delete programWeek to have less noise on debug output
                del data["programWeek"]

                self._tempSetMark = programWeek[today][index]
            except Exception as ex:
                _LOGGER.warning(ex)
                self._tempSetMark = "2"
            '''

            try:
                #self._battery =not bool(int(data.get("bat"))) #corrected to raise battery alert in ha 1=problem status false
                #@todo BeSim doesn't get battery status yet :(
                self._battery = 0
            except ValueError:
                self._battery = 0

            self._current_unit = data.get("units",0)

            try:
                self._frostT = self.convertReadingToCurrentUnits(data.get("t1"))
            except ValueError:
                self._frostT = 5.0
            try:
                self._saveT = self.convertReadingToCurrentUnits(data.get("t2"))
            except ValueError:
                self._saveT = 16.0

            try:
                self._comfT = self.convertReadingToCurrentUnits(data.get("t3"))
            except ValueError:
                self._comfT = 20.0
            try:
                self._current_temp = self.convertReadingToCurrentUnits(data.get("temp"))
            except ValueError:
                self._current_temp = 20.0

            self._heating_state = data.get("heating", 0) == 1
            try:
                self._current_state = int(data.get("mode"))
            except ValueError:
                self._current_state = 0
            self._season = data.get("winter")
            self._current_operation = data.get("winter")
            

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_MODE: self._current_state,
            "battery_state": self._battery,
            "frost_t": self._frostT,
            "confort_t": self._comfT,
            "save_t": self._saveT,
            "season_mode": self.hvac_mode,
            "heating_state": self._heating_state,
            "units": self._current_unit
        }

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._current_unit == 0:
            return TEMP_CELSIUS
        else:
            return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def hvac_mode(self):
        """Current mode."""
        return self.HVAC_MODE_BESMART_TO_HA.get(self._season)

    @property
    def hvac_action(self):
        """Current mode."""
        if self._heating_state:
            mode = self.hvac_mode
            if mode == HVAC_MODE_HEAT:
                return CURRENT_HVAC_HEAT
            else:
                return CURRENT_HVAC_COOL
        else:
            return CURRENT_HVAC_OFF

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self.HVAC_MODE_LIST

    def set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (COOL, HEAT)."""
        mode = self.HVAC_MODE_HA_BESMART.get(hvac_mode)
        self._cl.setSettings(self._room_name, mode)
        _LOGGER.debug("Set hvac_mode hvac_mode=%s(%s)", str(hvac_mode), str(mode))

    @property
    def preset_mode(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""

        return self.PRESET_BESMART_TO_HA.get(self._current_state, "IDLE")

    @property
    def preset_modes(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""

        return self.PRESET_MODE_LIST

    def set_preset_mode(self, preset_mode):
        """Set HVAC mode (comfort, home, sleep, Party, Off)."""

        mode = self.PRESET_HA_TO_BESMART.get(preset_mode, self.AUTO)
        self._cl.setRoomMode(self._roomId, mode)
        _LOGGER.debug("Set operation mode=%s(%s)", str(preset_mode), str(mode))

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        target_temp_high = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        target_temp_low = kwargs.get(ATTR_TARGET_TEMP_LOW)

        _LOGGER.debug(
            "temperature Frost: {} Eco: {} Conf: {}".format(
                temperature, target_temp_low, target_temp_high
            )
        )

        if temperature:
            self._cl.setRoomConfortTemp(self._roomId, self.convertTemp(temperature))
            # self._cl.setRoomFrostTemp(self._roomId, self.convertTemp(temperature))
        if target_temp_high:
            self._cl.setRoomConfortTemp(self._roomId, self.convertTemp(target_temp_high))
        if target_temp_low:
            self._cl.setRoomECOTemp(self._roomId, self.convertTemp(target_temp_low))
