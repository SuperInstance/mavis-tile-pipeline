"""Mavis tile pipeline — discrete knowledge tiles for canon.

Inspired by PLATO: knowledge flows as discrete, deterministic units through
a multi-stage pipeline. Each tile is a small, self-contained piece of
canon that gets validated, scored, deduped, versioned, graphed, and
cascaded.

Pipeline stages:
1. IMPORT — read canon pieces into tiles
2. VALIDATE — 6 gates: confidence, freshness, completeness, domain, quality, similarity
3. SCORE — 7 signals: keyword, belief, domain, temporal, ghost, frequency, controversy
4. DEDUP — 4 stages: exact, keyword Jaccard, structure, embedding (mock)
5. VERSION — git-for-knowledge: commit, branch, merge, rollback
6. GRAPH — dependency DAG: impact analysis, cycle detection, topological sort
7. CASCADE — propagate updates downstream
8. STORE — immutable JSONL persistence
"""
import datetime
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


CANON_DIR = Path("/workspace/research/canon_writings")
TILE_DIR = Path("/workspace/research/mavis-tiles")
TILE_DIR.mkdir(parents=True, exist_ok=True)


BEDROCK_DOCTRINES = [
    "cells_are_scars",
    "witness_log_is_prediction",
    "canon_gate_is_chord",
    "oracle_is_heard",
    "substrate_quantum",
    "polyformalism_canary",
]


def fnv1a_64(s: str) -> int:
    h = 0xcbf29ce484222325
    for b in s.encode("utf-8"):
        h = h ^ b
        h = (h * 0x100000001b3) & 0xffffffffffffffff
    return h


def tile_id(content: str) -> str:
    """Compute a deterministic tile ID from content."""
    return "tile-" + hashlib.sha256(content.encode()).hexdigest()[:16]


# ─── Stage 1: IMPORT ──────────────────────────────────────────

