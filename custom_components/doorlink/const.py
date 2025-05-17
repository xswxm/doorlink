from homeassistant.const import Platform
from typing import Final
# from enum import StrEnum

# DEVICE_MODEL: Final = "Indoor Monitor"
DOMAIN: Final = "doorlink"

MANUFACTURER: Final = "doorlink"
SW_VERSION: Final = "1.0.0"

DEVICE_ID: Final = "device_id"

SENSOR_LAST_EVENT: Final = 'last_event'
SENSOR_RING_STATUS: Final = 'ring_status'

# Configuration
CONF_SIP_INFO = "sip_info"
CONF_FAMILY: Final = 'family'
CONF_ELEV_ID: Final = "elev_id"

DEFAULT_PORT: Final = 5060
DEFAULT_FAMILY: Final = 1
DEFAULT_ELEV_ID: Final = 0

CONF_OPENWRT_ADDREDD: Final = "openwrt_address"
CONF_RING_PORT: Final = 'ring_port'
DEFAULT_RING_PORT: Final = 30884

CONF_STATIONS: Final = 'stations'
CONF_LIVE_SUPPORT: Final = 'live_supprt'

# CONTACT_FILENAME: Final = '/config/doorlink/contacts.json'
from pathlib import Path
STATION_FILENAME: Final = Path(__file__).parent / 'stations.json'

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
