# Algorithm visualizations (`spytial.sequence`)

These notebooks step through CLRS algorithms frame-by-frame using
`spytial.sequence(...)`. The static data-structure visualizations live in
the parent `src/` directory; this folder is just for the per-step,
animated views.

Each notebook is self-contained — it re-defines the minimum class it
needs so it can be run in isolation.

## `sequence_policy` cheat sheet

| Policy | Behaviour |
|---|---|
| `stability` | Atoms try to stay anchored to their previous position; only essential motion happens |
| `change_emphasis` | Atoms whose relationships/positions changed are visually highlighted |

The viewer has a dropdown to flip between policies at runtime — useful
for feeling the tradeoff on the same trace.

## Choosing a policy: rule of thumb

Stability is the right default when **most motion between frames is
incidental** — the structural change per step is a small edit (a pointer
rewire, an added edge) and the rest of the layout could legitimately
stay put. Suppressing the cosmetic motion lets the eye see the essential
change.

## Examples here (stability)

| Notebook | Algorithm | Why this policy |
|---|---|---|
| `disjoint-sets.ipynb` | Union-Find with path compression + union by rank | A `UNION` only rewires one parent pointer; no node has to move. Stability lets the eye land on the single edge that changed. |
| `dag-build.ipynb` | Incremental DAG construction | Each step adds one edge. Vertices stay put; the topological left-to-right layout is preserved frame-to-frame. |

More examples (for `change_emphasis`) will follow.
