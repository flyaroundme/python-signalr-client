#!/usr/bin/python
# -*- coding: utf-8 -*-

# signalr_aio/transports/_transport.py
# Stanislav Lazarov

from ._exceptions import ConnectionClosed
from ._parameters import WebSocketParameters
from ._queue_events import InvokeEvent, CloseEvent

try:
    from ujson import dumps, loads
except:
    from json import dumps, loads
import websockets
import asyncio
import ssl
import logging

import aiohttp

try:
    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ModuleNotFoundError:
    pass

logger = logging.getLogger(__name__)

class Transport:
    def __init__(self, connection):
        self._connection = connection
        self._ws_params = None
        self.ws_loop = None
        self.invoke_queue = None
        self.futures = []
        self.ws = None
        self._set_loop()

    def _set_loop(self):
        try:
            self.ws_loop = asyncio.get_event_loop()
        except RuntimeError:
            self.ws_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.ws_loop)
        self.invoke_queue = asyncio.Queue(loop=self.ws_loop)

    def start(self):
        self._ws_params = WebSocketParameters(self._connection)
        if not self.ws_loop.is_running():
                self.ws_loop.run_until_complete(self.socket(self.ws_loop))
        else:
            self.futures.append(asyncio.ensure_future(self.socket(self.ws_loop), loop=self.ws_loop))
    
    async def start_async(self):
        self._ws_params = WebSocketParameters(self._connection)
        await self.socket(self.ws_loop)


    def send(self, message):
        asyncio.Task(self.invoke_queue.put(InvokeEvent(message)), loop=self.ws_loop)

    def close(self):
        asyncio.Task(self.invoke_queue.put(CloseEvent()), loop=self.ws_loop)

    async def socket(self, loop):
        ws_connect_kwargs = dict(
            uri=self._ws_params.socket_url, extra_headers=self._ws_params.headers, loop=loop
        )
        if not self._ws_params.verify_ssl:
            
            ssl_context = ssl.SSLContext()
            ssl_context.check_hostname = False
            ws_connect_kwargs.update(ssl=ssl_context)

        async with websockets.connect(**ws_connect_kwargs) as self.ws:
            
            self._connection.started = True
            logger.info("WS connection started")
            async with aiohttp.ClientSession(
                headers=self._ws_params.headers,
                connector=aiohttp.TCPConnector(verify_ssl=False)
            ) as session:
                result = await session.get(
                    url=self._ws_params.get_start_url(),
                )
                print(f"start result: {result}")
            await self.handler(self.ws)

    async def handler(self, ws):
        consumer_task = asyncio.ensure_future(self.consumer_handler(ws), loop=self.ws_loop)
        producer_task = asyncio.ensure_future(self.producer_handler(ws), loop=self.ws_loop)
        self.futures.append(consumer_task)
        self.futures.append(producer_task)

        done, pending = await asyncio.gather(consumer_task, producer_task,
                                             loop=self.ws_loop, return_exceptions=False)

        for task in pending:
            task.cancel()

    async def consumer_handler(self, ws):
        while True:
            message = await ws.recv()
            if len(message) > 0:
                data = loads(message)
                logger.debug(f"WS received: {data}")
                await self._connection.received.fire(**data)

    async def producer_handler(self, ws):
        while True:
            try:
                event = await self.invoke_queue.get()
                if event is not None:
                    if event.type == 'INVOKE':
                        data_to_send = dumps(event.message)
                        logger.debug(f"WS sent: {data_to_send}")
                        await ws.send(dumps(event.message))
                    elif event.type == 'CLOSE':
                        await ws.close()
                        while ws.open is True:
                            asyncio.sleep(0.1)
                        else:
                            self._connection.started = False
                            break
                else:
                    break
                self.invoke_queue.task_done()
            except Exception as e:
                raise e
