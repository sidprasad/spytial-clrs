# SpyTial CLRS

This repository contains notebooks showing SpyTial's implementation of CLRS data structures.





| Chapter                            | Structures                                                  | Notebook            | # Constraints           | # Directives            |
| ---------------------------------- | ----------------------------------------------------------- | ------------------- | ----------------------- | ----------------------- |
| 6 Heapsort                         | Max Heap                                                    | heaps.ipynb         | 3                       | 2                       |
| 10 Elementary Data Structures      | **Stacks**                                                  | stacksqueues.ipynb  | 2                       | 3                       |
| 10 Elementary Data Structures      | Queues                                                      | stacksqueues.ipynb  | 2                       | 5                       |
| 10.2 Linked lists                  | **Linked Lists**                                            | linked-lists.ipynb  | 2                       | 0                       |
| 10.2 Linked lists                  | **Doubly Linked Lists**                                     | linked-lists.ipynb  | 4                       | 2                       |
| 10.2 Linked lists                  | **Circular Linked Lists**                                   | linked-lists.ipynb  | 2                       | 2                       |
| 11 Hash Tables                     | **Direct-address tables**                                   | hash-tables.ipynb   | 3                       | 4                       |
| 11.2 Hash tables                   | **Chained Hash Tables**                                     | hash-tables.ipynb   | 5                       | 4                       |
| 12 Binary Search Trees             | **Binary Search Trees**                                     | trees.ipynb         | 3                       | 2                       |
| 13 Red-Black Trees                 | **Red-black trees**                                         | trees.ipynb         | 3                       | 5                       |
| 14 Augmenting Data Structures      | **Order Statistic Tree**                                    | trees.ipynb         | 0 + RBTree              | 1 + RBTree              |
| 14.3 Interval trees                | **Interval Trees**                                          | trees.ipynb         | 0 + RBTree              | 3 + RBTree              |
| 15.2 Matrix-chain multiplication   | Memoization matrix                                          | memoization.ipynb   |                         |                         |
| 16.3 Huffman codes                 | **Huffman codes as tree**                                   | huffman.ipynb       | 5                       | 2                       |
| 18 B-Trees                         | **B-trees**                                                 | trees.ipynb         | 5                       | 3                       |
| 19 Fibonacci Heaps                 | **Fibonacci heaps**                                         | heaps.ipynb         | 4                       | 5                       |
| 20 van Emde Boas Trees             | **VEB Tree**                                                | trees.ipynb         | 2                       | 3                       |
| 21.3 Disjoint-set forests          | **Disjoint Set Forest / Set view**                          | disjoint-sets.ipynb | 6                       | 2                       |
| 22 Elementary Graph Algorithms     | **Unweighted Graph from Adjacency Matrix**                  | graphs.ipynb        | 1                       | 1                       |
| 22.4 Topological sort              | Adj Matrix Topologically sorted                             | graphs.ipynb        | 1 + Adj Matrix to Graph | 0 + Adj Matrix to Graph |
| 22.5 Strongly connected components | Adj matrix → Graph grouped by strongly connected components | graphs.ipynb        | 1 + Adj Matrix to Graph | 0 + Adj Matrix to Graph |
| 22 Elementary Graph Algorithms     | **Weighted Graph from Adj List**                            | graphs.ipynb        | 1                       | 2                       |
| 23 Minimum Spanning Trees          | **MST on graph**                                            | graphs.ipynb        | 1                       | 2                       |

Bonus: 
- BDD in `simple-bdd.ipynb`


## Local Setup

To run the notebooks locally:

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Launch Jupyter: `jupyter notebook src/`

