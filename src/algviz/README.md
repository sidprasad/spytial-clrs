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

Change emphasis is the right pick when **per-step motion is essential
and cannot be suppressed** — every frame forces atoms to move (e.g. a
swap is a 2-cycle in the atom→position mapping). Trying to "stabilize"
fights the algorithm. Better to embrace the motion and highlight what
just changed.

## The four examples here

| Notebook | Algorithm | Policy | Why |
|---|---|---|---|
| `disjoint-sets.ipynb` | Union-Find with path compression + union by rank | `stability` | A `UNION` only rewires one parent pointer; no node has to move. Stability lets the eye land on the single edge that changed. |
| `dag-build.ipynb` | Incremental DAG construction | `stability` | Each step adds one edge. Vertices stay put; the topological left-to-right layout is preserved frame-to-frame. |
| `max-heap.ipynb` | Array-backed binary max-heap (`BUILD-MAX-HEAP`, `EXTRACT-MAX`) | `change_emphasis` | Index `i` pins each cell's tree position, so the visible atoms are the values, which **must** trade places on every swap. Stability can't suppress that motion — change_emphasis highlights the two cells that swapped. |
| `bubble-sort.ipynb` | Bubble sort on an array | `change_emphasis` | Same shape as max-heap: each step is a forced adjacent swap. The lesson of each frame *is* the swap pair. |

The split is roughly: **stability for pointer-graph algorithms** (atoms
persist, edges change), **change_emphasis for array-indexed algorithms**
(positions are pinned, values migrate).
