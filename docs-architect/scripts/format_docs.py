#!/usr/bin/env python3
"""Deterministic post-processor, module stitcher, and validator for docs-architect.

Responsibilities:
1. Modular Include Stitching (`<!-- INCLUDE: docs/module.md -->`):
   - Expands `<!-- INCLUDE: path/to/file.md -->` (and idempotently refreshes
     `<!-- BEGIN INCLUDE: ... -->...<!-- END INCLUDE: ... -->` blocks).
   - Formats each included `docs/<module>.md` file in place on disk (with links valid
     relative to `docs/`).
   - Shifts Markdown heading levels in the stitched copy so module headings nest cleanly
     at `###` (H3) under `## 5. Core Components`, and rebases relative file links from
     `docs/` (`../src/...`) to the root architecture document (`./src/...`).
2. Mermaid Syntax Hardening:
   - sequenceDiagram: replaces statement-breaking semicolons (;) inside messages,
     notes, and block headers (alt/else/opt/loop/par/critical/break/rect) with commas.
   - flowchart / graph: wraps unquoted node labels, subgraph titles, and edge labels
     containing parser-sensitive characters ((), {}, [], /, ;, :, $, @, &, |, ") in
     double quotes, and converts nested double quotes inside quoted labels to single quotes.
3. Markdown Link Normalization (strictly outside fenced code blocks):
   - Strips accidental outer backticks around entire links: `[text](url)` -> [text](url).
   - Wraps file-path or underscore-containing link text in backticks for consistent
     monospace rendering and to prevent underscore italics corruption.
   - Resolves and normalizes relative file paths (`./` or `../`) against the filesystem.
4. Structural & Referential Validation:
   - Verifies balanced Mermaid block keywords (subgraph/alt/opt/loop/par/critical/break/rect vs end).
   - Verifies that relative file links resolve to existing paths relative to the document.
   - Verifies presence of the 11 mandatory sections on top-level architecture manuals.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

FENCED_BLOCK_RE = re.compile(r"(```[\s\S]*?```|~~~[\s\S]*?~~~)")
MERMAID_BLOCK_RE = re.compile(r"```mermaid[ \t]*\r?\n([\s\S]*?)```")

# Matches an already-expanded `<!-- BEGIN INCLUDE: path -->...<!-- END INCLUDE: path -->` block (which may span fenced code blocks)
BEGIN_END_INCLUDE_RE = re.compile(
    r"<!--[ \t]*BEGIN INCLUDE:[ \t]*([^\n]+?)[ \t]*-->[\s\S]*?<!--[ \t]*END INCLUDE:[ \t]*\1[ \t]*-->"
)
# Matches a fresh single-line `<!-- INCLUDE: path -->` directive
SINGLE_INCLUDE_RE = re.compile(r"<!--[ \t]*INCLUDE:[ \t]*([^\n]+?)[ \t]*-->")

# Characters inside an unquoted flowchart label that break Mermaid's lexer/parser
FLOWCHART_SPECIAL_CHARS = set('(){}[]/\\;:$@&|<>"')

# Node shape delimiters ordered from longest/most-specific to shortest
NODE_SHAPES: list[tuple[str, str]] = [
    ("([", "])"),
    ("[[", "]]"),
    ("[(", ")]"),
    ("((", "))"),
    ("{{", "}}"),
    ("[", "]"),
    ("(", ")"),
    ("{", "}"),
]

FLOWCHART_KEYWORDS = {
    "subgraph",
    "end",
    "direction",
    "classDef",
    "class",
    "style",
    "linkStyle",
    "click",
}

SEQ_BLOCK_HEADERS_RE = re.compile(
    r"^(\s*(?:alt|else|opt|loop|par|and|critical|option|break|rect)\b[ \t]*)(.+)$"
)
SEQ_NOTE_RE = re.compile(r"^(\s*Note\b[^:\n]*:[ \t]*)(.+)$", re.IGNORECASE)
SEQ_MESSAGE_RE = re.compile(
    r"^(\s*[^\n:]+?(?:<<->>|<<-->>|->>|-->>|->|-->|-x|--x|-\)|--\))[+-]?[ \t]*[^\n:]+?:[ \t]*)(.+)$"
)

FILE_EXTENSIONS = (
    ".py",
    ".pyi",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".cjs",
    ".json",
    ".toml",
    ".lock",
    ".yaml",
    ".yml",
    ".md",
    ".rst",
    ".txt",
    ".sh",
    ".bash",
    ".zsh",
    ".fish",
    ".tex",
    ".sty",
    ".cls",
    ".bib",
    ".bst",
    ".latexmkrc",
    ".css",
    ".scss",
    ".html",
    ".svg",
    ".sql",
    ".rs",
    ".go",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".java",
    ".kt",
    ".swift",
    ".rb",
    ".lua",
    ".vim",
    ".dockerfile",
    ".gitignore",
    ".env",
)


def _strip_unescaped_semicolons(text: str) -> str:
    """Replaces raw semicolons in sequenceDiagram text with commas, preserving entity codes like #59;."""
    return re.sub(
        r"(?:#[0-9a-zA-Z]+;|&[0-9a-zA-Z]+;)|;",
        lambda m: "," if m.group(0) == ";" else m.group(0),
        text,
    )


