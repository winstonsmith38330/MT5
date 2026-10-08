"""SYNTHETIC Windows worker/API fixtures; never executes MetaTrader."""
import csv,io,json,os,threading,time
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from mt5_research.worker import Worker
from mt5_research.security import PolicyError
from mt5_research.export import export


def worker(tmp_path,monkeypatch):
    terminal=tmp_path/'terminal';terminal.mkdir()
    for name in ['terminal64.exe','metaeditor64.exe']:(terminal/name).write_bytes(b'MOCK_EXECUTABLE_NOT_RUN')
    (tmp_path/'worker.json').write_text(json.dumps({'dedicated_installation':True,'terminal':'terminal/terminal64.exe','metaeditor':'terminal/metaeditor64.exe','data_dir':'terminal'}), encoding='utf-8')
    monkeypatch.setattr(Worker,'windows',lambda self:None)
    monkeypatch.setattr('mt5_research.worker.ensure_closed',lambda p:None)
    return Worker(tmp_path),terminal

@pytest.mark.parametrize('outcome',['fresh','missing','stale','errors'])
def test_compiler_diagnostics_freshness_and_documented_args(tmp_path,monkeypatch,outcome):
    w,t=worker(tmp_path,monkeypatch);src=tmp_path/'sources'/'EA';src.mkdir(parents=True)
    (src/'EA.mq5').write_text('// SYNTHETIC FIXTURE; not an EA implementation', encoding='utf-8')
    (src/'EA.ex5').write_bytes(b'OLD_OUTPUT_MUST_NOT_BE_REUSED')
    def simulated(args,timeout,cancel):
        assert '/log' in args and any(str(a).startswith('/include:') for a in args)
        target=Path(next(str(a).split(':',1)[1] for a in args if str(a).startswith('/compile:')))
        assert not target.with_suffix('.ex5').exists()
        target.with_suffix('.log').write_text('Result: '+('1 errors, 0 warnings' if outcome=='errors' else '0 errors, 0 warnings'), encoding='utf-8')
        if outcome!='missing':
            ex=target.with_suffix('.ex5');ex.write_bytes(b'MOCK_EX5_NOT_A_REAL_BINARY')
            if outcome=='stale':os.utime(ex,(1,1))
        return 0
    monkeypatch.setattr(w,'process',simulated)
    if outcome=='fresh':assert w.compile('sources/EA/EA.mq5',cancel=threading.Event())['status']=='COMPILED'
    else:
        with pytest.raises(RuntimeError):w.compile('sources/EA/EA.mq5',cancel=threading.Event())
    assert (src/'EA.ex5').read_bytes()==b'OLD_OUTPUT_MUST_NOT_BE_REUSED'


def test_export_disjoint_chunks_duplicates_and_bounds(tmp_path,monkeypatch):
    tick_dtype=[('time_msc','i8'),('bid','f8'),('ask','f8'),('last','f8'),('volume','i8'),('flags','i8'),('volume_real','f8')]
    bar_dtype=[('time','i8'),('open','f8'),('high','f8'),('low','f8'),('close','f8'),('tick_volume','i8'),('spread','i8'),('real_volume','i8')]
    intervals=[]
    class Fake:
        COPY_TICKS_ALL=0;TIMEFRAME_M15=15;TIMEFRAME_H4=4;TIMEFRAME_D1=1
        def symbol_info(self,symbol):return SimpleNamespace(_asdict=lambda:{'name':symbol})
        def symbol_select(self,*args):return True
        def copy_ticks_range(self,symbol,a,b,flags):
            intervals.append((a,b));ms=int(a.timestamp()*1000)
            return np.array([(ms,1,1.1,0,0,2,0),(ms,1.01,1.11,0,0,4,0)],dtype=tick_dtype)
        def copy_rates_range(self,*args):return np.array([(1735689600,1,1.2,.9,1.1,2,1,0)],dtype=bar_dtype)
    @contextmanager
    def session(*a,**kw):yield Fake()
    monkeypatch.setattr('mt5_research.export.broker_session',session)
    result=export(tmp_path,'MOCK','EURUSD.MOCK','2025-01-01T00:00:00Z','2025-01-01T02:00:00Z',cancel=threading.Event())
    assert int((intervals[1][0]-intervals[0][1]).total_seconds()*1000)==1
    out=tmp_path/result['output'];rows=list(csv.DictReader((out/'ticks.csv').open(encoding='utf-8-sig')))
    assert len(rows)==4 and rows[0]['time_msc']==rows[1]['time_msc'] and rows[3]['sequence']=='3'
    assert result['quality']['complete_requested_ticks']
    truncated=export(tmp_path,'MOCK','EURUSD.MOCK','2025-01-01T00:00:00Z','2025-01-01T02:00:00Z',max_ticks=3,cancel=threading.Event())
    assert truncated['quality']['ticks']==2 and not truncated['quality']['complete_requested_ticks']
    assert any('TRUNCATED' in w for w in truncated['quality']['warnings'])
    assert (tmp_path/truncated['output']/'H4.csv').exists()


