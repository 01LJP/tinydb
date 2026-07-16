"""Tests for tinydb B-tree index.

Covers: BTreeNode creation/serialization, insert + split, search, range scan,
and IndexManager CRUD.
"""

import os
import pickle
import tempfile
import pytest
from bisect import bisect_left, bisect_right

from tinydb.storage.page import Page
from tinydb.storage.file_manager import FileManager
from tinydb.storage.buffer_pool import BufferPool
from tinydb.catalog import Catalog
from tinydb.types import ColumnDef, DataType
from tinydb.index.btree import BTreeNode, BTree, IndexManager


# =========================================================================
# BTreeNode tests
# =========================================================================

class TestBTreeNode:
    """Verify BTreeNode structure and serialization."""

    def test_create_leaf_node(self):
        node = BTreeNode(page_id=5, is_leaf=True)
        assert node.page_id == 5
        assert node.is_leaf is True
        assert node.keys == []
        assert node.children == []
        assert node.pointers == []
        assert node.parent_id == -1
        assert node.right_ptr == -1

    def test_create_internal_node(self):
        node = BTreeNode(page_id=3, is_leaf=False)
        assert node.is_leaf is False
        assert node.children == []

    def test_is_full_default_order(self):
        node = BTreeNode(page_id=1, is_leaf=True)
        # default order = 250
        node.keys = list(range(250))
        assert node.is_full() is True

    def test_is_full_custom_order(self):
        node = BTreeNode(page_id=1, is_leaf=True)
        node.keys = list(range(4))
        assert node.is_full(order=5) is False
        node.keys = list(range(5))
        assert node.is_full(order=5) is True

    def test_serialize_deserialize_leaf(self):
        node = BTreeNode(page_id=10, is_leaf=True)
        node.keys = [1, 5, 10]
        node.pointers = [100, 500, 1000]
        node.parent_id = 2
        node.right_ptr = 11

        data = node.serialize()
        node2 = BTreeNode.deserialize(data)

        assert node2.page_id == 10
        assert node2.is_leaf is True
        assert node2.keys == [1, 5, 10]
        assert node2.pointers == [100, 500, 1000]
        assert node2.parent_id == 2
        assert node2.right_ptr == 11

    def test_serialize_deserialize_internal(self):
        node = BTreeNode(page_id=7, is_leaf=False)
        node.keys = [10, 20]
        node.children = [1, 2, 3]
        node.parent_id = 6
        node.right_ptr = -1

        data = node.serialize()
        node2 = BTreeNode.deserialize(data)

        assert node2.page_id == 7
        assert node2.is_leaf is False
        assert node2.keys == [10, 20]
        assert node2.children == [1, 2, 3]
        assert node2.parent_id == 6


# =========================================================================
# BTree tests — insert and search
# =========================================================================

class TestBTreeInsertAndSearch:
    """Verify B-tree insert + point search, including splits."""

    def test_insert_without_split(self):
        bt = BTree(order=4)
        for i in range(3):
            bt.insert(i, i * 100)
        assert bt.search(0) == 0
        assert bt.search(1) == 100
        assert bt.search(2) == 200

    def test_search_missing_key(self):
        bt = BTree(order=4)
        bt.insert(10, 999)
        assert bt.search(5) == -1
        assert bt.search(15) == -1

    def test_insert_triggers_leaf_split(self):
        """Insert enough keys to force a leaf split (order=4 -> max 4 keys)."""
        bt = BTree(order=4)
        for i in range(10):
            bt.insert(i, i * 10)
        # all keys searchable
        for i in range(10):
            assert bt.search(i) == i * 10

    def test_insert_triggers_internal_split(self):
        """Insert enough keys to force internal node splits."""
        bt = BTree(order=3)  # small order to force deep splits
        for i in range(50):
            bt.insert(i, i * 7)
        for i in range(50):
            assert bt.search(i) == i * 7

    def test_large_insert_and_search(self):
        """Stress test with order=250 and many keys."""
        bt = BTree(order=250)
        n = 5000
        for i in range(n):
            bt.insert(i, i * 3)
        # spot check
        assert bt.search(0) == 0
        assert bt.search(249) == 747
        assert bt.search(250) == 750
        assert bt.search(4999) == 14997
        assert bt.search(5000) == -1

    def test_insert_duplicate_key_overrides(self):
        bt = BTree(order=4)
        bt.insert(5, 100)
        bt.insert(5, 200)
        assert bt.search(5) == 200