def _fix_sequence_diagram(body: str) -> str:
    """Fixes statement-breaking semicolons in sequenceDiagram messages, notes, and headers."""
    fixed_lines: list[str] = []
    for line in body.splitlines():
        msg_match = SEQ_MESSAGE_RE.match(line)
        if msg_match:
            prefix, payload = msg_match.groups()
            fixed_lines.append(f"{prefix}{_strip_unescaped_semicolons(payload)}")
            continue

        note_match = SEQ_NOTE_RE.match(line)
        if note_match:
            prefix, payload = note_match.groups()
            fixed_lines.append(f"{prefix}{_strip_unescaped_semicolons(payload)}")
            continue

        hdr_match = SEQ_BLOCK_HEADERS_RE.match(line)
        if hdr_match:
            prefix, payload = hdr_match.groups()
            fixed_lines.append(f"{prefix}{_strip_unescaped_semicolons(payload)}")
            continue

        fixed_lines.append(line)

    return "\n".join(fixed_lines)


def _find_matching_close(text: str, start: int, open_d: str, close_d: str) -> int:
    """Finds the closing shape delimiter index on a line while respecting nested brackets/parens/braces."""
    if len(open_d) == 2:
        depth = 1
        i = start
        o_char, c_char = open_d[1], close_d[0]
        while i < len(text):
            if text.startswith(close_d, i):
                depth -= 1
                if depth == 0:
                    return i
                i += 2
                continue
            if text.startswith(open_d, i):
                depth += 1
                i += 2
                continue
            if text[i] == o_char:
                depth += 1
            elif text[i] == c_char:
                depth = max(1, depth - 1)
            i += 1
        return -1

    o_char, c_char = open_d, close_d
    depth = 1
    i = start
    while i < len(text):
        ch = text[i]
        if ch == o_char:
            depth += 1
        elif ch == c_char:
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _fix_flowchart_line(line: str) -> str:
    """Quotes unquoted node, subgraph, and edge labels containing special characters."""
    stripped = line.strip()
    if not stripped or stripped.startswith("%%"):
        return line

    # Handle `subgraph ID [Unquoted Label]`
    subgraph_match = re.match(r"^(\s*subgraph\s+[A-Za-z0-9_.-]+\s*\[)(.*)(\]\s*)$", line)
    if subgraph_match:
        prefix, label, suffix = subgraph_match.groups()
        label_str = label.strip()
        if label_str.startswith('"') and label_str.endswith('"') and len(label_str) >= 2:
            inner = label_str[1:-1].replace('"', "'")
            return f'{prefix}"{inner}"{suffix}'
        if any(ch in FLOWCHART_SPECIAL_CHARS for ch in label_str):
            inner = label_str.replace('"', "'")
            return f'{prefix}"{inner}"{suffix}'
        return line

    first_word = stripped.split()[0]
    if first_word in FLOWCHART_KEYWORDS:
        return line

    # Fix pipe edge labels: -->|unquoted (label)|
    def _fix_pipe_edge(m: re.Match[str]) -> str:
        arrow, label, close_pipe = m.groups()
        label_s = label.strip()
        if label_s.startswith('"') and label_s.endswith('"') and len(label_s) >= 2:
            inner = label_s[1:-1].replace('"', "'")
            return f'{arrow}"{inner}"{close_pipe}'
        if any(ch in FLOWCHART_SPECIAL_CHARS for ch in label_s):
            inner = label_s.replace('"', "'")
            return f'{arrow}"{inner}"{close_pipe}'
        return m.group(0)

    line = re.sub(r"((?:-->|-\.->|==>|--)\|)(?!\")([^|\n]+?)(\|)", _fix_pipe_edge, line)

    # Fix inline edge labels: `NodeId -- unquoted (label) -->`
    def _fix_inline_edge(m: re.Match[str]) -> str:
        prefix, label, arrow = m.groups()
        label_s = label.strip()
        if any(ch in FLOWCHART_SPECIAL_CHARS for ch in label_s):
            inner = label_s.replace('"', "'")
            return f'{prefix}"{inner}"{arrow}'
        return m.group(0)

    line = re.sub(
        r"^(\s*[A-Za-z0-9_]+\s+(?:--|-\.|==)\s+)(?!\")(.+?)(\s+(?:-->|\.->|==>)\s+)",
        _fix_inline_edge,
        line,
    )

    # Scan left-to-right for node definitions: NodeId + OpenShape + Label + CloseShape
    out: list[str] = []
    i = 0
    n = len(line)
    node_id_re = re.compile(r"[A-Za-z0-9_]+")

    while i < n:
        if line[i] == '"':
            end_q = line.find('"', i + 1)
            if end_q != -1:
                out.append(line[i : end_q + 1])
                i = end_q + 1
                continue

        m = node_id_re.match(line, i)
        if m and (i == 0 or not (line[i - 1].isalnum() or line[i - 1] in "_/.-")):
            node_id = m.group(0)
            after_id = m.end()

            matched_shape: tuple[str, str] | None = None
            for open_d, close_d in NODE_SHAPES:
                if line.startswith(open_d, after_id):
                    matched_shape = (open_d, close_d)
                    break

            if matched_shape is not None and node_id not in FLOWCHART_KEYWORDS:
                open_d, close_d = matched_shape
                content_start = after_id + len(open_d)
                close_idx = _find_matching_close(line, content_start, open_d, close_d)
                if close_idx != -1:
                    raw_label = line[content_start:close_idx]
                    trimmed = raw_label.strip()
                    if trimmed.startswith('"') and trimmed.endswith('"') and len(trimmed) >= 2:
                        inner = trimmed[1:-1].replace('\\"', "'").replace('"', "'")
                        out.append(f'{node_id}{open_d}"{inner}"{close_d}')
                    elif any(ch in FLOWCHART_SPECIAL_CHARS for ch in trimmed):
                        inner = trimmed.replace('\\"', "'").replace('"', "'")
                        out.append(f'{node_id}{open_d}"{inner}"{close_d}')
                    else:
                        out.append(line[i : close_idx + len(close_d)])
                    i = close_idx + len(close_d)
                    continue

            out.append(node_id)
            i = after_id
            continue

        out.append(line[i])
        i += 1

    return "".join(out)


