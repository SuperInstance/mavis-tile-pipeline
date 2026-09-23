# mavis-tile-pipeline

Discrete knowledge tiles for canon. The PLATO pattern ported to Quilt.

## Stages

1. **IMPORT** — read canon pieces into raw tiles
2. **VALIDATE** — 6 gates: confidence, freshness, completeness, domain, quality, similarity
3. **SCORE** — 7 signals: keyword, belief, domain, temporal, ghost, frequency, controversy
4. **DEDUP** — 4 stages: exact hash, word-set Jaccard, structure, embedding (mocked)
5. **VERSION** — git-for-knowledge: commit, branch, merge, rollback
6. **GRAPH** — dependency DAG via shared doctrines
7. **CASCADE** — propagate updates downstream
8. **STORE** — JSONL persistence

## Run

```bash
python3 -m mavis_tile_pipeline run --limit 30
python3 -m mavis_tile_pipeline graph --limit 30 --verbose
python3 -m mavis_tile_pipeline validate "your text here"
python3 -m mavis_tile_pipeline score "your text here"
```

## Tests

```bash
python3 run_tests.py    # 14/14 passing
```

## Real Pipeline Output

```
Imported: 30
Validated: 30
Unique: 30
Duplicates: 0
Graph: 30 nodes, 7 edges
Version commits: 30
```

## Backed by

- Forgemaster/PLATO pattern: tile-based knowledge pipeline
- Quilt canon substrate: each tile is a canon piece
- 6 bedrock doctrines used as graph edges
