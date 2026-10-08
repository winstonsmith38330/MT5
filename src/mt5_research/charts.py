"""Offline broker-bar reference charts. No EA behavior is invented."""
import json, uuid
from pathlib import Path
import pandas as pd
from .security import scoped, PolicyError

MAX_ROWS=100000

def frame(path, required):
    path=Path(path)
    if path.stat().st_size>32*1024*1024: raise PolicyError('Chart input exceeds 32 MiB')
    data=pd.read_csv(path,nrows=MAX_ROWS+1)
    if len(data)>MAX_ROWS: raise PolicyError('Chart row limit exceeded')
    missing=set(required)-set(data.columns)
    if missing: raise PolicyError('DATA_MISSING: columns '+','.join(sorted(missing)))
    if not len(data): raise PolicyError('DATA_MISSING: empty chart input')
    return data


def timestamps(series):
    if pd.api.types.is_numeric_dtype(series): return pd.to_datetime(series,unit='s',utc=True)
    return pd.to_datetime(series,utc=True,errors='raise')


def indicators(h4,d1=None):
    h4=h4.copy();h4['time']=timestamps(h4['time'])
    if h4['time'].duplicated().any() or not h4['time'].is_monotonic_increasing:
        raise PolicyError('H4 bars must have unique chronological opens')
    for col in ['open','high','low','close']:
        h4[col]=pd.to_numeric(h4[col],errors='raise')
        if not h4[col].map(lambda v: float('-inf')<v<float('inf')).all(): raise PolicyError('Nonfinite OHLC')
    if ((h4.high<h4[['open','close','low']].max(axis=1)) | (h4.low>h4[['open','close','high']].min(axis=1))).any():
        raise PolicyError('Invalid OHLC geometry')
    h4['SMA5']=h4.close.rolling(5,min_periods=5).mean()
    h4['SMA55']=h4.close.rolling(55,min_periods=55).mean()
    if d1 is not None:
        d1=d1.copy();d1['time']=timestamps(d1.time)
        if d1.time.duplicated().any() or not d1.time.is_monotonic_increasing: raise PolicyError('D1 opens must be chronological and unique')
        for c in ['high','low','close']: d1[c]=pd.to_numeric(d1[c],errors='raise')
        d1['P']=((d1.high+d1.low+d1.close)/3).shift(1)
        d1['R1']=2*d1.P-d1.low.shift(1);d1['S1']=2*d1.P-d1.high.shift(1)
        h4=pd.merge_asof(h4,d1[['time','P','R1','S1']],on='time',direction='backward')
    return h4


def chart(root, h4, d1=None, markers=None, schema=None, output=None, *, cancel=None):
    if cancel is not None and cancel.is_set(): raise TimeoutError('Cancelled')
    root=Path(root).resolve()
    data=frame(scoped(root,h4,exists=True),['time','open','high','low','close'])
    daily=frame(scoped(root,d1,exists=True),['time','high','low','close']) if d1 else None
    data=indicators(data,daily)
    warnings=[]
    if daily is None: warnings.append('DATA_MISSING: D1 reference bars; pivots omitted')
    if len(data)<55: warnings.append('DATA_MISSING: insufficient SMA55 warmup')
    events=None
    if markers:
        mapping=json.loads(scoped(root,schema,exists=True).read_text(encoding='utf-8-sig')) if schema else {'time':'time','price':'price','label':'label'}
        if set(mapping)!= {'time','price','label'} or not all(isinstance(v,str) for v in mapping.values()): raise PolicyError('Invalid marker schema')
        events=frame(scoped(root,markers,exists=True),mapping.values()).rename(columns={v:k for k,v in mapping.items()})
        events.time=timestamps(events.time);events.price=pd.to_numeric(events.price,errors='raise')
    else: warnings.append('DATA_MISSING: actual EA trade/audit markers')
    out=scoped(root,output or ('outputs/'+uuid.uuid4().hex));out.mkdir(parents=True,exist_ok=True)
    import plotly.graph_objects as go
    fig=go.Figure(go.Candlestick(x=data.time,open=data.open,high=data.high,low=data.low,close=data.close,name='Broker H4'))
    for c in ['SMA5','SMA55','P','R1','S1']:
        if c in data: fig.add_trace(go.Scatter(x=data.time,y=data[c],name=c,mode='lines'))
    if events is not None: fig.add_trace(go.Scatter(x=events.time,y=events.price,text=events.label.astype(str),name='Supplied audit',mode='markers'))
    fig.update_layout(title='Reference chart — completed broker bars, UTC opens',xaxis_rangeslider_visible=False)
    fig.write_html(out/'chart.html',include_plotlyjs=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as md
    from matplotlib.patches import Rectangle
    fig2,ax=plt.subplots(figsize=(14,6))
    # Bound rendered candlesticks; full input remains in enriched CSV/HTML.
    view=data.tail(3000);x=md.date2num(view.time.to_numpy())
    for t,row in zip(x,view.itertuples()):
        color='green' if row.close>=row.open else 'red'
        ax.vlines(t,row.low,row.high,color=color,linewidth=.5)
        ax.add_patch(Rectangle((t-.05,min(row.open,row.close)),.10,max(abs(row.close-row.open),1e-10),color=color))
    for c in ['SMA5','SMA55','P','R1','S1']:
        if c in view: ax.plot(x,view[c],label=c,linewidth=.7)
    if events is not None: ax.scatter(md.date2num(events.time.to_numpy()),events.price,s=12,label='Supplied audit')
    ax.xaxis_date();ax.set_title('H4 reference candles / UTC');ax.legend();fig2.autofmt_xdate();fig2.tight_layout();fig2.savefig(out/'chart.png');plt.close(fig2)
    data.to_csv(out/'reference.csv',index=False)
    result={'output':str(out.relative_to(root)),'warnings':warnings,'math':'Completed H4 close SMA5/55; classical previous broker D1 P/R1/S1. Reference only; verify actual EA formulas/shift/price/session.'}
    (out/'chart-manifest.json').write_text(json.dumps(result,indent=2), encoding='utf-8')
    return result
