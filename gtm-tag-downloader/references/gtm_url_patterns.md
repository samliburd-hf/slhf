# GTM URL Patterns Reference

Google Tag Manager URLs follow standard structures. The `gtm-tag-downloader` skill parses these URLs to extract the required IDs: `accountId`, `containerId`, `workspaceId`, and optionally `tagId`.

---

## 1. Supported GTM URL Patterns

### Workspace URL (Most Common)
```text
https://tagmanager.google.com/#/container/accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}
```
**Example:**
`https://tagmanager.google.com/#/container/accounts/2046984759/containers/7951148/workspaces/273`
- `accountId`: `2046984759`
- `containerId`: `7951148`
- `workspaceId`: `273`

### Tags List URL
```text
https://tagmanager.google.com/#/container/accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}/tags
```

### Direct Tag Detail URL
```text
https://tagmanager.google.com/#/container/accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}/tags/{tagId}
```
**Example:**
`https://tagmanager.google.com/#/container/accounts/2046984759/containers/7951148/workspaces/273/tags/2`
- `accountId`: `2046984759`
- `containerId`: `7951148`
- `workspaceId`: `273`
- `tagId`: `2`

### URL with Query Parameters (e.g. `authuser`)
```text
https://tagmanager.google.com/?authuser=0#/container/accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}
```
Query parameters preceding or following the hash fragment do not affect extraction.

### API Resource Path (Relative)
```text
accounts/{accountId}/containers/{containerId}/workspaces/{workspaceId}/tags/{tagId}
```

---

## 2. Extraction Regex

- **Account ID**: `accounts/(?P<accountId>\d+)`
- **Container ID**: `containers/(?P<containerId>\d+)`
- **Workspace ID**: `workspaces/(?P<workspaceId>\d+)`
- **Tag ID**: `tags/(?P<tagId>\d+)`

All IDs in the GTM REST API are treated as strings of digits.
