from datetime import date
import re
from .security import PolicyError

SAFE = re.compile(r'^[A-Za-z0-9_. -]{1,100}$')

def tester_ini(*, expert, symbol, start, end, report, preset, risk_input=None):
    for value in (expert,symbol,report,preset):
        if not SAFE.fullmatch(value) or '..' in value:
            raise PolicyError('Unsafe tester field')
    a,b = date.fromisoformat(start),date.fromisoformat(end)
    if not a < b or (b-a).days > 366:
        raise PolicyError('Invalid or excessive date interval')
    if not expert.endswith('.ex5') or not preset.endswith('.set'):
        raise PolicyError('Compiled EA and preset required')
    return '\n'.join(['[Experts]','AllowLiveTrading=0','AllowDllImport=0','[Tester]',f'Expert={expert}',f'ExpertParameters={preset}',f'Symbol={symbol}','Period=H4','Model=4','Optimization=0','ForwardMode=0','UseLocal=1','UseRemote=0','UseCloud=0',f'FromDate={a:%Y.%m.%d}',f'ToDate={b:%Y.%m.%d}','Deposit=3000','Currency=USD','Leverage=1:100','Visual=0',f'Report={report}','ReplaceReport=0','ShutdownTerminal=1',''])

def preset_text(original, risk_input=None):
    if any(re.search(r'password|token|secret|api.?key|^login$',line.split('=',1)[0],re.I) for line in original.splitlines() if '=' in line):
        raise PolicyError('Credential-like preset fields forbidden; keep authentication in terminal UI')
    if risk_input is None:
        return original, ['RISK_UNVERIFIED: no EA risk input mapping supplied']
    if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*',risk_input):
        raise PolicyError('Invalid EA input name')
    lines=original.splitlines()
    matched=[i for i,line in enumerate(lines) if line.split('=',1)[0].strip()==risk_input]
    if len(matched)!=1:
        raise PolicyError('DATA_MISSING: risk input not uniquely present in supplied preset')
    # Value in percent; user must confirm EA uses percent rather than fraction/money.
    lines[matched[0]]=risk_input+'=0.50'
    return '\n'.join(lines)+'\n', []
