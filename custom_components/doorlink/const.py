"""Constants for the doorlink integration."""

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "doorlink"

MANUFACTURER: Final = "doorlink"
SW_VERSION: Final = "5.0.1"

# Configuration
CONF_SOC_TEMP: Final = "soc_temp"
CONF_SIP_INFO: Final = "sip"
CONF_FAMILY: Final = "family"
CONF_STREAM: Final = "stream"
CONF_PLAYBACK: Final = "playback"
CONF_RTSP_URL: Final = "rtsp_url"
CONF_SERVER_ADDRESS: Final = "server_address"
CONF_STATIONS: Final = "stations"
CONF_FILEPATH: Final = "filepath"

# Service argument names
ATTR_SIP_INFO: Final = "sip_info"
ATTR_JSON_DATA: Final = "json_data"
ATTR_FLOOR: Final = "floor"
ATTR_DIRECT: Final = "direct"

PORT_CONFIG: Final = 8080
PORT_STREAM: Final = 8554

STREAM_TYPE_MJPEG: Final = "mjpeg"
STREAM_TYPE_H264: Final = "h264"

# Elevator direction
DIRECT_UP: Final = 1
DIRECT_DOWN: Final = 2

EVENT_RING: Final = "ring"
EVENT_SOC_TEMP: Final = "soc_temp"
EVENT_UNLOCK: Final = "unlock"
EVENT_APPOINT: Final = "appoint"
EVENT_PERMIT: Final = "permit"
EVENT_BYE: Final = "bye"
EVENT_RELOAD: Final = "reload"

LATEST_EVENT: Final = "latest_event"
RING_STATUS: Final = "ring_status"
SOC_TEMP: Final = "soc_temp"
KEEPALIVE_INTERVAL: Final = 180

# HTTP timeout for requests made to the doorlink server
REQUEST_TIMEOUT: Final = 10

# Playback video polling (3s x 60 = 180s)
PLAYBACK_POLL_INTERVAL: Final = 3
PLAYBACK_POLL_ATTEMPTS: Final = 60

# How long the ring binary sensor stays on after a call
RING_RESET_DELAY: Final = 1

# How long the lock stays unlocked before it reports locked again
LOCK_AUTO_RELOCK_DELAY: Final = 2

PLATFORMS: Final = [
    Platform.LOCK,
    Platform.BUTTON,
    Platform.CAMERA,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]
