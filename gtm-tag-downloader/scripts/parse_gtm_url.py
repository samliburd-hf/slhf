#!/usr/bin/env python3
"""GTM URL parser and tag artifact utility.

Extracts accountId, containerId, workspaceId, and optional tagId from Google Tag Manager URLs.
Also provides utilities to sanitize filenames, extract referenced variables and triggers from tags,
and save individual tag setups or comprehensive bundles (tag + triggers + variables).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


def parse_gtm_url(url: str) -> Dict[str, Optional[str]]:
    """Parse a GTM URL or path and extract account, container, workspace, and tag IDs."""
    account_match = re.search(r"accounts/(?P<id>\d+)", url)
    container_match = re.search(r"containers/(?P<id>\d+)", url)
    workspace_match = re.search(r"workspaces/(?P<id>\d+)", url)
    tag_match = re.search(r"tags/(?P<id>\d+)", url)

    account_id = account_match.group("id") if account_match else None
    container_id = container_match.group("id") if container_match else None
    workspace_id = workspace_match.group("id") if workspace_match else None
    tag_id = tag_match.group("id") if tag_match else None

    is_valid = bool(account_id and container_id and workspace_id)

    return {
        "valid": is_valid,
        "accountId": account_id,
        "containerId": container_id,
        "workspaceId": workspace_id,
        "tagId": tag_id,
        "rawUrl": url,
    }


def sanitize_filename(name: str) -> str:
    """Sanitize tag, trigger, or variable name into a filesystem-safe string."""
    clean = re.sub(r'[\\/*?:"<>|]', "", name)
    clean = re.sub(r"\s+", "_", clean.strip())
    clean = clean.strip("._-")
    return clean or "unnamed"


def extract_referenced_variables(data: Any) -> List[str]:
    """Recursively search for variable references {{variable_name}} inside any data structure."""
    var_pattern = re.compile(r"\{\{([^}]+)\}\}")
    found: Set[str] = set()

    def _traverse(node: Any) -> None:
        if isinstance(node, str):
            for match in var_pattern.findall(node):
                clean_name = match.strip()
                if clean_name:
                    found.add(clean_name)
        elif isinstance(node, dict):
            for v in node.values():
                _traverse(v)
        elif isinstance(node, list):
            for item in node:
                _traverse(item)

    _traverse(data)
    return sorted(list(found))


def extract_associated_triggers(tag_data: Dict[str, Any]) -> Dict[str, List[str]]:
    """Extract firing and blocking trigger IDs from a tag JSON."""
    firing = [str(tid) for tid in tag_data.get("firingTriggerId", []) if tid]
    blocking = [str(tid) for tid in tag_data.get("blockingTriggerId", []) if tid]
    all_triggers = list(dict.fromkeys(firing + blocking))
    return {
        "firing": firing,
        "blocking": blocking,
        "all": all_triggers,
    }


def save_tag_json(
    tag_data: Dict[str, Any], output_dir: Path | str = "tags"
) -> Path:
    """Save standalone tag JSON configuration to output directory with standardized naming."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    tag_id = str(tag_data.get("tagId", "unknown"))
    tag_name = tag_data.get("name", "")
    sanitized_name = sanitize_filename(tag_name)

    if sanitized_name and sanitized_name != "unnamed":
        filename = f"{tag_id}_{sanitized_name}.json"
    else:
        filename = f"tag_{tag_id}.json"

    file_path = out_dir / filename
    formatted_json = json.dumps(tag_data, indent=2, ensure_ascii=False) + "\n"
    file_path.write_text(formatted_json, encoding="utf-8")

    return file_path


