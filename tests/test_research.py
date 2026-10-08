import asyncio, csv, io, json, os, threading, time
from pathlib import Path
from contextlib import asynccontextmanager
from types import SimpleNamespace
import pandas as pd
import pytest
from mt5_research.security import PolicyError, scoped, redact
from mt5_research.config import tester_ini as make_ini,preset_text
from mt5_research.jobs import Jobs
from mt5_research.export import write_ticks,export
from mt5_research.charts import frame,indicators,chart
from mt5_research.worker import Worker
from mt5_research.native import Native

@pytest.mark.parametrize('path',['../escape','/etc/passwd','file:stream','.'])
def test_paths_rejected(tmp_path,path):
    with pytest.raises(PolicyError): scoped(tmp_path,path)

def test_symlink_escape(tmp_path):
    try: (tmp_path/'escape').symlink_to('/etc',target_is_directory=True)
    except OSError: pytest.skip('OS does not permit local symlink creation')
    with pytest.raises(PolicyError): scoped(tmp_path,'escape/passwd')

def test_scoped_local_and_missing(tmp_path):
    assert scoped(tmp_path,'outputs/a')==tmp_path/'outputs/a'
    with pytest.raises(PolicyError,match='DATA_MISSING'): scoped(tmp_path,'missing',exists=True)

def test_redaction(monkeypatch):
    monkeypatch.setenv('MT5_TERMINAL_TOKEN','test-secret')
    assert redact({'Authorization':'Bearer test-secret','text':['test-secret']})=={'Authorization':'[REDACTED]','text':['[REDACTED]']}

def ini(**kwargs):
    return make_ini(**dict(expert='EA.ex5',symbol='EURUSD.a',start='2025-01-01',end='2025-02-01',report='unique',preset='EA.set',**kwargs))

def test_config_mechanical():
    s=ini();assert all(v in s for v in ['Model=4','Optimization=0','Visual=0','Deposit=3000','Leverage=1:100','Currency=USD','ShutdownTerminal=1'])
    assert 'Login' not in s and 'Password' not in s and s==ini()

@pytest.mark.parametrize('symbol',['EURUSD\nLogin=123','../EURUSD','a/b'])
def test_config_injection(symbol):
    with pytest.raises(PolicyError): make_ini(expert='a.ex5',symbol=symbol,start='2025-01-01',end='2025-02-01',report='r',preset='a.set')

def test_dates_and_preset():
    with pytest.raises(PolicyError): make_ini(expert='a.ex5',symbol='x',start='2025-02-01',end='2025-01-01',report='r',preset='a.set')
    text,warnings=preset_text('RiskPct=1\nOther=2\n','RiskPct');assert text=='RiskPct=0.50\nOther=2\n' and warnings==[]
    assert preset_text('Other=2')[1]
    with pytest.raises(PolicyError): preset_text('Other=2','RiskPct')


def wait(jobs,jid):
    for _ in range(500):
        state=jobs.status(jid)
        if state['state'] in ('COMPLETED','FAILED','CANCELLED'): return state
        time.sleep(.01)
    raise AssertionError('job did not finish')

def test_jobs_serial_failure_cancel():
    jobs=Jobs();entered=threading.Event();release=threading.Event();order=[]
    def first(cancel): entered.set();release.wait(2);order.append(1);return {'ok':True}
    def second(cancel): order.append(2)
    a=jobs.submit(first);entered.wait(1);b=jobs.submit(second)
    assert jobs.status(b)['state']=='QUEUED';jobs.cancel(b);release.set()
    assert wait(jobs,a)['state']=='COMPLETED' and wait(jobs,b)['state']=='CANCELLED' and order==[1]
    def fail(cancel): raise ValueError('deliberate failure')
    c=jobs.submit(fail);assert wait(jobs,c)['state']=='FAILED'
    with pytest.raises(ValueError):jobs.status('unknown')

