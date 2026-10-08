"""Discover real schemas; forward only operator-reviewed read/research tools."""
import json, os
from urllib.parse import urlsplit
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from .security import PolicyError, redact, scoped

CATEGORIES = {'inspect', 'export', 'source_read', 'compile', 'tester', 'report', 'journal', 'chart'}
# Names from official capabilities documentation, checked 2026-10-08.
# Website names are only candidates; installed schemas must still confirm them.
KNOWN = {
 'get_workspace_info':'inspect','get_time_information':'inspect',
 'get_trading_account_info':'inspect','get_marketwatch_symbols':'inspect',
 'get_expert_advisor_parameters':'inspect','list_available_expert_advisors':'inspect',
 'get_chart_history':'export','get_chart_ticks_history':'export',
 'read_file':'source_read','read_file_by_lines':'source_read',
 'list_directory':'source_read','find_files_by_glob':'source_read',
 'compile_file':'compile',
 'tester_get_status':'tester','tester_get_configuration':'tester',
 'tester_get_report':'report','get_terminal_journal':'journal',
 'get_expert_journal':'journal','get_tester_journal':'journal',
 'chart_get_indicator_state':'chart','list_open_charts':'inspect',
}
REQUIRED = {'inspect', 'export', 'compile', 'tester', 'report', 'journal'}

class Native:
    def __init__(self, root):
        self.root = root

    def policy(self):
        p = scoped(self.root, 'native-policy.json')
        return json.loads(p.read_text()) if p.exists() else {}

    async def request(self, endpoint, name=None, arguments=None):
        if endpoint not in ('terminal','editor'):
            raise PolicyError('Unknown endpoint')
        url = os.environ.get(f'MT5_{endpoint.upper()}_URL', '')
        token = os.environ.get(f'MT5_{endpoint.upper()}_TOKEN', '')
        u = urlsplit(url)
        if u.hostname not in ('localhost', '127.0.0.1', '::1') or u.scheme not in ('http','https') or u.username or u.password or u.query or u.fragment:
            raise PolicyError('Native endpoint must be a copied loopback URL without credentials')
        if not token:
            raise PolicyError('Native bearer credential missing; set locally')
        async with streamablehttp_client(url, headers={'Authorization': f'Bearer {token}'}) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                actual = {t.name:t for t in (await session.list_tools()).tools}
                policy = self.policy().get(endpoint, {})
                enabled = {n:p for n,p in policy.items() if n in actual and p.get('category') == KNOWN.get(n) and p.get('category') in CATEGORIES and p.get('reviewed') is True}
                blocked={n:'Bounded native export adapter required' for n,p in enabled.items() if p['category']=='export'}
                blocked.update({n:'Scoped path mapping required' for n,p in enabled.items() if p['category'] in {'source_read','compile'} and not p.get('path_fields')})
                enabled={n:p for n,p in enabled.items() if n not in blocked}
                if name is None:
                    return redact({'endpoint':endpoint,'schemas':[t.model_dump() for t in actual.values()], 'enabled':list(enabled), 'adapter_required':blocked, 'missing_categories':sorted(REQUIRED - {p['category'] for p in enabled.values()}), 'missing_tools':sorted(set(policy)-set(actual))})
                if name not in enabled:
                    raise PolicyError('Tool not explicitly reviewed and allowed')
                p = enabled[name]
                # Generic forwarding is limited to inspect/read/report/journal/chart. Mutations
                # and exports need a specific schema adapter to validate paths and bounds.
                if p['category'] not in {'inspect','source_read','compile','tester','report','journal','chart'}:
                    raise PolicyError('Schema-specific bounded adapter required; use fallback jobs')
                args = arguments or {}
                allowed = p.get('fixed_arguments', {})
                if args != allowed:
                    raise PolicyError('Only operator-reviewed fixed arguments are permitted')
                paths=p.get('path_fields',{})
                if p['category'] in {'source_read','compile'} and not paths:
                    raise PolicyError('Schema-specific scoped path_fields mapping required')
                for field,kind in paths.items():
                    if field not in args or not isinstance(args[field],str): raise PolicyError('Mapped path missing')
                    target=scoped(self.root,args[field],exists=True)
                    if kind=='source':
                        from pathlib import Path
                        if not target.is_relative_to(Path(self.root).resolve()/'sources'):
                            raise PolicyError('Source path outside sources directory')
                        if target.is_file() and target.suffix.lower() not in {'.mq5','.mqh'}: raise PolicyError('Only MQL5 source reads/compilation')
                    elif kind=='output':
                        from pathlib import Path
                        if not target.is_relative_to(Path(self.root).resolve()/'outputs'): raise PolicyError('Output path outside outputs')
                    else: raise PolicyError('Unknown scoped path kind')
                import jsonschema
                jsonschema.validate(args, actual[name].inputSchema)
                return redact((await session.call_tool(name, args)).model_dump())
