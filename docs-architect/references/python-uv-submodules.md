# Python / `uv` Multi-Submodule Documentation Blueprint

Use this workflow whenever documenting a Python repository that contains multiple submodules, packages, or CLI entry points (e.g., `src/<module_a>/`, `src/<module_b>/`, or multiple `[project.scripts]` entries in `pyproject.toml`).

To defeat single-turn output compression, you MUST document each submodule in its own dedicated `docs/<module>.md` file first, format each file with `format_docs.py`, and then deterministically stitch them into `ARCHITECTURE.md` using `<!-- INCLUDE: docs/<module>.md -->` directives. **Keep all `docs/<module>.md` files in the repository.**

---

## Step-by-Step Execution Workflow

### Step 1: Full Repository & Submodule Inventory

1. Read `pyproject.toml`, `pyproject.json` (if present), `uv.lock`, `AGENTS.md` / `GEMINI.md`, and `README.md`.
2. Enumerate every package/submodule directory under `src/` (or top-level package directories) and read **every** `.py` file (`__init__.py`, `main.py`, helpers) in full.
3. Map:
   - How `[build-system]` (`uv_build`, `hatchling`, `setuptools`) and `[project.scripts]` bind CLI commands to `submodule:callable` or `submodule.main:callable`.
   - Why a root package namespace directory (e.g., `src/<project_name>/__init__.py`) exists alongside functional submodules (`src/dl/`, `src/hd/`, etc.), and why certain submodules place logic directly in `__init__.py` while others split `__init__.py` and `main.py`.

---

### Step 2: Generate `docs/<module>.md` for Each Submodule (One Dedicated Tool Call Per Submodule)

For **each** submodule in `src/` (excluding trivial 1–5 line root build-namespace stubs, which can be documented directly in `ARCHITECTURE.md` Section 5 or in their own `docs/<pkg>.md`), create `docs/<module>.md` using a **separate, dedicated `write_to_file` call per submodule** (or parallel subagents). Never batch multiple submodules into a single prose generation pass.

Each `docs/<module>.md` file MUST remain in the repository as a standalone reference manual and MUST follow this exact structure:

````markdown
# 5.X `<module>` Module — <Descriptive Title>

- **Source File(s)**: [`src/<module>/__init__.py`](../src/<module>/__init__.py) (Lines `1–N`)
- **CLI Entry Point**: `<cli_name> = "<module>:main"` (defined in [`pyproject.toml`](../pyproject.toml), Line `L`)
- **Architectural Role**: <1–2 paragraph summary of what the module does, its external library bindings, and its stdin/stdout/stderr & exit-code contract>

## Execution Flow (`<module>`)

```mermaid
sequenceDiagram
    ...
```
````

1. **<Step 1 Name>**: <Detailed walkthrough with line numbers...>
2. **<Step 2 Name>**: <Detailed walkthrough with line numbers...>
   ...

## Data Models, Constants, & State

| Symbol | Lines | Type / Value | Architectural Purpose |
| :----- | :---- | :----------- | :-------------------- |
| ...    | ...   | ...          | ...                   |

_(If the module has no classes, dataclasses, or module-level constants, explicitly state how state is passed between functions via `argparse.Namespace`, tuples, or dicts.)_

## Symbol & Function Inventory

| Symbol       | Lines   | Signature & Return Type    | Detailed Behavior & Side Effects |
| :----------- | :------ | :------------------------- | :------------------------------- |
| `parse_args` | `17–35` | `() -> argparse.Namespace` | ...                              |
| ...          | ...     | ...                        | ...                              |

