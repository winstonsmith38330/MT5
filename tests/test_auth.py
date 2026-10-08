import asyncio,time
from types import SimpleNamespace
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from mt5_research.auth import Verifier,oauth_settings
import pytest


def test_oauth_signature_scope_expiry_audience(monkeypatch):
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    v=Verifier('https://issuer.example','https://gateway.example/mcp','https://issuer.example/jwks')
    monkeypatch.setattr(v.keys,'get_signing_key_from_jwt',lambda _:SimpleNamespace(key=key.public_key()))
    claims={'iss':v.issuer,'aud':v.audience,'sub':'operator','scope':'mt5:research','exp':int(time.time())+60}
    def verify(c):return asyncio.run(v.verify_token(jwt.encode(c,key,algorithm='RS256')))
    assert verify(claims).resource==v.audience
    assert verify({**claims,'scope':'other'}) is None
    assert verify({**claims,'aud':'https://other.example'}) is None
    assert verify({**claims,'exp':int(time.time())-60}) is None
    wrong=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    assert asyncio.run(v.verify_token(jwt.encode(claims,wrong,algorithm='RS256'))) is None


def test_oauth_settings_fail_closed(monkeypatch):
    for n in ['ISSUER','RESOURCE','JWKS']:monkeypatch.delenv('MT5_OAUTH_'+n,raising=False)
    assert oauth_settings()=={}
    monkeypatch.setenv('MT5_OAUTH_ISSUER','https://issuer.example')
    with pytest.raises(ValueError):oauth_settings()
    monkeypatch.setenv('MT5_OAUTH_RESOURCE','https://gateway.example/mcp')
    monkeypatch.setenv('MT5_OAUTH_JWKS','https://issuer.example/jwks')
    settings=oauth_settings()
    assert settings['auth'].validate_token_resource and settings['transport_security'].enable_dns_rebinding_protection
