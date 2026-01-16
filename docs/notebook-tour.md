# Notebook Tour

The notebooks in `src/` are the primary reference for how SpyTial is used. This tour is meant to help you pick the right starting point and understand what each notebook demonstrates.

## Recommended reading order

1. **Linked lists (`linked-lists.ipynb`)** — The smallest, clearest examples of `@orientation`, `@attribute`, and conditional layouts.
2. **Stacks and queues (`stacksqueues.ipynb`)** — Shows how to model arrays and use sentinels to preserve empty slots.
3. **Hash tables (`hash-tables.ipynb`)** — Introduces `@inferredEdge`, `@group`, and `@hideField` for cleaner diagrams.
4. **Trees (`trees.ipynb`)** — Expands into multi-annotation layouts with BSTs, red-black trees, B-trees, and more.
5. **Graphs (`graphs.ipynb`)** — Uses inferred edges to convert adjacency matrices/lists into graph diagrams.
6. **Heaps (`heaps.ipynb`)** — Demonstrates both array and pointer-based heap views (including Fibonacci heaps).
7. **Disjoint sets (`disjoint-sets.ipynb`)** — Combines parent pointers with rank-based layout hints.
8. **Memoization (`memoization.ipynb`)** — Shows matrix diagrams via `@align` and row/column ordering.
9. **Huffman (`huffman.ipynb`)** — Builds trees with explicit left/right orientation and symbol labels.
10. **Bonus: BDD (`simple-bdd.ipynb`)** — A multi-step walkthrough showing how to progressively refine a diagram from raw object graph to polished visualization.

## What to look for in each notebook

### Linked lists

* `@orientation` for pointer direction.
* `@attribute` to expose node data.
* `@apply_if` + `cyclic` to toggle circular layout.

### Stacks and queues

* Sentinel objects for empty array positions.
* `@inferredEdge` to map array indexes to logical top/head/tail nodes.
* Repeated calls to `diagram(...)` to show evolution across operations.

### Hash tables

* `@inferredEdge` to build “maps-to” edges.
* `@group` and `@align` for bucket layout.
* `@hideField` to suppress internal pointers.

### Trees

* Multiple `@orientation` rules for left/right child placement.
* `@atomColor` for red/black node styling.
* Use of derived fields (e.g., subtree size for order-statistic trees).

### Graphs

* Converting adjacency matrices or lists into explicit graph nodes/edges.
* Layout comparisons between directed/undirected views.

### Heaps

* `@inferredEdge` selectors for left/right children in array heaps.
* Annotation-driven layouts for Fibonacci heap parent/child relationships.

### Disjoint sets

* Orienting parent pointers and using ranks as a visual cue for hierarchy.

### Memoization

* Matrix visualization with `@align` for rows/columns and `@orientation` for ordering.

### Huffman

* Orientation and alignment for binary trees with `0`/`1` edges.

### BDD

* Step-by-step refinements: hide irrelevant structure, align by variable, group by layer, color terminals, and resolve conflicting constraints.
