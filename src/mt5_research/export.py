"""Bounded UTC tick export. MT5 Python package has no tester/compiler API."""
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
import csv, json, platform, subprocess, time
from pathlib import Path
from .security import PolicyError, scoped

@contextmanager
def broker_session(terminal, require_demo=True, owned=False):
    if platform.system()!='Windows': raise PolicyError('WINDOWS_ACTION_REQUIRED: broker not connected')
    import MetaTrader5 as mt5
    process=None
    if owned:
        from .worker import ensure_closed
        ensure_closed(terminal)
        process=subprocess.Popen([str(terminal), '/portable'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        if not mt5.initialize(str(terminal),portable=True,timeout=60000): raise RuntimeError('MT5 initialization failed')
        terminal_info=mt5.terminal_info()
        if terminal_info is None or not terminal_info.connected: raise PolicyError('Dedicated terminal is not connected to its broker')
        expected=Path(terminal).resolve().parent
        if Path(terminal_info.path).resolve()!=expected or Path(terminal_info.data_path).resolve()!=expected:
            raise PolicyError('API attached to unexpected installation/data directory')
        account=mt5.account_info()
        if account is None: raise PolicyError('Log into dedicated demo terminal locally first')
        if require_demo and account.trade_mode!=mt5.ACCOUNT_TRADE_MODE_DEMO:
            raise PolicyError('Research worker requires an authenticated demo account')
        yield mt5
    finally:
        mt5.shutdown()
        if process is not None and process.poll() is None:
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,check=False)
            process.wait(timeout=15)


def write_ticks(rows, writer, sequence, previous=None):
    for row in rows:
        ms=int(row['time_msc'])
        if previous is not None and ms<previous: raise ValueError('Tick stream is not chronological')
        writer.writerow([sequence,ms,str(datetime.fromtimestamp(ms/1000,timezone.utc).isoformat()),float(row['bid']),float(row['ask']),float(row['last']),int(row['volume']),int(row['flags']),float(row['volume_real'])])
        sequence+=1;previous=ms
    return sequence,previous


def export(root, terminal, symbol, start, end, *, cancel, max_ticks=2000000, output=None):
    a=datetime.fromisoformat(start);b=datetime.fromisoformat(end)
    if a.tzinfo is None or b.tzinfo is None: raise PolicyError('Explicit UTC offsets required')
    a=a.astimezone(timezone.utc);b=b.astimezone(timezone.utc)
    if a.microsecond % 1000 or b.microsecond % 1000: raise PolicyError('Tick interval must align to milliseconds')
    if not a<b or b-a>timedelta(days=32) or not 1<=max_ticks<=2000000:
        raise PolicyError('Export bounded to 32 days and 2 million ticks')
    import uuid
    out=scoped(root,output or ('outputs/'+uuid.uuid4().hex))
    if not out.is_relative_to(Path(root).resolve()/'outputs'): raise PolicyError('Export output must be under outputs')
    out.mkdir(parents=True,exist_ok=False)
    warnings=[];count=0;previous=None;first_msc=None;max_gap_ms=0;zero_quotes=0
    with broker_session(terminal,owned=True) as mt5:
        info=mt5.symbol_info(symbol)
        if info is None: raise PolicyError('Discover exact broker alias before exporting')
        if not mt5.symbol_select(symbol,True): raise RuntimeError('Symbol selection failed')
        (out/'symbol.json').write_text(json.dumps(info._asdict(),indent=2,default=str), encoding='utf-8')
        with (out/'ticks.csv').open('w',newline='', encoding='utf-8') as f:
            writer=csv.writer(f);writer.writerow(['sequence','time_msc','utc','bid','ask','last','volume','flags','volume_real'])
            cursor=a
            # Disjoint millisecond intervals preserve all equal-timestamp records.
            while cursor<b:
                if cancel.is_set(): raise TimeoutError('Cancelled')
                stop=min(cursor+timedelta(hours=1),b)
                rows=mt5.copy_ticks_range(symbol,cursor,stop-timedelta(milliseconds=1),mt5.COPY_TICKS_ALL)
                if rows is None: raise RuntimeError('Broker tick retrieval failed')
                if len(rows)>max_ticks-count:
                    warnings.append('TRUNCATED: tick bound reached before chunk at '+cursor.isoformat()+'; request narrower intervals')
                    break
                if len(rows):
                    times=rows['time_msc']
                    if int(times[0])<int(cursor.timestamp()*1000) or int(times[-1])>=int(stop.timestamp()*1000):
                        raise ValueError('Broker tick API returned data outside requested chunk')
                    if first_msc is None: first_msc=int(times[0])
                    gaps=[int(times[i])-int(times[i-1]) for i in range(1,len(times))]
                    if previous is not None: gaps.append(int(times[0])-previous)
                    max_gap_ms=max(max_gap_ms,max(gaps,default=0))
                    zero_quotes+=sum(1 for row in rows if float(row['bid'])<=0 or float(row['ask'])<=0)
                count,previous=write_ticks(rows,writer,count,previous);cursor=stop
        for name,tf in [('M15',mt5.TIMEFRAME_M15),('H4',mt5.TIMEFRAME_H4),('D1',mt5.TIMEFRAME_D1)]:
            bars=mt5.copy_rates_range(symbol,tf,a-timedelta(days=120),b)
            if bars is None: raise RuntimeError('Broker reference bar retrieval failed')
            with (out/(name+'.csv')).open('w',newline='', encoding='utf-8') as f:
                writer=csv.writer(f);writer.writerow(bars.dtype.names);writer.writerows(bars.tolist())
            if not len(bars): warnings.append('DATA_MISSING: '+name+' bars')
        if count==0: warnings.append('DATA_MISSING: no ticks')
        if zero_quotes: warnings.append('ZERO_QUOTES: bid/ask absent or nonpositive on '+str(zero_quotes)+' ticks; interpret flags/instrument conventions')
        metadata={'first_time_msc':first_msc,'last_time_msc':previous,'max_gap_ms':max_gap_ms,'gap_note':'Gaps include legitimate closed sessions; compare broker calendar/history before classifying data loss','symbol':symbol,'start_utc':a.isoformat(),'end_utc_exclusive':b.isoformat(),'ticks':count,'complete_requested_ticks':cursor>=b,'tick_order':'source sequence; equal millisecond timestamps retained','quote_sides':['bid','ask','last'],'warnings':warnings,'broker_chart_timezone':'UNKNOWN: supply actual broker session/D1 boundaries; never infer from OS timezone','coverage':'Requested interval is not proof of complete broker history; inspect gaps and tester journal'}
        (out/'data-quality.json').write_text(json.dumps(metadata,indent=2), encoding='utf-8')
    return {'output':str(out.relative_to(Path(root).resolve())),'quality':metadata}
