from homeassistant.const import Platform
from typing import Final

DOMAIN: Final = "doorlink"

MANUFACTURER: Final = "doorlink"
SW_VERSION: Final = "4.1.0"

DEVICE_ID: Final = "device_id"

# Configuration
CONF_SIP_INFO = "sip"
CONF_FAMILY: Final = 'family'
CONF_ELEV_ID: Final = "elev"
CONF_STREAM: Final = "stream"
CONF_PLAYBACK: Final = "playback"
CONF_RTSP_URL: Final = "rtsp_url"
CONF_SERVER_ADDRESS: Final = "server_address"
CONF_STATIONS: Final = 'stations'
CONF_FILEPATH: Final = 'filepath'

PORT_CONFIG: Final = 8080
PORT_STREAM: Final = 8554

STREAM_TYPE_MJPEG = "mjpeg"
STREAM_TYPE_RTSP = "rtsp"

LATEST_EVENT: Final = 'latest_event'
RING_STATUS: Final = 'ring_status'
KEEPALIVE_INTERVAL: Final = 180

PLATFORMS: Final = [
    Platform.LOCK,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]
