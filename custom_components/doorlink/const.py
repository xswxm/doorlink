from homeassistant.const import Platform
from typing import Final

DOMAIN: Final = "doorlink"

MANUFACTURER: Final = "doorlink"
SW_VERSION: Final = "4.0.0"

DEVICE_ID: Final = "device_id"

SENSOR_LATEST_EVENT: Final = 'latest_event'
SENSOR_RING_STATUS: Final = 'ring_status'

# Configuration
CONF_SIP_INFO = "sip"
CONF_FAMILY: Final = 'family'
CONF_ELEV_ID: Final = "elev"
CONF_STREAM: Final = "stream"
CONF_RTSP_URL: Final = "rtsp_url"
CONF_SERVER_ADDREDD: Final = "server_address"
CONF_STATIONS: Final = 'stations'

PORT_CONFIG: Final = 8080
PORT_STREAM: Final = 8554

STREAM_TYPE_MJPEG = "mjpeg"
STREAM_TYPE_RTSP = "rtsp"

MONITOR: Final = 'monitor'
STATION: Final = 'station'
STATIONS: Final = 'stations'

PLATFORMS: Final = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]
