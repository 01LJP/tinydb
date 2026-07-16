"""B-tree index for tinydb.

A classic B+ tree style index where:

- Each node occupies one 4096-byte page (conceptually).  For simplicity, nodes
  are held in memory and the entire B-tree is serialised with ``pickle`` onto
  a single index page (sufficient for teaching workloads with modest data).
- Leaf nodes store ``(key, record_pointer)`` pairs, linked together via
  ``right_ptr`` to support efficient range scans.
- Internal nodes store separator keys and child page-ids.

The default order is 250: with ~8 bytes per key+pointer entry a leaf fits
comfortably inside a 4 KB page.
"""

import pickle
from bisect import bisect_left, bisect_right
from typing import List, Optional


# Sentinel record-pointer returned when a key is not found.
NOT_FOUND = -1


class BTreeNode:
    """A B-tree node (conceptually one 4096-byte page).

    Attributes
    ----------
    page_id: int
        Unique node identifier.
    is_leaf: bool
        True if this is a leaf node.
    keys: list
        Sorted keys.
    children: list
        Child page-ids (internal nodes only).  Length is ``len(keys) + 1``.
    pointers: list
        Record pointers (leaf nodes only).  Aligned one-to-one with ``keys``.
    parent_id: int
        Parent node's page_id, or -1 for the root.
    right_ptr: int
        Page_id of the next leaf in the leaf-level linked list, or -1.
    """

    __slots__ = (
        "page_id", "is_leaf", "keys", "children",
        "pointers", "parent_id", "right_ptr",
    )

    def __init__(self, page_id: int, is_leaf: bool = True):
        self.page_id = page_id
        self.is_leaf = is_leaf
        self.keys: list = []
        self.children: list = []      # internal: child page-ids
        self.pointers: list = []      # leaf: record pointers
        self.parent_id: int = -1
        self.right_ptr: int = -1      # leaf chain right neighbour

    # ------------------------------------------------------------------
    # Capacity
    # ------------------------------------------------------------------

    def is_full(self, order: int = 250) -> bool:
        """Return True when the node holds ``order`` keys (must split next)."""
        return len(self.keys) >= order

    # ------------------------------------------------------------------
    # Serialization (pickle based)
    # ------------------------------------------------------------------

    def serialize(self) -> bytes:
        """Return a byte representation of this node."""
        return pickle.dumps({
            "page_id": self.page_id,
            "is_leaf": self.is_leaf,
            "keys": self.keys,
            "children": self.children,
            "pointers": self.pointers,
            "parent_id": self.parent_id,
            "right_ptr": self.right_ptr,
        })

    @classmethod
    def deserialize(cls, data: bytes) -> "BTreeNode":
        """Reconstruct a node from :meth:`serialize` bytes."""
        blob = pickle.loads(data)
        node = cls(blob["page_id"], blob["is_leaf"])
        node.keys = blob["keys"]
        node.children = blob["children"]
        node.pointers = blob["pointers"]
        node.parent_id = blob["parent_id"]
        node.right_ptr = blob["right_ptr"]
        return node

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self):
        kind = "leaf" if self.is_leaf else "internal"
        return f"<BTreeNode {self.page_id} {kind} keys={self.keys}>"


