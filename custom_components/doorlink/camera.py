from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import Template
import yarl

from .const import (
    DOMAIN, 
    MANUFACTURER, 
    SW_VERSION, 

    DEVICE_ID, 
    STATIONS, 
)

import logging
_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    sensors = []
    for key, val in hass.data[DOMAIN][STATIONS].contacts.items():
        if val.rtsp_url:
            sensors.append(RTSPCamera(hass=hass, device_id=hass.data[DOMAIN][DEVICE_ID], name=f'{hass.data[DOMAIN][DEVICE_ID]}_{val.ip}', stream_source=val.rtsp_url, rtsp_username=val.rtsp_username, rtsp_password=val.rtsp_passwod))
    async_add_entities(sensors)

class RTSPCamera(Camera):
    def __init__(self, hass, device_id, name, stream_source, rtsp_username, rtsp_password):
        super().__init__()
        self._hass = hass
        self._name = name
        self._device_id = device_id
        self._attr_current_option = None
        self._stream_source = Template(stream_source, self._hass)
        self._attr_frame_interval = 1 / 15
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._rtsp_username = rtsp_username
        self._rtsp_password = rtsp_password

    @property
    def use_stream_for_stills(self) -> bool:
        """Whether or not to use stream to generate stills."""
        return True

    @property
    def unique_id(self):
        return f"{DOMAIN}_{self._device_id}_{self._name}"

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_id,
            "manufacturer": MANUFACTURER,
            "sw_version": SW_VERSION
        }

    @property
    def use_stream_for_stills(self):
        """Whether or not to use stream to generate stills."""
        return True

    async def async_camera_image(self, width=None, height=None):
        """Return a still image from the camera."""
        return None

    @property
    def name(self) -> str:
        """Return the name of this device."""
        return self._name

    @property
    def is_streaming(self):
        """Return true if the camera is streaming."""
        return True

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        try:
            stream_url = self._stream_source.async_render(parse_result=False)
            url = yarl.URL(stream_url)
            url = url.with_user(self._rtsp_username).with_password(self._rtsp_password)
            return str(url)
        except TemplateError as err:
            _LOGGER.error("Error parsing template %s: %s", self._stream_source, err)
            return None