import argparse, json, os
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--workspace',default=os.environ.get('MT5_RESEARCH_ROOT','local'))
    sub=p.add_subparsers(dest='command',required=True)
    g=sub.add_parser('gateway');g.add_argument('--mock',action='store_true');g.add_argument('--port',type=int,default=8765);g.add_argument('--stdio',action='store_true')
    d=sub.add_parser('discover');d.add_argument('endpoint',choices=['terminal','editor'])
    c=sub.add_parser('chart');c.add_argument('--h4',required=True);c.add_argument('--d1');c.add_argument('--markers');c.add_argument('--schema');c.add_argument('--output')
    sub.add_parser('health')
    k=sub.add_parser('call');k.add_argument('--request',required=True);k.add_argument('--wait',action='store_true');k.add_argument('--port',type=int,default=8765)
    a=p.parse_args();root=Path(a.workspace).resolve()
    if a.command=='gateway':
        from .gateway import create
        create(root,mock=a.mock,port=a.port).run(transport='stdio' if a.stdio else 'streamable-http')
    elif a.command=='discover':
        import asyncio
        from .native import Native
        print(json.dumps(asyncio.run(Native(root).request(a.endpoint)),indent=2))
    elif a.command=='chart':
        from .charts import chart
        print(json.dumps(chart(root,a.h4,a.d1,a.markers,a.schema,a.output),indent=2))
    elif a.command=='call':
        import asyncio
        from .client import call
        print(json.dumps(asyncio.run(call(json.loads(Path(a.request).read_text(encoding='utf-8-sig')),port=a.port,wait=a.wait)),indent=2))
    elif a.command=='health':
        import platform
        print(json.dumps({'host_os':platform.system(),'python':platform.python_version(),'workspace':str(root),'mode':'LOCAL_DIAGNOSTIC','broker_connected':False,'note':'Use MCP health_check on Windows for actual broker identity'},indent=2))

if __name__=='__main__': main()
