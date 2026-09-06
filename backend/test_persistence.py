"""Persistence tests for users, watchlists, and independent checkpoints."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from database import connect
from repository import DuplicateError, WatchlistRepository


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.conn = connect(":memory:")
        self.repo = WatchlistRepository(self.conn)
        self.t0 = datetime(2026, 9, 1, 4, 0, tzinfo=timezone.utc)

    def tearDown(self) -> None:
        self.conn.close()

    def test_create_user_and_watchlist(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)

        self.assertEqual(user.username, "alice")
        self.assertEqual(watchlist.user_id, user.id)
        self.assertEqual(watchlist.name, "Core")
        self.assertIsNone(watchlist.last_acknowledged_at)
        self.assertEqual(self.repo.get_user(user.id).username, "alice")
        self.assertEqual(self.repo.get_watchlist(watchlist.id).name, "Core")

        other = self.repo.create_user("bob", now=self.t0)
        bob_list = self.repo.create_watchlist(other.id, "Core", now=self.t0)
        self.assertNotEqual(watchlist.id, bob_list.id)
        self.assertEqual(bob_list.user_id, other.id)

        with self.assertRaises(DuplicateError):
            self.repo.create_user("alice")
        with self.assertRaises(DuplicateError):
            self.repo.create_watchlist(user.id, "Core")

    def test_add_stock(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        item = self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

        self.assertEqual(item.symbol, "RELIANCE.NS")
        self.assertEqual(item.watchlist_id, watchlist.id)
        self.assertEqual(item.added_at, self.t0)
        self.assertEqual(len(self.repo.list_items(watchlist.id)), 1)
        with self.assertRaises(DuplicateError):
            self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

    def test_store_and_retrieve_baseline_checkpoint(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        created = self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

        fetched = self.repo.get_item_by_symbol(watchlist.id, "RELIANCE.NS")
        self.assertEqual(fetched.id, created.id)
        self.assertEqual(fetched.checkpoint_at, self.t0)
        self.assertEqual(fetched.added_at, fetched.checkpoint_at)

        fetched_again = self.repo.get_item(created.id)
        self.assertEqual(fetched_again.checkpoint_at, self.t0)

    def test_update_checkpoint(self) -> None:
        later = self.t0 + timedelta(days=2)
        refresh_time = self.t0 + timedelta(days=1)
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        item = self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)

        # A later clock time used for market refresh is not written to the row.
        unchanged = self.repo.get_item(item.id)
        self.assertEqual(unchanged.checkpoint_at, self.t0)
        self.assertNotEqual(unchanged.checkpoint_at, refresh_time)

        acknowledged = self.repo.acknowledge_stock(
            watchlist.id, "RELIANCE.NS", now=later
        )
        self.assertEqual(acknowledged.checkpoint_at, later)
        self.assertEqual(acknowledged.added_at, self.t0)
        self.assertEqual(
            self.repo.get_item_by_symbol(watchlist.id, "RELIANCE.NS").checkpoint_at,
            later,
        )

        visit = self.t0 + timedelta(days=3)
        self.repo.acknowledge_watchlist(watchlist.id, now=visit)
        self.assertEqual(
            self.repo.get_item_by_symbol(watchlist.id, "RELIANCE.NS").checkpoint_at,
            visit,
        )
        self.assertEqual(self.repo.get_watchlist(watchlist.id).last_acknowledged_at, visit)

    def test_multiple_stocks_independent_checkpoints(self) -> None:
        t_rel = self.t0
        t_infy = self.t0 + timedelta(hours=3)
        ack_rel = self.t0 + timedelta(days=1)
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=t_rel)
        self.repo.add_stock(watchlist.id, "INFY.NS", now=t_infy)

        self.repo.acknowledge_stock(watchlist.id, "RELIANCE.NS", now=ack_rel)

        reliance = self.repo.get_item_by_symbol(watchlist.id, "RELIANCE.NS")
        infy = self.repo.get_item_by_symbol(watchlist.id, "INFY.NS")
        self.assertEqual(reliance.checkpoint_at, ack_rel)
        self.assertEqual(infy.checkpoint_at, t_infy)
        self.assertEqual(infy.added_at, t_infy)
        self.assertNotEqual(reliance.checkpoint_at, infy.checkpoint_at)

    def test_newly_added_stock_gets_own_baseline(self) -> None:
        user = self.repo.create_user("alice", now=self.t0)
        watchlist = self.repo.create_watchlist(user.id, "Core", now=self.t0)
        first = self.repo.add_stock(watchlist.id, "RELIANCE.NS", now=self.t0)
        later = self.t0 + timedelta(days=4)
        nifty = self.repo.add_stock(watchlist.id, "^NSEI", now=later)

        self.assertEqual(first.checkpoint_at, self.t0)
        self.assertEqual(nifty.checkpoint_at, later)
        self.assertEqual(nifty.added_at, later)
        self.assertEqual(
            self.repo.get_item_by_symbol(watchlist.id, "RELIANCE.NS").checkpoint_at,
            self.t0,
        )
        items = self.repo.list_items(watchlist.id)
        self.assertEqual([item.symbol for item in items], ["RELIANCE.NS", "^NSEI"])


if __name__ == "__main__":
    unittest.main()
