"""Fixed MCP server wrapper for Windows stdio compatibility."""

import asyncio
import sys
import os

# Set MEMORY_HOME before any imports
os.environ['MEMORY_HOME'] = r'C:\Git\.memory'

# Add src to path
sys.path.insert(0, r'c:\Git\MCP\echovault\src')

from memory.core import MemoryService
from memory.mcp_server import _create_server
from mcp.types import ListToolsRequest, CallToolRequest

async def main():
    service = MemoryService()
    server = _create_server(service)
    
    # Read from stdin line by line
    while True:
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
            if not line:
                break
                
            # Parse Content-Length header
            if line.startswith('Content-Length:'):
                length = int(line.split(':')[1].strip())
                # Read empty line
                empty = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
                # Read body
                body = await asyncio.get_event_loop().run_in_executor(None, lambda: sys.stdin.read(length))
                
                import json
                msg = json.loads(body)
                method = msg.get('method')
                msg_id = msg.get('id')
                
                # Handle initialize
                if method == 'initialize':
                    response = {
                        'jsonrpc': '2.0',
                        'id': msg_id,
                        'result': {
                            'protocolVersion': '2024-11-05',
                            'capabilities': {},
                            'serverInfo': {'name': 'echovault', 'version': '1.0'}
                        }
                    }
                    resp_str = json.dumps(response)
                    print(f'Content-Length: {len(resp_str)}\r\n\r\n{resp_str}', flush=True)
                
                # Handle tools/list
                elif method == 'tools/list':
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
                        'id': msg_id,
                        'result': {'tools': tools_data}
                    }
                    resp_str = json.dumps(response)
                    print(f'Content-Length: {len(resp_str)}\r\n\r\n{resp_str}', flush=True)
                
                # Handle tools/call
                elif method == 'tools/call':
                    handler = server.request_handlers[CallToolRequest]
                    result = await handler(msg.get('params', {}))
                    
                    response = {
                        'jsonrpc': '2.0',
                        'id': msg_id,
                        'result': result
                    }
                    resp_str = json.dumps(response)
                    print(f'Content-Length: {len(resp_str)}\r\n\r\n{resp_str}', flush=True)
                    
        except Exception as e:
            import traceback
            print(f'Error: {e}', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)

if __name__ == '__main__':
    asyncio.run(main())
