# GTM Tag Downloader Operational Rules & Invariants

## Scope
These operational directives govern all actions, script executions, and tool calls executed by agents using the `gtm-tag-downloader` skill.

---

## 1. Python Environment & Execution
- **Strict `uv` Requirement**: Always run Python commands, utilities, and helper scripts using `uv` (e.g., `uv run <path/to/script.py>`).
- **No Direct Python Invocations**: Never invoke bare `python` or `python3`.

## 2. GTM Resource Extraction & URL Validation
- **URL Decomposition**: Automatically parse GTM URLs to extract:
  - `accountId`
  - `containerId`
  - `workspaceId`
  - `tagId` (optional)
- **Pre-flight Validation**: Verify that `accountId`, `containerId`, and `workspaceId` are present before issuing any MCP tool calls. If missing, prompt the user for clarification.

## 3. Read-Only Safety & MCP Directives
- **Target Server**: `gtm-mcp-server`
- **Permitted Tools**: `gtm_tag`, `gtm_trigger`, `gtm_variable` (and `gtm_built_in_variable` where applicable).
- **Read-Only Invariant**: ONLY use read-only operations (`get`, `list`). NEVER execute mutations (`create`, `update`, `remove`, `revert`).
- **Tag Search by Name**: Use `gtm_tag` with `action: "list"` and paginate (`itemsPerPage: 20`) until found.
- **Rate Limit Defense**: When resolving referenced variables, ALWAYS prefer batch listing (`gtm_variable` `action: "list"`) over individual queries to avoid GTM API HTTP 429 quota exhaustion.

## 4. Associated Assets Mode
- **Conditional Trigger**: Execute only when the user explicitly requests dependencies, associated assets, triggers, or variables.
- **Trigger Extraction**: Read `firingTriggerId` and `blockingTriggerId` from the tag configuration, then fetch trigger details via `gtm_trigger`.
- **Variable Extraction**: Extract `{{...}}` variable references from tag configuration and triggers, and match against container variables.
- **Bundle Packaging**: Structure all assets in `tags/<tagId>_<sanitized_name>/` containing `tag.json`, `bundle.json`, `triggers/`, and `variables/`.

## 5. File Persistence & Presentation
- **Directory**: Always persist downloaded artifacts under `tags/` relative to workspace root.
- **JSON Formatting**: Format all saved JSON files with 2-space indentation.
- **Link Presentation**: Present results with clickable markdown links using the `file://` scheme (e.g., `[tag.json](file:///absolute/path/to/tags/...)`).
- **Privacy & Security**: Never commit or log authentication tokens, sensitive pixels, or client PII.