_(If any logic runs at module top-level or inside a monolithic `main()`, list every function AND provide a line-by-line phase breakdown table covering 100% of the file's lines.)_

## CLI Flag & Option Mapping Matrix

| CLI Argument / Flag | `argparse` Config (`type`, `nargs`, `default`, `choices`, `action`) | Downstream Library / API Option & Internal Behavior |
| :------------------ | :------------------------------------------------------------------ | :-------------------------------------------------- |
| ...                 | ...                                                                 | ...                                                 |

## Internal Mechanics, Error Handling, & Signal Contract

- **<Mechanism 1 (e.g., Filter Graph / Bitrate Math / Collision Resolution)>**: <Deep explanation with exact formulas, option keys, and line numbers>
- **<Mechanism 2 (e.g., Subprocess / Async Lifecycle & Signal Handling)>**: <How `KeyboardInterrupt` / `SIGINT`, child process cleanup, and temp files are handled>
- **Stream & Exit-Code Contract**:
  - `stdout`: <Exact output emitted for shell pipelining>
  - `stderr`: <Progress, diagnostics, and error messages>
  - Exit Codes: `0` (<success>), `1` (<validation/runtime error>), `130` (<SIGINT / Ctrl+C>)

````

---

### Step 3: Format & Validate Each `docs/<module>.md`

Run `format_docs.py` on all generated `docs/<module>.md` files using `uv run python`:

```bash
uv run python /Users/samliburd/.gemini/config/skills/docs-architect/scripts/format_docs.py docs/*.md
````

- `format_docs.py` automatically normalizes relative links inside `docs/<module>.md` so they resolve accurately from `docs/` (e.g., `../src/<module>/__init__.py` and `../pyproject.toml`) and sanitizes all Mermaid diagrams.

---

### Step 4: Generate `ARCHITECTURE.md` with `<!-- INCLUDE: docs/<module>.md -->` Directives

Write the root `ARCHITECTURE.md` containing all 11 mandatory sections:

1. **Section 1 (Executive Summary)**:
   - Include a **CLI / Submodule Matrix** that links to **both** the source file (`[src/<module>/__init__.py](./src/<module>/__init__.py)`) **and** the dedicated module documentation (`[docs/<module>.md](./docs/<module>.md)`).
2. **Section 2 (Repository Layout)**:
   - Include `docs/` and each `docs/<module>.md` file in the Mermaid repository tree diagram alongside `src/` and root configuration files.
   - Explain the `src/` multi-package layout, why `src/<project_name>/__init__.py` exists for `uv_build`, and why individual submodules use `__init__.py` vs `main.py`.
3. **Section 3 (System Context)**:
   - Include a **Cross-Submodule Architecture & Contract Matrix** comparing all submodules across key architectural dimensions:
     `| Submodule | Entry Point | Core Engine | Config / Env Vars | Staging / Output Strategy | Process & Signal Model | Shared vs Divergent Behavior |`
   - Explicitly analyze behavioral divergences across submodules (e.g., why one module uses synchronous `.run()` while another wraps `.run_async()` with `SIGINT` re-signaling; differing default CRF/bitrate constants; `/tmp` staging vs direct destination write).
4. **Section 4 (Execution Flow)**:
   - Provide high-level system/cross-tool pipeline flows (e.g., how tools compose in Unix shell pipelines such as `dl` / `hd` / `jellypy` $\rightarrow$ `trim` / `twopass`) with Mermaid diagrams and numbered prose walkthroughs.
5. **Section 5 (Core Components)**:
   - **DO NOT re-type or summarize the submodules here.** Instead, place `<!-- INCLUDE: docs/<module>.md -->` directives in order:
     ```markdown
     ## 5. Core Components

     <!-- INCLUDE: docs/dl.md -->

     ---

     <!-- INCLUDE: docs/hd.md -->

     ---

     <!-- INCLUDE: docs/jellypy.md -->

     ---

     <!-- INCLUDE: docs/trim.md -->

     ---

     <!-- INCLUDE: docs/twopass.md -->
     ```
   - Any root namespace stub (such as `src/<project_name>/__init__.py`) can either be included via `<!-- INCLUDE: docs/<project_name>.md -->` or documented directly as the final `### 5.X` subsection.
6. **Sections 6–11**:
   - Complete **Design Decisions**, **Deployment & Environment**, **Security & Privacy**, **Performance Characteristics**, **Troubleshooting**, and **Appendices** (`Reading Paths` + `Glossary`) with comprehensive system-wide coverage.

---

### Step 5: Stitch, Format, & Validate `ARCHITECTURE.md`

Run `format_docs.py` on `ARCHITECTURE.md` using `uv run python`:

```bash
uv run python /Users/samliburd/.gemini/config/skills/docs-architect/scripts/format_docs.py ARCHITECTURE.md
```

When run on `ARCHITECTURE.md`, `format_docs.py` will deterministically:

1. Format each referenced `docs/<module>.md` file in place on disk (keeping `docs/<module>.md` in the repo with valid `../src/...` links).
2. Expand every `<!-- INCLUDE: docs/<module>.md -->` block verbatim into `ARCHITECTURE.md` (wrapped in idempotent `<!-- BEGIN INCLUDE: ... -->` / `<!-- END INCLUDE: ... -->` markers so future re-runs cleanly refresh the stitched sections).
3. Shift the heading levels of the stitched copy so `# 5.X ...` becomes `### 5.X ...` and `## ...` becomes `#### ...` inside `ARCHITECTURE.md`.
4. Rebase all relative file links in the stitched copy from `../src/...` to `./src/...` so every link works from the repository root.
5. Sanitize all Mermaid blocks and validate that all 11 sections exist, all Mermaid control blocks are balanced, and all relative links resolve to existing files on disk.