def _fix_flowchart_diagram(body: str) -> str:
    """Applies line-by-line node, subgraph, and edge label fixes to a flowchart/graph block."""
    return "\n".join(_fix_flowchart_line(line) for line in body.splitlines())


def fix_mermaid_blocks(content: str) -> str:
    """Dispatches diagram-specific Mermaid syntax fixes across all ```mermaid blocks."""

    def replacer(match: re.Match[str]) -> str:
        body = match.group(1)
        first_line = ""
        for line in body.splitlines():
            s = line.strip()
            if s and not s.startswith("%%"):
                first_line = s
                break

        if first_line.startswith("sequenceDiagram"):
            fixed_body = _fix_sequence_diagram(body)
        elif first_line.startswith(("flowchart", "graph")):
            fixed_body = _fix_flowchart_diagram(body)
        else:
            fixed_body = body

        if not fixed_body.endswith("\n"):
            fixed_body += "\n"
        return f"```mermaid\n{fixed_body}```"

    return MERMAID_BLOCK_RE.sub(replacer, content)


def _should_backtick_link_text(text: str, url: str) -> bool:
    """Determines whether markdown link text represents a code symbol or file path that should be wrapped in backticks."""
    if text.startswith("`") and text.endswith("`"):
        return False
    if "_" in text or "/" in text:
        return True
    clean_url = url.split("#", 1)[0].lstrip("./")
    if text == clean_url or text.lower().endswith(FILE_EXTENSIONS):
        return True
    return False


