# mcp-schema-audit

**Audit recorded MCP listings for wire shapes that make clients silently reject tools. Offline, deterministic, zero dependencies.**

MCP servers publish broken tool listings in ways that are invisible server-side: the
endpoint returns 200, no log fires — the failure happens entirely in the client's
validation:

- `inputSchema: {}` → **every client rejects the listing**
  ([gitlab-mcp #286](https://github.com/zereight/gitlab-mcp/issues/286))
- a dropped schema is replaced with `{}` and the model reverse-engineers arguments one
  failed call at a time ([prime-agent #1073](https://github.com/PrimeIntellect-ai/prime-agent/issues/1073))
- root without `type: "object"` (z.intersection → `allOf`) → Claude Code **silently drops**
  the tools ([langfuse #13804](https://github.com/langfuse/langfuse/issues/13804))
- draft-07 dialect with tuple `items: [...]` → strict 2020-12 clients reject **everything**
  ([strapi #27395](https://github.com/strapi/strapi/issues/27395), upstream TS SDK #2084 P1 for 3 months)
- protocol version negotiation chaos: hardcoded versions
  ([mcpkit #12](https://github.com/panyam/mcpkit/issues/12)), echoing a modern-era
  version through the legacy handshake
  ([go-sdk #1033](https://github.com/modelcontextprotocol/go-sdk/issues/1033)),
  hard-error instead of negotiating down ([ferrum-edge #2168](https://github.com/ferrum-edge/ferrum-edge/issues/2168)),
  hanging on initialize ([stripe #290](https://github.com/stripe/ai/issues/290))

Quality linters (mcp-schema-lint, mcp-assert) grade descriptions and naming. This tool
checks the shapes that make clients REJECT tools outright.

## What it detects

| Severity | Finding |
|---|---|
| CRITICAL | `inputSchema` missing or `{}` |
| CRITICAL | root `type` not `"object"` (incl. `allOf` intersections) |
| CRITICAL | draft-07 dialect with tuple syntax (2020-12 incompatible) |
| CRITICAL | duplicate tool names / unnamed tools |
| CRITICAL | negotiated protocolVersion is not a known MCP revision |
| WARNING  | initialize without serverInfo.name / draft-07 without tuples |
| WARNING  | empty tools listing / no initialize in the recording |
| INFO     | version renegotiated (legal, worth confirming intent) |

## Input format

JSONL of recorded MCP messages (same format as mcp-session-audit):

```jsonl
{"direction":"request","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25"}}
{"direction":"response","id":1,"result":{"protocolVersion":"2025-11-25","serverInfo":{"name":"srv","version":"1.0"}}}
{"direction":"response","id":2,"result":{"tools":[{"name":"search","inputSchema":{"type":"object","properties":{}}}]}}
```

## Usage

```
python3 mcp_schema_audit.py recording.jsonl
```

Exit codes (CI-friendly): **0** clean · **1** warnings · **2** any CRITICAL.

MIT License.