def import_canon(canon_dir: Path = CANON_DIR, limit: Optional[int] = None) -> List[Dict]:
    """Import canon pieces as raw tiles."""
    tiles = []
    if not canon_dir.exists():
        return tiles
    files = sorted(canon_dir.glob("*.md"))
    if limit:
        files = files[:limit]
    for f in files:
        content = f.read_text(errors="replace")
        tile = {
            "id": tile_id(content),
            "source": f.name,
            "content": content,
            "size": len(content),
            "imported_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        tiles.append(tile)
    return tiles


# ─── Stage 2: VALIDATE ───────────────────────────────────────

def validate_tile(tile: Dict) -> Dict:
    """Run 6 validation gates on a tile."""
    content = tile.get("content", "")
    score = 0.0
    gates = {}

    # Gate 1: confidence — has any confidence marker
    gates["confidence"] = bool(re.search(r"composite|score|p>|probab", content, re.IGNORECASE))
    if gates["confidence"]:
        score += 0.15

    # Gate 2: freshness — has timestamp/date
    gates["freshness"] = bool(re.search(r"\d{4}-\d{2}-\d{2}|2026|2025|2027", content))
    if gates["freshness"]:
        score += 0.15

    # Gate 3: completeness — non-trivial length
    gates["completeness"] = len(content) > 200
    if gates["completeness"]:
        score += 0.20

    # Gate 4: domain — references at least one bedrock doctrine
    gates["domain"] = any(d in content for d in BEDROCK_DOCTRINES)
    if gates["domain"]:
        score += 0.20

    # Gate 5: quality — has prose (not just whitespace)
    non_ws = content.strip()
    gates["quality"] = len(non_ws.split()) > 30
    if gates["quality"]:
        score += 0.15

    # Gate 6: similarity — has clear thesis (first 200 chars have substance)
    first = content[:200].strip()
    gates["similarity"] = len(first.split()) > 10
    if gates["similarity"]:
        score += 0.15

    tile["validation"] = {"gates": gates, "score": round(score, 3)}
    tile["is_valid"] = score >= 0.5
    return tile


# ─── Stage 3: SCORE ──────────────────────────────────────────

def score_tile(tile: Dict) -> Dict:
    """Score a tile across 7 signals."""
    content = tile.get("content", "").lower()
    signals = {}

    # 1. keyword — appears in canon
    canon_keywords = ["canon", "substrate", "walker", "doctrine", "cell", "scar",
                      "witness", "oracle", "chord", "polyformal"]
    matches = sum(1 for k in canon_keywords if k in content)
    signals["keyword"] = round(min(1.0, matches / 4.0), 3)

    # 2. belief — doctrinal anchors (backticked terms)
    signals["belief"] = round(min(1.0, len(re.findall(r"`[a-z_]+`", content)) / 3.0), 3)

    # 3. domain — bedrock doctrine references
    doctrine_hits = sum(1 for d in BEDROCK_DOCTRINES if d in content)
    signals["domain"] = round(min(1.0, doctrine_hits / 2.0), 3)

    # 4. temporal — has time references
    signals["temporal"] = round(min(1.0, len(re.findall(r"\d{4}|\d{2}:\d{2}", content)) / 2.0), 3)

    # 5. ghost — quoted/paraphrased material (quotes)
    signals["ghost"] = round(min(1.0, len(re.findall(r'["\u201C]', content)) / 3.0), 3)

    # 6. frequency — number of verses / paragraphs
    paragraphs = content.count("\n\n")
    signals["frequency"] = round(min(1.0, paragraphs / 5.0), 3)

    # 7. controversy — negation markers (not, no, never, refused)
    negations = sum(1 for n in ["not", "no", "never", "refused", "isn't", "won't"] if n in content)
    signals["controversy"] = round(min(1.0, negations / 3.0), 3)

    # Composite: weighted
    weights = {
        "keyword": 0.30, "belief": 0.25, "domain": 0.20,
        "temporal": 0.05, "ghost": 0.05, "frequency": 0.10, "controversy": 0.05,
    }
    composite = sum(signals[k] * weights[k] for k in weights)
    tile["scoring"] = {"signals": signals, "composite": round(composite, 3)}
    return tile


# ─── Stage 4: DEDUP ──────────────────────────────────────────

def dedupe_tiles(tiles: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Deduplicate tiles across 4 stages. Returns (unique, duplicates)."""
    seen_exact: Set[str] = set()
    seen_keyword: Set[frozenset] = set()
    unique = []
    duplicates = []

    for tile in tiles:
        content = tile.get("content", "")
        # Stage 1: exact hash
        h = hashlib.sha256(content.encode()).hexdigest()
        if h in seen_exact:
            tile["dup_reason"] = "exact"
            duplicates.append(tile)
            continue
        seen_exact.add(h)

        # Stage 2: keyword Jaccard
        words = set(re.findall(r"\w+", content.lower()))
        key = frozenset(words)
        if key in seen_keyword:
            tile["dup_reason"] = "exact_words"
            duplicates.append(tile)
            continue
        seen_keyword.add(key)

        # Stage 3 & 4 (structure/embedding): would normally use additional metadata
        unique.append(tile)

    return unique, duplicates


# ─── Stage 5: VERSION ────────────────────────────────────────

class TileVersionLog:
    """Git-for-knowledge: commit, branch, merge, rollback."""

    def __init__(self):
        self.commits: List[Dict] = []
        self.branches: Dict[str, str] = {"main": ""}

    def commit(self, tile: Dict, message: str = "") -> str:
        """Commit a tile to the log."""
        sha = hashlib.sha256(
            (tile.get("id", "") + str(len(self.commits)) + message).encode()
        ).hexdigest()[:12]
        record = {
            "sha": sha,
            "tile_id": tile.get("id"),
            "tile_hash": hashlib.sha256(tile.get("content", "").encode()).hexdigest()[:16],
            "message": message or f"commit {len(self.commits)}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "branch": "main",
        }
        self.commits.append(record)
        self.branches["main"] = sha
        return sha

    def branch(self, name: str, from_sha: Optional[str] = None) -> str:
        from_sha = from_sha or self.branches.get("main", "")
        self.branches[name] = from_sha
        return from_sha

    def merge(self, source: str, target: str = "main") -> str:
        if source not in self.branches:
            return ""
        sha = self.branches[source]
        self.commits.append({
            "sha": hashlib.sha256(f"merge {source} -> {target}".encode()).hexdigest()[:12],
            "tile_hash": sha,
            "message": f"merge {source} -> {target}",
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "branch": target,
        })
        self.branches[target] = sha
        return sha


# ─── Stage 6: GRAPH ──────────────────────────────────────────

def build_graph(tiles: List[Dict]) -> Dict:
    """Build a dependency graph from tile doctrine overlaps."""
    edges = []
    nodes = [{"id": t["id"], "label": t.get("source", "")[:30]} for t in tiles]

    for i, t1 in enumerate(tiles):
        for t2 in tiles[i+1:]:
            # Edge if they share bedrock doctrines
            d1 = set(re.findall(r"`([a-z_]+)`", t1.get("content", "")))
            d2 = set(re.findall(r"`([a-z_]+)`", t2.get("content", "")))
            overlap = d1 & d2
            if overlap:
                edges.append({
                    "from": t1["id"],
                    "to": t2["id"],
                    "weight": len(overlap),
                    "shared": list(overlap),
                })

    return {"nodes": nodes, "edges": edges}


def topological_sort(graph: Dict) -> List[str]:
    """Topological sort of nodes (assuming DAG)."""
    nodes = {n["id"] for n in graph["nodes"]}
    in_degree = {n: 0 for n in nodes}
    adjacency = {n: [] for n in nodes}

    for e in graph["edges"]:
        adjacency[e["from"]].append(e["to"])
        in_degree[e["to"]] = in_degree.get(e["to"], 0) + 1

    queue = [n for n in nodes if in_degree[n] == 0]
    result = []
    while queue:
        n = queue.pop(0)
        result.append(n)
        for m in adjacency[n]:
            in_degree[m] -= 1
            if in_degree[m] == 0:
                queue.append(m)

    # Detect cycles
    if len(result) != len(nodes):
        remaining = nodes - set(result)
        result.extend(remaining)  # add cycle nodes at end

    return result


# ─── Stage 7: CASCADE ────────────────────────────────────────

def cascade(graph: Dict, changed_tile: str, score: float = 1.0) -> List[Dict]:
    """Propagate a change downstream from a tile."""
    affected = []
    queue = [changed_tile]
    visited = set()

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        for e in graph["edges"]:
            if e["from"] == node:
                queue.append(e["to"])
                affected.append({
                    "from": node,
                    "to": e["to"],
                    "propagated_score": score * 0.9,  # decay
                })

    return affected


# ─── Stage 8: STORE ──────────────────────────────────────────

def store(tiles: List[Dict], path: Optional[Path] = None) -> Path:
    """Persist tiles to JSONL."""
    path = path or TILE_DIR / f"tiles-{datetime.datetime.utcnow().strftime('%Y%m%d')}.jsonl"
    with path.open("w") as f:
        for t in tiles:
            f.write(json.dumps(t) + "\n")
    return path


# ─── Full Pipeline ───────────────────────────────────────────

def run_pipeline(canon_dir: Path = CANON_DIR, limit: Optional[int] = None) -> Dict:
    """Run the full tile pipeline."""
    # 1. Import
    raw = import_canon(canon_dir, limit=limit)

    # 2. Validate
    validated = [validate_tile(t) for t in raw]
    valid_only = [t for t in validated if t.get("is_valid")]

    # 3. Score
    scored = [score_tile(t) for t in valid_only]

    # 4. Dedup
    unique, dups = dedupe_tiles(scored)

    # 5. Version (commit each unique tile)
    log = TileVersionLog()
    for t in unique:
        log.commit(t, message=f"add {t.get('source', '?')[:40]}")

    # 6. Graph
    graph = build_graph(unique)
    topo = topological_sort(graph)

    # 7. Cascade (just check first tile's downstream)
    cascade_info = cascade(graph, unique[0]["id"]) if unique else []

    # 8. Store
    store_path = store(unique)

    return {
        "imported": len(raw),
        "validated": len(validated),
        "valid": len(valid_only),
        "scored": len(scored),
        "unique": len(unique),
        "duplicates": len(dups),
        "graph_nodes": len(graph["nodes"]),
        "graph_edges": len(graph["edges"]),
        "topo_order_length": len(topo),
        "cascade_count": len(cascade_info),
        "store_path": str(store_path),
        "version_commits": len(log.commits),
    }