def _format_rel_url(rel_path: str, anchor: str = "") -> str:
    """Formats a relative path with forward slashes and leading './' or '../'."""
    rel_posix = rel_path.replace("\\", "/")
    if not rel_posix.startswith(("./", "../")):
        rel_posix = f"./{rel_posix}"
    return f"{rel_posix}#{anchor}" if anchor else rel_posix


def _resolve_relative_url(url: str, doc_dir: Path | None) -> str:
    """Normalizes a relative URL and resolves repo-root vs subdirectory ('docs/') relative paths if doc_dir is provided."""
    if url.startswith(("http://", "https://", "mailto:", "file://", "#", "/")):
        return url

    if "#" in url:
        path_part, anchor = url.split("#", 1)
    else:
        path_part, anchor = url, ""

    if not path_part:
        return url

    if doc_dir is not None:
        direct_candidate = (doc_dir / path_part).resolve()
        if direct_candidate.exists():
            rel = os.path.relpath(direct_candidate, doc_dir)
            return _format_rel_url(rel, anchor)

        # If doc_dir is a subdirectory (e.g. `docs/`) and the author wrote `./src/foo.py`
        # relative to the repo root, check the parent directory.
        stripped = path_part.lstrip("./")
        parent_candidate = (doc_dir.parent / stripped).resolve()
        if parent_candidate.exists():
            rel = os.path.relpath(parent_candidate, doc_dir)
            return _format_rel_url(rel, anchor)

    if not path_part.startswith(("./", "../")):
        path_part = f"./{path_part}"
    return f"{path_part}#{anchor}" if anchor else path_part


def _fix_links_in_prose_segment(segment: str, doc_dir: Path | None = None) -> str:
    """Fixes markdown links within a non-code-block prose segment."""
    # 1. Strip outer backticks wrapping an entire markdown link: `[text](url)` -> [text](url)
    segment = re.sub(r"`(\[[^\]]+\]\([^)]+\))`", r"\1", segment)

    def replacer(match: re.Match[str]) -> str:
        text = match.group(1)
        url = match.group(2).strip()

        url = _resolve_relative_url(url, doc_dir)

        if _should_backtick_link_text(text, url):
            text = f"`{text}`"

        return f"[{text}]({url})"

    return re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", replacer, segment)


def fix_markdown_links(content: str, doc_path: Path | None = None) -> str:
    """Applies markdown link normalization strictly outside fenced code blocks."""
    doc_dir = doc_path.parent.resolve() if doc_path is not None else None
    parts = FENCED_BLOCK_RE.split(content)
    for idx in range(0, len(parts), 2):
        parts[idx] = _fix_links_in_prose_segment(parts[idx], doc_dir)
    return "".join(parts)


