"""Windows-only compilation and sequential, isolated historical testing."""
import json, os, platform, shutil, subprocess, time, uuid, re, hashlib
from datetime import datetime, timezone
from pathlib import Path
from .config import tester_ini, preset_text
from .security import PolicyError, scoped, redact

class Worker:
    def __init__(self, root):
        self.root = Path(root).resolve()

    def settings(self):
        p = scoped(self.root,'worker.json',exists=True)
        c = json.loads(p.read_text(encoding='utf-8-sig'))
        if c.get('dedicated_installation') is not True:
            raise PolicyError('Dedicated portable MT5 installation must be explicitly confirmed')
        for k in ('terminal','metaeditor'):
            p = scoped(self.root,c[k],exists=True)
            if p.suffix.lower() != '.exe': raise PolicyError('Expected Windows executable')
            c[k]=p
        c['data_dir']=scoped(self.root,c['data_dir'],exists=True)
        # /portable makes terminal folder its data directory; do not touch interactive installation.
        if c['terminal'].parent != c['data_dir']:
            raise PolicyError('Dedicated portable terminal and data_dir must coincide')
        if c['metaeditor'].parent != c['data_dir']:
            raise PolicyError('Use MetaEditor from the dedicated installation')
        return c

    def windows(self):
        if platform.system() != 'Windows':
            raise PolicyError('WINDOWS_ACTION_REQUIRED: no MT5 connected in this host')

    def process(self, args, *, timeout, cancel):
        self.windows()
        if not 1 <= timeout <= 7200: raise PolicyError('Timeout must be 1..7200 seconds')
        p=subprocess.Popen([str(a) for a in args],cwd=str(self.root),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        deadline=time.monotonic()+timeout
        while p.poll() is None:
            if cancel.is_set() or time.monotonic() > deadline:
                subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],capture_output=True,check=False)
                p.wait(timeout=15)
                raise TimeoutError('Cancelled' if cancel.is_set() else 'Worker timeout')
            time.sleep(.2)
        return p.returncode

    def compile(self, source, *, cancel, timeout=120):
        self.windows(); c=self.settings()
        src=scoped(self.root,source,exists=True)
        if src.suffix.lower()!='.mq5': raise PolicyError('Expected .mq5 input')
        run=scoped(self.root,'outputs/'+uuid.uuid4().hex);run.mkdir(parents=True)
        # Copy the source tree so fresh output cannot overwrite a user's EX5.
        if not src.is_relative_to(self.root/'sources'): raise PolicyError('Source must be under workspace/sources')
        source_files=list(src.parent.rglob('*'))
        if any(p.is_symlink() for p in source_files): raise PolicyError('Source tree symlinks forbidden')
        if len(source_files)>5000 or sum(p.stat().st_size for p in source_files if p.is_file())>64*1024*1024:
            raise PolicyError('Compile source tree bounded to 5000 entries / 64 MiB')
        build=run/'source';shutil.copytree(src.parent,build,ignore=shutil.ignore_patterns('*.ex5','*.log','.git'))
        target=build/src.name; log=target.with_suffix('.log');started=time.time()
        ensure_closed(c['metaeditor'])
        rc=self.process([c['metaeditor'],f'/compile:{target}','/log',f'/include:{c["data_dir"] / "MQL5"}'],timeout=timeout,cancel=cancel)
        text=read_log(log)
        diagnostics=[line for line in text.splitlines() if re.search(r'error|warning|result',line,re.I)]
        ex5=target.with_suffix('.ex5')
        summary=re.search(r'\b0 errors?\b',text,re.I)
        good=bool(summary and ex5.exists() and ex5.stat().st_size>0 and ex5.stat().st_mtime>=started-2)
        result={'status':'COMPILED' if good else 'FAILED','returncode':rc,'diagnostics':diagnostics,'log':str(log.relative_to(self.root)),'ex5':str(ex5.relative_to(self.root)) if good else None}
        (run/'compile.json').write_text(json.dumps(result,indent=2), encoding='utf-8')
        if not good: raise RuntimeError(json.dumps(result))
        return result

    def smoke(self, ex5, preset, aliases, *, cancel, start='2025-01-01',end='2025-02-01',risk_input=None,timeout=1800):
        self.windows(); c=self.settings()
        if set(aliases) != {'EURUSD','NAS100'} or len(set(aliases.values())) != 2:
            raise PolicyError('Supply distinct discovered EURUSD and NAS100 broker aliases')
        ea=scoped(self.root,ex5,exists=True);ps=scoped(self.root,preset,exists=True)
        if ea.suffix.lower()!='.ex5' or ps.suffix.lower()!='.set': raise PolicyError('EA EX5 and SET required')
        if ea.stat().st_size==0: raise PolicyError('Empty EA binary')
        if not 1 <= timeout <= 7200: raise PolicyError('Invalid tester timeout')
        original=read_log(ps);prepared,warnings=preset_text(original,risk_input)
        for alias in aliases.values():
            tester_ini(expert='validation.ex5',symbol=alias,start=start,end=end,report='validation',preset='validation.set')
        # Verify demo identity via Python API before starting tester. No account credentials in INI.
        from .export import broker_session
        with broker_session(c['terminal'], require_demo=True, owned=True) as mt5:
            account=mt5.account_info();terminal=mt5.terminal_info()
            for alias in aliases.values():
                if mt5.symbol_info(alias) is None: raise PolicyError('Broker alias not found')
            identity={'broker':account.company,'server':account.server,'build':terminal.build,'trade_mode':account.trade_mode}
        runid=uuid.uuid4().hex;out=scoped(self.root,'outputs/'+runid);out.mkdir(parents=True)
        settings={'run_id':runid,'start':start,'end':end,'aliases':aliases,'period':'H4','deposit':3000,'currency':'USD','leverage':'1:100','model':4,'optimization':False,'visual':False,'risk_input':risk_input,'identity':identity,'status':'INCONCLUSIVE','ea_sha256':hashlib.sha256(ea.read_bytes()).hexdigest(),'preset_sha256':hashlib.sha256(prepared.encode()).hexdigest(),'warnings':warnings+['DATA_MISSING: EA-specific audit schema and verified marker semantics'],'assets':[]}
        (out/'manifest.json').write_text(json.dumps(settings,indent=2), encoding='utf-8')
        expert='research_'+runid+'.ex5';presetname='research_'+runid+'.set'
        dst=scoped(self.root,str((c['data_dir']/'MQL5'/'Experts'/expert).relative_to(self.root)));dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ea,dst)
        dstps=scoped(self.root,str((c['data_dir']/'MQL5'/'Profiles'/'Tester'/presetname).relative_to(self.root)));dstps.parent.mkdir(parents=True,exist_ok=True)
        dstps.write_text(prepared,encoding='utf-16')
        try:
            for asset in ('EURUSD','NAS100'):
                alias=aliases[asset]
                if cancel.is_set(): raise TimeoutError('Cancelled')
                report='research_'+runid+'_'+asset
                config=out/(asset+'.ini')
                config.write_text(tester_ini(expert=expert,symbol=alias,start=start,end=end,report=report,preset=presetname),encoding='utf-16')
                started=time.time()
                ensure_closed(c['terminal'])
                rc=self.process([c['terminal'],'/portable',f'/config:{config}'],timeout=timeout,cancel=cancel)
                assetdir=out/asset;assetdir.mkdir()
                reports=list(c['data_dir'].glob(report+'*'))
                fresh=[p for p in reports if p.resolve().is_relative_to(self.root) and p.is_file() and p.suffix.lower() in ('.htm','.html','.xml','.png','.gif') and p.stat().st_mtime>=started-2]
                for p in fresh: shutil.copy2(p,assetdir/p.name)
                logs=0
                for folder in (c['data_dir']/'logs',c['data_dir']/'Tester',c['data_dir']/'MQL5'/'Files'):
                    if folder.exists():
                        for p in folder.rglob('*'):
                            if p.resolve().is_relative_to(self.root) and p.is_file() and p.stat().st_mtime>=started-2 and p.suffix.lower() in ('.log','.csv','.json'):
                                rel=p.relative_to(c['data_dir']);dest=assetdir/'evidence'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
                                # Logs could contain identifying/account information; only local artifacts.
                                shutil.copy2(p,dest);logs+=1
                evidence={'asset':asset,'alias':alias,'returncode':rc,'fresh_report':bool(fresh),'evidence_files':logs,'status':'INCONCLUSIVE'}
                settings['assets'].append(evidence)
                if rc!=0: raise RuntimeError('Tester process returned nonzero status '+str(rc))
                if not any(p.suffix.lower() in ('.htm','.html') for p in fresh): raise RuntimeError('No fresh tester report: configuration/history/tester failure')
                settings['warnings'].append(asset+': verify report settings, real-tick coverage, deals and EA audits; no performance validation asserted')
                try:
                    from .export import export
                    from .charts import chart
                    exported=export(self.root,c['terminal'],alias,start+'T00:00:00+00:00',end+'T00:00:00+00:00',cancel=cancel,output=str((assetdir/'market-data').relative_to(self.root)))
                    prefix=str((assetdir/'market-data').relative_to(self.root))
                    plotted=chart(self.root,prefix+'/H4.csv',prefix+'/D1.csv',output=str((assetdir/'charts').relative_to(self.root)),cancel=cancel)
                    evidence['export']=exported['quality'];evidence['charts']=plotted
                except Exception as e:
                    settings['warnings'].append(asset+': DATA_MISSING export/chart: '+redact(str(e)))
                (out/'manifest.json').write_text(json.dumps(settings,indent=2), encoding='utf-8')
        except Exception as e:
            settings['status']='CANCELLED' if cancel.is_set() else 'MECHANICAL_FAILURE'
            settings['error']=redact(str(e))
            raise
        finally:
            dst.unlink(missing_ok=True);dstps.unlink(missing_ok=True)
            (out/'manifest.json').write_text(json.dumps(settings,indent=2), encoding='utf-8')
        return {'output':str(out.relative_to(self.root)),'status':'INCONCLUSIVE','manifest':settings}


def read_log(path):
    if not Path(path).exists(): return ''
    raw=Path(path).read_bytes()
    return raw.decode('utf-16' if raw.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8',errors='replace')


def ensure_closed(executable):
    """Check exact dedicated executable; never kill a pre-existing session."""
    # Path passed as an environment value rather than executable PowerShell source.
    env=dict(os.environ);env['MT5_CHECK_EXECUTABLE']=str(Path(executable).resolve())
    script="$p=$env:MT5_CHECK_EXECUTABLE; $x=@(Get-CimInstance Win32_Process -ErrorAction Stop | Where-Object { $_.ExecutablePath -eq $p }); if ($x.Count -gt 0) { exit 10 }"
    result=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],env=env,capture_output=True,timeout=20)
    if result.returncode != 0:
        raise PolicyError('Dedicated executable already running or process inspection failed; close that dedicated application first')
