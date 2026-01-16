# Getting Started with SpyTial in This Repo

This repository is a collection of CLRS-aligned data structure notebooks that use SpyTial to diagram Python object graphs. The notebooks follow a shared pattern:

1. Install the diagramming library.
2. Import SpyTial APIs and annotations.
3. Define Python classes for the structure you want to visualize.
4. Add SpyTial annotations to control layout.
5. Build a concrete instance and call `diagram(...)` to render it.

## 1) Install and import

Most notebooks begin with the same setup:

```python
%pip install -q spytial-diagramming
from spytial import *
from spytial.annotations import *
```

## 2) Define a class and add annotations

SpyTial annotations decorate your classes to convey layout intentions. For example, a singly linked list lays out `next` pointers in a row and shows the `data` field under each node:

```python
@orientation(selector='next', directions=['directlyRight'])
@orientation(selector='data', directions=['below'])
class SinglyNode:
    def __init__(self, data, next_node=None):
        self.data = data
        self.next = next_node
```

## 3) Build an instance and render

Once you have an instance, call `diagram`:

```python
xs = SinglyNode('c', SinglyNode('b', SinglyNode('a')))
diagram(xs)
```

You will see a graph-like diagram where objects become nodes and fields become labeled arrows. The notebooks often switch to a browser renderer for performance testing:

```python
diagram(xs, method="browser", headless=True)
```

## 4) Use sentinel objects when structure size matters

For array-based structures (like stacks/queues), the notebooks use a sentinel `EmptySlot` rather than `None` so empty positions remain distinct atoms and layout can respect array size. This keeps diagrams faithful to CLRS figures.

## 5) Explore the notebooks

The notebooks in `src/` are structured as cookbook examples. Start with linked lists and stacks/queues for the most compact examples, then move to trees, graphs, and the BDD walkthrough for more advanced annotation usage.
