import aiofiles
import json
from typing import Dict
from .const import STATION_FILENAME

import logging
_LOGGER = logging.getLogger(__name__)

class SIPContact:
    def __init__(self, info, password = '') -> None:
        if ':' not in info:
            info = info + ':5060'
        self.info = info
        self.password = password
        self.name, ip_port = info.split('@')
        self.ip, self.port = ip_port.split(':')
        self.port = int(self.port)
        if self.name[-2] == '-':
            self.no = self.name[-1]
            self.id = self.name[:-2]
        else:
            self.no = None
            self.id = self.name
        self.id.replace('-', '')
        try:
            id = int(self.id)
            build_unit = id // 10000
            self.build = build_unit // 100
            self.unit = build_unit % 100
            room_floor = id % 10000
            self.room = room_floor % 100
            self.floor = room_floor // 100
        except:
            self.build = None
            self.unit = None
            self.room = None
            self.floor = None


class Stations:
    def __init__(self) -> None:
        self.contacts = {}

    def to_string(self):
        """Convert the SIP contacts to a string representation."""
        output_str = ",".join([f'"{value.info}":"{value.password}"' for key, value in self.contacts.items()])
        output_str = '{' + output_str + '}'
        _LOGGER.debug(f'Converted SIP contacts to string: {output_str}')
        return output_str

    async def load(self) -> Dict[str, SIPContact]:
        """Load JSON data from a file."""
        try:
            async with aiofiles.open(STATION_FILENAME, mode='r', encoding='utf-8') as file:
                contents = await file.read()
                _LOGGER.debug(f'Loaded data from {STATION_FILENAME}: {contents}')
                self.load_from_string(contents)
        except FileNotFoundError:
            _LOGGER.error(f'{STATION_FILENAME} not found.')
        except json.JSONDecodeError:
            _LOGGER.error(f'Failed to decode JSON from {STATION_FILENAME}.')

    def load_from_string(self, contents: str) -> None:
        data = json.loads(contents)
        for key, value in data.items():
            contact = SIPContact(key, value)
            self.contacts[contact.name] = contact

    async def save(self) -> None:
        await self.save_string(self.to_string())

    async def save_string(self, contents: str) -> None:
        async with aiofiles.open(STATION_FILENAME, mode='w', encoding='utf-8') as file:
            await file.write(self.to_string())
        
        _LOGGER.debug(f'Result saved as {STATION_FILENAME}.')

async def load_json(filename: str) -> Dict[str, SIPContact]:
    """Load JSON data from a file."""
    res = {}
    try:
        async with aiofiles.open(filename, mode='r', encoding='utf-8') as file:
            contents = await file.read()
            data = json.loads(contents)
            _LOGGER.debug(f'Loaded data from {filename}: {data}')
            for key, value in data.items():
                contact = SIPContact(key, value)
                res[contact.name] = contact
            return res
    except FileNotFoundError:
        _LOGGER.error(f'{filename} not found.')
        return res
    except json.JSONDecodeError:
        _LOGGER.error(f'Failed to decode JSON from {filename}.')
        return res

async def save_json(result: Dict[str, str], filename: str) -> None:
    if not result:
        return
    async with aiofiles.open(filename, mode='w', encoding='utf-8') as file:
        await file.write(json.dumps(result, ensure_ascii=False, indent=4))
    
    _LOGGER.debug(f'Result saved as {filename}.')
