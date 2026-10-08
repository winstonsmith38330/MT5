import threading, time, uuid
from concurrent.futures import ThreadPoolExecutor
from .security import redact

class Jobs:
    """One Windows worker; queued tasks and cancellation are explicit."""
    def __init__(self):
        self.pool = ThreadPoolExecutor(max_workers=1)
        self.jobs = {}
        self.lock = threading.Lock()

    def submit(self, fn, **kwargs):
        with self.lock:
            if len(self.jobs) >= 100:
                raise ValueError('Job limit reached; restart gateway after collecting results')
            jid = uuid.uuid4().hex
            cancel = threading.Event()
            state = {'id':jid,'state':'QUEUED','created':time.time(),'cancel':cancel}
            self.jobs[jid] = state
        def run():
            if cancel.is_set():
                state['state'] = 'CANCELLED'; return
            state['state'] = 'RUNNING'
            try:
                state['result'] = redact(fn(cancel=cancel, **kwargs))
                state['state'] = 'CANCELLED' if cancel.is_set() else 'COMPLETED'
            except Exception as e:
                state['state'] = 'CANCELLED' if cancel.is_set() else 'FAILED'
                state['error'] = redact(f'{type(e).__name__}: {e}')
            finally:
                state['finished'] = time.time()
        self.pool.submit(run)
        return jid

    def status(self, jid):
        if jid not in self.jobs: raise ValueError('Unknown job ID')
        return redact({k:v for k,v in self.jobs[jid].items() if k != 'cancel'})

    def cancel(self, jid):
        if jid not in self.jobs: raise ValueError('Unknown job ID')
        self.jobs[jid]['cancel'].set()
        return {'id':jid,'cancel_requested':True}
