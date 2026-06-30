from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.components.mjpeg.camera import MjpegCamera
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.template import Template
import yarl

from .const import (
    DOMAIN, 
    MANUFACTURER, 
    SW_VERSION, 

    STREAM_TYPE_MJPEG,
    STREAM_TYPE_H264,
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    entities = []
    client = hass.data[DOMAIN][entry.entry_id]
    monitor = client.monitor
    if monitor.mjpeg_url != None:
        entities.append(
            MjpegStream(
                entry=entry,
                device_id=monitor.device_id,
                mjpeg_url=monitor.mjpeg_url,
                snapshot_url=monitor.snapshot_url,
                translation_key = 'stream'
            )
        )
    elif monitor.rtsp_url != None:
        entities.append(
            RTSPStream(
                hass=hass,
                device_id=monitor.device_id, 
                stream_source=monitor.rtsp_url, 
                username=None, 
                password=None,
                translation_key = 'stream'
            )
        )

    if monitor.playback_url != None:
        if monitor.stream_type == STREAM_TYPE_MJPEG:
            entities.append(
                MjpegStream(
                    entry=entry,
                    device_id=monitor.device_id,
                    mjpeg_url=monitor.playback_url,
                    snapshot_url=monitor.snapshot_url,
                    translation_key = 'playback'
                )
            )
        elif monitor.stream_type == STREAM_TYPE_H264:
            entities.append(
                H264Stream(
                    hass=hass,
                    device_id=monitor.device_id, 
                    playback_url=monitor.playback_url,
                    translation_key = 'playback'
                )
            )

    for key, val in client.stations.contacts.items():
        if val.rtsp_url:
            entities.append(
                RTSPStream(
                    hass=hass, 
                    device_id=val.device_id, 
                    stream_source=val.rtsp_url, 
                    username=val.rtsp_username, 
                    password=val.rtsp_password,
                    translation_key = 'stream'
                )
            )

    async_add_entities(entities)

class RTSPStream(Camera):
    def __init__(self, hass, device_id, stream_source, username, password, translation_key):
        super().__init__()
        self._hass = hass
        self._device_id = device_id
        self._attr_current_option = None
        self._stream_source = Template(stream_source, self._hass)
        self._attr_frame_interval = 1 / 15
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._rtsp_username = username
        self._rtsp_password = password
        self._translation_key = translation_key

    @property
    def use_stream_for_stills(self) -> bool:
        return True

    @property
    def has_entity_name(self) -> bool:
        return True

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "sw_version": SW_VERSION
        }

    @property
    def translation_key(self) -> str:
        return self._translation_key

    async def async_camera_image(self, width=None, height=None):
        return None

    @property
    def is_streaming(self):
        return False

    async def stream_source(self) -> str | None:
        try:
            stream_url = self._stream_source.async_render(parse_result=False)
            url = yarl.URL(stream_url)
            url = url.with_user(self._rtsp_username).with_password(self._rtsp_password)
            return str(url)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._stream_source, err)
            return None

    async def async_camera_image(self, width=None, height=None) -> bytes | None:
        return None

class MjpegStream(MjpegCamera):
    def __init__(self, entry, device_id,  mjpeg_url,  snapshot_url, translation_key):
        super().__init__(
            mjpeg_url=mjpeg_url,
            still_image_url=snapshot_url,
        )
        _LOGGER.info(self._attr_name)
        self._entry = entry
        self._device_id = device_id
        self._attr_should_poll = False
        self._translation_key = translation_key
        # self._attr_name = None

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "sw_version": SW_VERSION
        }

    @property
    def has_entity_name(self) -> bool:
        return True

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

    @property
    def translation_key(self) -> str:
        return self._translation_key

class H264Stream(Camera):
    def __init__(self, hass, device_id, playback_url, translation_key):
        super().__init__()
        self._hass = hass
        self._device_id = device_id
        self._attr_current_option = None
        self._stream_url = playback_url
        self._attr_frame_interval = 1 / 15
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._translation_key = translation_key
        # self._attr_has_entity_name = False
        # self._attr_name = None

    @property
    def use_stream_for_stills(self) -> bool:
        return True

    @property
    def has_entity_name(self) -> bool:
        return True

    @property
    def unique_id(self) -> str:
        return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "sw_version": SW_VERSION
        }

    @property
    def translation_key(self) -> str:
        return self._translation_key

    @property
    def is_streaming(self) -> bool:
        return False

    def available(self) -> bool:
        return True

    async def stream_source(self) -> str | None:
        return f"ffmpeg:{self._stream_url}#video=h264#raw"

    async def async_camera_image(self, width=None, height=None):
        return b""