# =========================================================================
# BTree tests — split correctness
# =========================================================================

class TestBTreeSplit:
    """Verify split invariants: median promotion, leaf linked list."""

    def test_split_leaf_median_promoted(self):
        bt = BTree(order=4)
        for i in range(5):  # forces first split at 5th insert (i=4)
            bt.insert(i, i)
        # root should now be internal with one median key
        root = bt._read_node(bt.root_page_id)
        assert root.is_leaf is False
        assert len(root.keys) >= 1
        # children should be leaves
        for cid in root.children:
            child = bt._read_node(cid)
            assert child.is_leaf is True

    def test_leaf_linked_list_maintained(self):
        """After splits, leaf chain via right_ptr covers all keys in order."""
        bt = BTree(order=4)
        for i in range(20):
            bt.insert(i, i)

        # walk the leaf chain
        root = bt._read_node(bt.root_page_id)
        # find leftmost leaf
        node = root
        while not node.is_leaf:
            node = bt._read_node(node.children[0])

        collected = []
        current = node
        while current.page_id != -1:
            collected.extend(current.keys)
            current = bt._read_node(current.right_ptr) if current.right_ptr != -1 else None
            if current is None:
                break

        assert collected == sorted(collected)
        assert set(collected) == set(range(20))

    def test_internal_split_promotes_median(self):
        bt = BTree(order=2)  # every insert likely triggers a split
        for i in range(10):
            bt.insert(i, i)

        # verify via full scan that all keys present
        keys = bt.range_scan(0, 9)
        assert set(keys) == set(range(10))


# =========================================================================
# BTree tests — range scan
# =========================================================================

class TestBTreeRangeScan:
    """Verify range scan using leaf linked list."""

    def test_range_scan_basic(self):
        bt = BTree(order=4)
        for i in range(100):
            bt.insert(i, i * 10)
        result = bt.range_scan(10, 20)
        assert result == [i * 10 for i in range(10, 21)]

    def test_range_scan_empty_result(self):
        bt = BTree(order=4)
        for i in range(50):
            bt.insert(i, i)
        result = bt.range_scan(100, 200)
        assert result == []

    def test_range_scan_single_element(self):
        bt = BTree(order=4)
        for i in range(50):
            bt.insert(i, i)
        result = bt.range_scan(25, 25)
        assert result == [25]

    def test_range_scan_entire_range(self):
        bt = BTree(order=4)
        for i in range(30):
            bt.insert(i, i)
        result = bt.range_scan(0, 29)
        assert result == list(range(30))

    def test_range_scan_after_many_splits(self):
        """Range scan still correct after deep splits."""
        bt = BTree(order=3)
        for i in range(100):
            bt.insert(i, i)
        result = bt.range_scan(33, 67)
        assert result == list(range(33, 68))


# =========================================================================
# BTree tests — persistence via buffer pool
# =========================================================================

