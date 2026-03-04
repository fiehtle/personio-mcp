# Personio Public MCP (Render)

This project turns Personio v2 API endpoints into one hosted MCP server using FastMCP and streamable HTTP transport.

## What it does

- Pulls all Personio v2 OpenAPI registries from the Personio Developer Hub metadata.
- Merges them into a single OpenAPI file (`specs/personio-v2-openapi.json`).
- Auto-generates MCP tools for all merged API operations via `FastMCP.from_openapi`.
- Handles Personio OAuth token lifecycle using `PERSONIO_CLIENT_ID` and `PERSONIO_CLIENT_SECRET`.
- Exposes manual auth tools for token/revoke/cache control.

## Project structure

- `scripts/sync_personio_openapi.py`: fetches and merges Personio OpenAPI specs.
- `scripts/generate_tool_catalog.py`: generates endpoint-to-tool markdown catalog.
- `src/server.py`: FastMCP server + Personio auth integration.
- `src/tool_naming.py`: semantic operation-to-tool naming map used by FastMCP.
- `render.yaml`: Render web service definition.

## Local run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/sync_personio_openapi.py --output specs/personio-v2-openapi.json
python scripts/generate_tool_catalog.py --spec specs/personio-v2-openapi.json --output docs/personio-tool-catalog.md

export PERSONIO_CLIENT_ID="your-client-id"
export PERSONIO_CLIENT_SECRET="your-client-secret"
export PERSONIO_APP_ID="PERSONIO_MCP"
export PERSONIO_PARTNER_ID="YOUR_PARTNER"

python src/server.py
```

Then connect an MCP client to:

- `http://localhost:8000/mcp`
- transport: `Streamable HTTP`

## Render deployment

1. Push this repo to GitHub.
2. Create a new Render Web Service from the repo.
3. Render will use `render.yaml`.
4. Set secret env vars in Render:
   - `PERSONIO_CLIENT_ID`
   - `PERSONIO_CLIENT_SECRET`
5. Deploy.

Your public MCP endpoint will be:

- `https://<your-render-service>.onrender.com/mcp`

## Env vars

- `PERSONIO_CLIENT_ID` (required)
- `PERSONIO_CLIENT_SECRET` (required)
- `PERSONIO_BASE_URL` (default: `https://api.personio.de`)
- `PERSONIO_OPENAPI_PATH` (default: `specs/personio-v2-openapi.json`)
- `PERSONIO_HTTP_TIMEOUT_SECONDS` (default: `30`)
- `PERSONIO_TOKEN_REFRESH_BUFFER_SECONDS` (default: `60`)
- `PERSONIO_DEFAULT_SCOPE` (optional)
- `PERSONIO_APP_ID` (default: `PERSONIO_MCP`)
- `PERSONIO_PARTNER_ID` (optional but recommended by Personio)
- `PERSONIO_ALLOW_TOKEN_EXPOSURE` (default: `false`)

## Notes

- Auth paths (`/v2/auth/token`, `/v2/auth/revoke`) are implemented as manual MCP tools because OpenAPI auto-tools in FastMCP currently send JSON request bodies, while Personio auth endpoints require `application/x-www-form-urlencoded`.
- The merged spec is generated at build time by `render.yaml` and can be refreshed any time with the sync script.
- Tool names are rewritten to semantic names (for example `list_persons`, `get_person`, `list_webhooks`) via `mcp_names` for better AI-assistant tool selection.
