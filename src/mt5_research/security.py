import os
from pathlib import Path

class PolicyError(ValueError):
    pass


def scoped(root, path, *, exists=False):
    root = Path(root).resolve()
    result = (root / path).resolve()
    if not result.is_relative_to(root) or result == root:
        raise PolicyError("Path must be a child of the research workspace")
    # Refuse Windows alternate streams and ambiguous device paths, also on Linux.
    if ':' in str(path).removeprefix(Path(path).drive):
        raise PolicyError("Alternate streams are forbidden")
    if exists and not result.exists():
        raise PolicyError("DATA_MISSING: requested input does not exist")
    return result


def redact(value):
    secrets = [os.environ.get(k, '') for k in ('MT5_TERMINAL_TOKEN', 'MT5_EDITOR_TOKEN', 'MT5_GATEWAY_TOKEN')]
    if isinstance(value, dict):
        return {k: '[REDACTED]' if any(s in k.lower() for s in ('authorization','password','token','secret')) else redact(v) for k,v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        for secret in secrets:
            if secret:
                value = value.replace(secret, '[REDACTED]')
    return value
