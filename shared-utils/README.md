# shared-utils

Reusable utility scripts and skills shared across `indie-toolkit` plugins. Currently provides Notion API helpers and MongoDB query primitives; intended to grow as common cross-plugin needs emerge.

## Components

### Skills

- **notion-with-api** — Skill and scripts for authenticated Notion API operations (create/update pages, query databases). Migrated from the previous global `~/.claude/skills/notion-with-api`.

### Scripts

- **`scripts/mongo_query.py`** — CLI wrapper around `pymongo` for one-shot queries. Returns JSON on stdout.

## Cross-Plugin Invocation

Plugins installed via the `indie-toolkit` marketplace live at:

```
~/.claude/plugins/cache/indie-toolkit/<plugin>/
```

Sibling plugins can call shared-utils scripts using either a relative path or the absolute install path.

From another plugin's agent (preferred):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/../shared-utils/scripts/mongo_query.py" \
  --uri "$MONGO_URI" \
  --db health \
  --collection metrics \
  --filter '{"date": {"$gte": "2026-01-01"}}' \
  --limit 100
```

Fallback absolute path (works even when `CLAUDE_PLUGIN_ROOT` is unset, e.g. during local dev):

```bash
python3 ~/.claude/plugins/cache/indie-toolkit/shared-utils/scripts/mongo_query.py ...
```

## Dependency

Install order: plugins depending on `shared-utils` must have `shared-utils` installed in the same marketplace. There is no formal `plugin.json` `depends` field yet; declare the requirement in each consumer plugin's README.

## Scripts

### `mongo_query.py`

```
usage: mongo_query.py [-h] --uri URI --db DB --collection COLLECTION
                      [--filter FILTER] [--projection PROJECTION]
                      [--sort SORT] [--limit LIMIT]

Query a MongoDB collection and print results as JSON.

required arguments:
  --uri URI             MongoDB connection string
  --db DB               Database name
  --collection COLL     Collection name

optional arguments:
  --filter FILTER       JSON filter document (default: {})
  --projection PROJ     JSON projection document (default: null)
  --sort SORT           JSON sort spec (default: null)
  --limit LIMIT         Max documents to return (default: 100)
```

Returns a JSON array on stdout. Non-zero exit on connection failure or invalid JSON.

Requires `pymongo[srv]`. Install at the plugin level: `pip3 install pymongo[srv]`.
