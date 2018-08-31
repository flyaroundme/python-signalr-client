#!/usr/bin/python
# -*- coding: utf-8 -*-

# signalr_aio/_connection.py
# Stanislav Lazarov

import asyncio
from typing import Dict, Optional

from .events import EventHook
from .hubs import Hub
from .transports import Transport


class Connection(object):
    protocol_version = '1.5'

    def __init__(self, url, session=None, adal_token=None, verify_ssl=True, qs: Optional[dict] = None):
        self.url = url
        self.__hubs: Dict[str, Hub] = {}
        self.__send_counter = -1
        self.hub: Optional[Hub] = None
        self.session = session
        self.adal_token = adal_token
        self.verify_ssl = verify_ssl
        self.received = EventHook()
        self.error = EventHook()
        self.__transport = Transport(self)
        self.started = False
        self.connection_started = asyncio.Event()
        self.qs: dict = qs or dict()

        async def handle_error(**data):
            error = data["E"] if "E" in data else None
            if error is not None:
                await self.error.fire(error)
        
        async def handle_connected(**data):
            if "C" in data:
                self.connection_started.set()

        self.received += handle_error
        self.received += handle_connected
        


    def start(self):
        self.hub = [hub_name for hub_name in self.__hubs][0]
        self.__transport.start()
    
    async def start_async(self):
        self.hub = [hub_name for hub_name in self.__hubs][0]
        await self.__transport.start_async()


    def register_hub(self, name: str) -> Hub:
        if name not in self.__hubs:
            if self.started:
                raise RuntimeError(
                    'Cannot create new hub because connection is already started.')
            self.__hubs[name] = Hub(name, self)
            return self.__hubs[name]

    def increment_send_counter(self) -> int:
        self.__send_counter += 1
        return self.__send_counter

    def send(self, message):
        self.__transport.send(message)

    def close(self):
        self.__transport.close()
