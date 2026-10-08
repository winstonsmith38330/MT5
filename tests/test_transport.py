"""Real MCP HTTP exchange against labelled MOCK, no Windows/broker operations."""
import asyncio, json, os, socket, subprocess, sys, time
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def payload(result):
    assert not result.isError,result
    return result.structuredContent or json.loads(result.content[0].text)


def test_streamable_http_discovery_and_chart_job(tmp_path):
    import pandas as pd
    n=60
    pd.DataFrame({'time':[1735689600+14400*i for i in range(n)],'open':[1.1]*n,'high':[1.2]*n,'low':[1.0]*n,'close':[1.15]*n}).to_csv(tmp_path/'H4.csv',index=False)
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    process=subprocess.Popen([sys.executable,'-m','mt5_research.cli','--workspace',str(tmp_path),'gateway','--mock','--port',str(port)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        for _ in range(100):
            try:
                httpx.get(f'http://127.0.0.1:{port}/mcp',timeout=.2);break
            except httpx.TransportError:time.sleep(.05)
        async def scenario():
            async with streamablehttp_client(f'http://127.0.0.1:{port}/mcp') as (r,w,_):
                async with ClientSession(r,w) as client:
                    await client.initialize()
                    tools=(await client.list_tools()).tools
                    assert 'smoke_batch' in {t.name for t in tools}
                    health=await client.call_tool('health_check',{})
                    assert not health.isError,health
                    h=health.structuredContent or json.loads(health.content[0].text)
                    assert h['mode']=='MOCK' and not h['broker_connected']
                    denied=await client.call_tool('compile_ea',{'source':'nothing.mq5'})
                    assert denied.isError
                    job=payload(await client.call_tool('chart_job',{'h4':'H4.csv'}))['job_id']
                    for _ in range(200):
                        status=payload(await client.call_tool('job_status',{'job_id':job}))
                        if status['state'] in ('COMPLETED','FAILED'):break
                        await asyncio.sleep(.05)
                    assert status['state']=='COMPLETED',status
                    output=status['result']['output']
                    artifact=payload(await client.call_tool('chart_artifact',{'path':output+'/chart.png'}))
                    assert artifact['mime_type']=='image/png' and artifact['base64'].startswith('iVBOR')
                    denied=await client.call_tool('artifact_manifest',{'path':'../secrets.json'})
                    assert denied.isError
        asyncio.run(scenario())
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
