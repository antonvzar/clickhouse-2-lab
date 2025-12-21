from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from tabulate import tabulate

def split_category_path(full_path_name: str) -> List[str]:
    if full_path_name is None:
        return []
    s = str(full_path_name).strip()
    # в parquet путь записан как "A\B\C"
    return [p.strip() for p in re.split(r"\\+", s) if p.strip()]

def path_slash(parts: List[str]) -> str:
    return "/".join(parts)

def parent_path_slash(parts: List[str]) -> Optional[str]:
    if len(parts) <= 1:
        return None
    return "/".join(parts[:-1])

def utc_now_naive() -> datetime:
    return datetime.utcnow()

def json_pretty(obj: Any) -> str:
    def default(o):
        if isinstance(o, datetime):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, ensure_ascii=False, indent=2, default=default)

def print_json(title: str, obj: Any) -> None:
    print(f"\n--- {title} ---")
    print(json_pretty(obj))

def print_table(title: str, rows: List[Dict[str, Any]], columns: List[Tuple[str, str]]) -> None:
    """columns: [(key, header), ...]"""
    print(f"\n--- {title} ---")
    if not rows:
        print("(empty)")
        return
    headers = [h for _, h in columns]
    data = []
    for r in rows:
        data.append([r.get(k, "") for k, _ in columns])
    print(tabulate(data, headers=headers, tablefmt="github"))

def extract_index_used_from_explain(explain: Dict[str, Any]) -> str:
    qp = explain.get("queryPlanner", {}) or {}
    wp = qp.get("winningPlan", {}) or {}

    def walk(node: Any) -> Optional[str]:
        if not isinstance(node, dict):
            return None
        stage = node.get("stage")
        if stage == "COLLSCAN":
            return "COLLSCAN"
        if "indexName" in node:
            return node["indexName"]
        for k in ("inputStage", "inputStages", "shards", "children", "plans"):
            v = node.get(k)
            if isinstance(v, list):
                for it in v:
                    res = walk(it)
                    if res:
                        return res
            else:
                res = walk(v)
                if res:
                    return res
        return None

    res = walk(wp)
    return res or "UNKNOWN"

def explain_agg_time_ms(db, collection_name: str, pipeline: List[Dict[str, Any]]) -> Optional[int]:
    try:
        exp = db.command("explain", {"aggregate": collection_name, "pipeline": pipeline, "cursor": {}}, verbosity="executionStats")
    except Exception:
        return None

    def find_int(d, key):
        if isinstance(d, dict):
            if key in d and isinstance(d[key], int):
                return d[key]
            for v in d.values():
                r = find_int(v, key)
                if r is not None:
                    return r
        elif isinstance(d, list):
            for it in d:
                r = find_int(it, key)
                if r is not None:
                    return r
        return None

    return find_int(exp, "executionTimeMillis") or find_int(exp, "executionTimeMillisEstimate")
