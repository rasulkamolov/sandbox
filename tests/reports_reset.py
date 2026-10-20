#!/usr/bin/env python3
"""Report arithmetic and owner-only cleanup regression tests against real PHP.

Run: PHP_BIN=/path/to/php python3 tests/reports_reset.py
Each test owns a temporary database and sessions. Never touches finance.db.
"""
from __future__ import annotations

import csv
import io
import os
from pathlib import Path
import shutil
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
import urllib.error

import integration as base_api
from integration import Client, PASSWORD, ROOT


FINANCIAL_TABLES = (
    "accounts", "categories", "tags", "transactions", "transfers", "budgets",
    "debts", "repayments", "recurring", "transaction_tags",
)
MARKED_TABLES = FINANCIAL_TABLES[:-1]


class IsolatedApi(unittest.TestCase):
    demo = False
    # Reuse the established HTTP assertions, not the original suite's shared DB.
    ok = base_api.IntegrationTests.ok
    rejected = base_api.IntegrationTests.rejected
    query_db = base_api.IntegrationTests.query_db
    account = base_api.IntegrationTests.account
    category = base_api.IntegrationTests.category
    transaction = base_api.IntegrationTests.transaction
    unique = base_api.IntegrationTests.unique
    balance = base_api.IntegrationTests.balance
    record = base_api.IntegrationTests.record
    counter = 0

    def setUp(self):
        self.php = os.environ.get("PHP_BIN") or shutil.which("php")
        if not self.php:
            self.skipTest("PHP with PDO SQLite required; set PHP_BIN.")
        self.temporary = tempfile.TemporaryDirectory(prefix="vela-reports-reset-")
        self.addCleanup(self.temporary.cleanup)
        self.db_path = Path(self.temporary.name) / "test.db"
        self.sessions = Path(self.temporary.name) / "sessions"
        self.sessions.mkdir()
        self.log = open(Path(self.temporary.name) / "server.log", "w+")
        self.addCleanup(self.log.close)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.base = f"http://127.0.0.1:{self.port}"
        self.owner = Client(self.base)
        self.environment = {**os.environ, "FINANCE_DB_PATH": str(self.db_path),
                            "FINANCE_SESSION_PATH": str(self.sessions)}
        preflight = subprocess.run(
            [self.php, "-r", "require $argv[1]; echo DATABASE_PATH;", str(ROOT / "config/config.php")],
            cwd=ROOT, env=self.environment, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(preflight.returncode, 0)
        self.assertEqual(preflight.stdout.strip(), str(self.db_path), "Refusing to use a real database.")
        self.addCleanup(self.stop_server)
        self.start_server()
        self.ok("setup", "POST", {"name": "Report Reset Owner", "email": "feature-owner@example.test",
                                   "password": PASSWORD, "demo": self.demo})

    def start_server(self):
        self.server = subprocess.Popen(
            [self.php, "-S", f"127.0.0.1:{self.port}", "-t", str(ROOT / "public")],
            cwd=ROOT, env=self.environment, stdout=self.log, stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.server.poll() is not None:
                self.log.seek(0)
                self.fail("PHP server exited: " + self.log.read())
            try:
                self.ok("session")
                self.assertTrue(self.db_path.is_file())
                return
            except (OSError, urllib.error.URLError):
                time.sleep(0.05)
        self.fail("PHP server did not become ready.")

    def stop_server(self):
        if hasattr(self, "server") and self.server.poll() is None:
            self.server.terminate()
            try:
                self.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server.kill()
                self.server.wait(timeout=5)

    def snapshot(self):
        return {table: self.query_db(f"SELECT * FROM {table} ORDER BY 1,2")
                for table in FINANCIAL_TABLES}

    def assistant(self):
        self.ok("users", "POST", {"name": "Operations", "email": "feature-assistant@example.test",
                                    "password": PASSWORD, "active": True})
        assistant = Client(self.base)
        self.ok("session", client=assistant)
        self.ok("login", "POST", {"email": "feature-assistant@example.test", "password": PASSWORD},
                client=assistant)
        return assistant

    def cleanup_data(self, action, **overrides):
        return {"current_password": PASSWORD,
                "confirmation": "REMOVE SAMPLE DATA" if action == "clear_sample_data" else "RESET FINANCES",
                **overrides}


class CleanupTests(IsolatedApi):
    demo = True

    def test_sample_markers_and_pure_sample_clear_are_repeatable(self):
        status = self.ok("demo_status")
        self.assertGreater(status["sample_records"], 0)
        self.assertEqual(status["sample_records"], status["financial_records"])
        self.assertTrue(status["can_remove_samples"])
        self.assertFalse(status["legacy_sample_data_possible"])
        for table in MARKED_TABLES:
            rows = self.query_db(f"SELECT is_demo FROM {table}")
            self.assertTrue(rows, table)
            self.assertTrue(all(row["is_demo"] == 1 for row in rows), table)
        result = self.ok("clear_sample_data", "POST", self.cleanup_data("clear_sample_data"))
        self.assertEqual(result["deleted_records"], status["sample_records"])
        self.assertEqual(result["status"]["financial_records"], 0)
        self.assertEqual(result["preserved_records"], 0)
        for rows in self.snapshot().values():
            self.assertEqual(rows, [])
        again = self.ok("clear_sample_data", "POST", self.cleanup_data("clear_sample_data"))
        self.assertEqual(again["deleted_records"], 0)
        self.assertEqual(self.query_db("PRAGMA foreign_key_check"), [])

    def test_cleanup_rejections_are_atomic_and_owner_only(self):
        assistant = self.assistant()
        anonymous = Client(self.base)
        self.ok("session", client=anonymous)
        for action in ("clear_sample_data", "reset_finances"):
            for options, expected in (
                ({"client": assistant}, (403,)),
                ({"client": anonymous}, (401,)),
                ({"data": self.cleanup_data(action, current_password="incorrect-password")}, (422,)),
                ({"data": self.cleanup_data(action, confirmation="wrong confirmation")}, (422,)),
            ):
                with self.subTest(action=action, expected=expected, kind=list(options)):
                    before = self.snapshot()
                    self.rejected(action, data=options.get("data", self.cleanup_data(action)),
                                  client=options.get("client"), statuses=expected)
                    self.assertEqual(self.snapshot(), before)
            before = self.snapshot()
            status, value, _ = self.owner.request(action, "POST", self.cleanup_data(action), csrf=False)
            self.assertEqual(status, 419)
            self.assertFalse(value["ok"])
            self.assertEqual(self.snapshot(), before)
            self.rejected(action, method="GET", statuses=(403, 404, 405))
        self.rejected("demo_status", method="GET", client=assistant, statuses=(403,))

    def test_sample_clear_preserves_real_rows_and_promotes_edited_samples(self):
        account = next(row for row in self.ok("accounts") if row["currency"] == "USD")
        category = next(row for row in self.ok("categories") if row["type"] == "expense")
        actual_child = self.category(name="Actual child category", parent_id=category["id"])
        tag = self.ok("tags")[0]
        real = self.transaction(account, "23.45", category_id=category["id"], tags=[tag["name"]],
                                description="My actual business purchase")
        sample = next(row for row in self.ok("transactions") if row["id"] != real["id"])
        self.ok("transactions", "PUT", {"id": sample["id"], "description": "My corrected actual transaction"})
        self.assertEqual(self.query_db("SELECT is_demo FROM transactions WHERE id=?", (sample["id"],))[0]["is_demo"], 0)
        actual_rows = self.query_db("SELECT * FROM transactions WHERE is_demo=0 ORDER BY id")
        junction = self.query_db("SELECT * FROM transaction_tags WHERE transaction_id=?", (real["id"],))
        result = self.ok("clear_sample_data", "POST", self.cleanup_data("clear_sample_data"))
        self.assertGreater(result["deleted_records"], 0)
        self.assertGreater(result["preserved_records"], 0)
        self.assertEqual(self.query_db("SELECT * FROM transactions ORDER BY id"), actual_rows)
        self.assertEqual(self.query_db("SELECT * FROM transaction_tags WHERE transaction_id=?", (real["id"],)), junction)
        self.assertEqual(self.record("accounts", account["id"])["name"], account["name"])
        self.assertEqual(self.record("categories", category["id"])["name"], category["name"])
        self.assertEqual(self.record("categories", actual_child["id"])["parent_id"], category["id"])
        self.assertEqual(self.record("tags", tag["id"])["name"], tag["name"])
        self.assertEqual(self.ok("demo_status")["sample_records"], 0)
        self.assertEqual(self.query_db("PRAGMA foreign_key_check"), [])

    def test_generated_sample_recurrences_keep_sample_provenance(self):
        recurring = self.ok("recurring")[0]
        # Arrange a due sample schedule without editing/promoting it through UI.
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE recurring SET next_date=date('now') WHERE id=?", (recurring["id"],))
        generated = self.ok("process_recurring", "POST", {})
        self.assertGreater(generated["processed"], 0)
        rows = self.query_db("SELECT id,is_demo FROM transactions WHERE recurring_id=?", (recurring["id"],))
        self.assertTrue(rows)
        self.assertTrue(all(row["is_demo"] == 1 for row in rows))
        self.ok("clear_sample_data", "POST", self.cleanup_data("clear_sample_data"))
        self.assertEqual(self.ok("transactions"), [])
        self.assertEqual(self.ok("recurring"), [])

    def test_real_repayment_retains_entire_sample_debt_context(self):
        debt = next(row for row in self.ok("debts") if row["direction"] == "lending")
        self.ok("repayments", "POST", {"debt_id": debt["id"], "account_id": debt["account_id"], "amount": "1.25"})
        before = self.record("debts", debt["id"])
        payments = self.ok("repayments", query={"debt_id": debt["id"]})
        self.ok("clear_sample_data", "POST", self.cleanup_data("clear_sample_data"))
        after = self.record("debts", debt["id"])
        self.assertEqual(after["amount"], before["amount"])
        self.assertEqual(after["remaining"], before["remaining"])
        self.assertEqual(after["paid"], before["paid"])
        self.assertEqual([row["id"] for row in self.ok("repayments", query={"debt_id": debt["id"]})],
                         [row["id"] for row in payments])
        self.assertEqual(self.query_db("SELECT is_demo FROM debts WHERE id=?", (debt["id"],))[0]["is_demo"], 0)
        self.assertTrue(all(row["is_demo"] == 0 for row in self.query_db("SELECT is_demo FROM repayments")))
        self.assertEqual(self.query_db("PRAGMA foreign_key_check"), [])

    def test_full_reset_preserves_credentials_locale_sessions_and_append_only_audit(self):
        assistant = self.assistant()
        self.ok("locale", "POST", {"locale": "uz"})
        before_users = self.query_db("SELECT * FROM users ORDER BY id")
        before_audit = self.query_db("SELECT * FROM audit_logs ORDER BY id")
        result = self.ok("reset_finances", "POST", self.cleanup_data("reset_finances"))
        self.assertGreater(result["deleted_records"], 0)
        self.assertEqual(result["status"]["financial_records"], 0)
        self.assertEqual(self.snapshot(), {table: [] for table in FINANCIAL_TABLES})
        self.assertEqual(self.query_db("SELECT * FROM users ORDER BY id"), before_users)
        audit = self.query_db("SELECT * FROM audit_logs ORDER BY id")
        self.assertEqual(audit[:len(before_audit)], before_audit)
        self.assertGreater(len(audit), len(before_audit))
        self.assertEqual(audit[-1]["action"], "reset_finances")
        self.assertEqual(self.ok("session")["locale"], "uz")
        self.assertEqual(self.ok("session")["user"]["role"], "owner")
        self.assertEqual(self.ok("session", client=assistant)["user"]["role"], "assistant")
        self.assertFalse(self.ok("session")["needs_setup"])
        self.assertEqual(self.ok("reset_finances", "POST", self.cleanup_data("reset_finances"))["deleted_records"], 0)
        with sqlite3.connect(self.db_path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM audit_logs WHERE id=?", (before_audit[0]["id"],))
        self.assertEqual(self.query_db("PRAGMA integrity_check")[0]["integrity_check"], "ok")
        self.assertEqual(self.query_db("PRAGMA foreign_key_check"), [])
        self.log.flush()
        self.log.seek(0)
        self.assertNotIn(PASSWORD, self.log.read())

    def test_legacy_database_migration_never_guesses_sample_provenance(self):
        # Remove only the newly introduced columns to reproduce a real previous
        # installation. The actual application's migrations must restore them.
        self.stop_server()
        with sqlite3.connect(self.db_path) as db:
            for table in MARKED_TABLES:
                db.execute(f"ALTER TABLE {table} DROP COLUMN is_demo")
        self.start_server()
        before = self.snapshot()
        status = self.ok("demo_status")
        self.assertEqual(status["sample_records"], 0)
        self.assertTrue(status["legacy_sample_data_possible"])
        self.assertGreater(status["financial_records"], 0)
        for table in MARKED_TABLES:
            self.assertEqual([row["name"] for row in self.query_db(f"PRAGMA table_info({table})")].count("is_demo"), 1)
            self.assertTrue(all(row["is_demo"] == 0 for row in self.query_db(f"SELECT is_demo FROM {table}")))
        result = self.ok("clear_sample_data", "POST", self.cleanup_data("clear_sample_data"))
        self.assertEqual(result["deleted_records"], 0)
        self.assertEqual(self.snapshot(), before)
        self.assertTrue(self.ok("demo_status")["legacy_sample_data_possible"])
        self.stop_server()
        self.start_server()
        self.assertEqual(self.snapshot(), before, "Re-running migrations must preserve all rows.")
        self.ok("reset_finances", "POST", self.cleanup_data("reset_finances"))
        self.assertEqual(self.snapshot(), {table: [] for table in FINANCIAL_TABLES})


class ReportTests(IsolatedApi):
    def fixture(self):
        usd = self.account("1000")
        second_usd = self.account("0")
        uzs = self.account("10000", currency="UZS")
        parent = self.category(name="Office")
        child = self.category(name="Software", parent_id=parent["id"])
        self.transaction(usd, "100", "income", date="2026-01-10 00:00:00", description="Client payment")
        self.transaction(usd, "10", date="2026-01-10 23:59:59", category_id=parent["id"], description="Office supplies")
        self.transaction(usd, "20", date="2026-01-12 23:59:59", category_id=child["id"], description="=Unsafe formula")
        self.transaction(usd, "50", "income", date="2026-01-07")
        self.transaction(usd, "4", date="2026-01-09")
        self.transaction(usd, "999", date="2026-01-13")
        self.transaction(usd, "999", date="2026-01-06")
        self.transaction(uzs, "100000", "income", date="2026-01-10")
        self.transaction(uzs, "4000", date="2026-01-11")
        self.ok("transfers", "POST", {"from_account_id": usd["id"], "to_account_id": uzs["id"],
            "amount": "100", "received_amount": "1250000", "fee": "2", "date": "2026-01-11"})
        debt = self.ok("debts", "POST", {"direction": "borrowing", "counterparty": "Supplier", "currency": "USD",
            "amount": "50", "account_id": usd["id"], "date": "2026-01-10", "due_date": "2026-02-10"})
        self.ok("repayments", "POST", {"debt_id": debt["id"], "account_id": usd["id"], "amount": "5", "date": "2026-01-12"})
        self.ok("budgets", "POST", {"category_id": parent["id"], "currency": "USD", "amount": "100", "month": "2026-01"})
        self.report_query = {"currency": "USD", "from": "2026-01-10", "to": "2026-01-12"}
        return usd, second_usd, uzs, parent, child

    def test_report_totals_equal_period_comparison_inclusive_dates_and_currency_isolation(self):
        usd, _, uzs, _, _ = self.fixture()
        report = self.ok("reports", query=self.report_query)
        self.assertEqual(report["currency"], "USD")
        self.assertEqual((report["previous_from"], report["previous_to"]), ("2026-01-07", "2026-01-09"))
        period = report["period"]
        self.assertEqual(period["days"], 3)
        self.assertEqual((period["income"], period["expense"], period["net"]), (100, 32, 68))
        self.assertEqual(period["fees"], 2)
        self.assertEqual(period["transaction_count"], 3)
        self.assertEqual(period["savings_rate"], 68)
        self.assertAlmostEqual(period["average_daily_expense"], 32 / 3, delta=.005)
        self.assertEqual((report["previous"]["income"], report["previous"]["expense"]), (50, 4))
        self.assertEqual(report["changes"]["income"]["percent"], 100)
        self.assertEqual(report["changes"]["expense"]["percent"], 700)
        self.assertEqual([row["date"] for row in report["daily"]], ["2026-01-10", "2026-01-11", "2026-01-12"])
        self.assertEqual([row["expense"] for row in report["daily"]], [10, 2, 20])
        self.assertEqual(sum(row["net"] for row in report["daily"]), 68)
        foreign = self.ok("reports", query={**self.report_query, "currency": "UZS"})
        self.assertEqual((foreign["period"]["income"], foreign["period"]["expense"]), (100000, 4000))
        self.assertEqual(foreign["period"]["fees"], 0)
        filtered = self.ok("reports", query={**self.report_query, "account_id": usd["id"]})
        self.assertEqual(filtered["period"], period)
        self.assertEqual([row["id"] for row in filtered["accounts"]], [usd["id"]])
        self.rejected("reports", method="GET", query={**self.report_query, "account_id": uzs["id"]}, statuses=(422,))

    def test_categories_shares_accounts_and_full_month_budgets_are_consistent(self):
        usd, _, _, parent, child = self.fixture()
        report = self.ok("reports", query=self.report_query)
        categories = report["categories"]
        self.assertEqual(sum(row["amount"] for row in categories), 32)
        self.assertAlmostEqual(sum(row["share"] for row in categories), 100, delta=.02)
        amounts = {row["id"]: row["amount"] for row in categories if row["kind"] == "category"}
        self.assertEqual(amounts[parent["id"]], 10)
        self.assertEqual(amounts[child["id"]], 20)
        self.assertEqual(next(row["amount"] for row in categories if row["kind"] == "transfer_fees"), 2)
        account = next(row for row in report["accounts"] if row["id"] == usd["id"])
        self.assertEqual((account["income"], account["expense"], account["net"]), (100, 32, 68))
        budget = next(row for row in report["budgets"] if row["category_id"] == parent["id"])
        self.assertTrue(budget["full_month"])
        self.assertEqual(budget["month"], "2026-01")
        self.assertEqual(budget["amount"], 100)
        self.assertEqual(budget["spent"], 30)
        self.assertEqual([row["amount"] for row in report["largest_expenses"]], [20, 10])

    def test_zero_baseline_negative_savings_and_zero_filled_days(self):
        account = self.account("0")
        self.transaction(account, "10", "income", date="2026-04-02")
        self.transaction(account, "25", date="2026-04-02")
        query = {"currency": "USD", "from": "2026-04-01", "to": "2026-04-03"}
        report = self.ok("reports", query=query)
        self.assertEqual(report["period"]["net"], -15)
        self.assertEqual(report["period"]["savings_rate"], -150)
        self.assertTrue(all(report["changes"][key]["percent"] is None for key in ("income", "expense", "net")))
        self.assertEqual([row["expense"] for row in report["daily"]], [0, 25, 0])
        empty = self.ok("reports", query={**query, "currency": "EUR"})
        self.assertEqual(empty["period"]["income"], 0)
        self.assertEqual(empty["period"]["expense"], 0)
        self.assertIsNone(empty["period"]["savings_rate"])
        self.assertEqual(len(empty["daily"]), 3)

    def test_reports_validate_filters_and_prevent_assistant_export(self):
        self.fixture()
        assistant = self.assistant()
        for action in ("reports", "report_export"):
            self.rejected(action, method="GET", query=self.report_query, client=assistant, statuses=(403,))
            anonymous = Client(self.base)
            self.ok("session", client=anonymous)
            self.rejected(action, method="GET", query=self.report_query, client=anonymous, statuses=(401,))
            for query in (
                {"from": "2026-02-30"}, {"from": "2026-01-20", "to": "2026-01-10"},
                {"currency": "BTC"}, {"from": "2000-01-01", "to": "2026-01-01"},
            ):
                self.rejected(action, method="GET", query={**self.report_query, **query}, statuses=(422,))
        self.rejected("reports", method="GET", query={**self.report_query, "account_id": 987654321}, statuses=(404,))

    def test_csv_matches_filtered_report_and_neutralizes_formula_cells(self):
        _, second_usd, _, _, _ = self.fixture()
        status, exported, headers = self.owner.request("report_export", query=self.report_query)
        self.assertEqual(status, 200)
        self.assertIsInstance(exported, bytes)
        self.assertTrue(exported.startswith(b"\xef\xbb\xbf"))
        self.assertIn("attachment", headers.get("Content-Disposition", ""))
        rows = list(csv.reader(io.StringIO(exported.decode("utf-8-sig"))))
        self.assertTrue(all(len(row) == 10 for row in rows))
        selected = next(row for row in rows[1:] if row[1] == "2026-01-10 / 2026-01-12")
        self.assertEqual([float(selected[index]) for index in (3, 4, 5)], [100, 32, 68])
        self.assertEqual(selected[7], "USD")
        self.assertTrue(any("'=Unsafe formula" in row for row in rows), "CSV text must be spreadsheet-safe.")
        status, exported, _ = self.owner.request("report_export", query={**self.report_query, "account_id": second_usd["id"]})
        self.assertEqual(status, 200)
        filtered = list(csv.reader(io.StringIO(exported.decode("utf-8-sig"))))
        selected = next(row for row in filtered[1:] if row[1] == "2026-01-10 / 2026-01-12")
        self.assertEqual([float(selected[index]) for index in (3, 4, 5)], [0, 0, 0])
        self.assertFalse(any("'=Unsafe formula" in row for row in filtered))


if __name__ == "__main__":
    unittest.main(verbosity=2)
