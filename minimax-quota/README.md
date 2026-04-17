# minimax-quota Plugin

MiniMax coding plan quota checker using official OpenAPI Bearer token authentication.

## Install

```bash
/plugin install minimax-quota@indie-toolkit
```

## Skill

| Skill | Description |
|---|---|
| `/minimax-coding-plan` | Query MiniMax coding-plan remains using `MINIMAX_API_KEY` |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `MINIMAX_API_KEY` | Yes | MiniMax OpenAPI API key from platform.minimaxi.com |
| `MINIMAX_GROUP_ID` | No | Group ID; uses account default if not set |
| `MINIMAX_OUTPUT` | No | Set to `json` for raw JSON output |

## API

- Endpoint: `GET https://www.minimaxi.com/v1/token_plan/remains`
- Auth: `Authorization: Bearer <API Key>`