def _shift_fragment_headings(content: str, target_min_level: int = 3) -> str:
    """Shifts ATX headings (outside fenced code blocks) in an included module doc so its top heading starts at target_min_level (default H3 `###`)."""
    parts = FENCED_BLOCK_RE.split(content)
    heading_re = re.compile(r"^(#{1,6})([ \t]+.+)$", re.MULTILINE)

    min_level = 7
    for idx in range(0, len(parts), 2):
        for m in heading_re.finditer(parts[idx]):
            min_level = min(min_level, len(m.group(1)))

    if min_level < target_min_level and min_level <= 6:
        delta = target_min_level - min_level
        for idx in range(0, len(parts), 2):
            parts[idx] = heading_re.sub(
                lambda m: ("#" * min(6, len(m.group(1)) + delta)) + m.group(2),
                parts[idx],
            )

    return "".join(parts)


def _rebase_links_for_host(content: str, frag_dir: Path, host_dir: Path) -> str:
    """Rebases relative Markdown links in an included fragment from frag_dir (e.g. `docs/`) to host_dir (e.g. repo root)."""
    if frag_dir == host_dir:
        return content

    parts = FENCED_BLOCK_RE.split(content)

    def replacer(match: re.Match[str]) -> str:
        text = match.group(1)
        url = match.group(2).strip()
        if url.startswith(("http://", "https://", "mailto:", "file://", "#", "/")):
            return match.group(0)

        if "#" in url:
            path_part, anchor = url.split("#", 1)
        else:
            path_part, anchor = url, ""

        if not path_part:
            return match.group(0)

        candidate_from_frag = (frag_dir / path_part).resolve()
        candidate_from_host = (host_dir / path_part.lstrip("./")).resolve()

        if candidate_from_frag.exists():
            resolved = candidate_from_frag
        elif candidate_from_host.exists():
            resolved = candidate_from_host
        else:
            resolved = candidate_from_frag

        rebased = os.path.relpath(resolved, host_dir)
        return f"[{text}]({_format_rel_url(rebased, anchor)})"

    for idx in range(0, len(parts), 2):
        parts[idx] = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", replacer, parts[idx])

    return "".join(parts)


def expand_includes(content: str, host_doc_path: Path) -> tuple[str, list[str]]:
    """Expands `<!-- INCLUDE: path -->` directives and refreshes `<!-- BEGIN INCLUDE: path -->` blocks."""
    host_dir = host_doc_path.parent.resolve()
    included_files: list[str] = []

    def replacer(match: re.Match[str]) -> str:
        raw_target = match.group(1).strip()
        frag_path = (host_dir / raw_target).resolve()
        if not frag_path.exists() or not frag_path.is_file():
            print(
                f"Warning: Included file '{raw_target}' ({frag_path}) not found.",
                file=sys.stderr,
            )
            return match.group(0)

        # 1. Read and format the standalone module doc on disk first
        frag_raw = frag_path.read_text(encoding="utf-8")
        frag_formatted = fix_markdown_links(fix_mermaid_blocks(frag_raw), frag_path)
        frag_path.write_text(frag_formatted, encoding="utf-8")
        included_files.append(raw_target)

        # 2. Prepare stitched content for the host document (heading shift + link rebasing)
        stitched = _shift_fragment_headings(frag_formatted.strip(), target_min_level=3)
        stitched = _rebase_links_for_host(stitched, frag_path.parent.resolve(), host_dir)

        return (
            f"<!-- BEGIN INCLUDE: {raw_target} -->\n\n"
            f"{stitched}\n\n"
            f"<!-- END INCLUDE: {raw_target} -->"
        )

    # 1. Refresh any already-expanded BEGIN/END INCLUDE blocks (which may contain fenced code blocks)
    content = BEGIN_END_INCLUDE_RE.sub(replacer, content)

    # 2. Expand any fresh single-line `<!-- INCLUDE: ... -->` directives strictly outside fenced code blocks
    parts = FENCED_BLOCK_RE.split(content)
    for idx in range(0, len(parts), 2):
        parts[idx] = SINGLE_INCLUDE_RE.sub(replacer, parts[idx])

    return "".join(parts), included_files


def _is_submodule_doc(doc_path: Path) -> bool:
    """Returns True if doc_path is a per-module documentation file inside a `docs/` directory rather than the root manual."""
    return (
        doc_path.parent.name.lower() == "docs"
        and doc_path.name.lower() != "architecture.md"
    )


