import asyncio,json,time
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def payload(result):
    if result.isError: raise RuntimeError(result.content[0].text if result.content else 'MCP tool failed')
    return result.structuredContent or json.loads(result.content[0].text)


async def call(request, *, port=8765, wait=False, deadline=7300):
    async with streamablehttp_client(f'http://127.0.0.1:{port}/mcp') as (read,write,_):
        async with ClientSession(read,write) as client:
            await client.initialize()
            names={t.name for t in (await client.list_tools()).tools}
            if request.get('tool') not in names: raise ValueError('Unknown research tool')
            result=payload(await client.call_tool(request['tool'],request.get('arguments',{})))
            if wait and 'job_id' in result:
                end=time.monotonic()+deadline
                while time.monotonic()<end:
                    state=payload(await client.call_tool('job_status',result))
                    if state['state'] in ('COMPLETED','FAILED','CANCELLED'):
                        if state['state']!='COMPLETED': raise RuntimeError(json.dumps(state))
                        return state
                    await asyncio.sleep(1)
                raise TimeoutError('Client polling deadline exceeded; job may still run, inspect/cancel its ID: '+result['job_id'])
            return result