class TestBTreePersistence:
    """Verify B-tree can be saved/loaded through buffer pool."""

    def test_save_and_load(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        tmp.close()
        try:
            fm = FileManager(tmp.name)
            bp = BufferPool(fm, capacity=10)
            bt = BTree(buffer_pool=bp, order=4)
            for i in range(50):
                bt.insert(i, i * 2)

            root_pid = bt.root_page_id
            bt.save()
            bp.flush_all()

            # reload using the same root page id
            bt2 = BTree(buffer_pool=bp, root_page_id=root_pid)
            bt2.load()
            for i in range(50):
                assert bt2.search(i) == i * 2

            bp.close()
        finally:
            os.unlink(tmp.name)

    def test_persistence_empty_tree(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        tmp.close()
        try:
            fm = FileManager(tmp.name)
            bp = BufferPool(fm, capacity=10)
            bt = BTree(buffer_pool=bp, order=4)
            bt.save()
            bp.flush_all()

            bt2 = BTree(buffer_pool=bp)
            bt2.load()
            assert bt2.search(0) == -1

            bp.close()
        finally:
            os.unlink(tmp.name)


# =========================================================================
# IndexManager tests
# =========================================================================

class TestIndexManager:
    """Verify IndexManager CRUD against a real catalog + buffer pool."""

    def _make_env(self):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        tmp.close()
        fm = FileManager(tmp.name)
        bp = BufferPool(fm, capacity=20)
        catalog = Catalog(bp)
        return tmp.name, fm, bp, catalog

    def _cleanup(self, path, bp):
        bp.close()
        os.unlink(path)

    def test_create_and_get_index(self):
        path, fm, bp, catalog = self._make_env()
        try:
            im = IndexManager(bp, catalog)
            bt = im.create_index("users", "id")
            assert isinstance(bt, BTree)
            assert im.get_index("users", "id") is bt
            assert im.get_index("users", "name") is None
        finally:
            self._cleanup(path, bp)

    def test_insert_and_search_via_manager(self):
        path, fm, bp, catalog = self._make_env()
        try:
            im = IndexManager(bp, catalog)
            im.create_index("users", "age")

            im.insert_indexes("users", {"age": 30}, 100)
            im.insert_indexes("users", {"age": 25}, 200)
            im.insert_indexes("users", {"age": 35}, 300)

            bt = im.get_index("users", "age")
            assert bt.search(30) == 100
            assert bt.search(25) == 200
            assert bt.search(35) == 300
        finally:
            self._cleanup(path, bp)

    def test_delete_indexes(self):
        path, fm, bp, catalog = self._make_env()
        try:
            im = IndexManager(bp, catalog)
            im.create_index("users", "age")

            im.insert_indexes("users", {"age": 30}, 100)
            assert im.get_index("users", "age").search(30) == 100

            im.delete_indexes("users", {"age": 30}, 100)
            assert im.get_index("users", "age").search(30) == -1
        finally:
            self._cleanup(path, bp)

    def test_update_indexes(self):
        path, fm, bp, catalog = self._make_env()
        try:
            im = IndexManager(bp, catalog)
            im.create_index("users", "age")

            im.insert_indexes("users", {"age": 30}, 100)
            assert im.get_index("users", "age").search(30) == 100

            # update age from 30 -> 40
            im.update_indexes("users", {"age": 30}, {"age": 40}, 100)
            assert im.get_index("users", "age").search(30) == -1
            assert im.get_index("users", "age").search(40) == 100
        finally:
            self._cleanup(path, bp)

    def test_create_index_scans_existing_records(self):
        """create_index should build the index from existing table records."""
        path, fm, bp, catalog = self._make_env()
        try:
            from tinydb.storage.table import Table
            table_id = catalog.create_table("users", [
                ColumnDef("id", DataType.INT),
                ColumnDef("name", DataType.TEXT),
            ])
            table = Table(table_id, "users", catalog.columns[table_id], bp)
            catalog.register_table_object("users", table)

            # insert some records
            r1 = table.insert([1, "Alice"])
            r2 = table.insert([2, "Bob"])
            r3 = table.insert([3, "Carol"])

            im = IndexManager(bp, catalog)
            bt = im.create_index("users", "id")
            assert bt.search(1) == r1
            assert bt.search(2) == r2
            assert bt.search(3) == r3
        finally:
            self._cleanup(path, bp)