def validate_document(content: str, doc_path: Path) -> list[str]:
    """Performs structural, Mermaid, and link target validation, returning any warnings."""
    warnings: list[str] = []
    doc_dir = doc_path.parent.resolve()

    # 1. Check Mermaid block balance (alt/opt/loop/par/critical/break/rect/subgraph vs end)
    block_open_re = re.compile(
        r"^\s*(?:subgraph|alt|opt|loop|par|critical|break|rect)\b"
    )
    block_end_re = re.compile(r"^\s*end\s*$")
    for idx, match in enumerate(MERMAID_BLOCK_RE.finditer(content), start=1):
        body = match.group(1)
        opens = 0
        ends = 0
        for line in body.splitlines():
            if line.strip().startswith("%%"):
                continue
            if block_open_re.match(line):
                opens += 1
            elif block_end_re.match(line):
                ends += 1
        if opens != ends:
            warnings.append(
                f"Mermaid block #{idx} has unbalanced control blocks: {opens} opener(s) vs {ends} 'end' statement(s)."
            )

    # 2. Check relative file links outside fenced code blocks
    parts = FENCED_BLOCK_RE.split(content)
    prose = "\n".join(parts[0::2])
    for match in re.finditer(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)", prose):
        url = match.group(2).strip()
        if url.startswith(("./", "../")):
            target_rel = url.split("#", 1)[0]
            if target_rel:
                resolved = (doc_dir / target_rel).resolve()
                if not resolved.exists():
                    warnings.append(
                        f"Broken relative file link: [{match.group(1)}]({url}) -> {resolved} does not exist."
                    )

    # 3. Check mandatory sections (11 macro sections for ARCHITECTURE.md; module sections for docs/$MODULE.md)
    headings = [line.strip() for line in prose.splitlines() if line.strip().startswith("#")]
    if _is_submodule_doc(doc_path):
        if not headings:
            warnings.append("Submodule document contains no Markdown headings.")
    else:
        expected_sections = [
            "Executive Summary",
            "Repository Layout",
            "System Context",
            "Execution Flow",
            "Core Components",
            "Design Decisions",
            "Deployment & Environment",
            "Security & Privacy",
            "Performance Characteristics",
            "Troubleshooting",
            "Appendices",
        ]
        for section in expected_sections:
            if not any(section.lower() in h.lower() for h in headings):
                warnings.append(f"Missing mandatory section heading containing: '{section}'")

    return warnings


def process_file(file_path: Path) -> bool:
    """Formats, expands includes, and validates a single Markdown file. Returns True if valid without warnings."""
    if not file_path.exists():
        print(f"Error: {file_path} not found.", file=sys.stderr)
        return False

    content = file_path.read_text(encoding="utf-8")

    # 1. Expand any `<!-- INCLUDE: docs/... -->` directives first
    content, included_files = expand_includes(content, file_path)

    # 2. Apply deterministic Mermaid and Markdown link fixes
    content = fix_mermaid_blocks(content)
    content = fix_markdown_links(content, file_path)

    file_path.write_text(content, encoding="utf-8")
    if included_files:
        print(
            f"Successfully stitched {len(included_files)} module doc(s) ({', '.join(included_files)}) "
            f"and formatted: {file_path}"
        )
    else:
        print(f"Successfully formatted Mermaid blocks and Markdown URIs for: {file_path}")

    warnings = validate_document(content, file_path)
    if warnings:
        print(f"\nValidation Warnings for {file_path}:", file=sys.stderr)
        for warning in warnings:
            print(f"  - {warning}", file=sys.stderr)
        return False
    return True


def main() -> None:
    if len(sys.argv) < 2:
        print(
            "Usage: uv run python format_docs.py <path_to_markdown_file> [<more_files.md> ...]",
            file=sys.stderr,
        )
        sys.exit(1)

    for arg in sys.argv[1:]:
        path = Path(arg)
        if not path.exists():
            print(f"Error: {path} not found.", file=sys.stderr)
            sys.exit(1)
        process_file(path)


if __name__ == "__main__":
    main()
