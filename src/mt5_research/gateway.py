import os, platform, json
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from .auth import oauth_settings
from .jobs import Jobs
from .native import Native
from .worker import Worker
from .charts import chart
from .security import PolicyError, redact


def create(root, *, mock=False, port=8765):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True)
    jobs=Jobs();worker=Worker(root);native=Native(root)
    server=FastMCP('MT5 research',instructions='Research only. No account order operations. MOCK is offline and never broker connected.',host='127.0.0.1',port=port,stateless_http=True,log_level='WARNING',**oauth_settings())

    @server.tool()
    def health_check() -> dict:
        """Actual OS, workspace, configured local paths and readiness; no credentials."""
        result={'mode':'MOCK' if mock else 'LOCAL','host_os':platform.system(),'workspace':str(root),'python':platform.python_version(),'broker_connected':False,'native':{k:bool(os.environ.get('MT5_'+k.upper()+'_URL')) for k in ['terminal','editor']},'missing':[]}
        if platform.system()!='Windows' or mock:
            result['missing'].append('WINDOWS_ACTION_REQUIRED: actual Windows terminal/broker not connected')
            return result
        try:
            c=worker.settings();result['paths']={k:str(c[k]) for k in ['terminal','metaeditor','data_dir']}
            from .export import broker_session
            with broker_session(c['terminal']) as mt5:
                a=mt5.account_info();t=mt5.terminal_info()
                result.update(broker_connected=True,broker=a.company,server=a.server,build=t.build,terminal_path=t.path,data_path=t.data_path,account_scope='DEMO')
        except Exception as e: result['missing'].append(redact(str(e)))
        return result

    @server.tool()
    async def discover_native(endpoint: str) -> dict:
        """Read installed terminal/editor tool schemas; report missing capabilities."""
        if mock or platform.system()!='Windows': return {'mode':'MOCK' if mock else 'NOT_CONNECTED','schemas':[],'missing':['Windows native endpoint']}
        return await native.request(endpoint)

    @server.tool()
    async def native_research_call(endpoint: str, name: str, arguments: dict) -> dict:
        """Forward operator-reviewed fixed read-only operations; no arbitrary mutation."""
        if mock: raise PolicyError('MOCK cannot invoke broker tools')
        worker.windows()
        from .export import broker_session
        c=worker.settings()
        with broker_session(c['terminal']): pass
        return await native.request(endpoint,name,arguments)

    @server.tool()
    def compile_ea(source: str, timeout: int = 120) -> dict:
        """Queue dedicated MetaEditor compile; no strategy/source modification."""
        if mock: raise PolicyError('MOCK cannot compile MQL5')
        worker.windows()
        return {'job_id':jobs.submit(worker.compile,source=source,timeout=timeout)}

    @server.tool()
    def smoke_batch(ex5: str, preset: str, aliases: dict[str,str], start: str = '2025-01-01', end: str = '2025-02-01', risk_input: str | None = None, timeout: int = 1800) -> dict:
        """Sequential EURUSD/NAS100 historical tester jobs; missing EA is DATA_MISSING."""
        if mock: raise PolicyError('MOCK cannot run tester')
        worker.windows()
        return {'job_id':jobs.submit(worker.smoke,ex5=ex5,preset=preset,aliases=aliases,start=start,end=end,risk_input=risk_input,timeout=timeout)}

    @server.tool()
    def broker_inspect() -> dict:
        """Discover exact broker symbols and specifications on the dedicated demo terminal."""
        if mock: return {'mode':'MOCK','symbols':[],'broker_connected':False}
        worker.windows();c=worker.settings()
        from .export import broker_session
        def inspect(cancel):
            with broker_session(c['terminal'],owned=True) as mt5:
                a=mt5.account_info();t=mt5.terminal_info()
                symbols=mt5.symbols_get()
                if symbols is None: raise RuntimeError('Symbol discovery failed')
                return {'broker':a.company,'server':a.server,'build':t.build,'account_scope':'DEMO','symbols':[{'name':s.name,'description':s.description,'digits':s.digits,'point':s.point,'contract_size':s.trade_contract_size,'currency_profit':s.currency_profit} for s in symbols][:10000]}
        return {'job_id':jobs.submit(inspect)}

    @server.tool()
    def export_market_data(symbol: str, start: str, end: str, max_ticks: int = 2000000) -> dict:
        """Export bounded ordered ticks and broker M15/H4/D1 bars via demo terminal."""
        if mock: raise PolicyError('MOCK cannot export broker data')
        worker.windows();c=worker.settings()
        from .export import export
        return {'job_id':jobs.submit(export,root=root,terminal=c['terminal'],symbol=symbol,start=start,end=end,max_ticks=max_ticks)}

    @server.tool()
    def chart_job(h4: str, d1: str | None = None, markers: str | None = None, schema: str | None = None) -> dict:
        """Bounded offline HTML/PNG chart from workspace CSVs; no shell access."""
        return {'job_id':jobs.submit(chart,root=root,h4=h4,d1=d1,markers=markers,schema=schema)}

    @server.tool()
    def job_status(job_id: str) -> dict:
        return jobs.status(job_id)

    @server.tool()
    def cancel_job(job_id: str) -> dict:
        return jobs.cancel(job_id)

    @server.tool()
    def artifact_manifest(path: str) -> dict:
        """Read bounded JSON result manifests only; no arbitrary files/credential stores."""
        from .security import scoped
        p=scoped(root,path,exists=True)
        if not p.is_relative_to(root/'outputs') or p.suffix!='.json' or p.stat().st_size>1024*1024: raise PolicyError('Only output JSON manifests up to 1 MiB')
        return redact(json.loads(p.read_text(encoding='utf-8-sig')))

    @server.tool()
    def chart_artifact(path: str) -> dict:
        """Retrieve generated chart PNG/HTML, bounded to 16 MiB inside outputs."""
        import base64
        from .security import scoped
        p=scoped(root,path,exists=True)
        if not p.is_relative_to(root/'outputs') or p.name not in {'chart.png','chart.html'} or p.stat().st_size>16*1024*1024:
            raise PolicyError('Only generated chart PNG/HTML up to 16 MiB')
        if p.suffix=='.png': return {'mime_type':'image/png','base64':base64.b64encode(p.read_bytes()).decode()}
        return {'mime_type':'text/html','text':redact(p.read_text(encoding='utf-8-sig'))}

    return server