class BTree:
    """B-tree index over integer (or comparable) keys.

    Parameters
    ----------
    buffer_pool : BufferPool or None
        When provided, :meth:`save` and :meth:`load` persist the tree through it.
    root_page_id : int or None
        Page-id of a previously saved tree root (used with ``load``).
    order : int
        Maximum number of keys per node before a split (default 250).
    """

    # Magic prefix so we can recognise a valid B-tree blob on reload.
    _MAGIC = b"BTR\x01"

    def __init__(self, buffer_pool=None, root_page_id=None, order: int = 250):
        self.buffer_pool = buffer_pool
        self.root_page_id = root_page_id
        self.order = order
        self._next_page_id: int = 1       # monotonically increasing allocator
        self._nodes: dict = {}            # page_id -> BTreeNode (in-memory map)

        if self.root_page_id is not None:
            self._nodes.setdefault(
                self.root_page_id,
                BTreeNode(self.root_page_id, is_leaf=True),
            )

    def _ensure_root_page(self) -> None:
        """Allocate a root page if we don't have one yet."""
        if self.root_page_id is None and self.buffer_pool is not None:
            fm = self.buffer_pool.file_manager
            self.root_page_id = fm.allocate_page()
            self._next_page_id = max(self._next_page_id, self.root_page_id + 1)
            self._nodes.setdefault(
                self.root_page_id,
                BTreeNode(self.root_page_id, is_leaf=True),
            )

    # ------------------------------------------------------------------
    # Internal node management
    # ------------------------------------------------------------------

    def _new_page_id(self) -> int:
        pid = self._next_page_id
        self._next_page_id += 1
        return pid

    def _read_node(self, page_id: int) -> BTreeNode:
        """Return the in-memory node for *page_id*.

        For the teaching implementation nodes live in ``self._nodes``.  When a
        ``buffer_pool`` is supplied we also consult it as an overflow.
        """
        if page_id in self._nodes:
            return self._nodes[page_id]
        # Try buffer pool if available
        if self.buffer_pool is not None:
            page = self.buffer_pool.get_page(page_id)
            if page.slot_count > 0:
                data = page.get_record(0)  # whole node blob in one slot
                node = self._decode_node_blob(data)
                self._nodes[page_id] = node
                return node
        raise KeyError(f"node page {page_id} not found")

    def _save_node(self, node: BTreeNode) -> None:
        """Write a node into the in-memory map (and optional buffer pool)."""
        self._nodes[node.page_id] = node
        if self.buffer_pool is not None:
            blob = self._encode_node_blob(node)
            page = self.buffer_pool.get_page(node.page_id)
            # store as a single record in the page
            if page.slot_count > 0:
                # page already has data — reset it by recreating flags only
                page.buf = bytearray(page.PAGE_SIZE)
                page.slot_count = 0
                page.free_space = page.PAGE_SIZE - page.HEADER_SIZE
                page._write_header()
            page.insert_record(blob)
            page.flags = 2  # INDEX_DATA
            self.buffer_pool.mark_dirty(node.page_id)

    # ------------------------------------------------------------------
    # Encode / decode helpers (pickle wrappers kept separate for clarity)
    # ------------------------------------------------------------------

    @staticmethod
    def _encode_node_blob(node: BTreeNode) -> bytes:
        return node.serialize()

    @staticmethod
    def _decode_node_blob(data: bytes) -> BTreeNode:
        return BTreeNode.deserialize(data)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, key) -> int:
        """Return the *record_pointer* for *key*, or -1 if not found."""
        if self.root_page_id is None:
            return NOT_FOUND
        node = self._read_node(self.root_page_id)
        while not node.is_leaf:
            i = bisect_right(node.keys, key)
            node = self._read_node(node.children[i])
        i = bisect_left(node.keys, key)
        if i < len(node.keys) and node.keys[i] == key:
            return node.pointers[i]
        return NOT_FOUND

    # ------------------------------------------------------------------
    # Range scan
    # ------------------------------------------------------------------

    def range_scan(self, low, high) -> List[int]:
        """Return record pointers for keys in the inclusive interval [low, high]."""
        result: List[int] = []
        if self.root_page_id is None:
            return result
        # descend to the leaf that may contain ``low``
        node = self._read_node(self.root_page_id)
        while not node.is_leaf:
            i = bisect_right(node.keys, low)
            node = self._read_node(node.children[i])

        # walk the leaf chain
        current = node
        while current is not None:
            for k, ptr in zip(current.keys, current.pointers):
                if k > high:
                    return result
                if k >= low:
                    result.append(ptr)
            if current.right_ptr == -1:
                break
            current = self._read_node(current.right_ptr)
        return result

    # ------------------------------------------------------------------
    # Insert
    # ------------------------------------------------------------------

    def insert(self, key, record_pointer: int) -> None:
        """Insert ``(key, record_pointer)`` into the index.

        If the key already exists its pointer is updated in place.
        """
        if self.root_page_id is None:
            # pure in-memory tree: allocate a virtual page id
            pid = self._new_page_id()
            self.root_page_id = pid
            self._nodes[pid] = BTreeNode(pid, is_leaf=True)
        self._ensure_root_page()

        root = self._read_node(self.root_page_id)
        if root.is_full(self.order):
            # root split: create a new root
            new_root_pid = self._new_page_id()
            new_root = BTreeNode(new_root_pid, is_leaf=False)
            new_root.children.append(root.page_id)
            root.parent_id = new_root_pid
            self._save_node(root)
            self._split_child(new_root, 0)
            self.root_page_id = new_root_pid
            self._save_node(new_root)
            # refresh local reference
            root = new_root

        self._insert_nonfull(root, key, record_pointer)

    def _insert_nonfull(self, node: BTreeNode, key, pointer: int) -> None:
        """Insert into a node that is guaranteed not to be full."""
        if node.is_leaf:
            i = bisect_left(node.keys, key)
            if i < len(node.keys) and node.keys[i] == key:
                # overwrite existing key
                node.pointers[i] = pointer
            else:
                node.keys.insert(i, key)
                node.pointers.insert(i, pointer)
            self._save_node(node)
        else:
            i = bisect_right(node.keys, key)
            child = self._read_node(node.children[i])
            if child.is_full(self.order):
                self._split_child(node, i)
                # after split re-check which child to descend into
                if key > node.keys[i]:
                    i += 1
                elif key == node.keys[i]:
                    # duplicate on separator — update child pointer position
                    pass
                child = self._read_node(node.children[i])
            self._insert_nonfull(child, key, pointer)

    # ------------------------------------------------------------------
    # Splitting
    # ------------------------------------------------------------------

    def _split_child(self, parent: BTreeNode, index: int) -> None:
        """Split the *index*-th child of *parent*."""
        child = self._read_node(parent.children[index])
        if child.is_leaf:
            new_node, median_key = self._split_leaf(child)
        else:
            new_node, median_key = self._split_internal(child)
        # insert median_key and new_node reference into parent
        parent.keys.insert(index, median_key)
        parent.children.insert(index + 1, new_node.page_id)
        new_node.parent_id = parent.page_id
        self._save_node(child)
        self._save_node(new_node)
        self._save_node(parent)

    def _split_leaf(self, node: BTreeNode):
        """Split a leaf node.

        Returns ``(new_node, median_key)``.  ``median_key`` is the first key of
        the new (right-hand) node and is promoted to the parent.  ``node``
        keeps the left half.
        """
        mid = len(node.keys) // 2
        new_pid = self._new_page_id()
        new_node = BTreeNode(new_pid, is_leaf=True)

        # right half goes to new_node
        new_node.keys = node.keys[mid:]
        new_node.pointers = node.pointers[mid:]

        # left half stays in node
        node.keys = node.keys[:mid]
        node.pointers = node.pointers[:mid]

        # linked list: new_node takes node's old right neighbour
        new_node.right_ptr = node.right_ptr
        node.right_ptr = new_node.page_id

        median_key = new_node.keys[0]
        return new_node, median_key

    def _split_internal(self, node: BTreeNode):
        """Split an internal node.

        Returns ``(new_node, median_key)``.  ``median_key`` is promoted to the
        parent; the keys that follow it in the original node go to the new
        right-hand node.
        """
        mid = len(node.keys) // 2
        median_key = node.keys[mid]

        new_pid = self._new_page_id()
        new_node = BTreeNode(new_pid, is_leaf=False)

        # right half (keys after median) goes to new_node
        new_node.keys = node.keys[mid + 1:]
        new_node.children = node.children[mid + 1:]

        # update parent pointers of moved children
        for cid in new_node.children:
            child = self._read_node(cid)
            child.parent_id = new_pid
            self._save_node(child)

        # left half stays in node
        node.keys = node.keys[:mid]
        node.children = node.children[:mid + 1]

        return new_node, median_key

    # ------------------------------------------------------------------
    # Delete (simple tombstone-style: removes the key/pointer from the leaf)
    # ------------------------------------------------------------------

    def delete(self, key) -> bool:
        """Delete *key*.  Returns True if the key was found and removed."""
        if self.root_page_id is None:
            return False
        node = self._read_node(self.root_page_id)
        while not node.is_leaf:
            i = bisect_right(node.keys, key)
            node = self._read_node(node.children[i])
        i = bisect_left(node.keys, key)
        if i < len(node.keys) and node.keys[i] == key:
            node.keys.pop(i)
            node.pointers.pop(i)
            self._save_node(node)
            return True
        return False

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Persist the entire B-tree to the buffer pool.

        One node per page, addressed by the node's own virtual ``page_id``
        (written directly via ``fm.write_page`` — no ``allocate_page`` calls,
        so virtual ids never collide with file-manager pages).  The root
        page holds the meta record at slot 0 plus the root node at slot 1.
        The meta record lists every node's page id so ``load()`` can find
        them all.
        """
        if self.buffer_pool is None:
            return
        self._ensure_root_page()
        fm = self.buffer_pool.file_manager

        # write each non-root node to its own virtual page id
        node_pages: list = []
        for node in self._nodes.values():
            if node.page_id == self.root_page_id:
                continue
            page = self.buffer_pool.get_page(node.page_id)
            page.buf = bytearray(page.PAGE_SIZE)
            page.slot_count = 0
            page.free_space = page.PAGE_SIZE - page.HEADER_SIZE
            page._write_header()
            page.flags = 2  # INDEX_DATA
            page.insert_record(self._encode_node_blob(node))
            self.buffer_pool.mark_dirty(node.page_id)
            node_pages.append(node.page_id)

        # root page: meta at slot 0, root node at slot 1
        meta = {
            "magic": self._MAGIC,
            "order": self.order,
            "root_page_id": self.root_page_id,
            "next_page_id": self._next_page_id,
            "node_pages": node_pages,
        }
        root_page = self.buffer_pool.get_page(self.root_page_id)
        root_page.buf = bytearray(root_page.PAGE_SIZE)
        root_page.slot_count = 0
        root_page.free_space = root_page.PAGE_SIZE - root_page.HEADER_SIZE
        root_page._write_header()
        root_page.flags = 2
        root_page.insert_record(pickle.dumps(meta))
        root_page.insert_record(self._encode_node_blob(
            self._nodes[self.root_page_id]))
        self.buffer_pool.mark_dirty(self.root_page_id)

    def load(self) -> None:
        """Load a B-tree previously written with :meth:`save`."""
        if self.buffer_pool is None:
            return
        if self.root_page_id is None:
            return
        root_page = self.buffer_pool.get_page(self.root_page_id)
        if root_page.slot_count == 0:
            return
        meta = pickle.loads(root_page.get_record(0))
        if meta.get("magic") != self._MAGIC:
            raise ValueError("buffer does not contain a valid B-tree image")
        self.order = meta["order"]
        self.root_page_id = meta["root_page_id"]
        self._next_page_id = meta["next_page_id"]
        self._nodes = {}

        # root node at slot 1 of root page
        if root_page.slot_count > 1:
            node = self._decode_node_blob(root_page.get_record(1))
            self._nodes[node.page_id] = node

        # other nodes: one per page at slot 0
        for pid in meta.get("node_pages", []):
            page = self.buffer_pool.get_page(pid)
            if page.slot_count == 0:
                continue
            data = page.get_record(0)
            if not data:
                continue
            try:
                node = self._decode_node_blob(data)
            except Exception:
                continue
            self._nodes[node.page_id] = node


# =========================================================================
# IndexManager
# =========================================================================


class IndexManager:
    """Manage all indices for a database.

    Keyed by ``(table_name, column_name)`` and holds a :class:`BTree` per
    index.  For simplicity the index map itself is held in memory (catalog
    persistence is out of scope here).
    """

    def __init__(self, buffer_pool, catalog):
        self.buffer_pool = buffer_pool
        self.catalog = catalog
        self.indices: dict = {}   # (table, column) -> BTree

    # ------------------------------------------------------------------
    # Index lifecycle
    # ------------------------------------------------------------------

    def create_index(self, table_name: str, column: str) -> BTree:
        """Create a new B-tree index on ``table_name.column``.

        If the table object is registered with the catalog this method scans
        its existing records and populates the index.
        """
        key = (table_name, column)
        # allocate a fresh page for the root
        fm = self.buffer_pool.file_manager
        root_page_id = fm.allocate_page()
        bt = BTree(
            buffer_pool=self.buffer_pool,
            root_page_id=root_page_id,
        )
        bt.save()
        # populate from existing rows if the table is registered
        table_obj = self.catalog.get_table_object(table_name)
        if table_obj is not None:
            for row in table_obj.scan():
                val = row[column]
                if val is not None:
                    bt.insert(val, row.record_id)
            bt.save()
        self.indices[key] = bt
        return bt

    def get_index(self, table_name: str, column: str) -> Optional[BTree]:
        """Return the B-tree for ``(table_name, column)`` or None."""
        return self.indices.get((table_name, column))

    # ------------------------------------------------------------------
    # DML hooks
    # ------------------------------------------------------------------

    def insert_indexes(self, table_name: str, row: dict, record_pointer: int) -> None:
        """Update every index for *table_name* to include the new row."""
        for (tname, col), bt in self.indices.items():
            if tname != table_name:
                continue
            val = row.get(col)
            if val is not None:
                bt.insert(val, record_pointer)

    def delete_indexes(self, table_name: str, row: dict, record_pointer: int) -> None:
        """Remove *row* from every index for *table_name*."""
        for (tname, col), bt in self.indices.items():
            if tname != table_name:
                continue
            val = row.get(col)
            if val is not None:
                bt.delete(val)

    def update_indexes(
        self,
        table_name: str,
        old_row: dict,
        new_row: dict,
        record_pointer: int,
    ) -> None:
        """Reflect an update across every index for *table_name*."""
        for (tname, col), bt in self.indices.items():
            if tname != table_name:
                continue
            old_val = old_row.get(col)
            new_val = new_row.get(col)
            if old_val == new_val:
                continue
            if old_val is not None:
                bt.delete(old_val)
            if new_val is not None:
                bt.insert(new_val, record_pointer)