def test_tick_order_duplicates_flags():
    rows=[dict(time_msc=1000,bid=1.0,ask=1.1,last=0,volume=0,flags=2,volume_real=0),dict(time_msc=1000,bid=1.01,ask=1.11,last=0,volume=0,flags=4,volume_real=0)]
    f=io.StringIO();count,last=write_ticks(rows,csv.writer(f),0)
    parsed=list(csv.reader(io.StringIO(f.getvalue())))
    assert count==2 and last==1000 and [r[0] for r in parsed]==['0','1'] and parsed[0][7]=='2' and parsed[1][7]=='4'
    with pytest.raises(ValueError):write_ticks(rows,csv.writer(f),2,previous=2000)

def bars(n=70):
    t=pd.date_range('2025-01-01',periods=n,freq='4h',tz='UTC')
    return pd.DataFrame({'time':t.astype('int64')//10**9,'open':range(100,100+n),'high':range(102,102+n),'low':range(99,99+n),'close':range(101,101+n)})

def test_sma_and_shifted_pivot():
    h=bars();d=pd.DataFrame({'time':[1735689600,1735776000],'high':[110,120],'low':[90,100],'close':[100,110]})
    result=indicators(h,d)
    assert result.SMA5.iloc[4]==103 and pd.isna(result.SMA55.iloc[53]) and result.SMA55.iloc[54]==128
    assert pd.isna(result.P.iloc[0]) and result.P.iloc[6]==100 and result.R1.iloc[6]==110 and result.S1.iloc[6]==90

def test_chart_real_artifacts(tmp_path,monkeypatch):
    bars().to_csv(tmp_path/'H4.csv',index=False)
    pd.DataFrame({'event_time_utc':['2025-01-02T00:00:00Z'],'event_price':[107],'event_type':['SYNTHETIC_TEST']}).to_csv(tmp_path/'audit.csv',index=False)
    (tmp_path/'schema.json').write_text(json.dumps({'time':'event_time_utc','price':'event_price','label':'event_type'}), encoding='utf-8')
    result=chart(tmp_path,'H4.csv',markers='audit.csv',schema='schema.json')
    out=tmp_path/result['output']
    assert (out/'chart.png').read_bytes().startswith(b'\x89PNG')
    original_read_text=Path.read_text
    def windows_default_read(path,encoding=None,errors=None):
        return original_read_text(path,encoding=encoding or 'cp1252',errors=errors)
    monkeypatch.setattr(Path,'read_text',windows_default_read)
    with pytest.raises(UnicodeDecodeError): (out/'chart.html').read_text()
    assert 'SYNTHETIC_TEST' in (out/'chart.html').read_text(encoding='utf-8-sig')
    from mt5_research.gateway import create
    server=create(tmp_path,mock=True)
    retrieved=asyncio.run(server.call_tool('chart_artifact',{'path':result['output']+'/chart.html'}))
    assert 'SYNTHETIC_TEST' in str(retrieved)
    assert any('D1' in w for w in result['warnings'])
    assert len(pd.read_csv(out/'reference.csv'))==70

def test_data_missing_and_invalid_bars(tmp_path):
    (tmp_path/'empty.csv').write_text('time,close\n', encoding='utf-8')
    with pytest.raises(PolicyError,match='DATA_MISSING'):frame(tmp_path/'empty.csv',['time','close'])
    h=bars();h.loc[1,'time']=h.loc[0,'time']
    with pytest.raises(PolicyError):indicators(h)
    h=bars();h.loc[1,'high']=0
    with pytest.raises(PolicyError):indicators(h)


def test_cloud_refuses_mt5(tmp_path,monkeypatch):
    monkeypatch.setattr('platform.system',lambda:'Linux')
    with pytest.raises(PolicyError,match='WINDOWS_ACTION_REQUIRED'):Worker(tmp_path).compile('missing.mq5',cancel=threading.Event())
    from mt5_research.export import broker_session
    with pytest.raises(PolicyError):
        with broker_session('terminal.exe'):pass

def test_dedicated_paths(tmp_path):
    (tmp_path/'terminal').mkdir()
    for n in ['terminal64.exe','metaeditor64.exe']:(tmp_path/'terminal'/n).touch()
    (tmp_path/'worker.json').write_text(json.dumps({'dedicated_installation':True,'terminal':'terminal/terminal64.exe','metaeditor':'terminal/metaeditor64.exe','data_dir':'terminal'}), encoding='utf-8')
    assert Worker(tmp_path).settings()['data_dir']==tmp_path/'terminal'
    c=json.loads((tmp_path/'worker.json').read_text(encoding='utf-8-sig'));c['data_dir']='..';(tmp_path/'worker.json').write_text(json.dumps(c), encoding='utf-8')
    with pytest.raises(PolicyError):Worker(tmp_path).settings()


def test_native_endpoint_and_allowlist(tmp_path,monkeypatch):
    monkeypatch.setenv('MT5_TERMINAL_URL','https://remote.example/mcp');monkeypatch.setenv('MT5_TERMINAL_TOKEN','secret')
    with pytest.raises(PolicyError):asyncio.run(Native(tmp_path).request('terminal'))
    monkeypatch.setenv('MT5_TERMINAL_URL','http://127.0.0.1:123/mcp')
    class Tool:
        name='get_workspace_info'
        inputSchema={'type':'object'}
        def model_dump(self):return {'name':self.name,'inputSchema':{'type':'object'}}
    class Session:
        def __init__(self,*a):pass
        async def __aenter__(self):return self
        async def __aexit__(self,*a):pass
        async def initialize(self):pass
        async def list_tools(self):return SimpleNamespace(tools=[Tool()])
        async def call_tool(self,name,args):return SimpleNamespace(model_dump=lambda:{'text':'secret'})
    @asynccontextmanager
    async def transport(*args,**kwargs):
        assert kwargs['headers']=={'Authorization':'Bearer secret'}
        yield (None,None,None)
    monkeypatch.setattr('mt5_research.native.ClientSession',Session);monkeypatch.setattr('mt5_research.native.streamablehttp_client',transport)
    n=Native(tmp_path)
    result=asyncio.run(n.request('terminal'));assert result['enabled']==[] and 'compile' in result['missing_categories']
    with pytest.raises(PolicyError):asyncio.run(n.request('terminal','order_send',{}))
    (tmp_path/'native-policy.json').write_text(json.dumps({'terminal':{'get_workspace_info':{'reviewed':True,'category':'inspect','fixed_arguments':{}}}}), encoding='utf-8')
    assert asyncio.run(n.request('terminal','get_workspace_info',{}))=={'text':'[REDACTED]'}
    with pytest.raises(PolicyError):asyncio.run(n.request('terminal','get_workspace_info',{'path':'../secret'}))
    (tmp_path/'native-policy.json').write_text(json.dumps({'terminal':{'get_workspace_info':{'reviewed':True,'category':'tester','fixed_arguments':{}}}}), encoding='utf-8')
    with pytest.raises(PolicyError):asyncio.run(n.request('terminal','get_workspace_info',{}))
    Tool.name='trade_send_market_order'
    (tmp_path/'native-policy.json').write_text(json.dumps({'terminal':{'trade_send_market_order':{'reviewed':True,'category':'inspect','fixed_arguments':{}}}}), encoding='utf-8')
    with pytest.raises(PolicyError):asyncio.run(n.request('terminal','trade_send_market_order',{}))


def test_gateway_schema_and_mock(tmp_path):
    from mt5_research.gateway import create
    server=create(tmp_path,mock=True)
    async def run():
        tools=await server.list_tools();names={t.name for t in tools}
        assert names=={'health_check','discover_native','native_research_call','compile_ea','smoke_batch','export_market_data','chart_job','job_status','cancel_job','artifact_manifest','broker_inspect','chart_artifact'}
        result=await server.call_tool('health_check',{})
        # FastMCP returns text and structured content; verify explicitly labelled mock.
        assert 'MOCK' in str(result) and 'broker_connected' in str(result)
        with pytest.raises(Exception):await server.call_tool('compile_ea',{'source':'a.mq5'})
    asyncio.run(run())