def save_bundle(
    bundle_data: Dict[str, Any], base_output_dir: Path | str = "tags"
) -> Dict[str, Any]:
    """Save a comprehensive bundle of tag, triggers, and variables.

    Creates:
      tags/<tagId>_<sanitized_tag_name>/
      ├── tag.json
      ├── bundle.json
      ├── triggers/
      │   └── <triggerId>_<name>.json
      └── variables/
          └── <variableId>_<name>.json
    Also saves/updates tags/<tagId>_<sanitized_tag_name>.json for standalone access.
    """
    tag = bundle_data.get("tag", {})
    triggers = bundle_data.get("triggers", [])
    variables = bundle_data.get("variables", [])

    tag_id = str(tag.get("tagId", "unknown"))
    tag_name = tag.get("name", "unnamed_tag")
    sanitized_tag_name = sanitize_filename(tag_name)
    folder_name = f"{tag_id}_{sanitized_tag_name}"

    root_tags_dir = Path(base_output_dir)
    bundle_dir = root_tags_dir / folder_name
    triggers_dir = bundle_dir / "triggers"
    variables_dir = bundle_dir / "variables"

    bundle_dir.mkdir(parents=True, exist_ok=True)
    triggers_dir.mkdir(parents=True, exist_ok=True)
    variables_dir.mkdir(parents=True, exist_ok=True)

    # 1. Save standalone tag in root tags dir
    standalone_tag_path = save_tag_json(tag, output_dir=root_tags_dir)

    # 2. Save tag inside bundle dir
    tag_file = bundle_dir / "tag.json"
    tag_file.write_text(json.dumps(tag, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 3. Save each trigger
    saved_triggers: List[Dict[str, str]] = []
    for trigger in triggers:
        trig_id = str(trigger.get("triggerId", "unknown"))
        trig_name = sanitize_filename(trigger.get("name", "trigger"))
        trig_filename = f"{trig_id}_{trig_name}.json"
        trig_path = triggers_dir / trig_filename
        trig_path.write_text(json.dumps(trigger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        saved_triggers.append({
            "triggerId": trig_id,
            "name": trigger.get("name", ""),
            "path": str(trig_path.resolve()),
            "relative": str(trig_path.relative_to(root_tags_dir.parent)),
        })

    # 4. Save each variable
    saved_variables: List[Dict[str, str]] = []
    for var in variables:
        var_id = str(var.get("variableId", "unknown"))
        var_name = sanitize_filename(var.get("name", "variable"))
        var_filename = f"{var_id}_{var_name}.json"
        var_path = variables_dir / var_filename
        var_path.write_text(json.dumps(var, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        saved_variables.append({
            "variableId": var_id,
            "name": var.get("name", ""),
            "path": str(var_path.resolve()),
            "relative": str(var_path.relative_to(root_tags_dir.parent)),
        })

    # 5. Save bundle.json
    bundle_file = bundle_dir / "bundle.json"
    bundle_summary = {
        "tag": tag,
        "triggers": triggers,
        "variables": variables,
        "metadata": {
            "tagId": tag_id,
            "tagName": tag_name,
            "triggersCount": len(triggers),
            "variablesCount": len(variables),
        },
    }
    bundle_file.write_text(json.dumps(bundle_summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return {
        "status": "success",
        "bundleDir": str(bundle_dir.resolve()),
        "standaloneTag": str(standalone_tag_path.resolve()),
        "bundleFile": str(bundle_file.resolve()),
        "triggers": saved_triggers,
        "variables": saved_variables,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse GTM URL and format/save GTM tag setups and associated assets."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # 'parse' command
    parse_cmd = subparsers.add_parser("parse", help="Parse a GTM URL")
    parse_cmd.add_argument("url", help="GTM URL or resource path")

    # 'extract-refs' command
    extract_cmd = subparsers.add_parser(
        "extract-refs", help="Extract referenced trigger IDs and variable names from tag JSON"
    )
    extract_cmd.add_argument("--file", "-f", help="Path to tag JSON file", required=True)

    # 'save' command
    save_cmd = subparsers.add_parser("save", help="Save tag JSON to file")
    save_cmd.add_argument(
        "--json-input",
        "-j",
        help="JSON string of tag configuration",
        default=None,
    )
    save_cmd.add_argument(
        "--file-input",
        "-f",
        help="Path to file containing raw tag JSON",
        default=None,
    )
    save_cmd.add_argument(
        "--output-dir",
        "-o",
        help="Directory to save tag file in",
        default="tags",
    )

    # 'save-bundle' command
    bundle_cmd = subparsers.add_parser(
        "save-bundle", help="Save tag, triggers, and variables bundle"
    )
    bundle_cmd.add_argument(
        "--bundle-file",
        "-b",
        help="Path to JSON file containing {tag: ..., triggers: [...], variables: [...]}",
        required=True,
    )
    bundle_cmd.add_argument(
        "--output-dir",
        "-o",
        help="Base directory to save bundle in",
        default="tags",
    )

    # 'sanitize' command
    sanitize_cmd = subparsers.add_parser(
        "sanitize", help="Sanitize a name for filename"
    )
    sanitize_cmd.add_argument("name", help="Resource name")

    args = parser.parse_args()

    if args.command == "parse" or (args.command is None and len(sys.argv) == 2):
        target_url = args.url if args.command == "parse" else sys.argv[1]
        result = parse_gtm_url(target_url)
        print(json.dumps(result, indent=2))
        return 0 if result["valid"] else 1

    if args.command == "sanitize":
        print(sanitize_filename(args.name))
        return 0

    if args.command == "extract-refs":
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"Error: File not found: {file_path}", file=sys.stderr)
            return 1
        data = json.loads(file_path.read_text(encoding="utf-8"))
        triggers_info = extract_associated_triggers(data)
        variables_info = extract_referenced_variables(data)
        result = {
            "tagId": data.get("tagId"),
            "tagName": data.get("name"),
            "triggers": triggers_info,
            "variables": variables_info,
        }
        print(json.dumps(result, indent=2))
        return 0

    if args.command == "save-bundle":
        bundle_path = Path(args.bundle_file)
        if not bundle_path.exists():
            print(f"Error: Bundle file not found: {bundle_path}", file=sys.stderr)
            return 1
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
        res = save_bundle(data, base_output_dir=args.output_dir)
        print(json.dumps(res, indent=2))
        return 0

    if args.command == "save":
        raw_json = None
        if args.json_input:
            raw_json = args.json_input
        elif args.file_input:
            raw_json = Path(args.file_input).read_text(encoding="utf-8")
        elif not sys.stdin.isatty():
            raw_json = sys.stdin.read()

        if not raw_json:
            print("Error: No JSON input provided for save command.", file=sys.stderr)
            return 1

        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError as err:
            print(f"Error parsing JSON input: {err}", file=sys.stderr)
            return 1

        saved_path = save_tag_json(data, output_dir=args.output_dir)
        print(
            json.dumps(
                {
                    "status": "success",
                    "path": str(saved_path.resolve()),
                    "filename": saved_path.name,
                    "tagId": data.get("tagId"),
                    "name": data.get("name"),
                },
                indent=2,
            )
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
