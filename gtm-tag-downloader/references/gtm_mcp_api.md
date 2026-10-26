# GTM MCP Server API Reference

The `gtm-mcp-server` exposes GTM operations via the Model Context Protocol (MCP). For downloading tag configurations and their associated assets, the primary tools are `gtm_tag`, `gtm_trigger`, and `gtm_variable`.

---

## 1. Tool: `gtm_tag`

### Action: `get`
Fetches a single tag by its unique numeric ID.

**Arguments:**
```json
{
  "action": "get",
  "accountId": "2046984759",
  "containerId": "7951148",
  "workspaceId": "273",
  "tagId": "2"
}
```

### Action: `list`
Lists tags in a workspace with pagination.

**Arguments:**
```json
{
  "action": "list",
  "accountId": "2046984759",
  "containerId": "7951148",
  "workspaceId": "273",
  "page": 1,
  "itemsPerPage": 20
}
```

---

## 2. Tool: `gtm_trigger`

Fetches trigger definitions referenced in `firingTriggerId` or `blockingTriggerId`.

### Action: `get`
**Arguments:**
```json
{
  "action": "get",
  "accountId": "2046984759",
  "containerId": "7951148",
  "workspaceId": "273",
  "triggerId": "511"
}
```

**Key Response Fields:**
- `triggerId`: Unique trigger ID string.
- `name`: Trigger display name (e.g. `CE - request_callback`).
- `type`: Trigger type (e.g. `customEvent`, `pageview`, `click`).
- `customEventFilter` / `filter`: Condition parameters which may also reference `{{variable_name}}`.

---

## 3. Tool: `gtm_variable`

Fetches user-defined variable configurations.

### Action: `list`
Lists variables with pagination. Used to match referenced variable names.

**Arguments:**
```json
{
  "action": "list",
  "accountId": "2046984759",
  "containerId": "7951148",
  "workspaceId": "273",
  "page": 1,
  "itemsPerPage": 20
}
```

**Key Response Fields:**
- `variableId`: Unique variable ID string.
- `name`: Display name matching `{{name}}` references.
- `type`: Variable type (e.g. `v` for Data Layer, `c` for Constant, `jsm` for Custom JS).
- `parameter`: Variable configuration parameters.

### Action: `get`
Fetches a single variable by ID.
```json
{
  "action": "get",
  "accountId": "2046984759",
  "containerId": "7951148",
  "workspaceId": "273",
  "variableId": "430"
}
```

---

## 4. Rate Limits & Quotas
- The GTM API enforces queries-per-minute limits.
- If a `Google API Error 429 - Quota exceeded` error is encountered, wait briefly before retrying.
- Use `action: "list"` with pagination to batch retrieve variables rather than firing dozens of individual `get` requests.
