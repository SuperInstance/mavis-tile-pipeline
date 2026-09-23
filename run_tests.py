"""Test runner for mavis-tile-pipeline."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, "/workspace/repos/mavis-tile-pipeline")

from mavis_tile_pipeline.pipeline import (
    import_canon, validate_tile, score_tile, dedupe_tiles,
    TileVersionLog, build_graph, topological_sort, cascade, store,
    run_pipeline, tile_id, fnv1a_64, BEDROCK_DOCTRINES,
)


results = []
failures = []


def test(name, func):
    try:
        func()
        results.append((name, "PASS"))
    except AssertionError as e:
        results.append((name, f"FAIL: {e}"))
        failures.append(name)
    except Exception as e:
        results.append((name, f"ERROR: {type(e).__name__}: {e}"))
        failures.append(name)


def t_fnv1a():
    assert f"0x{fnv1a_64('café Δ 日本語'):016x}" == "0x24a555471370b18d"


def t_tile_id():
    tid = tile_id("test content")
    assert tid.startswith("tile-")
    assert len(tid) > 10


def t_bedrock_doctrines():
    assert "cells_are_scars" in BEDROCK_DOCTRINES
    assert len(BEDROCK_DOCTRINES) >= 5


def t_validate_empty():
    t = validate_tile({"content": ""})
    assert t["validation"]["score"] == 0
    assert not t["is_valid"]


def t_validate_full():
    t = validate_tile({
        "content": "composite score 0.9 on 2026-09-23. `cells_are_scars`. A scar is a refusal that records entry."
    })
    assert t["validation"]["score"] > 0.5
    assert t["is_valid"]


def t_score_tile():
    t = score_tile({"content": "The substrate walker canon is doctrine. It walks the cells. `cells_are_scars`.\n\nFirst paragraph. `canon_gate_is_chord`.\n\nSecond paragraph about refusing."})
    assert "signals" in t["scoring"]
    assert 0 < t["scoring"]["composite"] <= 1.0


def t_dedupe_exact():
    a = {"content": "hello world", "id": "1"}
    b = {"content": "hello world", "id": "2"}
    c = {"content": "different content", "id": "3"}
    unique, dups = dedupe_tiles([a, b, c])
    assert len(unique) == 2
    assert len(dups) == 1


def t_version_log():
    log = TileVersionLog()
    sha1 = log.commit({"id": "t1", "content": "first"}, "initial")
    sha2 = log.commit({"id": "t2", "content": "second"}, "second")
    assert sha1 != sha2
    assert log.branches["main"] == sha2
    assert len(log.commits) == 2


def t_version_branch_merge():
    log = TileVersionLog()
    log.commit({"id": "t1", "content": "x"}, "a")
    log.commit({"id": "t2", "content": "y"}, "b")
    log.branch("feature")
    log.commit({"id": "t3", "content": "z"}, "feature work")
    merged = log.merge("feature", "main")
    assert merged
    assert len(log.commits) == 4


def t_build_graph():
    tiles = [
        {"id": "a", "content": "doctrine `cells_are_scars` matters", "source": "a.md"},
        {"id": "b", "content": "also `cells_are_scars` here", "source": "b.md"},
        {"id": "c", "content": "unrelated content", "source": "c.md"},
    ]
    g = build_graph(tiles)
    assert len(g["nodes"]) == 3
    # a-b share doctrine, expect edge
    edge_pairs = {(e["from"], e["to"]) for e in g["edges"]}
    assert ("a", "b") in edge_pairs or ("b", "a") in edge_pairs


def t_topological_sort():
    tiles = [
        {"id": "a", "content": "shares `cells_are_scars` with b", "source": "a.md"},
        {"id": "b", "content": "shares `cells_are_scars` with a", "source": "b.md"},
    ]
    g = build_graph(tiles)
    topo = topological_sort(g)
    assert len(topo) == 2


def t_cascade():
    g = {
        "nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
        "edges": [
            {"from": "a", "to": "b", "weight": 1, "shared": ["x"]},
            {"from": "b", "to": "c", "weight": 1, "shared": ["x"]},
        ],
    }
    affected = cascade(g, "a")
    # Should reach b and c
    assert len(affected) == 2


def t_store():
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "tiles.jsonl"
        tiles = [{"id": "a", "content": "x"}, {"id": "b", "content": "y"}]
        path = store(tiles, path=out)
        assert path.exists()
        lines = path.read_text().strip().split("\n")
        assert len(lines) == 2


def t_run_pipeline_minimal():
    """Run pipeline against a temp canon dir."""
    with tempfile.TemporaryDirectory() as td:
        canon = Path(td) / "canon"
        canon.mkdir()
        (canon / "01_test.md").write_text(
            "composite score 0.95 on 2026-09-23. `cells_are_scars`. "
            "A scar is a witness log entry that records attempted access. "
            "The substrate walker canon doctrine predicts refusals as map points."
        )
        result = run_pipeline(canon_dir=canon, limit=5)
        assert result["imported"] >= 1
        assert result["valid"] >= 1
        assert result["unique"] >= 1
        assert result["graph_nodes"] >= 1


test("test_fnv1a", t_fnv1a)
test("test_tile_id", t_tile_id)
test("test_bedrock_doctrines", t_bedrock_doctrines)
test("test_validate_empty", t_validate_empty)
test("test_validate_full", t_validate_full)
test("test_score_tile", t_score_tile)
test("test_dedupe_exact", t_dedupe_exact)
test("test_version_log", t_version_log)
test("test_version_branch_merge", t_version_branch_merge)
test("test_build_graph", t_build_graph)
test("test_topological_sort", t_topological_sort)
test("test_cascade", t_cascade)
test("test_store", t_store)
test("test_run_pipeline_minimal", t_run_pipeline_minimal)

print("\n=== mavis-tile-pipeline test results ===")
for name, status in results:
    print(f"  {status:60} {name}")

print(f"\n{len(results) - len(failures)}/{len(results)} passed")
if failures:
    sys.exit(1)
