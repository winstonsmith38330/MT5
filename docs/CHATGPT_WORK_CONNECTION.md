# Hosted ChatGPT Work connection

A local Windows Codex connection and a hosted ChatGPT connection are different modes. Hosted ChatGPT cannot reach Nicolas's localhost by virtue of a GitHub connection. If the Work deployment already offers a verified local MCP connection to the dedicated terminal, discover its schemas and use that direct research-only connection; do not deploy a gateway solely because this template exists.

The supplied gateway combines restricted native forwarding with named compile/test/export/chart jobs; it never exposes a shell. Native bearer tokens are attached only on Windows when contacting copied loopback endpoints. They are not OAuth credentials for ChatGPT. Returned structured/text values redact the local tokens and secret-named fields. Debug/HTTP body logging must remain off. Account passwords remain with MT5.

## OpenAI Secure MCP Tunnel (preferred private deployment)

The [official Secure MCP Tunnel guide](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels), checked 2026-10-08, documents these commands and boundaries. Nothing has been deployed automatically.

1. In [Platform tunnel settings](https://platform.openai.com/settings/organization/tunnels), create/manage the actual tunnel. Creator needs Tunnels Read + Manage; operator/app creator needs Read + Use. These are organization-level permissions, separate from ChatGPT custom MCP permissions.
2. Associate the tunnel with the managing Platform organization **and the target ChatGPT Work workspace**, plus any organization that Codex/API use requires. A personal organization association alone is insufficient for a work workspace.
3. Download the latest official client using the link in Platform settings or [openai/tunnel-client releases](https://github.com/openai/tunnel-client/releases/latest), selecting a supported host binary. Do not invent a tunnel identity or install an unofficial binary. If no usable Windows binary is available, run the official client on a trusted reachable host with an authenticated route, or use the HTTPS mode below; WSL localhost reachability must be checked rather than assumed.
4. Configure its runtime key securely on the Windows host (`CONTROL_PLANE_API_KEY` per the guide), not in repository files. Example PowerShell secret entry:

```powershell
$secure = Read-Host 'Tunnel runtime API key' -AsSecureString
$env:CONTROL_PLANE_API_KEY = [System.Net.NetworkCredential]::new('', $secure).Password
$env:MT5_TUNNEL_ID = Read-Host 'Actual tunnel_id from Platform settings'
./tunnel-client.exe help quickstart
./tunnel-client.exe init --profile mt5-research --tunnel-id $env:MT5_TUNNEL_ID --mcp-server-url http://127.0.0.1:8765/mcp
./tunnel-client.exe doctor --profile mt5-research --explain
./tunnel-client.exe run --profile mt5-research
```

Place the downloaded executable outside the tracked tree or under ignored `local/`, and adjust `./tunnel-client.exe` to its actual location. `init` options should be confirmed with the installed release's quickstart; the official HTTP mode uses `--mcp-server-url` rather than `--mcp-command`. Keep the local gateway running in a second window. The client needs outbound HTTPS to `api.openai.com:443` (or `mtls.api.openai.com:443` for configured control-plane mTLS), plus local access to the gateway. No inbound public port is needed.

5. At [ChatGPT Plugins](https://chatgpt.com/plugins), plus → Add custom MCP server → Connection: Tunnel; select the associated tunnel or paste its real ID. Configure the supported authentication choice for this private server, review the product risk warning and create the plugin. Workspace restrictions may require an administrator. The default private gateway has no application OAuth: tunnel organization/workspace authorization is its remote boundary. Use that only where the supported private-tunnel connection flow permits it. If organizational policy requires per-user OAuth, enable the OAuth resource-server mode below and choose OAuth in the connection flow. Never treat a public unauthenticated URL as equivalent to this private mode.
6. From ChatGPT, run `health_check`, `discover_native`, then a bounded offline chart job and inspect its artifact. Verify Windows identity and DEMO scope before any compiler/tester/export job. If health says MOCK, the connection targets the cloud test instance rather than the Windows worker.

The client doctor/admin health surfaces prove transport, not broker readiness. Keep its run process healthy. If the tunnel is absent, check workspace association and Read + Use permissions; the guide notes permission propagation can take time. Do not invent links, IDs or account keys. Tunnel OAuth discovery does not automatically tunnel the identity provider itself. Private tunnel testing is distinct from public plugin submission/distribution.

## Authenticated HTTPS fallback

The gateway has an optional MCP SDK resource-server implementation with external OAuth JWT verification. It requires a real public authorization server/IdP supporting the target ChatGPT OAuth connection flow (discovery, user authorization, client registration or configured client credentials and appropriate resource/scopes). This repository does **not** provision an IdP or claim that an arbitrary JWT issuer is sufficient.

Set non-secret deployment values locally before starting the gateway:

```powershell
$env:MT5_OAUTH_ISSUER = Read-Host 'Actual HTTPS issuer URL'
$env:MT5_OAUTH_RESOURCE = Read-Host 'Actual HTTPS MCP resource URL (including /mcp)'
$env:MT5_OAUTH_JWKS = Read-Host 'Actual HTTPS JWKS URL'
./scripts/windows/Start-Gateway.ps1 -Workspace local
```

Run an administrator-managed TLS reverse proxy to loopback, preserving Authorization and MCP HTTP semantics. Do not bind the worker to all interfaces. The SDK publishes OAuth protected-resource metadata; it validates signed RS256/ES256 tokens, issuer, resource audience, expiry, subject and `mt5:research` scope. Host/origin rebinding protection remains enabled and includes only the configured public host plus loopback. Configure the IdP to issue exactly that resource/scope and configure the ChatGPT connection with the real OAuth client/redirect settings required by its UI. JWKS traffic uses normal TLS verification. Partial OAuth settings refuse startup.

This mode's signature/scope/audience/expiry handling is tested offline; the actual IdP, public DNS/certificate, reverse proxy, ChatGPT authorization and tunnel are **NOT RUN**. Keep them external prerequisites. No public listener, certificate or tunnel was created by cloud setup. Do not expose the default no-OAuth listener through a public reverse proxy.