def test_demo_guard_rejects_live_and_wrong_terminal(tmp_path,monkeypatch):
    import sys
    from mt5_research.export import broker_session
    monkeypatch.setattr('platform.system',lambda:'Windows')
    fake=SimpleNamespace(initialize=lambda *a,**kw:True,shutdown=lambda:None,ACCOUNT_TRADE_MODE_DEMO=0,account_info=lambda:SimpleNamespace(trade_mode=2),terminal_info=lambda:SimpleNamespace(connected=True,path=str(tmp_path),data_path=str(tmp_path)))
    monkeypatch.setitem(sys.modules,'MetaTrader5',fake)
    with pytest.raises(PolicyError,match='demo'):
        with broker_session(tmp_path/'terminal.exe'):pass
    fake.account_info=lambda:SimpleNamespace(trade_mode=0)
    fake.terminal_info=lambda:SimpleNamespace(connected=True,path='/wrong',data_path='/wrong')
    with pytest.raises(PolicyError,match='unexpected'):
        with broker_session(tmp_path/'terminal.exe'):pass


def test_timeout_kills_only_started_pid(tmp_path,monkeypatch):
    w,_=worker(tmp_path,monkeypatch);calls=[]
    p=SimpleNamespace(pid=12345,poll=lambda:None,wait=lambda timeout:0)
    monkeypatch.setattr('subprocess.Popen',lambda *a,**kw:p)
    monkeypatch.setattr('subprocess.run',lambda args,**kw:calls.append(args))
    cancel=threading.Event();cancel.set()
    with pytest.raises(TimeoutError,match='Cancelled'):w.process(['MOCK.exe'],timeout=1,cancel=cancel)
    assert calls==[['taskkill','/PID','12345','/T','/F']]


def test_smoke_order_fresh_artifacts_and_manifest(tmp_path,monkeypatch):
    w,terminal=worker(tmp_path,monkeypatch)
    (tmp_path/'EA.ex5').write_bytes(b'MOCK_EX5');(tmp_path/'EA.set').write_text('RiskPercent=1\n', encoding='utf-8')
    fake=SimpleNamespace(account_info=lambda:SimpleNamespace(company='MOCK_BROKER',server='MOCK_SERVER',trade_mode=0),terminal_info=lambda:SimpleNamespace(build=0),symbol_info=lambda s:object())
    @contextmanager
    def session(*a,**kw):yield fake
    monkeypatch.setattr('mt5_research.export.broker_session',session)
    order=[]
    def simulated(args,timeout,cancel):
        from configparser import ConfigParser
        config=Path(next(str(a).split(':',1)[1] for a in args if str(a).startswith('/config:')))
        c=ConfigParser();c.read(config,encoding='utf-16');order.append(c['Tester']['Symbol'])
        (terminal/(c['Tester']['Report']+'.htm')).write_text('<html>MOCK REPORT: no real tester executed</html>', encoding='utf-8')
        logs=terminal/'Tester'/'Agent-MOCK'/'logs';logs.mkdir(parents=True,exist_ok=True);(logs/'test.log').write_text('MOCK tester journal', encoding='utf-8')
        return 0
    monkeypatch.setattr(w,'process',simulated)
    def mock_export(root,terminal,symbol,start,end,**kwargs):
        import pandas as pd
        out=Path(root)/kwargs['output'];out.mkdir(parents=True)
        pd.DataFrame({'time':[1735689600+14400*i for i in range(60)],'open':[1]*60,'high':[1.2]*60,'low':[.9]*60,'close':[1.1]*60}).to_csv(out/'H4.csv',index=False)
        pd.DataFrame({'time':[1735689600,1735776000],'high':[1.2,1.2],'low':[.9,.9],'close':[1.1,1.1]}).to_csv(out/'D1.csv',index=False)
        return {'quality':{'mode':'MOCK'},'output':str(out.relative_to(root))}
    monkeypatch.setattr('mt5_research.export.export',mock_export)
    result=w.smoke('EA.ex5','EA.set',{'NAS100':'NAS.MOCK','EURUSD':'EUR.MOCK'},cancel=threading.Event(),risk_input='RiskPercent')
    assert order==['EUR.MOCK','NAS.MOCK'] and result['status']=='INCONCLUSIVE'
    out=tmp_path/result['output'];manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8-sig'))
    assert manifest['deposit']==3000 and len(manifest['assets'])==2
    assert all(a['fresh_report'] and a['evidence_files'] for a in manifest['assets'])
    assert (out/'EURUSD'/'charts'/'chart.png').exists() and (out/'NAS100'/'charts'/'chart.html').exists()
    assert not list((terminal/'MQL5'/'Experts').glob('research_*'))


def test_credential_preset_rejected():
    from mt5_research.config import preset_text
    with pytest.raises(PolicyError,match='Credential'):preset_text('BrokerPassword=not-a-real-password')
