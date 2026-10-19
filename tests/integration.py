#!/usr/bin/env python3
"""Exercise the real PHP/SQLite API without third-party test dependencies.

Run: PHP_BIN=/path/to/php python3 tests/integration.py
The suite creates a private temporary database and starts/stops its own PHP server.
It never opens or modifies database/finance.db.
"""
from __future__ import annotations

import csv
import datetime as dt
import http.cookiejar
import io
import json
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
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PASSWORD = "Correct-Horse-837!"
TODAY = dt.datetime.now(dt.timezone(dt.timedelta(hours=5))).date()


class Client:
    def __init__(self, base: str):
        self.base = base
        self.csrf: str | None = None
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def request(self, action: str, method: str = "GET", data: dict | None = None,
                query: dict | None = None, csrf: bool = True, headers: dict | None = None):
        params = {"action": action, **(query or {})}
        url = self.base + "/api.php?" + urllib.parse.urlencode(params)
        request_headers = {"Accept": "application/json", **(headers or {})}
        payload = None if data is None else json.dumps(data).encode()
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
        if csrf and self.csrf:
            request_headers["X-CSRF-Token"] = self.csrf
        req = urllib.request.Request(url, data=payload, headers=request_headers, method=method)
        try:
            response = self.opener.open(req, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            status = response.status
            response_headers = response.headers
        if "application/json" in response_headers.get("Content-Type", ""):
            try:
                value = json.loads(body)
            except ValueError as error:
                raise AssertionError(f"Invalid JSON ({status}): {body[:500]!r}") from error
            if isinstance(value, dict) and isinstance(value.get("data"), dict):
                self.csrf = value["data"].get("csrf", self.csrf)
            return status, value, response_headers
        return status, body, response_headers


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        php = os.environ.get("PHP_BIN") or shutil.which("php")
        if not php:
            raise RuntimeError("PHP 8.2+ with PDO SQLite is required; set PHP_BIN to its executable.")
        cls.temporary = tempfile.TemporaryDirectory(prefix="vela-integration-")
        cls.db_path = Path(cls.temporary.name) / "finance-test.db"
        cls.log = open(Path(cls.temporary.name) / "php.log", "w+", encoding="utf-8")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        cls.base = f"http://127.0.0.1:{port}"
        sessions = Path(cls.temporary.name) / "sessions"
        sessions.mkdir()
        environment = {**os.environ, "FINANCE_DB_PATH": str(cls.db_path), "FINANCE_SESSION_PATH": str(sessions)}
        preflight = subprocess.run(
            [php, "-r", "require $argv[1]; echo DATABASE_PATH;", str(ROOT / "config/config.php")],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=15,
        )
        if preflight.returncode or preflight.stdout.strip() != str(cls.db_path):
            cls.log.close()
            cls.temporary.cleanup()
            raise RuntimeError("FINANCE_DB_PATH is not supported; refusing to start the application against a real database.")
        cls.server = subprocess.Popen(
            [php, "-S", f"127.0.0.1:{port}", "-t", str(ROOT / "public")],
            cwd=ROOT, env=environment, stdout=cls.log, stderr=subprocess.STDOUT,
        )
        cls.addClassCleanup(cls.cleanup_server)
        cls.owner = Client(cls.base)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                cls.log.seek(0)
                raise RuntimeError("PHP server failed: " + cls.log.read())
            try:
                status, session, _ = cls.owner.request("session")
                break
            except (OSError, urllib.error.URLError):
                time.sleep(0.1)
        else:
            raise RuntimeError("PHP server did not become ready.")
        if status != 200 or not session.get("ok"):
            raise AssertionError(f"Initial session failed: {status} {session!r}")
        if not cls.db_path.is_file():
            raise AssertionError("FINANCE_DB_PATH was ignored; refusing to run against the repository database.")
        cls.initial_session = session["data"]
        cls.owner_email = "owner@example.test"
        status, setup, _ = cls.owner.request("setup", "POST", {
            "name": "Integration Owner", "email": cls.owner_email,
            "password": PASSWORD, "demo": False,
        })
        if status not in (200, 201) or not setup.get("ok"):
            raise AssertionError(f"Owner setup failed: {status} {setup!r}")
        cls.owner.csrf = setup["data"].get("csrf", cls.owner.csrf)
        cls.counter = 0

    @classmethod
    def cleanup_server(cls):
        if hasattr(cls, "server"):
            cls.server.terminate()
            try:
                cls.server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server.kill()
                cls.server.wait(timeout=5)
        if hasattr(cls, "log"):
            cls.log.close()
        if hasattr(cls, "temporary"):
            cls.temporary.cleanup()

    def unique(self, prefix):
        type(self).counter += 1
        return f"{prefix} {self.counter}"

    def ok(self, action, method="GET", data=None, query=None, client=None):
        status, result, _ = (client or self.owner).request(action, method, data, query)
        self.assertIn(status, (200, 201), f"{action}: {status} {result!r}")
        self.assertIsInstance(result, dict)
        self.assertTrue(result.get("ok"), f"{action}: {result!r}")
        return result["data"]

    def rejected(self, action, method="POST", data=None, query=None, client=None, statuses=(400, 403, 404, 409, 422)):
        status, result, _ = (client or self.owner).request(action, method, data, query)
        self.assertIn(status, statuses, f"Expected rejection for {action}: {status} {result!r}")
        self.assertIsInstance(result, dict)
        self.assertFalse(result.get("ok"), f"{action}: {result!r}")
        return result

    def query_db(self, sql, args=()):
        with sqlite3.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            return [dict(row) for row in db.execute(sql, args)]

    def account(self, balance="100.00", currency="USD", **extra):
        return self.ok("accounts", "POST", {"name": self.unique("Account"), "type": "bank",
            "currency": currency, "initial_balance": balance, **extra})

    def category(self, kind="expense", **extra):
        return self.ok("categories", "POST", {"name": self.unique("Category"), "type": kind, **extra})

    def transaction(self, account, amount, kind="expense", **extra):
        return self.ok("transactions", "POST", {"account_id": account["id"], "currency": account["currency"],
            "type": kind, "amount": amount, "date": TODAY.isoformat(), **extra})

    def balance(self, account):
        accounts = self.ok("accounts")
        return next(row["current_balance"] for row in accounts if row["id"] == account["id"])

    def record(self, resource, record_id, **query):
        return next(row for row in self.ok(resource, query=query) if row["id"] == record_id)

    def test_00_first_run_and_database_invariants(self):
        self.assertTrue(self.initial_session["needs_setup"])
        self.assertIsNone(self.initial_session["user"])
        self.assertGreaterEqual(len(self.initial_session["csrf"]), 32)
        session = self.ok("session")
        self.assertFalse(session["needs_setup"])
        self.assertEqual(session["user"]["role"], "owner")
        self.assertNotIn("password_hash", session["user"])
        self.assertEqual(self.query_db("SELECT COUNT(*) n FROM accounts")[0]["n"], 0)
        self.assertEqual(self.query_db("SELECT COUNT(*) n FROM transactions")[0]["n"], 0)
        user = self.query_db("SELECT * FROM users WHERE email=?", (self.owner_email,))[0]
        self.assertTrue(user["password_hash"].startswith("$2y$"))
        self.assertNotIn(PASSWORD, user["password_hash"])
        self.assertEqual(self.query_db("PRAGMA journal_mode")[0]["journal_mode"], "wal")
        self.assertEqual(self.query_db("PRAGMA integrity_check")[0]["integrity_check"], "ok")
        self.assertEqual(self.query_db("PRAGMA foreign_key_check"), [])
        self.assertGreaterEqual(len(self.query_db("PRAGMA foreign_key_list(transactions)")), 3)
        self.rejected("setup", data={"name": "Another", "email": "other@example.test", "password": PASSWORD},
                      statuses=(403, 409, 422))

    def test_01_authentication_csrf_and_session_isolation(self):
        anonymous = Client(self.base)
        session = self.ok("session", client=anonymous)
        self.assertIsNone(session["user"])
        self.assertNotEqual(anonymous.csrf, self.owner.csrf)
        self.rejected("login", data={"email": self.owner_email, "password": "wrong-password-837"},
                      client=anonymous, statuses=(401,))
        status, result, _ = anonymous.request("login", "POST", {
            "email": self.owner_email, "password": PASSWORD,
        }, csrf=False)
        self.assertEqual(status, 419)
        self.assertFalse(result["ok"])
        before_login_csrf = anonymous.csrf
        login = self.ok("login", "POST", {"email": self.owner_email, "password": PASSWORD}, client=anonymous)
        self.assertEqual(login["user"]["email"], self.owner_email)
        self.assertNotEqual(anonymous.csrf, before_login_csrf)
        cookies = list(anonymous.cookies)
        self.assertTrue(any(c.name.endswith("_session") for c in cookies))
        cookie = next(c for c in cookies if c.name.endswith("_session"))
        self.assertTrue(cookie.has_nonstandard_attr("HttpOnly"))
        self.assertEqual(cookie.get_nonstandard_attr("SameSite"), "Lax")
        self.ok("logout", "POST", {}, client=anonymous)
        self.assertIsNone(self.ok("session", client=anonymous)["user"])
        self.assertEqual(self.ok("session")["user"]["role"], "owner")

    def test_02_accounts_crud_and_integer_money(self):
        account = self.account("123.45", type="card", details="Visa • 4242", target_amount="500.00")
        self.assertEqual(account["current_balance"], 123.45)
        self.assertEqual(account["initial_balance"], 123.45)
        stored = self.query_db("SELECT initial_balance, typeof(initial_balance) storage FROM accounts WHERE id=?", (account["id"],))[0]
        self.assertEqual(stored, {"initial_balance": 12345, "storage": "integer"})
        updated = self.ok("accounts", "PUT", {"id": account["id"], "name": "Account O'Reilly; DROP TABLE users;--", "color": "#06b6d4"})
        self.assertEqual(updated["current_balance"], 123.45)
        self.assertEqual(updated["type"], "card")
        self.assertEqual(updated["color"], "#06b6d4")
        results = self.ok("accounts", query={"search": "O'Reilly; DROP"})
        self.assertEqual([row["id"] for row in results], [account["id"]])
        self.assertEqual(self.query_db("SELECT COUNT(*) n FROM users")[0]["n"], 1)
        self.rejected("accounts", data={"name": "Bad precision", "type": "cash", "currency": "USD", "initial_balance": "0.001"})
        self.ok("accounts", "PUT", {"id": account["id"], "status": "archived"})
        self.rejected("transactions", data={"type": "expense", "amount": "1", "account_id": account["id"]})
        deleted = self.ok("accounts", "DELETE", {"id": account["id"]})
        self.assertEqual(deleted["deleted"], account["id"])
        self.assertEqual(self.query_db("SELECT id FROM accounts WHERE id=?", (account["id"],)), [])

    def test_03_transactions_crud_filters_tags_and_ledger(self):
        account = self.account()
        income_category = self.category("income")
        expense_category = self.category()
        income = self.transaction(account, "45.12", "income", category_id=income_category["id"],
                                  description="Client O'Reilly invoice", tags=["Business", "Paid"])
        expense = self.transaction(account, "10.01", category_id=expense_category["id"], description="Lunch receipt", receipt="receipt-01.pdf")
        self.assertEqual(self.balance(account), 135.11)
        self.assertEqual(sorted(income["tags"]), ["Business", "Paid"])
        self.assertEqual(expense["receipt"], "receipt-01.pdf")
        self.assertEqual(self.query_db("SELECT amount FROM transactions WHERE id=?", (income["id"],))[0]["amount"], 4512)
        found = self.ok("transactions", query={"account_id": account["id"], "search": "O'Reilly", "from": TODAY.isoformat(), "to": TODAY.isoformat()})
        self.assertEqual([row["id"] for row in found], [income["id"]])
        self.assertEqual(self.ok("transactions", query={"account_id": account["id"], "from": (TODAY + dt.timedelta(days=1)).isoformat()}), [])
        self.assertEqual(self.ok("transactions", query={"search": "' OR 1=1 --"}), [])
        self.ok("transactions", "PUT", {"id": income["id"], "amount": "44.32", "tags": ["Revised"]})
        self.assertEqual(self.balance(account), 134.31)
        self.assertEqual(self.record("transactions", income["id"])["tags"], ["Revised"])
        self.ok("transactions", "PUT", {"id": expense["id"], "amount": "4.31"})
        self.assertEqual(self.balance(account), 140.01)
        self.rejected("accounts", "PUT", {"id": account["id"], "currency": "EUR"})
        self.rejected("accounts", "DELETE", {"id": account["id"]}, statuses=(409, 422))
        self.ok("transactions", "DELETE", {"id": income["id"]})
        self.assertEqual(self.balance(account), 95.69)
        self.ok("transactions", "DELETE", {"id": expense["id"]})
        self.assertEqual(self.balance(account), 100)
        self.assertEqual(self.query_db("SELECT * FROM transaction_tags WHERE transaction_id=?", (income["id"],)), [])
        self.ok("accounts", "DELETE", {"id": account["id"]})

    def test_04_transfers_fees_update_delete_and_atomic_rejection(self):
        source = self.account("1000.00")
        destination = self.account("100.00", type="savings")
        foreign = self.account("100.00", currency="EUR")
        transfer = self.ok("transfers", "POST", {"from_account_id": source["id"], "to_account_id": destination["id"],
            "amount": "100.00", "fee": "2.50", "date": TODAY.isoformat(), "description": "Move to reserve"})
        self.assertEqual(self.balance(source), 897.5)
        self.assertEqual(self.balance(destination), 200)
        transfer = self.ok("transfers", "PUT", {"id": transfer["id"], "amount": "120.00", "fee": "3.00"})
        self.assertEqual(self.balance(source), 877)
        self.assertEqual(self.balance(destination), 220)
        self.assertEqual(self.ok("transfers", query={"account_id": source["id"], "search": "reserve"})[0]["id"], transfer["id"])
        self.rejected("transfers", "PUT", {"id": transfer["id"], "to_account_id": foreign["id"], "amount": "400"})
        self.assertEqual(self.balance(source), 877)
        self.assertEqual(self.balance(destination), 220)
        self.assertEqual(self.balance(foreign), 100)
        self.assertEqual(self.record("transfers", transfer["id"])["amount"], 120)
        self.rejected("transfers", data={"from_account_id": source["id"], "to_account_id": source["id"], "amount": "1"})
        self.rejected("transfers", data={"from_account_id": source["id"], "to_account_id": foreign["id"], "amount": "1"})
        self.rejected("transfers", data={"from_account_id": source["id"], "to_account_id": destination["id"], "amount": "1", "fee": "-0.01"})
        self.ok("transfers", "DELETE", {"id": transfer["id"]})
        self.assertEqual(self.balance(source), 1000)
        self.assertEqual(self.balance(destination), 100)

    def test_05_budget_thresholds_descendants_and_currency(self):
        account = self.account("500")
        other_currency = self.account("500", currency="RUB")
        parent = self.category()
        child = self.category(parent_id=parent["id"])
        budget = self.ok("budgets", "POST", {"category_id": parent["id"], "amount": "100", "currency": "USD", "month": TODAY.strftime("%Y-%m")})
        expense = self.transaction(account, "74.99", category_id=child["id"])
        self.transaction(other_currency, "250", category_id=child["id"])
        current = self.record("budgets", budget["id"])
        self.assertEqual(current["status"], "healthy")
        self.assertEqual(current["spent"], 74.99)
        self.ok("transactions", "PUT", {"id": expense["id"], "amount": "75"})
        self.assertEqual(self.record("budgets", budget["id"])["status"], "warning")
        self.ok("transactions", "PUT", {"id": expense["id"], "amount": "99.99"})
        self.assertEqual(self.record("budgets", budget["id"])["status"], "warning")
        self.ok("transactions", "PUT", {"id": expense["id"], "amount": "100"})
        current = self.record("budgets", budget["id"])
        self.assertEqual(current["status"], "danger")
        self.assertEqual(current["percentage"], 100)
        self.assertEqual(current["remaining"], 0)
        updated = self.ok("budgets", "PUT", {"id": budget["id"], "amount": "200"})
        self.assertEqual(updated["status"], "healthy")
        self.assertIn(budget["id"], [row["id"] for row in self.ok("budgets", query={"month": TODAY.strftime("%Y-%m"), "category_id": parent["id"]})])
        self.ok("budgets", "DELETE", {"id": budget["id"]})
        self.assertNotIn(budget["id"], [row["id"] for row in self.ok("budgets")])

    def test_06_debts_repayment_crud_and_liquidity(self):
        account = self.account("1000")
        debt = self.ok("debts", "POST", {"direction": "borrowing", "counterparty": "Supplier", "contact": "+998 90 123 45 67",
            "amount": "200", "currency": "USD", "account_id": account["id"], "date": TODAY.isoformat(),
            "due_date": (TODAY + dt.timedelta(days=30)).isoformat()})
        self.assertEqual(self.balance(account), 1200)
        self.assertEqual(debt["remaining"], 200)
        repayment = self.ok("repayments", "POST", {"debt_id": debt["id"], "account_id": account["id"], "amount": "50", "date": TODAY.isoformat()})
        self.assertEqual(self.balance(account), 1150)
        self.assertEqual(self.record("debts", debt["id"])["remaining"], 150)
        self.rejected("repayments", data={"debt_id": debt["id"], "account_id": account["id"], "amount": "150.01"})
        self.assertEqual(self.balance(account), 1150)
        self.assertEqual(len(self.ok("repayments", query={"debt_id": debt["id"]})), 1)
        self.ok("repayments", "PUT", {"id": repayment["id"], "amount": "60"})
        self.assertEqual(self.balance(account), 1140)
        self.assertEqual(self.record("debts", debt["id"])["remaining"], 140)
        self.rejected("debts", "PUT", {"id": debt["id"], "amount": "59.99"})
        self.rejected("debts", "PUT", {"id": debt["id"], "direction": "lending"})
        self.ok("repayments", "DELETE", {"id": repayment["id"]})
        self.assertEqual(self.balance(account), 1200)
        self.ok("debts", "PUT", {"id": debt["id"], "counterparty": "Updated supplier"})
        self.assertEqual(self.record("debts", debt["id"])["counterparty"], "Updated supplier")
        self.ok("debts", "DELETE", {"id": debt["id"]})
        self.assertEqual(self.balance(account), 1000)
        lending = self.ok("debts", "POST", {"direction": "lending", "counterparty": "Client", "amount": "200", "currency": "USD", "account_id": account["id"]})
        self.assertEqual(self.balance(account), 800)
        self.ok("repayments", "POST", {"debt_id": lending["id"], "account_id": account["id"], "amount": "200"})
        paid = self.record("debts", lending["id"])
        self.assertEqual(paid["status"], "paid")
        self.assertEqual(paid["remaining"], 0)
        self.assertEqual(self.balance(account), 1000)
        self.ok("debts", "DELETE", {"id": lending["id"]})
        self.assertEqual(self.balance(account), 1000)
        self.assertEqual(self.ok("repayments", query={"debt_id": lending["id"]}), [])

    def test_07_recurring_processing_is_idempotent_and_preserves_ledger(self):
        account = self.account()
        recurring = self.ok("recurring", "POST", {"account_id": account["id"], "type": "expense", "amount": "12", "frequency": "daily",
            "next_date": (TODAY - dt.timedelta(days=2)).isoformat(), "description": self.unique("Recurring coffee")})
        result = self.ok("process_recurring", "POST", {})
        self.assertEqual(result["processed"], 3)
        self.assertEqual(self.balance(account), 64)
        rows = self.ok("transactions", query={"account_id": account["id"]})
        self.assertEqual(len(rows), 3)
        self.assertEqual(len({row["occurrence_date"] for row in rows}), 3)
        self.assertEqual(self.record("recurring", recurring["id"])["next_date"], (TODAY + dt.timedelta(days=1)).isoformat())
        self.assertEqual(self.ok("process_recurring", "POST", {})["processed"], 0)
        self.assertEqual(self.balance(account), 64)
        self.ok("recurring", "PUT", {"id": recurring["id"], "enabled": False, "amount": "20"})
        self.assertFalse(self.record("recurring", recurring["id"])["enabled"])
        self.ok("recurring", "DELETE", {"id": recurring["id"]})
        self.assertEqual(self.balance(account), 64)
        self.assertEqual(self.query_db("SELECT COUNT(*) n FROM transactions WHERE account_id=? AND recurring_id IS NULL", (account["id"],))[0]["n"], 3)

    def test_08_category_hierarchy_and_tags_crud(self):
        parent = self.category()
        child = self.category(parent_id=parent["id"])
        self.rejected("categories", "PUT", {"id": parent["id"], "parent_id": child["id"]})
        self.rejected("categories", "PUT", {"id": parent["id"], "parent_id": parent["id"]})
        self.rejected("categories", "DELETE", {"id": parent["id"]}, statuses=(409, 422))
        self.rejected("categories", data={"name": "Wrong parent type", "type": "income", "parent_id": parent["id"]})
        updated = self.ok("categories", "PUT", {"id": child["id"], "name": self.unique("Renamed"), "color": "#123abc"})
        self.assertEqual(updated["parent_id"], parent["id"])
        self.assertEqual(updated["color"], "#123abc")
        self.ok("categories", "DELETE", {"id": child["id"]})
        self.ok("categories", "DELETE", {"id": parent["id"]})
        tag = self.ok("tags", "POST", {"name": self.unique("Tag"), "color": "#abcdef"})
        tag = self.ok("tags", "PUT", {"id": tag["id"], "name": self.unique("Renamed tag")})
        self.assertIn(tag["id"], [row["id"] for row in self.ok("tags", query={"search": tag["name"]})])
        self.ok("tags", "DELETE", {"id": tag["id"]})
        self.assertNotIn(tag["id"], [row["id"] for row in self.ok("tags")])

    def test_09_invalid_inputs_and_atomic_tag_validation(self):
        account = self.account()
        expense_category = self.category()
        income_category = self.category("income")
        for amount in ("0", "-1", "1.001", "1e3", "NaN", "1; DROP TABLE users"):
            with self.subTest(amount=amount):
                self.rejected("transactions", data={"account_id": account["id"], "amount": amount, "type": "expense"})
        self.rejected("transactions", data={"account_id": account["id"], "amount": "1", "type": "expense", "date": "2026-02-30"})
        self.rejected("transactions", data={"account_id": account["id"], "amount": "1", "type": "expense", "currency": "EUR"})
        self.rejected("transactions", data={"account_id": account["id"], "amount": "1", "type": "income", "category_id": expense_category["id"]})
        self.rejected("transactions", data={"account_id": account["id"], "amount": "1", "type": "expense", "category_id": income_category["id"]})
        before = self.query_db("SELECT COUNT(*) n FROM transactions")[0]["n"]
        self.rejected("transactions", data={"account_id": account["id"], "amount": "5", "type": "expense", "tags": [f"Invalid{i}" for i in range(21)]})
        self.assertEqual(self.query_db("SELECT COUNT(*) n FROM transactions")[0]["n"], before)
        self.assertEqual(self.balance(account), 100)
        self.rejected("accounts", "PUT", {"id": "1 OR 1=1", "name": "Injected"})
        self.rejected("transactions", data={"account_id": 987654321, "amount": "1", "type": "expense"}, statuses=(404, 422))
        anonymous = Client(self.base)
        self.ok("session", client=anonymous)
        self.rejected("transactions", method="GET", client=anonymous, statuses=(401,))
        self.rejected("accounts", data={"name": "Unauthorized", "type": "cash"}, client=anonymous, statuses=(401,))
        status, _, _ = self.owner.request("transactions", "POST", {"account_id": account["id"], "type": "income", "amount": "1"}, csrf=False)
        self.assertEqual(status, 419)
        self.assertEqual(self.balance(account), 100)

    def test_10_currency_separation_reports_and_forecast(self):
        baseline = {row["currency"]: row for row in self.ok("bootstrap")["summary"]["currencies"]}
        usd = self.account("1.01")
        uzs = self.account("1000", currency="UZS")
        self.transaction(usd, "10", "income")
        self.transaction(usd, "2")
        self.transaction(uzs, "500", "income")
        self.transaction(uzs, "100")
        summary = {row["currency"]: row for row in self.ok("bootstrap")["summary"]["currencies"]}
        self.assertEqual(set(summary), {"USD", "UZS", "EUR", "RUB"})
        self.assertAlmostEqual(summary["USD"]["balance"] - baseline["USD"]["balance"], 9.01, places=2)
        self.assertEqual(summary["UZS"]["balance"] - baseline["UZS"]["balance"], 1400)
        self.assertEqual(summary["USD"]["income"] - baseline["USD"]["income"], 10)
        self.assertEqual(summary["USD"]["expense"] - baseline["USD"]["expense"], 2)
        self.assertEqual(summary["UZS"]["income"] - baseline["UZS"]["income"], 500)
        self.assertEqual(summary["UZS"]["expense"] - baseline["UZS"]["expense"], 100)
        before_forecast = self.ok("analytics", query={"currency": "USD"})
        self.assertEqual(before_forecast["currency"], "USD")
        self.assertEqual(before_forecast["balance"], summary["USD"]["balance"])
        self.assertAlmostEqual(sum(row["balance"] for row in before_forecast["distribution"]), before_forecast["balance"], places=2)
        self.assertEqual(len(before_forecast["monthly"]), 6)
        self.assertEqual(len(before_forecast["cashflow"]), 30)
        self.assertEqual(before_forecast["cashflow"][-1]["balance"], before_forecast["balance"])
        forecast_account = self.account("1000")
        schedule = self.ok("recurring", "POST", {"account_id": forecast_account["id"], "type": "expense", "amount": "1",
            "frequency": "daily", "next_date": (TODAY + dt.timedelta(days=1)).isoformat()})
        debt = self.ok("debts", "POST", {"direction": "borrowing", "counterparty": "Forecast due bill", "amount": "30", "currency": "USD",
            "due_date": (TODAY + dt.timedelta(days=15)).isoformat()})
        projected = self.ok("analytics", query={"currency": "USD"})
        self.assertEqual([row["days"] for row in projected["forecast"]], [30, 60, 90])
        for before, after in zip(before_forecast["forecast"], projected["forecast"]):
            days = after["days"]
            self.assertEqual(after["scheduled_expense"] - before["scheduled_expense"], days + 30)
            self.assertAlmostEqual(after["balance"] - before["balance"], 1000 - days - 30, places=2)
        self.ok("recurring", "DELETE", {"id": schedule["id"]})
        self.ok("debts", "DELETE", {"id": debt["id"]})
        self.rejected("analytics", method="GET", query={"currency": "BTC"})

    def test_11_assistant_rbac_credentials_and_revocation(self):
        account = self.account("987654.32", details="Private IBAN 123456789")
        assistant_email = f"assistant-{self.unique('user').split()[-1]}@example.test"
        user = self.ok("users", "POST", {"name": "Operations Assistant", "email": assistant_email, "password": PASSWORD, "active": True})
        self.assertEqual(user["role"], "assistant")
        self.assertNotIn("password_hash", user)
        assistant = Client(self.base)
        self.ok("session", client=assistant)
        session = self.ok("login", "POST", {"email": assistant_email, "password": PASSWORD}, client=assistant)
        self.assertEqual(session["user"]["role"], "assistant")
        bootstrap = self.ok("bootstrap", client=assistant)
        for private in ("summary", "analytics", "users", "audit"):
            self.assertNotIn(private, bootstrap)
        self.assertTrue(bootstrap["accounts"])
        for row in bootstrap["accounts"]:
            self.assertEqual(set(row), {"id", "name", "type", "currency"})
        for action in ("transfers", "budgets", "debts", "repayments", "users", "audit", "analytics", "backup"):
            with self.subTest(action=action):
                self.rejected(action, method="GET", client=assistant, statuses=(403,))
        for method, data in (("POST", {"name": "Forbidden account", "type": "bank"}),
                             ("PUT", {"id": account["id"], "name": "Unauthorized rename"}),
                             ("DELETE", {"id": account["id"]})):
            self.rejected("accounts", method, data, client=assistant, statuses=(403,))
        self.rejected("users", data={"name": "Attacker", "email": "attack@example.test", "password": PASSWORD}, client=assistant, statuses=(403,))
        self.rejected("audit", "DELETE", {"id": 1}, client=assistant, statuses=(403,))
        tx = self.ok("transactions", "POST", {"account_id": account["id"], "type": "expense", "amount": "5", "date": TODAY.isoformat(), "description": "Assistant operational receipt", "receipt": "daily-receipt.pdf"}, client=assistant)
        self.assertEqual(self.balance(account), 987649.32)
        self.ok("transactions", "PUT", {"id": tx["id"], "amount": "6"}, client=assistant)
        self.assertEqual(self.balance(account), 987648.32)
        self.assertIn(tx["id"], [row["id"] for row in self.ok("receipts", client=assistant)])
        self.ok("transactions", "DELETE", {"id": tx["id"]}, client=assistant)
        self.assertEqual(self.balance(account), 987654.32)
        self.rejected("password", data={"current_password": "wrong-password", "new_password": "Another-Password-937!"}, client=assistant, statuses=(403,))
        new_password = "Another-Password-937!"
        self.ok("password", "POST", {"current_password": PASSWORD, "new_password": new_password}, client=assistant)
        self.assertEqual(self.ok("session", client=assistant)["user"]["role"], "assistant")
        self.ok("users", "PUT", {"id": user["id"], "active": False})
        self.assertIsNone(self.ok("session", client=assistant)["user"])
        self.rejected("login", data={"email": assistant_email, "password": new_password}, client=assistant, statuses=(401,))
        reset_password = "Owner-Reset-Password-492!"
        self.ok("users", "PUT", {"id": user["id"], "active": True, "password": reset_password, "name": "Reactivated Assistant"})
        login = self.ok("login", "POST", {"email": assistant_email, "password": reset_password}, client=assistant)
        self.assertEqual(login["user"]["name"], "Reactivated Assistant")
        self.ok("logout", "POST", {}, client=assistant)

    def test_12_csv_formula_protection_and_consistent_sqlite_backup(self):
        account = self.account()
        formula = '=HYPERLINK("https://example.test","invoice")'
        tx = self.transaction(account, "1.23", description=formula)
        status, exported, headers = self.owner.request("export", query={"type": "transactions", "account_id": account["id"]})
        self.assertEqual(status, 200)
        self.assertIsInstance(exported, bytes)
        self.assertIn("attachment", headers.get("Content-Disposition", ""))
        rows = list(csv.DictReader(io.StringIO(exported.decode("utf-8-sig"))))
        exported_tx = next(row for row in rows if int(row["id"]) == tx["id"])
        self.assertEqual(exported_tx["description"], "'" + formula)
        self.assertEqual(exported_tx["amount"], "1.23")
        self.assertEqual(exported_tx["account_id"], str(account["id"]))
        status, backup, headers = self.owner.request("backup")
        self.assertEqual(status, 200)
        self.assertTrue(backup.startswith(b"SQLite format 3\x00"))
        self.assertIn("attachment", headers.get("Content-Disposition", ""))
        backup_path = Path(self.temporary.name) / "downloaded-backup.db"
        backup_path.write_bytes(backup)
        with sqlite3.connect(backup_path) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(db.execute("SELECT amount FROM transactions WHERE id=?", (tx["id"],)).fetchone()[0], 123)
            self.assertGreaterEqual(db.execute("SELECT COUNT(*) FROM audit_logs WHERE action='backup'").fetchone()[0], 1)
        self.ok("transactions", "DELETE", {"id": tx["id"]})

    def test_13_audit_append_only_and_locale_persistence(self):
        audit = self.ok("audit")
        self.assertTrue(audit)
        self.assertTrue(any(row["action"] == "create" for row in audit))
        for method in ("POST", "PUT", "DELETE"):
            self.rejected("audit", method, {"id": audit[0]["id"], "action": "tampered"}, statuses=(403,))
        with sqlite3.connect(self.db_path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM audit_logs WHERE id=?", (audit[0]["id"],))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE audit_logs SET action='tampered' WHERE id=?", (audit[0]["id"],))
        for locale in ("uz", "ru", "en"):
            result = self.ok("locale", "POST", {"locale": locale})
            self.assertEqual(result["locale"], locale)
            self.assertEqual(self.ok("session")["locale"], locale)
        self.rejected("locale", data={"locale": "invalid-language"})

    def test_14_explicit_currency_exchange_and_cashflow(self):
        source = self.account("1000", currency="USD")
        destination = self.account("0", currency="UZS")
        before_usd = self.ok("analytics", query={"currency": "USD"})
        before_uzs = self.ok("analytics", query={"currency": "UZS"})
        exchange = self.ok("transfers", "POST", {"from_account_id": source["id"], "to_account_id": destination["id"],
            "amount": "100", "received_amount": "1250000", "fee": "2", "date": TODAY.isoformat()})
        self.assertEqual(exchange["currency"], "USD")
        self.assertEqual(exchange["to_currency"], "UZS")
        self.assertEqual(exchange["received_amount"], 1250000)
        self.assertEqual(self.balance(source), 898)
        self.assertEqual(self.balance(destination), 1250000)
        after_usd = self.ok("analytics", query={"currency": "USD"})
        after_uzs = self.ok("analytics", query={"currency": "UZS"})
        self.assertEqual(after_usd["expense"] - before_usd["expense"], 2)
        self.assertEqual(after_uzs["expense"], before_uzs["expense"])
        def daily_change(analytics):
            return analytics["cashflow"][-1]["balance"] - analytics["cashflow"][-2]["balance"]
        self.assertAlmostEqual(daily_change(after_usd) - daily_change(before_usd), -102, places=2)
        self.assertAlmostEqual(daily_change(after_uzs) - daily_change(before_uzs), 1250000, places=2)
        self.rejected("transfers", "PUT", {"id": exchange["id"], "amount": "150"})
        self.assertEqual(self.balance(source), 898)
        self.ok("transfers", "PUT", {"id": exchange["id"], "amount": "150", "received_amount": "1875000"})
        self.assertEqual(self.balance(source), 848)
        self.assertEqual(self.balance(destination), 1875000)
        self.ok("transfers", "DELETE", {"id": exchange["id"]})
        self.assertEqual(self.balance(source), 1000)
        self.assertEqual(self.balance(destination), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
