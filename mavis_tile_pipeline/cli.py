"""CLI for mavis-tile-pipeline."""
import argparse
import json
import sys
from pathlib import Path

from .pipeline import (
    run_pipeline, import_canon, validate_tile, score_tile, dedupe_tiles,
    TileVersionLog, build_graph, topological_sort, cascade, store,
    tile_id, BEDROCK_DOCTRINES, CANON_DIR,
)


def cmd_run(args):
    """Run the full pipeline."""
    result = run_pipeline(canon_dir=Path(args.canon_dir) if args.canon_dir else CANON_DIR,
                          limit=args.limit)
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(f"=== Tile pipeline ===")
        print(f"Imported: {result['imported']}")
        print(f"Validated: {result['validated']}")
        print(f"Valid: {result['valid']}")
        print(f"Unique: {result['unique']}")
        print(f"Duplicates: {result['duplicates']}")
        print(f"Graph: {result['graph_nodes']} nodes, {result['graph_edges']} edges")
        print(f"Topo order: {result['topo_order_length']}")
        print(f"Cascade from first: {result['cascade_count']} affected")
        print(f"Version commits: {result['version_commits']}")
        print(f"Stored: {result['store_path']}")


def cmd_validate(args):
    """Validate a single tile."""
    tile = {"content": args.text}
    result = validate_tile(tile)
    print(json.dumps(result, indent=1))


def cmd_score(args):
    """Score a single tile."""
    tile = {"content": args.text}
    result = score_tile(tile)
    print(json.dumps(result, indent=1))


def cmd_dedup(args):
    """Run dedup on imported canon."""
    tiles = import_canon(limit=args.limit)
    unique, dups = dedupe_tiles(tiles)
    print(f"Unique: {len(unique)}, duplicates: {len(dups)}")
    if dups:
        for d in dups[:5]:
            print(f"  - {d['source']}: {d['dup_reason']}")


def cmd_graph(args):
    """Build the graph from canon."""
    tiles = import_canon(limit=args.limit)
    valid_tiles = []
    for t in tiles:
        t = validate_tile(t)
        if t.get("is_valid"):
            valid_tiles.append(score_tile(t))
    unique, _ = dedupe_tiles(valid_tiles)
    graph = build_graph(unique)
    topo = topological_sort(graph)
    print(f"Graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")
    print(f"Topo order length: {len(topo)}")
    if args.verbose:
        print(f"Sample edges: {graph['edges'][:5]}")


def main():
    p = argparse.ArgumentParser(description="mavis-tile-pipeline — discrete knowledge tiles for canon")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_r = sub.add_parser("run", help="Run full pipeline")
    p_r.add_argument("--canon-dir", help="Path to canon directory")
    p_r.add_argument("--limit", type=int, help="Max tiles to import")
    p_r.add_argument("--json", action="store_true")
    p_r.set_defaults(func=cmd_run)

    p_v = sub.add_parser("validate", help="Validate a single text")
    p_v.add_argument("text")
    p_v.set_defaults(func=cmd_validate)

    p_s = sub.add_parser("score", help="Score a single text")
    p_s.add_argument("text")
    p_s.set_defaults(func=cmd_score)

    p_d = sub.add_parser("dedup", help="Run dedup on canon")
    p_d.add_argument("--limit", type=int, default=20)
    p_d.set_defaults(func=cmd_dedup)

    p_g = sub.add_parser("graph", help="Build graph from canon")
    p_g.add_argument("--limit", type=int, default=20)
    p_g.add_argument("--verbose", "-v", action="store_true")
    p_g.set_defaults(func=cmd_graph)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
