#!/usr/bin/env python3
"""Standalone MCP server for echovault - bypasses broken MCP stdio."""

import asyncio
import json
import sys
import os

# Setup paths
os.environ['MEMORY_HOME'] = r'C:\Git\.memory'
sys.path.insert(0, r'c:\Git\MCP\echovault\src')

from memory.core import MemoryService
from memory.mcp_server import _create_server
from mcp.types import ListToolsRequest, CallToolRequest


class MCPServer:
    def __init__(self):
        self.service = MemoryService()
        self.server = _create_server(self.service)
        self.buffer = b""
    
    async def handle_message(self, msg):
        """Process single MCP message."""
        method = msg.get('method')
        msg_id = msg.get('id')
        
        # Initialize
        if method == 'initialize':
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {
                    'protocolVersion': '2024-11-05',
                    'capabilities': {},
                    'serverInfo': {'name': 'echovault', 'version': '1.27.0'}
                }
            }
        
        # Tools list
        elif method == 'tools/list':
            handler = self.server.request_handlers[ListToolsRequest]
            result = await handler(msg.get('params', {}))
            
            tools_data = []
            for tool in result.root.tools:
                tools_data.append({
                    'name': tool.name,
                    'description': tool.description,
                    'inputSchema': tool.inputSchema
                })
            
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': {'tools': tools_data}
            }
        
        # Tool call
        elif method == 'tools/call':
            handler = self.server.request_handlers[CallToolRequest]
            result = await handler(msg.get('params', {}))
            return {
                'jsonrpc': '2.0',
                'id': msg_id,
                'result': result
            }
        
        return None
    
    async def run(self):
        """Main server loop."""
        while True:
            try:
                # Read chunk from stdin
                chunk = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.buffer.read, 4096
                )
                if not chunk:
                    break
                
                self.buffer += chunk
                
                # Process complete messages
                while True:
                    header_end = self.buffer.find(b'\r\n\r\n')
                    if header_end == -1:
                        break
                    
                    header = self.buffer[:header_end].decode('utf-8', errors='ignore')
                    body_start = header_end + 4
                    
                    # Get content length
                    content_length = 0
                    for line in header.split('\r\n'):
                        if line.lower().startswith('content-length:'):
                            try:
                                content_length = int(line.split(':')[1].strip())
                            except:
                                pass
                            break
                    
                    # Check full message received
                    if len(self.buffer) < body_start + content_length:
                        break
                    
                    # Extract and parse body
                    body = self.buffer[body_start:body_start + content_length]
                    self.buffer = self.buffer[body_start + content_length:]
                    
                    try:
                        msg = json.loads(body.decode('utf-8'))
                        response = await self.handle_message(msg)
                        
                        if response:
                            resp_json = json.dumps(response)
                            output = f'Content-Length: {len(resp_json)}\r\n\r\n{resp_json}'
                            sys.stdout.write(output)
                            sys.stdout.flush()
                    
                    except Exception as e:
                        # Send error response
                        error = {
                            'jsonrpc': '2.0',
                            'id': msg.get('id') if isinstance(msg, dict) else None,
                            'error': {'code': -32603, 'message': str(e)}
                        }
                        err_json = json.dumps(error)
                        sys.stdout.write(f'Content-Length: {len(err_json)}\r\n\r\n{err_json}')
                        sys.stdout.flush()
            
            except Exception as e:
                print(f'Fatal error: {e}', file=sys.stderr)
                break


if __name__ == '__main__':
    server = MCPServer()
    asyncio.run(server.run())
