"""
Perf benchmark recipes for spytial-clrs data structures.

These used to live inside the notebooks as ``if RUN_PERF:`` blocks. They now live
here so the notebooks stay clean. ``run_perf.py`` reads a recipe, renders it into a
code cell, and appends that cell to a *temp copy* of the relevant notebook before
executing it. Because the cell is appended at the end, it runs in a kernel namespace
where the structure classes (``DirectAddress``, ``Graph``, ``BSTree``, …), the
``from spytial import *`` helpers (``inferredEdge``, ``hideAtom``, ``group``,
``orientation``), and notebook-defined constants (``ADJ_MATRIX_TO_EDGE_SELECTOR``)
are all already defined — so a recipe's ``build`` source can reference them freely.

Each recipe is keyed by structure name (matching ``run_perf.STRUCTURE_TO_NOTEBOOK``):

    build      source of ``def build(size): ... return <diagrammable obj>``.
    timeout    ``diagram(timeout=...)`` in seconds, or None to omit.
    sizes      optional list overriding ``perf_utils.SIZES`` (e.g. memoization).
    label      optional expression (in terms of ``size``) for the size used in the
               perf-result filename. Defaults to ``"size"``.
"""

RECIPES = {
    # ── hash-tables.ipynb ────────────────────────────────────────────────────
    "direct_address": {
        "timeout": 300,
        "build": '''
def build(size):
    da = DirectAddress(size)
    keys = random.sample(range(size), min(size, size // 2))
    for key in keys:
        hd = HashedData(key=key, sdata=f"data_{key}")
        da.insert(key, hd)
    return da
''',
    },
    "hash_table_chaining": {
        "timeout": 500,
        "build": '''
def build(size):
    ht = HashTableChaining(m=size)
    keys = random.sample(range(1, 1000), size)
    for key in keys:
        node = Node(key=key, val=f"value_{key}")
        ht.insert(node)
    return ht
''',
    },

    # ── linked-lists.ipynb ───────────────────────────────────────────────────
    "singly_linked_list": {
        "timeout": None,
        "build": '''
def build(size):
    elements = random.sample(range(1, 1000), size)
    return buildSinglyLinkedList(elements)
''',
    },
    "doubly_linked_list": {
        "timeout": None,
        "build": '''
def build(size):
    elements = random.sample(range(1, 1000), size)
    return buildDoublyLinkedList(elements)
''',
    },
    "circular_doubly_linked_list": {
        "timeout": None,
        "build": '''
def build(size):
    elements = random.sample(range(1, 1000), size)
    return buildCircularDoublyLinkedList(elements)
''',
    },

    # ── graphs.ipynb ─────────────────────────────────────────────────────────
    "unweighted_graph_adjmatrix": {
        "timeout": 300,
        "build": '''
def build(size):
    adj_matrix = [[random.randint(0, 1) if i != j else 0 for j in range(size)] for i in range(size)]
    dg = inferredEdge(selector=ADJ_MATRIX_TO_EDGE_SELECTOR, name="")(adj_matrix)
    dg = hideAtom(selector="list")(dg)
    return dg
''',
    },
    "weighted_graph": {
        "timeout": 800,
        "build": '''
def build(size):
    adj_matrix = [[random.randint(0, 1) if i != j else 0 for j in range(size)] for i in range(size)]
    g = Graph()
    nodes = {i: GNode(i) for i in range(size)}
    for i in range(size):
        for j in range(size):
            if adj_matrix[i][j] == 1:
                w = random.randint(1, 20)
                g.addEdge(nodes[i], nodes[j], w)
    return g
''',
    },
    "mst_graph": {
        "timeout": 500,
        "build": '''
def build(size):
    mst_graph = MSTGraph()
    nodes = {i: GNode(i) for i in range(size)}
    for i in range(size - 1):
        w = random.randint(1, 20)
        mst_graph.addEdge(nodes[i], nodes[i + 1], w)
    num_extra_edges = min(size, size * (size - 1) // 4)
    for _ in range(num_extra_edges):
        u = random.randint(0, size - 1)
        v = random.randint(0, size - 1)
        if u != v:
            w = random.randint(1, 20)
            mst_graph.addEdge(nodes[u], nodes[v], w)
    mst_graph.compute_mst()
    return mst_graph
''',
    },
    "scc_graph": {
        "timeout": 600,
        "build": '''
def build(size):
    adj_matrix = [[random.randint(0, 1) if i != j else 0 for j in range(size)] for i in range(size)]
    two_comp = inferredEdge(selector=ADJ_MATRIX_TO_EDGE_SELECTOR, name="")(adj_matrix)
    two_comp = hideAtom(selector="list")(two_comp)
    sss = f"(int->int) & {{u, v : int | ((u->v +v->u) in ^{ADJ_MATRIX_TO_EDGE_SELECTOR}) }}"
    two_comp = group(selector=sss, name="SCC")(two_comp)
    return two_comp
''',
    },
    "topo_sort_dag": {
        "timeout": 600,
        "build": '''
def build(size):
    dag_adj_matrix = [[0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1, size):
            if random.random() < 0.3:
                dag_adj_matrix[i][j] = 1
    dag = inferredEdge(selector=ADJ_MATRIX_TO_EDGE_SELECTOR, name="")(dag_adj_matrix)
    dag = orientation(selector=ADJ_MATRIX_TO_EDGE_SELECTOR, directions=["right"])(dag)
    dag = hideAtom(selector="list")(dag)
    return dag
''',
    },

    # ── memoization.ipynb ────────────────────────────────────────────────────
    # Iterates over chain lengths [3, 4, 7, 10]; perf files are labeled by the
    # number of triangular-matrix cells (size*(size+1)//2), not the chain length.
    "memoization_matrix": {
        "timeout": 600,
        "sizes": [3, 4, 7, 10],
        "label": "size * (size + 1) // 2",
        "build": '''
def build(size):
    p = [random.randint(5, 50) for _ in range(size)]
    m, s = bottom_up_matrix_chain(p)
    return MatrixWrapper(m, skip_inf=True)
''',
    },

    # ── disjoint-sets.ipynb ──────────────────────────────────────────────────
    "disjoint_set": {
        "timeout": 500,
        "build": '''
def build(size):
    ds = DisjointSet()
    elements = [ds.make_set(i) for i in range(size)]
    for _ in range(size // 2):
        i, j = random.sample(range(size), 2)
        ds.union(elements[i], elements[j])
    return hideAtom(selector="list")(elements)
''',
    },

    # ── heaps.ipynb ──────────────────────────────────────────────────────────
    "max_heap": {
        "timeout": 300,
        "build": '''
def build(size):
    values = random.sample(range(1, 1000), size)
    return MaxHeap(values)
''',
    },
    "fibonacci_heap": {
        "timeout": 300,
        "build": '''
def build(size):
    H = FibonacciHeap()
    values = random.sample(range(1, 1000), size)
    nodes = [H.insert(val) for val in values]
    if size > 2:
        H.extract_min()
        for i in range(min(3, len(nodes) - 1)):
            if nodes[i].key > 10:
                H.decrease_key(nodes[i], nodes[i].key - 5)
    return H
''',
    },

    # ── stacksqueues.ipynb ───────────────────────────────────────────────────
    "array_stack": {
        "timeout": None,
        "build": '''
def build(size):
    S = ArrayStack(size)
    values = random.sample(range(1, 1000), size)
    for val in values:
        S.push(val)
    return S
''',
    },
    "array_queue": {
        "timeout": None,
        "build": '''
def build(size):
    Q = ArrayQueue(size + 1)
    values = random.sample(range(1, 1000), size)
    for val in values:
        Q.enqueue(val)
    return Q
''',
    },

    # ── huffman.ipynb ────────────────────────────────────────────────────────
    "huffmantree": {
        "timeout": None,
        "build": '''
def build(size):
    import string
    num_chars = min(size, 26)
    chars = random.sample(string.ascii_lowercase, num_chars)
    s = ""
    for char in chars:
        s += char * random.randint(1, 100)
    codes, root = huffman_codes(s)
    return root
''',
    },

    # ── trees.ipynb ──────────────────────────────────────────────────────────
    "bstree": {
        "timeout": None,
        "build": '''
def build(size):
    values = random.sample(range(1, 1000), size)
    bst = BSTree()
    for val in values:
        bst.insert(val)
    return bst
''',
    },
    "rbtree": {
        "timeout": None,
        "build": '''
def build(size):
    values = random.sample(range(1, 1000), size)
    bst = RBTree()
    for val in values:
        bst.insert(val)
    return bst
''',
    },
    "ostree": {
        "timeout": None,
        "build": '''
def build(size):
    values = random.sample(range(1, 1000), size)
    bst = OSTree()
    for val in values:
        bst.insert(val)
    return bst
''',
    },
    "btree": {
        "timeout": 400,
        "build": '''
def build(size):
    import string, itertools
    char_pool = list(string.ascii_uppercase + string.ascii_lowercase)
    char_pool += [a + b for a, b in itertools.product(string.ascii_uppercase, string.ascii_lowercase)]
    values = random.sample(char_pool, min(size, len(char_pool)))
    b = BTree(2)
    for val in values:
        b.insert(val)
    return b
''',
    },
    "vebtree": {
        "timeout": 400,
        "build": '''
def build(size):
    # vEB requires universe size u as a power of two; 64 covers the fixed sizes.
    u = 64
    values = random.sample(range(0, u), size)
    veb = VEB(u=u)
    for val in values:
        veb.insert(val)
    return veb
''',
    },
    "intervaltree": {
        "timeout": 400,
        "build": '''
def build(size):
    intervals = []
    for _ in range(size):
        low = random.randint(0, 1000)
        high = random.randint(low + 1, 1000 + 10)
        intervals.append((low, high))
    it = IntervalTree()
    for low, high in intervals:
        it.insert(low, high)
    return it
''',
    },
}
