"""Optional external OAuth resource server; no local credential is exported."""
import asyncio, os
import jwt
from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings

class Verifier:
    def __init__(self, issuer, audience, jwks):
        if not all(x.startswith('https://') for x in (issuer,audience,jwks)):
            raise ValueError('OAuth issuer, resource and JWKS must use HTTPS')
        self.issuer=issuer;self.audience=audience;self.keys=jwt.PyJWKClient(jwks)

    async def verify_token(self, token):
        try:
            key=await asyncio.to_thread(self.keys.get_signing_key_from_jwt,token)
            claims=jwt.decode(token,key.key,algorithms=['RS256','ES256'],issuer=self.issuer,audience=self.audience,options={'require':['exp','iss','aud','sub']})
            scopes=claims.get('scope','').split()
            if 'mt5:research' not in scopes: return None
            return AccessToken(token=token,client_id=str(claims.get('client_id',claims['sub'])),subject=claims['sub'],scopes=scopes,expires_at=int(claims['exp']),resource=self.audience)
        except Exception:
            return None


def oauth_settings():
    from urllib.parse import urlsplit
    issuer=os.environ.get('MT5_OAUTH_ISSUER','');audience=os.environ.get('MT5_OAUTH_RESOURCE','');jwks=os.environ.get('MT5_OAUTH_JWKS','')
    if not any((issuer,audience,jwks)): return {}
    if not all((issuer,audience,jwks)): raise ValueError('All OAuth settings required')
    verifier=Verifier(issuer,audience,jwks)
    u=urlsplit(audience)
    if u.username or u.password or not u.hostname: raise ValueError('Invalid resource URL')
    return {'token_verifier':verifier,'auth':AuthSettings(issuer_url=issuer,resource_server_url=audience,required_scopes=['mt5:research'],validate_token_resource=True),'transport_security':TransportSecuritySettings(enable_dns_rebinding_protection=True,allowed_hosts=['127.0.0.1:*','localhost:*',u.netloc],allowed_origins=[f'https://{u.netloc}'])}
