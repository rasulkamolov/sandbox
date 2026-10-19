# HTTP API

All application requests target `/api.php?action=ACTION`. JSON responses use `{ "ok": true, "data": ... }` or `{ "ok": false, "error": "Message" }`. Use `Content-Type: application/json` for mutations. Authentication is cookie-based; keep the session cookie and use `X-CSRF-Token` on every POST, PUT and DELETE, including setup/login. The token is returned by `GET ?action=session`; authentication changes may rotate it, so use the new token returned by setup/login.

## Session actions

| Action | Method | Input / result |
| --- | --- | --- |
| `session` | GET | Current user or null, CSRF token, locale, setup requirement, supported currencies |
| `setup` | POST | `name`, `email`, `password`, `demo` boolean; only before owner creation |
| `login` | POST | `email`, `password` |
| `logout` | POST | Ends authentication |
| `locale` | POST | `locale`: `en`, `uz`, `ru` |
| `password` | POST | `current_password`, `new_password` |
| `bootstrap` | GET | Authorized module collections and dashboard data |

`GET /i18n.php?lang=en` returns a translation dictionary. Session locale is persisted through the API's `locale` action.

## Collections and writes

For each resource below, GET lists, POST creates, PUT updates and DELETE removes a record. Updates/deletes use the numeric `id` in the JSON body. See the UI forms for validation details. Amounts are positive decimal major units; the server converts to integer hundredths and validates currency consistency. ISO local dates/datetimes use the configured `Asia/Samarkand` timezone.

| Resource | Fields |
| --- | --- |
| `accounts` | `name`, `type`, `currency`, `initial_balance`, `icon`, `color`, `status`, `details`, `target_amount` |
| `transactions` | `type`, `amount`, `currency`, `account_id`, `category_id`, `date`, `description`, `tags` string array, `receipt` reference |
| `transfers` | `from_account_id`, `to_account_id`, `amount`, `received_amount` (required for different currencies), `fee`, `date`, `description` |
| `categories` | `name`, `type`, `parent_id`, `icon`, `color` |
| `tags` | `name`, `color` |
| `budgets` | `category_id`, `amount`, `currency`, `month` (`YYYY-MM`) |
| `debts` | `direction`, `counterparty`, `contact`, `amount`, `currency`, optional `account_id`, `due_date`, `date`, `description` |
| `repayments` | `debt_id`, `account_id`, `amount`, `date`, `description` |
| `recurring` | `type`, `amount`, `account_id`, `category_id`, `description`, `frequency`, `next_date`, `enabled` |
| `users` | `name`, `email`, `password`, `active` (owner-managed assistants only) |

Account types: `bank`, `card`, `cash`, `savings`, `digital`. Status: `active`, `archived`. Transaction/category types: `income`, `expense`. Debt directions: `borrowing`, `lending`. Recurrence: `daily`, `weekly`, `monthly`, `annual`.

GET filters include `search`, `from`, `to`, `account_id` and `category_id` where applicable. The UI also applies instant collection filters. Transfers require different accounts. For different currencies, supply the explicit `received_amount` in destination currency; for the same currency it must equal `amount`. Records linked to active ledger data may reject deletion to preserve referential integrity. Deleting or updating a financial record reverses/replaces its effects; posted balances are derived from the ledger.

`POST ?action=process_recurring` materializes due scheduled transactions once per occurrence. It is safe to run repeatedly. `GET ?action=analytics&currency=USD` returns monthly income/expenses, daily cash flow, distribution and forecast data. `GET ?action=audit` returns owner-only audit records; there is no delete action.

## Downloads

- `GET ?action=export&type=transactions`: native CSV download. Spreadsheet formulas in text cells are neutralized. Access obeys role permissions.
- `GET ?action=backup`: owner-only consistent SQLite database download.

## Authorization

The owner can use all modules. Assistants may access operational transactions, categories, tags, recurring records and minimal account selectors. Account balances and private account metadata, dashboard totals, analytics, transfers, budgets, debts, users, audit and backup require owner access. A disallowed request returns HTTP 403. Unauthenticated requests return HTTP 401. Invalid CSRF returns HTTP 419. Validation failures use HTTP 422; database relationship/uniqueness conflicts may use HTTP 409. Do not infer authorization merely from a hidden menu item.
