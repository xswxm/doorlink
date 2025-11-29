from homeassistant.const import Platform
from typing import Final

DOMAIN: Final = "doorlink"

MANUFACTURER: Final = "doorlink"
SW_VERSION: Final = "3.0.0"

DEVICE_ID: Final = "device_id"

SENSOR_LAST_EVENT: Final = 'last_event'
SENSOR_RING_STATUS: Final = 'ring_status'

# Configuration
CONF_SIP_INFO = "sip"
CONF_FAMILY: Final = 'family'
CONF_ELEV_ID: Final = "elev"
CONF_RTSP_URL: Final = "rtsp_url"
CONF_SERVER_ADDREDD: Final = "server_address"
CONF_STATIONS: Final = 'stations'

STATIONS: Final = 'stations'
STATION_LIST: Final = 'station_list'
STATION_SELECTED: Final = 'station_selected'

PLATFORMS: Final = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]
