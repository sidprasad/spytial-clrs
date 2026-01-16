# SpyTial Annotation Guide (From the Notebooks)

The notebooks show a consistent set of annotations for shaping diagrams. Below is a quick-reference guide with examples pulled from those patterns.

## Layout control

### `@orientation`

`orientation` steers edge directionality. For example, linked list nodes can be laid out left-to-right, and child pointers can be arranged below parents:

```python
@orientation(selector='next', directions=['directlyRight'])
@orientation(selector='data', directions=['below'])
class SinglyNode:
    ...
```

You can also specify different directions for different relations, such as `left` and `right` child links in trees or `prev` vs `next` pointers in doubly linked lists.

### `@align`

`align` pins nodes to a shared axis. Matrix visualizations rely on aligning cells by row and column:

```python
SAME_ROW = "(row.~row)"
SAME_COL = "(col.~col)"

@align(selector=SAME_ROW, direction='horizontal')
@align(selector=SAME_COL, direction='vertical')
class MatrixWrapper:
    ...
```

### `@group`

`group` puts nodes into labeled groupings, which is useful for hash table buckets or other collections:

```python
@group(selector="(((NoneType.~key) -> Node) & ^next) - iden", name='bucket')
class HashTable:
    ...
```

## Styling and visibility

### `@atomColor`

`atomColor` helps highlight key nodes:

```python
@atomColor(selector='{x : DoublyNode | x.prev in NoneType}', value='black')
class DoublyNode:
    ...
```

### `@hideAtom` and `@hideField`

Use these to suppress diagram noise, like sentinel atoms or implementation details:

```python
@hideAtom(selector='NoneType + int')
@hideField(selector='Node', field='prev')
class Node:
    ...
```

### `@attribute`

`attribute` ensures selected fields are shown explicitly (useful for making record-like nodes):

```python
@attribute(field='key')
@attribute(field='val')
class Node:
    ...
```

## Derived structure

### `@inferredEdge`

`inferredEdge` creates edges from selectors that describe relationships not explicitly encoded as object fields. Direct-address tables use this to connect keys to stored values:

```python
mapsto = "{k : int, v : (object - NoneType) | (some t : tuple | t.t1 not in NoneType and t.t1 = v and t.t0 = k)}"

@inferredEdge(selector=mapsto, name='maps-to')
class DirectAddress:
    ...
```

## Conditional layout

### `@apply_if` and `cyclic`

Some notebooks switch between layout styles by toggling a constant and conditionally applying annotations:

```python
VIEW = "CYCLIC"  # or "LINEAR"

@apply_if(
    VIEW=="CYCLIC",
    cyclic(selector='next & (CircularNode->CircularNode)', direction='clockwise')
)
class CircularNode:
    ...
```

This lets you quickly compare alternate visualizations of the same structure.
