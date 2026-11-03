"""Cameras for the doorlink integration."""

from __future__ import annotations

import logging

import yarl

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.helpers.device_registry import DeviceInfo

from .const import (
    DOMAIN,
    MANUFACTURER,
    STREAM_TYPE_H264,
    STREAM_TYPE_MJPEG,
    SW_VERSION,
)

_LOGGER = logging.getLogger(__name__)

try:  # the MJPEG proxy camera still lives in the mjpeg integration
    from homeassistant.components.mjpeg.camera import MjpegCamera
except ImportError:  # pragma: no cover - only if the mjpeg integration is gone
    MjpegCamera = None  # type: ignore[assignment,misc]
    _LOGGER.warning(
        "homeassistant.components.mjpeg is not available, "
        "MJPEG doorlink cameras will not be created"
    )


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up the doorlink cameras."""
    client = hass.data[DOMAIN][entry.entry_id]
    monitor = client.monitor
    entities: list[Camera] = []

    if monitor.mjpeg_url is not None and MjpegCamera is not None:
        entities.append(
            MjpegStream(
                device_id=monitor.device_id,
                mjpeg_url=monitor.mjpeg_url,
                snapshot_url=monitor.snapshot_url,
                translation_key="stream",
            )
        )
    elif monitor.rtsp_url is not None:
        entities.append(
            RTSPStream(
                device_id=monitor.device_id,
                stream_source=monitor.rtsp_url,
                username=None,
                password=None,
                translation_key="stream",
            )
        )

    if monitor.playback_url is not None:
        if monitor.stream_type == STREAM_TYPE_MJPEG and MjpegCamera is not None:
            entities.append(
                MjpegStream(
                    device_id=monitor.device_id,
                    mjpeg_url=monitor.playback_url,
                    snapshot_url=monitor.snapshot_url,
                    translation_key="playback",
                )
            )
        elif monitor.stream_type == STREAM_TYPE_H264:
            entities.append(
                H264Stream(
                    device_id=monitor.device_id,
                    playback_url=monitor.playback_url,
                    translation_key="playback",
                )
            )

    for contact in client.stations.contacts.values():
        if contact.rtsp_url:
            entities.append(
                RTSPStream(
                    device_id=contact.device_id,
                    stream_source=contact.rtsp_url,
                    username=contact.rtsp_username,
                    password=contact.rtsp_password,
                    translation_key="stream",
                )
            )

    async_add_entities(entities)


class RTSPStream(Camera):
    """A camera that hands its RTSP url to the stream component."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_frame_interval = 1 / 15

    def __init__(self, device_id, stream_source, username, password, translation_key):
        """Initialize the camera."""
        super().__init__()
        self._device_id = device_id
        self._stream_source = stream_source
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._rtsp_username = username
        self._rtsp_password = password
        self._translation_key = translation_key

    @property
    def use_stream_for_stills(self) -> bool:
        """Use the stream component to grab still images."""
        return True

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_id,
            manufacturer=MANUFACTURER,
            sw_version=SW_VERSION,
        )

    @property
    def translation_key(self) -> str:
        """Return the translation key."""
        return self._translation_key

    async def stream_source(self) -> str | None:
        """Return the RTSP url including the credentials."""
        if not self._stream_source:
            return None
        url = yarl.URL(self._stream_source)
        if self._rtsp_username:
            url = url.with_user(self._rtsp_username)
        if self._rtsp_password:
            url = url.with_password(self._rtsp_password)
        return str(url)


if MjpegCamera is not None:

    class MjpegStream(MjpegCamera):
        """MJPEG camera proxied through Home Assistant."""

        _attr_has_entity_name = True
        _attr_should_poll = False

        def __init__(self, device_id, mjpeg_url, snapshot_url, translation_key):
            """Initialize the camera."""
            super().__init__(mjpeg_url=mjpeg_url, still_image_url=snapshot_url)
            self._device_id = device_id
            self._translation_key = translation_key

        @property
        def device_info(self) -> DeviceInfo:
            """Return the device info."""
            return DeviceInfo(
                identifiers={(DOMAIN, self._device_id)},
                name=self._device_id,
                manufacturer=MANUFACTURER,
                sw_version=SW_VERSION,
            )

        @property
        def unique_id(self) -> str:
            """Return the unique id."""
            return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

        @property
        def translation_key(self) -> str:
            """Return the translation key."""
            return self._translation_key


class H264Stream(Camera):
    """Playback camera of a H264 doorlink server."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_frame_interval = 1 / 15

    def __init__(self, device_id, playback_url, translation_key):
        """Initialize the camera."""
        super().__init__()
        self._device_id = device_id
        self._stream_url = playback_url
        self._attr_supported_features = CameraEntityFeature.STREAM
        self._translation_key = translation_key

    @property
    def use_stream_for_stills(self) -> bool:
        """Use the stream component to grab still images."""
        return True

    @property
    def unique_id(self) -> str:
        """Return the unique id."""
        return f"{DOMAIN}_{self._device_id}_{self._translation_key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._device_id,
            manufacturer=MANUFACTURER,
            sw_version=SW_VERSION,
        )

    @property
    def translation_key(self) -> str:
        """Return the translation key."""
        return self._translation_key

    async def stream_source(self) -> str | None:
        """Return the playback stream url."""
        return f"ffmpeg:{self._stream_url}#video=h264#raw"
