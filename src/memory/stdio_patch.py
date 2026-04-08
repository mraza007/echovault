"""Patched stdio server for Windows compatibility."""

import asyncio
import sys
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

import mcp.types as types


@asynccontextmanager
async def stdio_server_patch():
    """Fixed stdio server that properly handles Content-Length headers."""
    
    read_queue = asyncio.Queue()
    write_queue = asyncio.Queue()
    
    async def stdin_reader():
        """Read from stdin and parse Content-Length messages."""
        buffer = b""
        
        while True:
            try:
                # Read raw bytes from stdin buffer
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.buffer.read, 4096
                )
                if not chunk:
                    break
                    
                buffer += chunk
                
                # Parse complete messages
                while True:
                    # Look for Content-Length header
                    header_end = buffer.find(b'\r\n\r\n')
                    if header_end == -1:
                        break
                        
                    header = buffer[:header_end].decode('utf-8')
                    body_start = header_end + 4
                    
                    # Extract content length
                    content_length = 0
                    for line in header.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            content_length = int(line.split(':')[1].strip())
                            break
                    
                    # Check if we have full body
                    if len(buffer) < body_start + content_length:
                        break
                        
                    # Extract body
                    body = buffer[body_start:body_start + content_length]
                    buffer = buffer[body_start + content_length:]
                    
                    # Parse JSON
                    try:
                        message = types.JSONRPCMessage.model_validate_json(body)
                        await read_queue.put(message)
                    except Exception as exc:
                        await read_queue.put(exc)
                        
            except Exception:
                break
    
    async def stdout_writer():
        """Write to stdout with proper Content-Length headers."""
        while True:
            try:
                message = await write_queue.get()
                if message is None:
                    break
                    
                json_str = message.model_dump_json(by_alias=True, exclude_none=True)
                json_bytes = json_str.encode('utf-8')
                
                # Format with Content-Length header
                output = f'Content-Length: {len(json_bytes)}\r\n\r\n'.encode('utf-8') + json_bytes
                
                # Write to stdout
                sys.stdout.buffer.write(output)
                sys.stdout.buffer.flush()
                
            except Exception:
                break
    
    # Create stream interfaces
    class ReadStream:
        def __aiter__(self):
            return self
        async def __anext__(self):
            item = await read_queue.get()
            if isinstance(item, Exception):
                raise item
            return item
    
    class WriteStream:
        async def send(self, message):
            await write_queue.put(message)
    
    # Start reader/writer tasks
    reader_task = asyncio.create_task(stdin_reader())
    writer_task = asyncio.create_task(stdout_writer())
    
    try:
        yield ReadStream(), WriteStream()
    finally:
        reader_task.cancel()
        writer_task.cancel()
        try:
            await reader_task
        except asyncio.CancelledError:
            pass
        try:
            await writer_task
        except asyncio.CancelledError:
            pass
