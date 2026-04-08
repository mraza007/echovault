"""Minimal stdio test for MCP."""

import sys
import os
import json

os.environ['MEMORY_HOME'] = r'C:\Git\.memory'
sys.path.insert(0, r'c:\Git\MCP\echovault\src')

from memory.core import MemoryService
from memory.mcp_server import _create_server
from mcp.types import ListToolsRequest
import asyncio

async def main():
    # Create server
    service = MemoryService()
    server = _create_server(service)
    
    # Read from stdin
    buffer = b""
    while True:
        chunk = sys.stdin.buffer.read(1024)
        if not chunk:
            break
        buffer += chunk
        
        # Parse message
        header_end = buffer.find(b'\r\n\r\n')
        if header_end == -1:
            continue
            
        header = buffer[:header_end].decode('utf-8')
        body_start = header_end + 4
        
        content_length = 0
        for line in header.split('\r\n'):
            if line.lower().startswith('content-length:'):
                content_length = int(line.split(':')[1].strip())
                break
        
        if len(buffer) < body_start + content_length:
            continue
            
        body = buffer[body_start:body_start + content_length]
        buffer = buffer[body_start + content_length:]
        
        msg = json.loads(body.decode('utf-8'))
        
        # Handle tools/list
        if msg.get('method') == 'tools/list':
            handler = server.request_handlers[ListToolsRequest]
            result = await handler(msg.get('params', {}))
            
            tools_data = []
            for tool in result.root.tools:
                tools_data.append({
                    'name': tool.name,
                    'description': tool.description,
                    'inputSchema': tool.inputSchema
                })
            
            response = {
                'jsonrpc': '2.0',
                'id': msg['id'],
                'result': {'tools': tools_data}
            }
            
            resp_json = json.dumps(response)
            output = f'Content-Length: {len(resp_json)}\r\n\r\n{resp_json}'
            sys.stdout.write(output)
            sys.stdout.flush()

asyncio.run(main())
