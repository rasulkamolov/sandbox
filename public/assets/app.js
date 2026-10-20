'use strict';

(() => {
  // Resolve from the script itself, so root, subfolder and index.php URLs all
  // share one application base without hardcoding a domain or deployment path.
  const appBase = new URL('../', document.currentScript?.src || new URL('assets/app.js', location.href).href);
  const bundleVersion = new URL(document.currentScript?.src || appBase.href).searchParams.get('v') || '';
  const appUrl = path => new URL(path, appBase).href;
  const preferences = {
    get(key) { try { return localStorage.getItem(key); } catch (_) { return null; } },
    set(key, value) { try { localStorage.setItem(key, value); } catch (_) { /* Storage may be disabled by the browser. */ } },
  };
  const state = {
    user: null, csrf: '', locale: 'en', dictionary: {}, page: 'dashboard', data: {},
    currency: 'USD', search: '', from: '', to: '', charts: [], chartFrame: null, modalReturn: null,
    theme: preferences.get('vela-theme') || 'dark', loading: false,
    reportFilters: null, report: null, reportLoading: false, reportError: '', reportRequest: 0, refreshRevision: 0,
  };
  const $ = (selector, parent = document) => parent.querySelector(selector);
  const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
  const escape = value => String(value ?? '').replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
  const defaults = {
    app_tagline: 'A clearer view of your money.', app_description: 'One thoughtful workspace for your personal finances and your business.',
    welcome_back: 'Welcome back', create_workspace: 'Create your workspace', setup_intro: 'Your financial clarity starts here. Set up your secure owner account.',
    login_intro: 'Sign in to your financial workspace.', owner_name: 'Your name', email: 'Email address', password: 'Password',
    password_hint: 'At least 12 characters', demo_data: 'Explore with sample data', demo_description: 'Add realistic accounts, activity, budgets, and debts. You can edit or remove them anytime.',
    create_account: 'Create workspace', sign_in: 'Sign in', secure_workspace: 'Your money. Your workspace.',
    secure_description: 'Private accounts, thoughtful insights, and a complete picture of where you stand.',
    privacy_first: 'Private by design', privacy_description: 'Your financial data stays in your own database.',
    currency_aware: 'Built for every currency', currency_description: 'Keep UZS, USD, EUR, and RUB clearly separated.',
    clarity_daily: 'Clarity, every day', clarity_description: 'Track spending, plan ahead, and move with confidence.',
    dashboard: 'Overview', accounts: 'Accounts', transactions: 'Transactions', transfers: 'Transfers', budgets: 'Budgets', debts: 'Debts & loans',
    reports: 'Reports & insights', categories: 'Categories & tags', recurring: 'Recurring activity', settings: 'Settings',
    dashboard_title: 'Your money, in focus.', dashboard_subtitle: 'A little clarity for your next big move.',
    accounts_subtitle: 'Every balance. Every account. All in one place.', transactions_subtitle: 'The complete story behind your money.',
    transfers_subtitle: 'Move money between your accounts with confidence.', budgets_subtitle: 'Make room for what matters most.',
    debts_subtitle: 'Keep promises and payments in clear view.', reports_subtitle: 'Understand today. Plan for tomorrow.',
    categories_subtitle: 'Give every transaction a meaningful place.', recurring_subtitle: 'Stay one step ahead of regular payments.',
    settings_subtitle: 'A workspace that works your way.', total_balance: 'Total balance', monthly_income: 'Income this month', monthly_expenses: 'Expenses this month',
    net_cashflow: 'Net cash flow', current_currency: 'In selected currency', this_month: 'This month', all_time: 'All time',
    cash_flow: 'Cash flow', cash_flow_description: 'Your balance over the last 30 days', income: 'Income', expense: 'Expense', balance: 'Balance',
    account_distribution: 'Account distribution', by_asset_type: 'A closer look at your assets', recent_activity: 'Recent activity', view_all: 'View all',
    your_accounts: 'Your accounts', add_account: 'Add account', budget_overview: 'Budget overview', upcoming_payments: 'Upcoming payments',
    financial_outlook: 'Your financial outlook', forecast_description: 'A planning estimate based on median daily spending and scheduled payments.',
    days: 'days', projected_balance: 'Projected balance', daily_median: 'Median daily spending', forecast_disclaimer: 'Estimates use recent history and current schedules. They are not a guarantee of future balances.',
    quick_add: 'Add transaction', add_transaction: 'Add transaction', add_transfer: 'New transfer', add_budget: 'Create budget', add_debt: 'Add debt',
    add_category: 'Add category', add_tag: 'Add tag', add_recurring: 'Add recurring', add_user: 'Add assistant', search: 'Search',
    search_placeholder: 'Search your activity…', from_date: 'From', to_date: 'To', currency: 'Currency', all_currencies: 'All currencies',
    no_activity: 'A fresh start awaits', no_activity_description: 'Add your first entry and start building a clearer financial picture.',
    no_results: 'Nothing matches your search', no_results_description: 'Try another search or clear the date filters.', clear_filters: 'Clear filters',
    no_accounts: 'Make yourself at home', no_accounts_description: 'Add a bank account, card, or cash wallet to get started.',
    no_budgets: 'Give your money a plan', no_budgets_description: 'Set a monthly limit for a category and track your progress.',
    no_debts: 'A clean slate', no_debts_description: 'Track what you owe and what is owed to you here.',
    no_recurring: 'Build a calmer routine', no_recurring_description: 'Schedule bills and income so nothing gets overlooked.',
    description: 'Description', amount: 'Amount', account: 'Account', category: 'Category', date: 'Date', type: 'Type', status: 'Status', actions: 'Actions',
    name: 'Name', initial_balance: 'Initial balance', current_balance: 'Current balance', icon: 'Icon', color: 'Color', details: 'Account details',
    target_amount: 'Savings target', active: 'Active', archived: 'Archived', bank: 'Bank account', card: 'Payment card', cash: 'Cash wallet', savings: 'Savings vault', digital: 'Digital wallet',
    edit: 'Edit', delete: 'Delete', cancel: 'Cancel', save: 'Save changes', create: 'Create', close: 'Close', optional: 'Optional',
    delete_title: 'Delete this entry?', delete_description: 'This permanently removes the entry and recalculates affected balances.',
    deleted: 'Entry deleted', saved: 'Changes saved', created: 'Entry created', error_generic: 'Something went wrong. Please try again.',
    api_response_error: 'The server returned a page instead of app data. Check that all uploaded files are present, then try again.', request_timeout: 'Your server took too long to respond. Please try again.',
    network_error: 'Unable to reach your workspace. Check your connection and try again.', loading: 'Getting things ready…',
    from_account: 'From account', to_account: 'To account', transfer_fee: 'Transfer fee', transfer_note: 'Transfer fees are deducted from the source account in addition to the transfer amount.', received_amount: 'Amount received', received_amount_hint: 'Enter the amount credited in the destination currency.', cross_currency_note: '{from} is deducted from the source. Enter the amount received in {to}; no exchange rate is assumed.', different_accounts_required: 'Choose two different accounts.', receipt: 'Receipt reference', receipt_hint: 'Optional receipt number, reference, or URL.', repayment_account_hint: 'The repayment updates this account balance.',
    transaction_note: 'The account determines the currency. Amounts are always positive.', tags: 'Tags', tags_hint: 'Separate tags with commas', uncategorized: 'Uncategorized',
    month: 'Month', spent: 'Spent', remaining: 'Remaining', budget: 'Budget', of_budget: 'of budget', over_budget: 'Over budget', on_track: 'On track', nearing_limit: 'Nearing limit',
    direction: 'Direction', borrowing: 'I owe someone', lending: 'Someone owes me', counterparty: 'Counterparty', contact: 'Contact', principal: 'Principal',
    due_date: 'Due date', no_due_date: 'No due date', repaid: 'Repaid', outstanding: 'Outstanding', overdue: 'Overdue', record_payment: 'Record repayment', repayments: 'Repayment history',
    payment_account_hint: 'Choose an account to also record the cash movement.', no_account_movement: 'No account movement', payment_saved: 'Repayment recorded',
    parent_category: 'Parent category', no_parent: 'Top-level category', frequency: 'Frequency', daily: 'Daily', weekly: 'Weekly', monthly: 'Monthly', annual: 'Annual',
    next_date: 'Next occurrence', enabled: 'Enabled', paused: 'Paused', process_recurring: 'Process due entries', recurring_processed: 'Due recurring entries processed',
    income_vs_expenses: 'Income vs. expenses', six_months: 'The last six months, side by side', export_csv: 'Export CSV',
    receivables: 'Money owed to you', payables: 'Money you owe', net_position: 'Net position', account_history: 'Account history', no_history: 'No activity for this account yet.',
    preferences: 'Preferences', preferences_description: 'Make this space feel like yours.', language: 'Language', appearance: 'Appearance', dark: 'Dark', light: 'Light',
    security: 'Security', security_description: 'Keep your workspace secure with a strong, unique password.', current_password: 'Current password', new_password: 'New password',
    confirm_password: 'Confirm new password', change_password: 'Change password', password_changed: 'Password updated', password_mismatch: 'Passwords do not match.',
    team: 'Your team', team_description: 'Assistants can manage daily activity. Private balances and security controls stay with you.',
    role: 'Role', owner: 'Owner', assistant: 'Assistant', inactive: 'Inactive', user_password_hint: 'Leave blank to keep the existing password.',
    data_backup: 'Data & backup', backup_description: 'Download a consistent copy of your complete SQLite database. Store it somewhere safe.', download_backup: 'Download database',
    audit_log: 'Audit log', audit_description: 'A read-only record of important workspace changes.', event: 'Event', user: 'User',
    sign_out: 'Sign out', signed_out: 'You have signed out', secure_session: 'Secure session', overview: 'Overview', more: 'More',
    selected_currency_only: 'Showing one currency at a time. Balances are never combined across currencies.',
    no_chart_data: 'Your insights will appear as you add activity.', no_upcoming: 'All clear. No upcoming payments.',
    good_morning: 'Good morning', good_afternoon: 'Good afternoon', good_evening: 'Good evening', workspace: 'Your workspace',
    live_balance: 'Live balance', last_four: 'Account details', account_archived: 'Archived account', full_name: 'Full name',
    session_refreshed: 'Your secure session was refreshed. Please try again.', retry: 'Try again', setup_failed: 'We could not load your workspace.', remember_secure: 'Protected by hashed passwords and a secure session.',
    transferred: 'Transferred', fee: 'Fee', transaction: 'Transaction', transfer: 'Transfer', debt: 'Debt', recurring_entry: 'Recurring entry',
    confirm_delete_payment: 'Delete this repayment?', password_minimum: 'Use at least 12 characters for your password.', payment_amount: 'Repayment amount',
    "report_period": "Report period",
    "report_last_month": "Last month",
    "report_last_90_days": "Last 90 days",
    "report_custom": "Custom dates",
    "report_apply": "Apply filters",
    "report_all_accounts": "All accounts",
    "report_period_label": "{from} – {to}",
    "report_comparison_label": "Compared with {from} – {to} ({days} days each).",
    "report_scope_note": "One currency at a time. Transfers between accounts are excluded from income and spending; transfer fees are included in expenses.",
    "report_period_income": "Period income",
    "report_period_expense": "Period expenses",
    "report_period_net": "Net cash flow",
    "report_savings_rate": "Savings rate",
    "report_savings_formula": "(Income − expenses) ÷ income",
    "report_no_income_rate": "Unavailable without income",
    "report_change_no_baseline": "No previous-period baseline",
    "report_change_equal": "Unchanged from the previous period",
    "report_change": "{amount} ({percent}) vs. previous period",
    "report_chart_data": "View chart data",
    "report_cumulative_net": "Cumulative net cash flow",
    "report_cumulative_note": "Income minus expenses accumulated during this period; this is not your account balance.",
    "report_spending_categories": "Where your money went",
    "report_spending_note": "Categories ranked by spending, including uncategorized expenses and transfer fees.",
    "report_transactions_count": "{count} transactions",
    "report_category_share": "{share} of spending",
    "report_transfer_fees": "Transfer fees",
    "report_no_spending": "No expenses in this period",
    "report_no_spending_hint": "Record an expense to see which categories use the most money.",
    "report_account_performance": "Account performance",
    "report_account_note": "Period income and spending alongside each account’s current balance.",
    "report_current_balance": "Balance now",
    "report_largest_expenses": "Largest expenses",
    "report_largest_note": "The biggest expense transactions in the selected period.",
    "report_no_largest": "No expense transactions to show.",
    "report_insights": "What needs your attention",
    "report_insights_note": "Practical observations from this period and your current obligations.",
    "report_as_of": "Current position as of {date}",
    "report_due_next30": "Due in the next 30 days",
    "report_overdue_payables": "Overdue payments you owe",
    "report_overdue_receivables": "Overdue payments owed to you",
    "report_payables_next30": "You need to pay",
    "report_receivables_next30": "You expect to receive",
    "report_upcoming_detail": "Upcoming bills & debt payments",
    "report_upcoming_note": "Scheduled items are shown from today, independently of the report period.",
    "report_liquidity": "Liquidity & planning",
    "report_daily_expense": "Average daily spending",
    "report_daily_expense_note": "Selected-period expenses ÷ {days} calendar days.",
    "report_runway": "Cash runway",
    "report_runway_value": "{days} days",
    "report_runway_unavailable": "Add spending history to estimate",
    "report_runway_note": "Current balance ÷ average daily spending. This assumes no future income.",
    "report_forecast_scope": "30 / 60 / 90-day forecast covers all {currency} accounts, regardless of the account filter.",
    "report_empty_title": "Your report starts with your first transaction",
    "report_empty_description": "This period has no income or expenses. Add activity or choose another period to uncover useful patterns.",
    "report_loading": "Preparing your report…",
    "report_failed": "The report could not be loaded.",
    "report_invalid_dates": "Choose a valid start date and an end date on or after it.",
    "report_insight_no_activity": "No activity in this period. Add your first transaction or try another date range.",
    "report_insight_no_income": "Expenses were recorded without income. Check that all income for this period has been added.",
    "report_insight_spending_increased": "Spending rose by {percent} ({amount}) compared with the previous period. Review the largest expenses below.",
    "report_insight_spending_decreased": "Spending fell by {percent} ({amount}) compared with the previous period.",
    "report_insight_biggest_category": "{name} accounts for {share} of expenses ({amount}). This is your biggest spending category.",
    "report_insight_savings_positive": "You retained {amount} after expenses in this period. Consider assigning a savings goal.",
    "report_insight_savings_negative": "Expenses exceeded income by {amount}. Review discretionary spending and upcoming bills.",
    "report_insight_overdue_debts": "You have {amount} in overdue debt payments. Review due dates and arrange repayment.",
    "report_insight_budget_exceeded": "{count} monthly budget limits are exceeded, by {amount} in total. Check Budgets before adding expenses.",
    "report_insight_low_runway": "At the current spending rate, your balance covers about {days} days. Review upcoming payments before committing funds.",
    "report_budget_note": "Budget insights use full monthly limits and actual full-month spending; limits are not prorated to this report period.",
    "sample_data_title": "Remove sample data",
    "sample_data_description": "Remove the marked example records. Your own entries and any sample records they still need are kept.",
    "sample_records_count": "{count} marked sample records",
    "financial_records_count": "{count} financial records in this workspace",
    "sample_none": "There are no marked sample records to remove.",
    "sample_legacy_warning": "This older workspace has no sample markers. To start empty, use Reset financial workspace; this removes ALL financial records.",
    "sample_dependency_note": "Sample accounts, categories, debts, or tags referenced by your own records are kept to protect your data.",
    "sample_removed": "Sample data removed. {count} records deleted.",
    "sample_preserved": "{count} marked records were kept because your own entries still use them.",
    "reset_workspace_title": "Reset financial workspace",
    "reset_workspace_description": "Permanently delete ALL financial data across every account and currency, and start with an empty workspace. This also removes your own entries.",
    "reset_workspace_scope": "Deletes all accounts, transactions, transfers, budgets, debts and repayments, categories, tags, and recurring schedules.",
    "reset_workspace_preserved": "Your login, password, assistants, preferences, and audit history are preserved.",
    "reset_workspace_action": "Reset all financial data",
    "reset_workspace_done": "Financial workspace reset. You can now add your first account.",
    "reset_not_reversible": "This cannot be undone in the app. Download a database backup first if you may need these records.",
    "reset_backup_link": "Download a backup before continuing",
    "reset_password_hint": "Enter your current owner password to authorize this action.",
    "reset_confirmation": "Type the confirmation phrase",
    "reset_confirmation_hint": "Type {phrase} exactly to enable deletion.",
    "reset_confirmation_invalid": "The confirmation phrase does not match.",
    "reset_sample_modal_intro": "Remove only marked sample records. Your own entries stay in this workspace.",
    "reset_all_modal_intro": "You are deleting ALL financial records, including your own real data.",
    "reset_deleted_count": "{count} financial records are currently in scope.",
    "reset_security_note": "Only the workspace owner can perform this action.",
  };
  function t(key, values = {}) {
    let value = state.dictionary[key] ?? defaults[key] ?? key.replaceAll('_', ' ');
    Object.entries(values).forEach(([name, replacement]) => { value = value.replaceAll(`{${name}}`, replacement); });
    return value;
  }
  window.t = t;
  const icon = (name, className = '') => `<i data-lucide="${escape(name || 'circle')}" class="${escape(className)}" aria-hidden="true"></i>`;
  const owner = () => state.user?.role === 'owner';
  const money = (value, currency = state.currency) => {
    try { return new Intl.NumberFormat({ en: 'en-US', uz: 'uz-UZ', ru: 'ru-RU' }[state.locale] || 'en-US', { style: 'currency', currency, maximumFractionDigits: currency === 'UZS' ? 0 : 2 }).format(Number(value || 0)); }
    catch (_) { return `${Number(value || 0).toFixed(2)} ${currency}`; }
  };
  const dateText = (date, includeTime = false, includeYear = false) => {
    if (!date) return '—';
    const raw = String(date).replace(' ', 'T');
    const parsed = new Date(/^\d{4}-\d{2}-\d{2}$/.test(raw) ? `${raw}T12:00:00` : raw);
    if (state.locale === 'uz' && !Number.isNaN(parsed.getTime())) {
      const months = ['yan', 'fev', 'mar', 'apr', 'may', 'iyn', 'iyl', 'avg', 'sen', 'okt', 'noy', 'dek'];
      return `${parsed.getDate()} ${months[parsed.getMonth()]}${includeYear ? ` ${parsed.getFullYear()}` : ''}${includeTime ? `, ${String(parsed.getHours()).padStart(2, '0')}:${String(parsed.getMinutes()).padStart(2, '0')}` : ''}`;
    }
    return Number.isNaN(parsed.getTime()) ? escape(date) : parsed.toLocaleDateString({ en: 'en-US', uz: 'uz-UZ', ru: 'ru-RU' }[state.locale], { month: 'short', day: 'numeric', ...(includeYear ? { year: 'numeric' } : {}), ...(includeTime ? { hour: '2-digit', minute: '2-digit' } : {}) });
  };
  const localDate = () => { const date = new Date(); return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`; };
  const localDateTime = () => `${localDate()}T${String(new Date().getHours()).padStart(2, '0')}:${String(new Date().getMinutes()).padStart(2, '0')}`;
  const array = key => Array.isArray(state.data[key]) ? state.data[key] : [];
  const find = (key, id) => array(key).find(item => Number(item.id) === Number(id));
  const accountCurrency = id => find('accounts', id)?.currency || 'USD';
  const noChart = () => `<p class="chart-empty muted">${escape(t('no_chart_data'))}</p>`;

  async function fetchJSON(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(appUrl(path), { ...options, signal: controller.signal });
      let result;
      try { result = await response.json(); }
      catch (error) {
        if (error.name === 'AbortError') throw error;
        throw new Error(t('api_response_error'));
      }
      if (!result || typeof result !== 'object') throw new Error(t('api_response_error'));
      return { response, result };
    } catch (error) {
      if (error.name === 'AbortError') throw new Error(t('request_timeout'));
      if (error instanceof TypeError) throw new Error(t('network_error'));
      throw error;
    } finally { clearTimeout(timeout); }
  }
  async function api(action, method = 'GET', body, params = {}) {
    const query = new URLSearchParams({ action, ...params });
    const { response, result } = await fetchJSON(`api.php?${query}`, {
      method, credentials: 'same-origin', headers: { Accept: 'application/json', ...(method !== 'GET' ? { 'Content-Type': 'application/json', 'X-CSRF-Token': state.csrf } : {}) },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    });
    if (!response.ok || result.ok === false) {
      if (response.status === 401 && action !== 'login' || response.status === 419) {
        try {
          const { result: freshResult } = await fetchJSON('api.php?action=session', { credentials: 'same-origin', headers: { Accept: 'application/json' } });
          const freshSession = freshResult.data || freshResult;
          if (freshSession.csrf) state.csrf = freshSession.csrf;
          if (!freshSession.user) { state.user = null; await showAuth(!!freshSession.needs_setup); }
        } catch (_) { /* The original error remains useful if reconnection fails. */ }
      }
      const rawMessage = typeof result.error === 'string' ? result.error : result.error?.message || t('error_generic');
      const translated = response.status === 419 ? t('session_refreshed') : state.dictionary.api_errors?.[rawMessage] || (/^\w+ is required\.$/.test(rawMessage) ? t('field_required') : /^Invalid [\w ]+\.$/.test(rawMessage) ? t('validation_error') : state.locale === 'en' ? rawMessage : t('error_generic'));
      const failure = new Error(translated);
      failure.status = response.status;
      throw failure;
    }
    return result.data ?? result;
  }
  async function loadDictionary(locale) {
    state.locale = ['en', 'uz', 'ru'].includes(locale) ? locale : 'en';
    try { const { response, result } = await fetchJSON(`i18n.php?lang=${state.locale}&v=${encodeURIComponent(bundleVersion)}`, { credentials: 'same-origin' }); state.dictionary = response.ok ? result.data || result : {}; }
    catch (_) { state.dictionary = {}; }
    document.documentElement.lang = state.locale;
  }
  function icons() { if (window.lucide) window.lucide.createIcons(); }
  function setTheme(theme) {
    state.theme = theme; preferences.set('vela-theme', theme);
    document.documentElement.dataset.theme = theme;
    document.documentElement.classList.toggle('dark', theme === 'dark');
    const button = $('#theme-toggle');
    if (button) { button.innerHTML = icon(theme === 'dark' ? 'sun' : 'moon'); button.setAttribute('aria-label', t(theme === 'dark' ? 'light' : 'dark')); }
  }
  function toast(message, type = 'success') {
    const root = $('#toast-root'); if (!root) return;
    const item = document.createElement('div'); item.className = `toast ${type}`; item.setAttribute('role', type === 'error' ? 'alert' : 'status');
    item.innerHTML = `${icon(type === 'error' ? 'circle-alert' : type === 'warning' ? 'triangle-alert' : 'circle-check')}<span>${escape(message)}</span><button class="icon-btn" aria-label="${escape(t('close'))}">${icon('x')}</button>`;
    item.querySelector('button').onclick = () => item.remove(); root.append(item); icons();
    setTimeout(() => { item.classList.add('toast-leave'); setTimeout(() => item.remove(), 250); }, 5000);
  }
  function destroyCharts() { if (state.chartFrame !== null) cancelAnimationFrame(state.chartFrame); state.chartFrame = null; state.charts.forEach(chart => chart.destroy()); state.charts = []; }
  function closeModal() {
    const root = $('#modal-root'); if (root) root.innerHTML = '';
    document.body.classList.remove('modal-open'); state.modalReturn?.focus?.();
  }
  function openModal(title, body, footer = '', wide = false) {
    if (!$('#modal-root .modal')) state.modalReturn = document.activeElement;
    $('#modal-root').innerHTML = `<div class="modal-overlay"><section class="modal ${wide ? 'modal-wide' : ''}" role="dialog" aria-modal="true" aria-labelledby="modal-title" tabindex="-1"><div class="modal-handle"></div><div class="modal-header"><div><span class="page-eyebrow">${escape(t('app_name'))} · ${escape(t('workspace'))}</span><h2 id="modal-title">${escape(title)}</h2></div><button class="icon-btn" data-action="close-modal" aria-label="${escape(t('close'))}">${icon('x')}</button></div><div class="modal-body">${body}</div>${footer ? `<div class="modal-footer">${footer}</div>` : ''}</section></div>`;
    document.body.classList.add('modal-open'); icons();
    setTimeout(() => { ($('#modal-root input:not([type=hidden])') || $('#modal-root select') || $('#modal-root .modal')).focus(); }, 20);
  }
  function empty(title = 'no_activity', description = 'no_activity_description', action = '', symbol = 'sparkles') {
    return `<div class="empty-state"><span class="empty-icon">${icon(symbol)}</span><h3>${escape(t(title))}</h3><p>${escape(t(description))}</p>${action}</div>`;
  }
  const button = (label, action, symbol = 'plus', variant = 'primary', extra = '') => `<button class="btn btn-${variant} ${variant}" data-action="${action}" ${extra}>${icon(symbol)}<span>${escape(t(label))}</span></button>`;
  const editButtons = (resource, id) => `<div class="row-actions"><button class="icon-btn" data-action="edit" data-resource="${resource}" data-id="${id}" aria-label="${escape(t('edit'))}">${icon('pencil')}</button><button class="icon-btn danger-text" data-action="delete" data-resource="${resource}" data-id="${id}" aria-label="${escape(t('delete'))}">${icon('trash-2')}</button></div>`;
  const amountDisplay = transaction => `<span class="${transaction.type === 'income' ? 'amount-income' : 'amount-expense'}">${transaction.type === 'income' ? '+' : '−'}${escape(money(transaction.amount, transaction.currency || accountCurrency(transaction.account_id)))}</span>`;
  function matches(items, fields = []) {
    const query = state.search.toLocaleLowerCase();
    return items.filter(item => {
      const date = String(item.date || item.due_date || item.next_date || (item.month ? `${item.month}-01` : ''));
      return (!query || fields.some(key => String(item[key] || '').toLocaleLowerCase().includes(query))) && (!state.from || date.slice(0, 10) >= state.from) && (!state.to || date.slice(0, 10) <= state.to);
    });
  }
  function filterBar({ date = true, currency = false, exportable = false } = {}) {
    return `<div class="filter-bar"><label class="search-field">${icon('search')}<input class="input" data-filter="search" value="${escape(state.search)}" placeholder="${escape(t('search_placeholder'))}" aria-label="${escape(t('search'))}"></label>${date ? `<div class="date-filters"><label><span>${escape(t('from_date'))}</span><input class="input" type="date" data-filter="from" value="${escape(state.from)}"></label><label><span>${escape(t('to_date'))}</span><input class="input" type="date" data-filter="to" value="${escape(state.to)}"></label></div>` : ''}${currency ? currencyPicker() : ''}${exportable ? `<a class="btn btn-secondary secondary" href="${escape(appUrl('api.php?action=export&type=transactions'))}" download>${icon('download')}<span>${escape(t('export_csv'))}</span></a>` : ''}${state.search || state.from || state.to ? `<button class="icon-btn" data-action="clear-filters" aria-label="${escape(t('clear_filters'))}">${icon('filter-x')}</button>` : ''}</div>`;
  }
  function currencyPicker() { return `<label class="currency-select"><span class="sr-only">${escape(t('currency'))}</span><select class="select" data-currency>${['USD', 'UZS', 'EUR', 'RUB'].map(currency => `<option ${state.currency === currency ? 'selected' : ''}>${currency}</option>`).join('')}</select></label>`; }
  function pageHead(title, subtitle, action = '') {
    return `<div class="page-heading"><div><div class="page-eyebrow">${escape(t('workspace'))} <span class="eyebrow-line"></span></div><h1>${escape(t(title))}</h1><p>${escape(t(subtitle))}</p></div><div class="heading-actions">${action}</div></div>`;
  }
  function transactionTable(items, compact = false) {
    if (!items.length) return empty(state.search || state.from || state.to ? 'no_results' : 'no_activity', state.search || state.from || state.to ? 'no_results_description' : 'no_activity_description', button('add_transaction', 'new-transaction'), 'arrow-left-right');
    return `<div class="table-wrap"><table class="data-table ${compact ? 'compact' : ''}"><thead><tr><th>${escape(t('transaction'))}</th><th>${escape(t('account'))}</th><th>${escape(t('date'))}</th><th class="text-right">${escape(t('amount'))}</th>${!compact ? `<th class="text-right">${escape(t('actions'))}</th>` : ''}</tr></thead><tbody>${items.map(item => {
      const category = find('categories', item.category_id); const account = find('accounts', item.account_id);
      const tags = Array.isArray(item.tags) ? item.tags : [];
      return `<tr><td data-label="${escape(t('transaction'))}"><div class="table-main"><span class="transaction-icon" style="--item-color:${safeColor(category?.color)}">${icon(category?.icon || (item.type === 'income' ? 'arrow-down-left' : 'arrow-up-right'))}</span><div><div class="transaction-name">${escape(item.description || item.category_name || category?.name || t(item.type))}</div><div class="transaction-note">${escape(item.category_name || category?.name || t('uncategorized'))}${tags.length ? ` <span class="tag-inline">${escape(tags.join(' · '))}</span>` : ''}</div></div></div></td><td data-label="${escape(t('account'))}"><span class="account-table-label">${escape(item.account_name || account?.name || '—')}</span></td><td data-label="${escape(t('date'))}" class="muted">${dateText(item.date)}</td><td data-label="${escape(t('amount'))}" class="text-right amount-cell">${amountDisplay(item)}</td>${!compact ? `<td class="text-right">${editButtons('transactions', item.id)}</td>` : ''}</tr>`;
    }).join('')}</tbody></table></div>`;
  }
  function safeColor(color) { return /^#[a-f0-9]{3,8}$/i.test(color || '') ? color : '#10b981'; }
  function statCard(label, value, symbol, tone = 'emerald', note = 'current_currency') {
    return `<article class="card stat-card"><div class="stat-top"><span class="stat-label">${escape(t(label))}</span><span class="stat-icon ${tone}">${icon(symbol)}</span></div><div class="stat-value">${escape(value)}</div><div class="stat-change"><span class="stat-mini-dot ${tone}"></span>${escape(t(note))}<span class="stat-currency">${state.currency}</span></div></article>`;
  }
  function summary() {
    const currencies = state.data.summary?.currencies || [];
    if (Array.isArray(currencies)) return currencies.find(row => row.currency === state.currency) || { balance: 0, income: 0, expense: 0, net: 0 };
    return currencies[state.currency] || {};
  }
  function accountCard(account) {
    const symbol = { bank: 'landmark', card: 'credit-card', cash: 'wallet', savings: 'vault', digital: 'smartphone' }[account.type] || 'wallet';
    return `<article class="account-card" style="--account-color:${safeColor(account.color)}"><div class="account-top"><span class="account-symbol">${icon(account.icon || symbol)}</span><span class="account-brand">${escape(account.currency)} <span class="account-status ${account.status === 'archived' ? 'is-archived' : ''}"></span></span></div><button class="account-name-button" data-action="account-history" data-id="${account.id}"><span class="account-name">${escape(account.name)}</span>${icon('arrow-up-right')}</button><div class="account-number">${escape(account.details || t(account.type))}</div><div class="account-bottom"><div><span class="account-caption">${escape(t('current_balance'))}</span><div class="account-balance">${escape(money(account.current_balance ?? account.balance, account.currency))}</div></div>${editButtons('accounts', account.id)}</div>${account.status === 'archived' ? `<span class="badge muted">${escape(t('archived'))}</span>` : ''}</article>`;
  }
  function budgetCard(budget, compact = false) {
    const category = find('categories', budget.category_id); const percentage = Number(budget.percentage ?? (Number(budget.amount) ? Number(budget.spent || 0) / Number(budget.amount) * 100 : 0));
    const tone = percentage >= 100 ? 'red' : percentage >= 75 ? 'amber' : 'emerald';
    return `<article class="${compact ? 'budget-item' : 'card budget-card'}"><div class="flex-between"><div class="table-main"><span class="transaction-icon" style="--item-color:${safeColor(category?.color)}">${icon(category?.icon || 'target')}</span><div><h3>${escape(budget.category_name || category?.name || t('budget'))}</h3><span class="small-text muted">${escape(budget.month || '')}</span></div></div>${compact ? `<span class="badge ${tone}">${Math.round(percentage)}%</span>` : editButtons('budgets', budget.id)}</div><div class="budget-values"><strong>${escape(money(budget.spent, budget.currency))}</strong><span class="muted"> / ${escape(money(budget.amount, budget.currency))}</span></div><div class="progress-track"><div class="progress-fill ${tone}" style="width:${Math.min(100, Math.max(0, percentage))}%"></div></div><div class="flex-between small-text"><span class="${tone}-text">${escape(t(percentage >= 100 ? 'over_budget' : percentage >= 75 ? 'nearing_limit' : 'on_track'))}</span><span class="muted">${escape(money(Number(budget.amount) - Number(budget.spent || 0), budget.currency))} ${escape(t('remaining'))}</span></div></article>`;
  }
  function forecastCards() {
    const forecasts = (state.analytics?.forecast || []).filter(item => [30, 60, 90].includes(Number(item.days)));
    if (!forecasts.length) return noChart();
    return `<div class="forecast-grid">${forecasts.map(item => `<div class="forecast-item"><div class="forecast-days"><span>${Number(item.days)}</span> ${escape(t('days'))}${icon('arrow-up-right')}</div><strong class="${Number(item.balance) < 0 ? 'red-text' : ''}">${escape(money(item.balance))}</strong><span class="small-text muted">${escape(t('projected_balance'))}</span></div>`).join('')}</div><p class="forecast-note">${icon('info')} ${escape(t('forecast_disclaimer'))}</p>`;
  }
  function upcomingPayments() {
    const bills = array('recurring').filter(item => item.enabled && item.type === 'expense' && accountCurrency(item.account_id) === state.currency).map(item => ({ ...item, title: item.description || item.category_name || t('recurring_entry'), due: item.next_date, symbol: 'repeat-2' }));
    const debts = array('debts').filter(item => item.direction === 'borrowing' && item.currency === state.currency && Number(item.remaining ?? item.remaining_balance) > 0 && item.due_date).map(item => ({ ...item, title: item.counterparty, amount: item.remaining ?? item.remaining_balance, due: item.due_date, symbol: 'hand-coins' }));
    const items = [...bills, ...debts].sort((a, b) => String(a.due).localeCompare(String(b.due))).slice(0, 4);
    return items.length ? `<div class="upcoming-list">${items.map(item => `<div class="upcoming-row"><span class="transaction-icon" style="--item-color:#06b6d4">${icon(item.symbol)}</span><div class="upcoming-details"><strong>${escape(item.title)}</strong><span class="muted small-text">${dateText(item.due)}</span></div><strong>${escape(money(item.amount, state.currency))}</strong></div>`).join('')}</div>` : `<div class="quiet-state">${icon('circle-check')}<span>${escape(t('no_upcoming'))}</span></div>`;
  }
  function renderDashboard() {
    const totals = summary(); const accounts = array('accounts').filter(item => item.currency === state.currency && item.status !== 'archived');
    const budgets = array('budgets').filter(item => item.currency === state.currency).slice(0, 3);
    return `${pageHead('dashboard_title', 'dashboard_subtitle', `<span class="period-pill">${icon('calendar-days')}${escape(t('this_month'))}</span>${currencyPicker()}`)}<div class="grid-4 stats-grid">${statCard('total_balance', money(totals.balance), 'wallet', 'emerald', 'live_balance')}${statCard('monthly_income', money(totals.income), 'arrow-down-left', 'cyan', 'this_month')}${statCard('monthly_expenses', money(totals.expense), 'arrow-up-right', 'violet', 'this_month')}${statCard('net_cashflow', money(totals.net ?? (totals.income - totals.expense)), 'chart-no-axes-combined', 'amber', 'this_month')}</div><div class="dashboard-grid"><section class="card chart-card"><div class="card-head"><div><h2>${escape(t('cash_flow'))}</h2><p>${escape(t('cash_flow_description'))}</p></div><span class="badge live-badge"><span></span>${state.currency}</span></div><div class="chart-key"><span><i class="legend-dot emerald"></i>${escape(t('balance'))}</span><span class="muted small-text">${escape(t('this_month'))}</span></div><div class="chart-wrap cashflow-chart"><canvas id="cashflow-chart" role="img" aria-label="${escape(t('cash_flow'))}"></canvas></div><p class="sr-only" id="cashflow-summary">${escape(t('total_balance'))}: ${escape(money(totals.balance))}</p></section><section class="card distribution-card"><div class="card-head"><div><h2>${escape(t('account_distribution'))}</h2><p>${escape(t('by_asset_type'))}</p></div><span class="subtle-icon">${icon('chart-pie')}</span></div><div class="donut-container"><div class="chart-wrap donut-chart"><canvas id="distribution-chart" role="img" aria-label="${escape(t('account_distribution'))}"></canvas></div><div class="donut-center"><span>${escape(t('total_balance'))}</span><strong>${escape(money(totals.balance))}</strong></div></div><div id="distribution-legend" class="distribution-legend"></div></section></div><div class="section-heading"><div><h2>${escape(t('your_accounts'))}<span class="count-badge">${accounts.length}</span></h2><p>${escape(t('selected_currency_only'))}</p></div><button class="btn btn-ghost ghost" data-page="accounts">${escape(t('view_all'))}${icon('arrow-right')}</button></div><div class="account-grid">${accounts.slice(0, 3).map(accountCard).join('') || empty('no_accounts', 'no_accounts_description', button('add_account', 'new-account'), 'wallet')}${accounts.length ? `<button class="account-add-card" data-action="new-account">${icon('plus')}<span>${escape(t('add_account'))}</span></button>` : ''}</div><div class="dashboard-grid activity-grid"><section class="card activity-card"><div class="card-head"><div><h2>${escape(t('recent_activity'))}</h2><p>${escape(t('transactions_subtitle'))}</p></div><button class="btn btn-ghost ghost" data-page="transactions">${escape(t('view_all'))}${icon('arrow-up-right')}</button></div>${transactionTable(array('transactions').filter(item => (item.currency || accountCurrency(item.account_id)) === state.currency).slice(0, 8), true)}</section><div class="stack"><section class="card"><div class="card-head"><h2>${escape(t('budget_overview'))}</h2><button class="icon-btn" data-page="budgets" aria-label="${escape(t('view_all'))}">${icon('arrow-up-right')}</button></div>${budgets.length ? `<div class="budget-stack">${budgets.map(item => budgetCard(item, true)).join('')}</div>` : empty('no_budgets', 'no_budgets_description', button('add_budget', 'new-budget', 'plus', 'secondary'), 'target')}</section><section class="card upcoming-card"><div class="card-head"><h2>${escape(t('upcoming_payments'))}</h2>${icon('calendar-clock')}</div>${upcomingPayments()}</section></div></div><section class="card forecast-card"><div class="card-head"><div><span class="eyebrow-chip">${icon('sparkles')}${escape(t('financial_outlook'))}</span><h2>${escape(t('forecast_description'))}</h2></div><button class="btn btn-ghost ghost" data-page="reports">${escape(t('view_all'))}${icon('arrow-right')}</button></div>${forecastCards()}</section>`;
  }
  function renderAccounts() {
    const items = matches(array('accounts'), ['name', 'type', 'currency', 'details']);
    return `${pageHead('accounts', 'accounts_subtitle', `${button('add_transfer', 'new-transfer', 'arrow-left-right', 'secondary')}${button('add_account', 'new-account')}`)}${filterBar({ date: false })}<div class="card-grid accounts-page-grid">${items.map(accountCard).join('') || empty('no_accounts', 'no_accounts_description', button('add_account', 'new-account'), 'wallet')}</div>`;
  }
  function renderTransactions() { return `${pageHead('transactions', 'transactions_subtitle', button('add_transaction', 'new-transaction'))}<section class="card">${filterBar({ exportable: true })}${transactionTable(matches(array('transactions'), ['description', 'category_name', 'account_name', 'type', 'tags']))}</section>`; }
  function renderTransfers() {
    const items = matches(array('transfers'), ['description', 'from_account_name', 'to_account_name']);
    return `${pageHead('transfers', 'transfers_subtitle', button('add_transfer', 'new-transfer', 'arrow-left-right'))}<section class="card">${filterBar()}${items.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>${escape(t('from_account'))}</th><th>${escape(t('to_account'))}</th><th>${escape(t('date'))}</th><th class="text-right">${escape(t('amount'))}</th><th class="text-right">${escape(t('fee'))}</th><th></th></tr></thead><tbody>${items.map(item => `<tr><td data-label="${escape(t('from_account'))}"><div class="table-main"><span class="transaction-icon" style="--item-color:#06b6d4">${icon('arrow-up-right')}</span><div><strong>${escape(item.from_account_name || find('accounts', item.from_account_id)?.name)}</strong><p class="small-text muted">${escape(item.description)}</p></div></div></td><td data-label="${escape(t('to_account'))}">${escape(item.to_account_name || find('accounts', item.to_account_id)?.name)}</td><td data-label="${escape(t('date'))}" class="muted">${dateText(item.date)}</td><td data-label="${escape(t('amount'))}" class="text-right"><strong>${escape(money(item.amount, item.currency || accountCurrency(item.from_account_id)))}</strong></td><td data-label="${escape(t('fee'))}" class="text-right muted">${escape(money(item.fee, item.currency || accountCurrency(item.from_account_id)))}</td><td>${editButtons('transfers', item.id)}</td></tr>`).join('')}</tbody></table></div>` : empty('no_activity', 'no_activity_description', button('add_transfer', 'new-transfer'), 'arrow-left-right')}</section>`;
  }
  function renderBudgets() {
    const items = matches(array('budgets'), ['category_name', 'month', 'currency']);
    return `${pageHead('budgets', 'budgets_subtitle', button('add_budget', 'new-budget'))}${filterBar()}<div class="grid-3">${items.map(item => budgetCard(item)).join('') || empty('no_budgets', 'no_budgets_description', button('add_budget', 'new-budget'), 'target')}</div>`;
  }
  function renderDebts() {
    const items = matches(array('debts'), ['counterparty', 'contact', 'description', 'direction']);
    return `${pageHead('debts', 'debts_subtitle', button('add_debt', 'new-debt'))}${filterBar()}<div class="grid-3 debt-grid">${items.map(item => {
      const remaining = Number(item.remaining ?? item.remaining_balance ?? item.amount); const paid = Number(item.amount) - remaining;
      const overdue = item.due_date && item.due_date < localDate() && remaining > 0;
      return `<article class="card debt-card"><div class="flex-between"><span class="badge ${item.direction === 'lending' ? 'emerald' : 'amber'}">${icon(item.direction === 'lending' ? 'arrow-down-left' : 'arrow-up-right')}${escape(t(item.direction))}</span>${editButtons('debts', item.id)}</div><div class="debt-person"><span class="person-avatar">${escape(item.counterparty?.slice(0, 2).toUpperCase())}</span><div><h3>${escape(item.counterparty)}</h3><span class="muted small-text">${escape(item.contact || '—')}</span></div></div><span class="stat-label">${escape(t('outstanding'))}</span><div class="debt-amount">${escape(money(remaining, item.currency))}</div><div class="progress-track"><div class="progress-fill emerald" style="width:${Math.min(100, paid / Number(item.amount || 1) * 100)}%"></div></div><div class="flex-between small-text muted"><span>${escape(t('repaid'))}: ${escape(money(paid, item.currency))}</span><span class="${overdue ? 'red-text' : ''}">${overdue ? `${escape(t('overdue'))} · ` : ''}${item.due_date ? dateText(item.due_date) : escape(t('no_due_date'))}</span></div><p class="debt-description muted">${escape(item.description || '')}</p><div class="debt-actions">${remaining > 0 ? button('record_payment', 'repayment', 'plus', 'secondary', `data-id="${item.id}"`) : `<span class="badge emerald">${icon('circle-check')}${escape(t('repaid'))}</span>`}<button class="icon-btn" data-action="debt-history" data-id="${item.id}" aria-label="${escape(t('repayments'))}">${icon('history')}</button></div></article>`;
    }).join('') || empty('no_debts', 'no_debts_description', button('add_debt', 'new-debt'), 'handshake')}</div>`;
  }
  function renderCategories() {
    const categories = matches(array('categories'), ['name', 'type']); const tags = matches(array('tags'), ['name']);
    return `${pageHead('categories', 'categories_subtitle', `${button('add_tag', 'new-tag', 'tag', 'secondary')}${button('add_category', 'new-category')}`)}${filterBar({ date: false })}<div class="grid-2 categories-columns">${['expense', 'income'].map(type => `<section class="card"><div class="card-head"><h2>${escape(t(type))}</h2><span class="count-badge">${categories.filter(item => item.type === type).length}</span></div><div class="category-list">${categories.filter(item => item.type === type).map(item => `<div class="category-row ${item.parent_id ? 'is-child' : ''}"><span class="transaction-icon" style="--item-color:${safeColor(item.color)}">${icon(item.icon || 'shapes')}</span><div class="category-name"><strong>${escape(item.name)}</strong>${item.parent_id ? `<span class="small-text muted">${escape(find('categories', item.parent_id)?.name || '')}</span>` : ''}</div>${editButtons('categories', item.id)}</div>`).join('') || empty('no_activity', 'no_activity_description', '', 'shapes')}</div></section>`).join('')}</div><section class="card tags-card"><div class="card-head"><h2>${escape(t('tags'))}</h2>${button('add_tag', 'new-tag', 'plus', 'ghost')}</div><div class="tags-list">${tags.map(item => `<div class="tag-pill" style="--item-color:${safeColor(item.color)}">${icon('tag')}<strong>${escape(item.name)}</strong>${editButtons('tags', item.id)}</div>`).join('') || `<p class="muted">${escape(t('no_activity_description'))}</p>`}</div></section>`;
  }
  function renderRecurring() {
    const items = matches(array('recurring'), ['description', 'account_name', 'category_name', 'frequency']);
    return `${pageHead('recurring', 'recurring_subtitle', `${button('process_recurring', 'process-recurring', 'refresh-cw', 'secondary')}${button('add_recurring', 'new-recurring')}`)}<section class="card">${filterBar()}${items.length ? `<div class="table-wrap"><table class="data-table"><thead><tr><th>${escape(t('description'))}</th><th>${escape(t('frequency'))}</th><th>${escape(t('next_date'))}</th><th>${escape(t('status'))}</th><th class="text-right">${escape(t('amount'))}</th><th></th></tr></thead><tbody>${items.map(item => `<tr><td data-label="${escape(t('description'))}"><div class="table-main"><span class="transaction-icon" style="--item-color:${item.type === 'income' ? '#10b981' : '#a78bfa'}">${icon('repeat-2')}</span><div><strong>${escape(item.description || item.category_name || t(item.type))}</strong><p class="small-text muted">${escape(item.account_name || find('accounts', item.account_id)?.name || '')}</p></div></div></td><td data-label="${escape(t('frequency'))}">${escape(t(item.frequency))}</td><td data-label="${escape(t('next_date'))}">${dateText(item.next_date)}</td><td data-label="${escape(t('status'))}"><span class="badge ${item.enabled ? 'emerald' : 'muted'}">${escape(t(item.enabled ? 'enabled' : 'paused'))}</span></td><td class="text-right" data-label="${escape(t('amount'))}">${amountDisplay({ ...item, currency: item.currency || accountCurrency(item.account_id) })}</td><td>${editButtons('recurring', item.id)}</td></tr>`).join('')}</tbody></table></div>` : empty('no_recurring', 'no_recurring_description', button('add_recurring', 'new-recurring'), 'repeat-2')}</section>`;
  }
  function reportFilters() {
    if (!state.reportFilters) state.reportFilters = { preset: 'this_month', ...reportRange('this_month'), account_id: '' };
    return state.reportFilters;
  }
  function reportRange(preset) {
    const today = new Date(`${localDate()}T12:00:00`);
    const formatted = value => `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
    let start = new Date(today), end = new Date(today);
    if (preset === 'last_month') { start = new Date(today.getFullYear(), today.getMonth() - 1, 1, 12); end = new Date(today.getFullYear(), today.getMonth(), 0, 12); }
    else if (preset === 'last90') start.setDate(start.getDate() - 89);
    else start.setDate(1);
    return { from: formatted(start), to: formatted(end) };
  }
  function reportParams(useLoaded = false) {
    const filters = useLoaded && state.report ? state.report : reportFilters();
    return { currency: useLoaded && state.report ? state.report.currency : state.currency, from: filters.from, to: filters.to, ...(filters.account_id ? { account_id: filters.account_id } : {}) };
  }
  async function loadReport() {
    if (!owner()) return;
    const request = ++state.reportRequest;
    const filters = reportFilters();
    if (!/^\d{4}-\d{2}-\d{2}$/.test(filters.from) || !/^\d{4}-\d{2}-\d{2}$/.test(filters.to) || filters.from > filters.to) throw new Error(t('report_invalid_dates'));
    state.reportLoading = true; state.reportError = ''; if (state.page === 'reports') render();
    try {
      const report = await api('reports', 'GET', undefined, reportParams());
      if (request !== state.reportRequest) return;
      state.report = report;
    } catch (error) {
      if (request !== state.reportRequest) return;
      state.reportError = error.message;
    } finally {
      if (request === state.reportRequest) { state.reportLoading = false; if (state.page === 'reports') render(); }
    }
  }
  const percentText = value => new Intl.NumberFormat({ en: 'en-US', uz: 'uz-UZ', ru: 'ru-RU' }[state.locale] || 'en-US', { style: 'percent', maximumFractionDigits: 1 }).format(Number(value || 0) / 100);
  function reportToolbar() {
    const filters = reportFilters();
    return `<form data-form="report-filters" class="report-toolbar card"><div class="report-toolbar-top"><div class="report-presets" role="group" aria-label="${escape(t('report_period'))}">${[['this_month', 'this_month'], ['last_month', 'report_last_month'], ['last90', 'report_last_90_days'], ['custom', 'report_custom']].map(([value, key]) => `<button type="button" class="btn ${filters.preset === value ? 'btn-primary primary' : 'btn-secondary secondary'}" data-action="report-period" data-period="${value}" aria-pressed="${filters.preset === value}">${escape(t(key))}</button>`).join('')}</div><div class="report-scope-filters">${currencyPicker()}<label class="report-account-select"><span class="sr-only">${escape(t('account'))}</span><select class="select" data-report-account aria-label="${escape(t('account'))}"><option value="">${escape(t('report_all_accounts'))}</option>${array('accounts').filter(item => item.currency === state.currency).map(item => `<option value="${Number(item.id)}" ${Number(item.id) === Number(filters.account_id) ? 'selected' : ''}>${escape(item.name)}${item.status === 'archived' ? ` · ${escape(t('archived'))}` : ''}</option>`).join('')}</select></label></div></div><div class="report-date-row"><label><span>${escape(t('from_date'))}</span><input class="input" name="from" type="date" data-report-date="from" required value="${escape(filters.from)}"></label><label><span>${escape(t('to_date'))}</span><input class="input" name="to" type="date" data-report-date="to" required min="${escape(filters.from)}" value="${escape(filters.to)}"></label><button type="submit" class="btn btn-secondary secondary">${icon('filter')}${escape(t('report_apply'))}</button></div><p class="report-scope-note muted">${escape(t('report_scope_note'))}</p></form>`;
  }
  function reportMetric(key, label, symbol, tone) {
    const report = state.report, period = report.period || {}, previous = report.previous || {};
    const value = key === 'savings_rate' ? period.savings_rate === null ? '—' : percentText(period.savings_rate) : money(period[key]);
    let note;
    if (key === 'savings_rate') note = t(period.savings_rate === null ? 'report_no_income_rate' : 'report_savings_formula');
    else {
      const change = report.changes?.[key] || {};
      note = Number(change.amount) === 0 && Number(previous[key]) === 0 ? t('report_change_no_baseline') : Number(change.amount) === 0 ? t('report_change_equal') : change.percent === null || change.percent === undefined ? `${Number(change.amount) > 0 ? '+' : '−'}${money(Math.abs(Number(change.amount)))} · ${t('report_change_no_baseline')}` : t('report_change', { amount: `${Number(change.amount) > 0 ? '+' : '−'}${money(Math.abs(Number(change.amount)))}`, percent: `${Number(change.percent) > 0 ? '+' : ''}${percentText(change.percent)}` });
    }
    return `<article class="card stat-card report-metric"><div class="stat-top"><span class="stat-label">${escape(t(label))}</span><span class="stat-icon ${tone}">${icon(symbol)}</span></div><div class="stat-value ${key === 'net' && Number(period.net) < 0 ? 'red-text' : ''}">${escape(value)}</div><p class="report-metric-note muted">${escape(note)}</p></article>`;
  }
  function reportRows() {
    const report = state.report || {};
    return Number(report.period?.days) <= 62 ? report.daily || [] : report.monthly || [];
  }
  function reportChartDataTable() {
    const rows = reportRows();
    return `<details class="chart-data-details"><summary>${escape(t('report_chart_data'))}</summary><div class="table-wrap"><table class="data-table"><thead><tr><th>${escape(t(Number(state.report?.period?.days) <= 62 ? 'date' : 'month'))}</th><th>${escape(t('income'))}</th><th>${escape(t('expense'))}</th><th>${escape(t('net_cashflow'))}</th></tr></thead><tbody>${rows.map(row => `<tr><td data-label="${escape(t('date'))}">${escape(row.date || row.month)}</td><td data-label="${escape(t('income'))}">${escape(money(row.income))}</td><td data-label="${escape(t('expense'))}">${escape(money(row.expense))}</td><td data-label="${escape(t('net_cashflow'))}">${escape(money(row.net))}</td></tr>`).join('')}</tbody></table></div></details>`;
  }
  function reportCategoryName(item) { return item.kind === 'transfer_fees' ? t('report_transfer_fees') : item.kind === 'uncategorized' ? t('uncategorized') : item.name || t('uncategorized'); }
  function reportCategories() {
    const items = state.report?.categories || [];
    if (!items.length) return empty('report_no_spending', 'report_no_spending_hint', '', 'chart-no-axes-column');
    return `<div class="report-category-list">${items.map(item => `<div class="report-category-item"><div class="flex-between"><div class="table-main"><span class="transaction-icon" style="--item-color:${safeColor(item.color)}">${icon(item.icon || 'shapes')}</span><div><strong>${escape(reportCategoryName(item))}</strong><span class="small-text muted">${escape(t('report_transactions_count', { count: Number(item.count) }))} · ${escape(t('report_category_share', { share: percentText(item.share) }))}</span></div></div><strong>${escape(money(item.amount))}</strong></div><div class="report-category-track"><div class="report-category-fill" style="width:${Math.min(100, Math.max(0, Number(item.share) || 0))}%;--item-color:${safeColor(item.color)}"></div></div></div>`).join('')}</div>`;
  }
  function reportInsights() {
    const allowed = ['no_activity', 'no_income', 'spending_increased', 'spending_decreased', 'biggest_category', 'savings_positive', 'savings_negative', 'overdue_debts', 'budget_exceeded', 'low_runway'];
    const items = (state.report?.insights || []).filter(item => allowed.includes(item.code));
    return `<div class="report-insight-list">${items.slice(0, 7).map(item => {
      const values = { ...(item.values || {}) };
      if ('amount' in values) values.amount = money(values.amount);
      if ('percent' in values) values.percent = percentText(values.percent);
      if ('share' in values) values.share = percentText(values.share);
      if ('days' in values) values.days = Math.max(0, Math.floor(Number(values.days)));
      if (item.code === 'biggest_category') values.name = reportCategoryName(values);
      const severity = ['info', 'success', 'warning', 'danger'].includes(item.severity) ? item.severity : 'info';
      return `<article class="report-insight-card ${severity}">${icon({ info: 'info', success: 'circle-check', warning: 'triangle-alert', danger: 'circle-alert' }[severity])}<div><p>${escape(t(`report_insight_${item.code}`, values))}</p>${item.code === 'budget_exceeded' ? `<button class="btn btn-ghost ghost" data-page="budgets">${escape(t('budgets'))}${icon('arrow-right')}</button>` : item.code === 'overdue_debts' ? `<button class="btn btn-ghost ghost" data-page="debts">${escape(t('debts'))}${icon('arrow-right')}</button>` : ''}</div></article>`;
    }).join('')}</div>${items.some(item => item.code === 'budget_exceeded') ? `<p class="small-text muted">${escape(t('report_budget_note'))}</p>` : ''}`;
  }
  function reportAccountTable() {
    const rows = state.report?.accounts || [];
    if (!rows.length) return empty('no_accounts', 'no_accounts_description', button('add_account', 'new-account'), 'wallet');
    return `<div class="table-wrap"><table class="data-table report-account-table"><thead><tr><th>${escape(t('account'))}</th><th class="text-right">${escape(t('income'))}</th><th class="text-right">${escape(t('expense'))}</th><th class="text-right">${escape(t('net_cashflow'))}</th><th class="text-right">${escape(t('report_current_balance'))}</th></tr></thead><tbody>${rows.map(item => `<tr><td data-label="${escape(t('account'))}"><strong>${escape(item.name)}</strong><p class="muted small-text">${escape(t(item.type))}${item.status === 'archived' ? ` · ${escape(t('archived'))}` : ''}</p></td><td data-label="${escape(t('income'))}" class="text-right amount-income">${escape(money(item.income))}</td><td data-label="${escape(t('expense'))}" class="text-right">${escape(money(item.expense))}</td><td data-label="${escape(t('net_cashflow'))}" class="text-right ${Number(item.net) < 0 ? 'red-text' : 'amount-income'}">${escape(money(item.net))}</td><td data-label="${escape(t('report_current_balance'))}" class="text-right"><strong>${escape(money(item.current_balance))}</strong></td></tr>`).join('')}</tbody></table></div>`;
  }
  function reportLargestTable() {
    const rows = state.report?.largest_expenses || [];
    if (!rows.length) return `<p class="quiet-state">${escape(t('report_no_largest'))}</p>`;
    return `<div class="table-wrap"><table class="data-table"><thead><tr><th>${escape(t('transaction'))}</th><th>${escape(t('account'))}</th><th>${escape(t('date'))}</th><th class="text-right">${escape(t('amount'))}</th></tr></thead><tbody>${rows.map(item => `<tr><td data-label="${escape(t('transaction'))}"><strong>${escape(item.description || item.category_name || t('expense'))}</strong><p class="muted small-text">${escape(item.category_name || t('uncategorized'))}</p></td><td data-label="${escape(t('account'))}">${escape(item.account_name)}</td><td data-label="${escape(t('date'))}">${dateText(item.date)}</td><td data-label="${escape(t('amount'))}" class="text-right amount-cell">${escape(money(item.amount, item.currency))}</td></tr>`).join('')}</tbody></table></div>`;
  }
  function reportObligations() {
    const report = state.report || {}, obligations = report.obligations || {};
    return `<section class="card report-obligations"><div class="card-head"><div><h2>${escape(t('report_due_next30'))}</h2><p>${escape(t('report_as_of', { date: dateText(report.as_of, false, true) }))}</p></div>${icon('calendar-clock')}</div><div class="report-obligation-grid">${[['report_payables_next30', obligations.due_next30_payables, 'amber'], ['report_receivables_next30', obligations.due_next30_receivables, 'emerald'], ['report_overdue_payables', obligations.overdue_payables, 'red'], ['report_overdue_receivables', obligations.overdue_receivables, 'amber']].map(([label, amount, tone]) => `<div class="report-obligation"><span class="muted">${escape(t(label))}</span><strong class="${Number(amount) > 0 ? `${tone}-text` : ''}">${escape(money(amount))}</strong></div>`).join('')}</div><p class="small-text muted">${escape(t('payables'))}: ${escape(money(obligations.payables))} · ${escape(t('receivables'))}: ${escape(money(obligations.receivables))}</p><details class="chart-data-details"><summary>${escape(t('report_upcoming_detail'))}</summary><p class="small-text muted">${escape(t('report_upcoming_note'))}</p><div class="report-upcoming-list">${(report.upcoming || []).length ? report.upcoming.slice(0, 12).map(item => `<div class="upcoming-row"><span class="transaction-icon" style="--item-color:${item.overdue ? '#f87171' : '#06b6d4'}">${icon(item.kind === 'debt' ? 'hand-coins' : 'repeat-2')}</span><div class="upcoming-details"><strong>${escape(item.description || t(item.kind === 'debt' ? 'debt' : 'recurring_entry'))}</strong><span class="small-text ${item.overdue ? 'red-text' : 'muted'}">${dateText(item.date)}${item.overdue ? ` · ${escape(t('overdue'))}` : ''}${item.account_name ? ` · ${escape(item.account_name)}` : ''}</span></div><strong class="${item.type === 'income' ? 'amount-income' : ''}">${item.type === 'income' ? '+' : '−'}${escape(money(item.amount, item.currency))}</strong></div>`).join('') : `<p class="quiet-state">${escape(t('no_upcoming'))}</p>`}</div></details></section>`;
  }
  function renderReports() {
    const report = state.report;
    const exportLink = report && !state.reportLoading && !state.reportError ? `<a class="btn btn-secondary secondary" href="${escape(appUrl(`api.php?${new URLSearchParams({ action: 'report_export', ...reportParams(true) })}`))}" download>${icon('download')}${escape(t('export_csv'))}</a>` : '';
    const head = `${pageHead('reports', 'reports_subtitle', exportLink)}${reportToolbar()}`;
    if (state.reportLoading || !report && !state.reportError) return `${head}<div class="card report-loading" role="status">${icon('loader-circle', 'spin')}<p>${escape(t('report_loading'))}</p></div>`;
    if (state.reportError) return `${head}<section class="card empty-state" role="alert">${icon('circle-alert')}<h2>${escape(t('report_failed'))}</h2><p>${escape(state.reportError)}</p>${button('retry', 'report-retry', 'refresh-cw')}</section>`;
    const liquidity = report.liquidity || {}, period = report.period || {};
    return `${head}<div class="report-period-summary"><h2>${escape(t('report_period_label', { from: dateText(report.from, false, true), to: dateText(report.to, false, true) }))}</h2><p class="muted">${escape(t('report_comparison_label', { from: dateText(report.previous_from, false, true), to: dateText(report.previous_to, false, true), days: Number(period.days) }))}</p></div><div class="grid-4 stats-grid report-metrics">${reportMetric('income', 'report_period_income', 'arrow-down-left', 'emerald')}${reportMetric('expense', 'report_period_expense', 'arrow-up-right', 'violet')}${reportMetric('net', 'report_period_net', 'chart-no-axes-combined', 'cyan')}${reportMetric('savings_rate', 'report_savings_rate', 'piggy-bank', 'amber')}</div>${Number(period.transaction_count) === 0 && !Number(period.fees) ? `<section class="card report-empty">${empty('report_empty_title', 'report_empty_description', button('add_transaction', 'new-transaction'), 'chart-no-axes-combined')}</section>` : ''}<div class="report-grid"><section class="card chart-card report-chart"><div class="card-head"><div><h2>${escape(t('income_vs_expenses'))}</h2><p>${escape(t('report_transactions_count', { count: Number(period.transaction_count) }))}</p></div></div><div class="chart-wrap"><canvas id="report-comparison-chart" role="img" aria-label="${escape(t('income_vs_expenses'))}"></canvas></div>${reportChartDataTable()}</section><section class="card chart-card report-chart"><div class="card-head"><div><h2>${escape(t('report_cumulative_net'))}</h2><p>${escape(t('report_cumulative_note'))}</p></div></div><div class="chart-wrap"><canvas id="report-trend-chart" role="img" aria-label="${escape(t('report_cumulative_net'))}"></canvas></div><p class="small-text muted">${escape(t('report_period_net'))}: ${escape(money(period.net))}</p></section></div><div class="report-grid"><section class="card report-category-card"><div class="card-head"><div><h2>${escape(t('report_spending_categories'))}</h2><p>${escape(t('report_spending_note'))}</p></div>${icon('chart-no-axes-column')}</div>${reportCategories()}</section><section class="card report-insights"><div class="card-head"><div><h2>${escape(t('report_insights'))}</h2><p>${escape(t('report_insights_note'))}</p></div>${icon('lightbulb')}</div>${reportInsights()}</section></div><section class="card report-account-card"><div class="card-head"><div><h2>${escape(t('report_account_performance'))}</h2><p>${escape(t('report_account_note'))}</p></div></div>${reportAccountTable()}</section><div class="report-grid"><section class="card"><div class="card-head"><div><h2>${escape(t('report_largest_expenses'))}</h2><p>${escape(t('report_largest_note'))}</p></div>${icon('arrow-up-right')}</div>${reportLargestTable()}</section>${reportObligations()}</div><section class="card forecast-card"><div class="card-head"><div><span class="eyebrow-chip">${icon('sparkles')}${escape(t('report_liquidity'))}</span><h2>${escape(t('report_as_of', { date: dateText(report.as_of, false, true) }))}</h2></div></div><div class="report-liquidity-grid"><div><span class="stat-label">${escape(t('current_balance'))}</span><strong>${escape(money(liquidity.balance))}</strong></div>${report.account_id ? '' : `<div><span class="stat-label">${escape(t('net_position'))}</span><strong>${escape(money(Number(liquidity.balance || 0) + Number(report.obligations?.receivables || 0) - Number(report.obligations?.payables || 0)))}</strong></div>`}<div><span class="stat-label">${escape(t('report_daily_expense'))}</span><strong>${escape(money(liquidity.average_daily_expense))}</strong><p class="small-text muted">${escape(t('report_daily_expense_note', { days: Number(period.days) }))}</p></div><div><span class="stat-label">${escape(t('report_runway'))}</span><strong>${escape(liquidity.runway_days === null ? t('report_runway_unavailable') : t('report_runway_value', { days: Math.max(0, Math.floor(Number(liquidity.runway_days))) }))}</strong><p class="small-text muted">${escape(t('report_runway_note'))}</p></div></div><p class="report-scope-note muted">${escape(t('report_forecast_scope', { currency: state.currency }))}</p>${forecastCards()}</section>`;
  }
  function renderDataResetSettings() {
    const status = state.data.demo_status || {};
    const sampleCount = Number(status.sample_records || 0), total = Number(status.financial_records || 0);
    return `<section class="card settings-card sample-data-card"><div class="card-head"><div><h2>${escape(t('sample_data_title'))}</h2><p>${escape(t('sample_data_description'))}</p></div>${icon('eraser')}</div><div class="reset-status"><strong>${escape(t('sample_records_count', { count: sampleCount }))}</strong><p class="small-text muted">${escape(t('sample_dependency_note'))}</p></div>${status.legacy_sample_data_possible ? `<p class="reset-legacy-warning">${icon('triangle-alert')}${escape(t('sample_legacy_warning'))}</p>` : !sampleCount ? `<p class="muted">${escape(t('sample_none'))}</p>` : ''}<button class="btn btn-secondary secondary" data-action="clear-sample-data" ${!status.can_remove_samples ? 'disabled' : ''}>${icon('eraser')}${escape(t('sample_data_title'))}</button></section><section class="card settings-card danger-zone"><div class="card-head"><div><h2>${escape(t('reset_workspace_title'))}</h2><p>${escape(t('reset_workspace_description'))}</p></div>${icon('triangle-alert')}</div><div class="reset-status"><strong>${escape(t('financial_records_count', { count: total }))}</strong><p>${escape(t('reset_workspace_scope'))}</p><p class="muted">${escape(t('reset_workspace_preserved'))}</p></div><p class="reset-warning">${escape(t('reset_not_reversible'))}</p><div class="reset-card-actions"><a class="btn btn-secondary secondary backup-link" href="${escape(appUrl('api.php?action=backup'))}" download>${icon('download')}${escape(t('download_backup'))}</a><button class="btn btn-danger danger" data-action="reset-finances" ${!total ? 'disabled' : ''}>${icon('trash-2')}${escape(t('reset_workspace_action'))}</button></div></section>`;
  }
  async function confirmFinancialReset(mode) {
    if (!owner()) return;
    const status = await api('demo_status');
    state.data.demo_status = status;
    const sampleOnly = mode === 'samples';
    const phrase = sampleOnly ? 'REMOVE SAMPLE DATA' : 'RESET FINANCES';
    if (sampleOnly && !status.can_remove_samples) { render(); toast(t('sample_none'), 'warning'); return; }
    const count = Number(sampleOnly ? status.sample_records : status.financial_records);
    const resources = Object.entries(status.by_resource || {}).filter(([, value]) => Number(sampleOnly ? value.sample : value.total) > 0);
    openModal(t(sampleOnly ? 'sample_data_title' : 'reset_workspace_title'), `<form data-form="financial-reset" data-reset-mode="${sampleOnly ? 'samples' : 'all'}" data-confirmation="${phrase}"><div class="form-error" role="alert" hidden></div><div class="reset-dialog-intro"><p><strong>${escape(t(sampleOnly ? 'reset_sample_modal_intro' : 'reset_all_modal_intro'))}</strong></p><p>${escape(t('reset_deleted_count', { count }))}</p>${!sampleOnly ? `<p>${escape(t('reset_workspace_scope'))}</p>` : `<p>${escape(t('sample_dependency_note'))}</p>`}<p class="muted">${escape(t('reset_workspace_preserved'))}</p>${resources.length ? `<dl class="reset-data-counts">${resources.map(([resource, values]) => `<div><dt>${escape(t(resource))}</dt><dd>${Number(sampleOnly ? values.sample : values.total)}</dd></div>`).join('')}</dl>` : ''}</div><p class="reset-warning">${escape(t('reset_not_reversible'))}</p><a class="btn btn-secondary secondary backup-link" href="${escape(appUrl('api.php?action=backup'))}" download>${icon('download')}${escape(t('reset_backup_link'))}</a><div class="form-grid">${field('current_password', 'current_password', 'password', '', { required: true, autocomplete: 'current-password', wide: true, hint: 'reset_password_hint' })}<div class="form-field field-wide"><label for="reset-confirmation">${escape(t('reset_confirmation'))}</label><code class="confirmation-phrase">${phrase}</code><input class="input" id="reset-confirmation" name="confirmation" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" required aria-describedby="reset-confirmation-hint"><span class="field-hint" id="reset-confirmation-hint">${escape(t('reset_confirmation_hint', { phrase }))}</span></div></div><p class="small-text muted">${escape(t('reset_security_note'))}</p><div class="modal-form-actions"><button type="button" class="btn btn-secondary secondary" data-action="close-modal">${escape(t('cancel'))}</button><button type="submit" class="btn btn-danger danger" disabled>${icon(sampleOnly ? 'eraser' : 'trash-2')}${escape(t(sampleOnly ? 'sample_data_title' : 'reset_workspace_action'))}</button></div></form>`);
  }
  function updateResetConfirmation(form) {
    if (!form || form.dataset.submitting) return;
    const submit = $('[type="submit"]', form);
    if (submit) submit.disabled = form.elements.confirmation.value !== form.dataset.confirmation || !form.elements.current_password.value;
  }
  function renderSettings() {
    return `${pageHead('settings', 'settings_subtitle')}<div class="settings-grid"><section class="card settings-card"><div class="card-head"><div><h2>${escape(t('preferences'))}</h2><p>${escape(t('preferences_description'))}</p></div>${icon('sliders-horizontal')}</div><div class="setting-row"><div><strong>${escape(t('language'))}</strong></div><select class="select" data-locale aria-label="${escape(t('language'))}">${languageOptions()}</select></div><div class="setting-row"><strong>${escape(t('appearance'))}</strong><div class="segmented-control"><button class="${state.theme === 'dark' ? 'selected' : ''}" data-action="set-theme" data-theme="dark">${icon('moon')}${escape(t('dark'))}</button><button class="${state.theme === 'light' ? 'selected' : ''}" data-action="set-theme" data-theme="light">${icon('sun')}${escape(t('light'))}</button></div></div></section><section class="card settings-card"><div class="card-head"><div><h2>${escape(t('security'))}</h2><p>${escape(t('security_description'))}</p></div>${icon('shield-check')}</div><form data-form="password"><div class="form-field"><label for="current-password">${escape(t('current_password'))}</label><input class="input" id="current-password" name="current_password" type="password" autocomplete="current-password" required></div><div class="form-grid">${field('new_password', 'new_password', 'password', '', { required: true, minlength: 12, autocomplete: 'new-password' })}${field('confirm_password', 'confirm_password', 'password', '', { required: true, minlength: 12, autocomplete: 'new-password' })}</div><div class="form-actions"><button class="btn btn-primary primary" type="submit">${icon('key-round')}${escape(t('change_password'))}</button></div></form></section>${owner() ? `<section class="card settings-card"><div class="card-head"><div><h2>${escape(t('data_backup'))}</h2><p>${escape(t('backup_description'))}</p></div>${icon('database-backup')}</div><a class="btn btn-secondary secondary" href="${escape(appUrl('api.php?action=backup'))}" download>${icon('download')}${escape(t('download_backup'))}</a></section>${renderDataResetSettings()}<section class="card settings-card team-card"><div class="card-head"><div><h2>${escape(t('team'))}</h2><p>${escape(t('team_description'))}</p></div>${button('add_user', 'new-user', 'user-plus')}</div><div class="user-list">${array('users').map(item => `<div class="user-row"><span class="person-avatar">${escape(item.name?.slice(0, 2).toUpperCase())}</span><div class="user-details"><strong>${escape(item.name)}</strong><span class="muted small-text">${escape(item.email)}</span></div><span class="badge ${item.active ? 'emerald' : 'muted'}">${escape(t(item.role === 'owner' ? 'owner' : item.active ? 'active' : 'inactive'))}</span>${item.role !== 'owner' ? `<button class="icon-btn" data-action="edit" data-resource="users" data-id="${item.id}" aria-label="${escape(t('edit'))}">${icon('pencil')}</button>` : ''}</div>`).join('')}</div></section><section class="card settings-card audit-card"><div class="card-head"><div><h2>${escape(t('audit_log'))}</h2><p>${escape(t('audit_description'))}</p></div>${icon('list-checks')}</div><div class="table-wrap"><table class="data-table"><thead><tr><th>${escape(t('event'))}</th><th>${escape(t('user'))}</th><th>${escape(t('date'))}</th></tr></thead><tbody>${array('audit').slice(0, 30).map(item => `<tr><td data-label="${escape(t('event'))}"><strong>${escape(item.action || item.event || '')}</strong><p class="muted small-text">${escape(item.entity || item.resource || '')}${item.entity_id ? ` #${Number(item.entity_id)}` : ''}</p></td><td data-label="${escape(t('user'))}">${escape(item.user_name || item.name || '—')}</td><td data-label="${escape(t('date'))}" class="muted">${dateText(item.created_at || item.date, true)}</td></tr>`).join('') || `<tr><td colspan="3" class="muted">${escape(t('no_activity'))}</td></tr>`}</tbody></table></div></section>` : ''}</div>`;
  }
  function field(name, label, type = 'text', value = '', options = {}) {
    const id = `field-${name}`;
    const attributes = Object.entries(options).filter(([key]) => !['hint', 'wide', 'step'].includes(key)).map(([key, val]) => val === false ? '' : val === true ? escape(key) : `${escape(key)}="${escape(val)}"`).join(' ');
    return `<div class="form-field ${options.wide ? 'field-wide' : ''}"><label for="${id}">${escape(t(label))}${options.required ? '<span class="required-marker">*</span>' : ''}</label><input class="input" id="${id}" name="${name}" type="${type}" value="${escape(value)}" ${type === 'number' ? `step="${options.step || '0.01'}"` : ''} ${attributes}>${options.hint ? `<span class="field-hint">${escape(t(options.hint))}</span>` : ''}</div>`;
  }
  function selectField(name, label, options, value, { required = false, wide = false, hint = '' } = {}) {
    return `<div class="form-field ${wide ? 'field-wide' : ''}"><label for="field-${name}">${escape(t(label))}${required ? '<span class="required-marker">*</span>' : ''}</label><select class="select" id="field-${name}" name="${name}" ${required ? 'required' : ''}>${options.map(option => {
      const item = typeof option === 'string' ? { value: option, label: t(option) } : option;
      return `<option value="${escape(item.value)}" ${String(item.value) === String(value ?? '') ? 'selected' : ''}>${escape(item.label)}</option>`;
    }).join('')}</select>${hint ? `<span class="field-hint">${escape(t(hint))}</span>` : ''}</div>`;
  }
  function textArea(name, label, value = '') { return `<div class="form-field field-wide"><label for="field-${name}">${escape(t(label))}</label><textarea class="textarea" id="field-${name}" name="${name}" rows="3" maxlength="2000">${escape(value)}</textarea></div>`; }
  const currencyOptions = () => ['USD', 'UZS', 'EUR', 'RUB'].map(value => ({ value, label: value }));
  const accountOptions = (optional = false, currency = null, includeArchived = false) => [ ...(optional ? [{ value: '', label: t('no_account_movement') }] : []), ...array('accounts').filter(account => (includeArchived || account.status !== 'archived') && (!currency || account.currency === currency)).map(account => ({ value: account.id, label: `${account.name} · ${account.currency}` })) ];
  const categoryOptions = (type = null, optional = true, except = null) => [ ...(optional ? [{ value: '', label: t('uncategorized') }] : []), ...array('categories').filter(category => (!type || category.type === type) && category.id !== except).map(category => ({ value: category.id, label: `${category.parent_id ? '↳ ' : ''}${category.name}` })) ];
  function resourceForm(resource, item = {}) {
    const editing = !!item.id;
    const amount = (name = 'amount', value = item.amount || '', label = 'amount') => field(name, label, 'number', value, { required: true, min: '0.01', max: '9999999999999' });
    const date = (name = 'date', value = item.date || localDateTime(), label = 'date') => field(name, label, name === 'date' ? 'datetime-local' : 'date', String(value).replace(' ', 'T').slice(0, name === 'date' ? 16 : 10), { required: name === 'date' });
    let contents = '';
    if (resource === 'accounts') {
      contents = `${field('name', 'name', 'text', item.name || '', { required: true, maxlength: 100 })}${selectField('type', 'type', ['bank', 'card', 'cash', 'savings', 'digital'], item.type || 'bank', { required: true })}${selectField('currency', 'currency', currencyOptions(), item.currency || state.currency, { required: true })}${field('initial_balance', 'initial_balance', 'number', item.initial_balance ?? 0, { required: true })}${selectField('status', 'status', ['active', 'archived'], item.status || 'active')}${field('color', 'color', 'color', item.color || '#10b981')}${selectField('icon', 'icon', ['landmark', 'credit-card', 'wallet', 'vault', 'smartphone', 'banknote', 'piggy-bank', 'bitcoin'].map(value => ({ value, label: value.replaceAll('-', ' ') })), item.icon || 'landmark')}${field('target_amount', 'target_amount', 'number', item.target_amount || '', { min: 0 })}${field('details', 'details', 'text', item.details || '', { wide: true, maxlength: 500 })}`;
    } else if (resource === 'transactions' || resource === 'recurring') {
      contents = `${selectField('type', 'type', ['expense', 'income'], item.type || 'expense', { required: true })}${amount()}${selectField('account_id', 'account', accountOptions(false, null, editing), item.account_id, { required: true })}${selectField('category_id', 'category', categoryOptions(item.type || 'expense'), item.category_id)}${resource === 'recurring' ? `${selectField('frequency', 'frequency', ['daily', 'weekly', 'monthly', 'annual'], item.frequency || 'monthly')}${date('next_date', item.next_date || localDate(), 'next_date')}${selectField('enabled', 'status', [{ value: '1', label: t('enabled') }, { value: '0', label: t('paused') }], item.enabled === 0 ? '0' : '1')}` : `${date()}${field('tags', 'tags', 'text', Array.isArray(item.tags) ? item.tags.join(', ') : item.tags || '', { hint: 'tags_hint', maxlength: 500 })}${field('receipt', 'receipt', 'text', item.receipt || '', { hint: 'receipt_hint', maxlength: 1000, wide: true })}`}${textArea('description', 'description', item.description)}<p class="form-note field-wide">${icon('info')}${escape(t('transaction_note'))}</p>`;
    } else if (resource === 'transfers') {
      contents = `${selectField('from_account_id', 'from_account', accountOptions(false, null, editing), item.from_account_id, { required: true })}${selectField('to_account_id', 'to_account', accountOptions(false, null, editing), item.to_account_id || array('accounts')[1]?.id, { required: true })}${amount()}${field('fee', 'transfer_fee', 'number', item.fee || 0, { min: 0 })}${field('received_amount', 'received_amount', 'number', item.received_amount || item.amount || '', { min: '0.01', hint: 'received_amount_hint' })}${date()}${textArea('description', 'description', item.description)}<p class="form-note field-wide">${icon('info')}<span data-transfer-note>${escape(t('transfer_note'))}</span></p>`;
    } else if (resource === 'budgets') {
      contents = `${selectField('category_id', 'category', categoryOptions('expense', false), item.category_id, { required: true })}${amount()}${selectField('currency', 'currency', currencyOptions(), item.currency || state.currency)}${field('month', 'month', 'month', item.month || localDate().slice(0, 7), { required: true })}`;
    } else if (resource === 'debts') {
      contents = `${selectField('direction', 'direction', ['borrowing', 'lending'], item.direction || 'borrowing')}${field('counterparty', 'counterparty', 'text', item.counterparty || '', { required: true, maxlength: 100 })}${field('contact', 'contact', 'text', item.contact || '', { maxlength: 200 })}${amount()}${selectField('currency', 'currency', currencyOptions(), item.currency || state.currency)}${selectField('account_id', 'account', accountOptions(true, item.currency || state.currency, editing), item.account_id, { hint: 'payment_account_hint' })}${date()}${date('due_date', item.due_date || '', 'due_date')}${textArea('description', 'description', item.description)}`;
    } else if (resource === 'categories') {
      contents = `${field('name', 'name', 'text', item.name || '', { required: true, maxlength: 100 })}${selectField('type', 'type', ['expense', 'income'], item.type || 'expense')}${selectField('parent_id', 'parent_category', [{ value: '', label: t('no_parent') }, ...categoryOptions(item.type || 'expense', false, item.id)], item.parent_id)}${selectField('icon', 'icon', ['shopping-bag', 'utensils', 'car', 'home', 'heart-pulse', 'briefcase-business', 'graduation-cap', 'gift', 'plane', 'coffee', 'banknote', 'shapes'].map(value => ({ value, label: value.replaceAll('-', ' ') })), item.icon || 'shapes')}${field('color', 'color', 'color', item.color || '#10b981')}`;
    } else if (resource === 'tags') {
      contents = `${field('name', 'name', 'text', item.name || '', { required: true, maxlength: 60 })}${field('color', 'color', 'color', item.color || '#06b6d4')}`;
    } else if (resource === 'users') {
      contents = `${field('name', 'full_name', 'text', item.name || '', { required: true, maxlength: 100 })}${field('email', 'email', 'email', item.email || '', { required: true, autocomplete: 'off' })}${field('password', 'password', 'password', '', { required: !editing, minlength: 12, autocomplete: 'new-password', hint: editing ? 'user_password_hint' : 'password_hint' })}${selectField('active', 'status', [{ value: '1', label: t('active') }, { value: '0', label: t('inactive') }], item.active === 0 ? '0' : '1')}`;
    }
    const titles = { accounts: 'add_account', transactions: 'add_transaction', transfers: 'add_transfer', budgets: 'add_budget', debts: 'add_debt', categories: 'add_category', tags: 'add_tag', recurring: 'add_recurring', users: 'add_user' };
    openModal(t(editing ? 'edit' : titles[resource]), `<form data-form="resource" data-resource="${resource}" ${editing ? `data-id="${item.id}"` : ''}><div class="form-error" role="alert" hidden></div><div class="form-grid">${contents}</div><div class="modal-form-actions"><button type="button" class="btn btn-secondary secondary" data-action="close-modal">${escape(t('cancel'))}</button><button type="submit" class="btn btn-primary primary">${icon(editing ? 'check' : 'plus')}${escape(t(editing ? 'save' : 'create'))}</button></div></form>`, '', true);
    if (resource === 'transfers') updateTransferForm($('#modal-root form'));
  }
  function updateTransferForm(form) {
    if (!form) return;
    const from = find('accounts', form.elements.from_account_id?.value), to = find('accounts', form.elements.to_account_id?.value);
    const received = form.elements.received_amount;
    if (!received) return;
    const crossCurrency = from && to && from.currency !== to.currency;
    received.required = !!crossCurrency;
    received.closest('.form-field').hidden = !crossCurrency;
    if (!crossCurrency) received.value = form.elements.amount.value;
    const note = $('[data-transfer-note]', form);
    if (note) note.textContent = crossCurrency ? t('cross_currency_note', { from: from.currency, to: to.currency }) : t('transfer_note');
  }
  function paymentForm(debtId, payment = {}) {
    const debt = find('debts', debtId); if (!debt) return;
    openModal(t('record_payment'), `<form data-form="repayment" data-debt-id="${debtId}" ${payment.id ? `data-id="${payment.id}"` : ''}><div class="form-error" role="alert" hidden></div><div class="repayment-summary"><span class="person-avatar">${escape(debt.counterparty.slice(0, 2).toUpperCase())}</span><div><strong>${escape(debt.counterparty)}</strong><p class="muted">${escape(t('remaining'))}: ${escape(money(debt.remaining ?? debt.remaining_balance ?? debt.amount, debt.currency))}</p></div></div><div class="form-grid">${field('amount', 'payment_amount', 'number', payment.amount || '', { required: true, min: '0.01' })}${field('date', 'date', 'datetime-local', String(payment.date || localDateTime()).replace(' ', 'T').slice(0, 16), { required: true })}${selectField('account_id', 'account', accountOptions(false, debt.currency, !!payment.id), payment.account_id, { wide: true, required: true, hint: 'repayment_account_hint' })}${textArea('description', 'description', payment.description)}</div><div class="modal-form-actions"><button type="button" class="btn btn-secondary secondary" data-action="close-modal">${escape(t('cancel'))}</button><button class="btn btn-primary primary" type="submit">${icon('check')}${escape(t('save'))}</button></div></form>`);
  }
  function paymentHistory(id) {
    const debt = find('debts', id); if (!debt) return;
    const payments = debt.payments || debt.repayments || [];
    openModal(`${t('repayments')} · ${debt.counterparty}`, payments.length ? `<div class="repayments-list">${payments.map(payment => `<div class="repayment-row"><span class="transaction-icon" style="--item-color:#10b981">${icon('check')}</span><div><strong>${escape(money(payment.amount, debt.currency))}</strong><p class="muted small-text">${dateText(payment.date)} · ${escape(payment.description || '')}</p></div><div class="row-actions"><button class="icon-btn" data-action="edit-repayment" data-id="${payment.id}" data-debt-id="${id}" aria-label="${escape(t('edit'))}">${icon('pencil')}</button><button class="icon-btn danger-text" data-action="delete" data-resource="repayments" data-id="${payment.id}" aria-label="${escape(t('delete'))}">${icon('trash-2')}</button></div></div>`).join('')}</div>` : empty('no_activity', 'no_activity_description', button('record_payment', 'repayment', 'plus', 'primary', `data-id="${id}"`), 'history'));
  }
  function accountHistory(id) {
    const account = find('accounts', id); if (!account) return;
    const transactions = array('transactions').filter(item => Number(item.account_id) === Number(id));
    const transfers = array('transfers').filter(item => Number(item.from_account_id) === Number(id) || Number(item.to_account_id) === Number(id));
    const debtMovements = [];
    array('debts').forEach(debt => {
      if (Number(debt.account_id) === Number(id)) debtMovements.push({ description: `${t(debt.direction)} · ${debt.counterparty}`, amount: debt.amount, currency: debt.currency, date: debt.date, type: debt.direction === 'borrowing' ? 'income' : 'expense' });
      (debt.payments || []).filter(payment => Number(payment.account_id) === Number(id)).forEach(payment => debtMovements.push({ description: `${t('record_payment')} · ${debt.counterparty}`, amount: payment.amount, currency: debt.currency, date: payment.date, type: debt.direction === 'lending' ? 'income' : 'expense' }));
    });
    openModal(`${account.name} · ${t('account_history')}`, `<div class="history-balance"><span class="stat-label">${escape(t('current_balance'))}</span><strong>${escape(money(account.current_balance ?? account.balance, account.currency))}</strong></div><h3 class="history-heading">${escape(t('transactions'))}</h3>${transactions.length ? transactionTable(transactions, true) : `<p class="muted">${escape(t('no_history'))}</p>`}${debtMovements.length ? `<h3 class="history-heading">${escape(t('debts'))}</h3>${transactionTable(debtMovements.sort((a, b) => String(b.date).localeCompare(String(a.date))), true)}` : ''}${transfers.length ? `<h3 class="history-heading">${escape(t('transfers'))}</h3><div class="history-transfers">${transfers.map(item => `<div class="upcoming-row">${icon('arrow-left-right')}<div><strong>${escape(item.description || t('transfer'))}</strong><p class="muted small-text">${escape(find('accounts', item.from_account_id)?.name)} → ${escape(find('accounts', item.to_account_id)?.name)} · ${dateText(item.date)}</p></div><strong>${Number(item.from_account_id) === Number(id) ? '−' : '+'}${escape(money(Number(item.from_account_id) === Number(id) ? Number(item.amount) + Number(item.fee || 0) : item.received_amount ?? item.amount, account.currency))}</strong></div>`).join('')}</div>` : ''}`, '', true);
  }
  function confirmDelete(resource, id) {
    openModal(t(resource === 'repayments' ? 'confirm_delete_payment' : 'delete_title'), `<div class="delete-warning">${icon('triangle-alert')}<p>${escape(t('delete_description'))}</p></div><div class="form-error" role="alert" hidden></div>`, `<button class="btn btn-secondary secondary" data-action="close-modal">${escape(t('cancel'))}</button><button class="btn btn-danger danger" data-action="confirm-delete" data-resource="${resource}" data-id="${id}">${icon('trash-2')}${escape(t('delete'))}</button>`);
  }
  function languageOptions() { return [{ value: 'en', label: 'English' }, { value: 'uz', label: "O‘zbekcha" }, { value: 'ru', label: 'Русский' }].map(item => `<option value="${item.value}" ${state.locale === item.value ? 'selected' : ''}>${item.label}</option>`).join(''); }
  async function showAuth(setup = false) {
    state.user = null; state.report = null; state.reportFilters = null; state.reportRequest++; state.refreshRevision++; $('#main-content').inert = false; destroyCharts(); closeModal();
    $('#app-shell').hidden = true; $('#auth-root').hidden = false;
    $('#auth-root').innerHTML = `<div class="auth-layout"><section class="auth-brand-panel"><a href="${escape(appBase.href)}" class="auth-logo"><span class="brand-mark">${icon('activity')}</span><span>vela<span class="brand-dot">.</span></span></a><div class="auth-brand-copy"><span class="eyebrow-chip">${icon('sparkles')}${escape(t('app_tagline'))}</span><h1>${escape(t('secure_workspace'))}</h1><p>${escape(t('secure_description'))}</p></div><div class="auth-orbit"><div class="auth-visual-card"><div class="flex-between"><span class="brand-mini">vela.</span>${icon('nfc')}</div><div class="auth-card-number">•••• &nbsp; •••• &nbsp; •••• &nbsp; 2084</div><div class="flex-between"><span>${escape(t('your_accounts'))}</span>${icon('wallet')}</div></div><div class="auth-mini-card">${icon('trending-up')}<span>${escape(t('financial_outlook'))}</span>${icon('sparkles')}</div></div><div class="auth-features">${[['shield-check', 'privacy_first', 'privacy_description'], ['globe-2', 'currency_aware', 'currency_description'], ['chart-no-axes-combined', 'clarity_daily', 'clarity_description']].map(([symbol, title, description]) => `<div class="auth-feature">${icon(symbol)}<div><strong>${escape(t(title))}</strong><span>${escape(t(description))}</span></div></div>`).join('')}</div><div class="auth-footer">© ${new Date().getFullYear()} Vela</div></section><section class="auth-form-panel"><div class="auth-controls"><select class="select" data-auth-locale aria-label="${escape(t('language'))}">${languageOptions()}</select><button class="icon-btn" data-action="toggle-theme" aria-label="${escape(t('appearance'))}">${icon(state.theme === 'dark' ? 'sun' : 'moon')}</button></div><div class="auth-form"><div class="auth-form-icon">${icon(setup ? 'sparkles' : 'fingerprint')}</div><span class="page-eyebrow">${escape(t('app_name'))} · ${escape(t('workspace'))}</span><h2 class="auth-title">${escape(t(setup ? 'create_workspace' : 'welcome_back'))}<span class="accent-dot">.</span></h2><p class="auth-subtitle">${escape(t(setup ? 'setup_intro' : 'login_intro'))}</p><form data-form="${setup ? 'setup' : 'login'}"><div class="form-error" role="alert" hidden></div>${setup ? field('name', 'owner_name', 'text', '', { required: true, autocomplete: 'name', maxlength: 100 }) : ''}${field('email', 'email', 'email', '', { required: true, autocomplete: 'username' })}${field('password', 'password', 'password', '', { required: true, ...(setup ? { minlength: 12, hint: 'password_hint' } : {}), autocomplete: setup ? 'new-password' : 'current-password' })}${setup ? `<label class="demo-checkbox"><input type="checkbox" name="demo" checked><span class="checkbox-control"></span><span><strong>${escape(t('demo_data'))}</strong><small>${escape(t('demo_description'))}</small></span></label>` : ''}<button class="btn btn-primary primary auth-submit" type="submit">${escape(t(setup ? 'create_account' : 'sign_in'))}${icon('arrow-right')}</button></form><div class="auth-security">${icon('lock-keyhole')}<span>${escape(t('remember_secure'))}</span></div></div></section></div>`;
    $('#auth-root').dataset.setup = setup ? '1' : '0'; icons();
  }
  function updateShell() {
    $('#app-shell').hidden = false; $('#auth-root').hidden = true;
    if ($('#user-name')) $('#user-name').textContent = state.user.name;
    if ($('#user-role')) $('#user-role').textContent = t(state.user.role === 'owner' ? 'owner' : 'assistant');
    if ($('#user-avatar')) $('#user-avatar').textContent = state.user.name.slice(0, 2).toUpperCase();
    if ($('#language-select')) { $('#language-select').innerHTML = languageOptions(); $('#language-select').setAttribute('aria-label', t('language')); }
    if ($('#search-input')) { $('#search-input').placeholder = t('search_placeholder'); $('#search-input').setAttribute('aria-label', t('search')); }
    const allowed = owner() ? ['dashboard', 'accounts', 'transactions', 'transfers', 'budgets', 'debts', 'reports', 'categories', 'recurring', 'settings'] : ['transactions', 'categories', 'recurring', 'settings'];
    $$('[data-page]').forEach(element => {
      const page = element.dataset.page; if (element.closest('#main-content') || element.closest('#modal-root')) return;
      element.hidden = !allowed.includes(page);
      element.classList.toggle('active', page === state.page); element.setAttribute('aria-current', page === state.page ? 'page' : 'false');
      const label = element.querySelector('[data-i18n]') || element.querySelector('.nav-label') || element.querySelector('span');
      if (label) label.textContent = t(page);
    });
    $$('[data-i18n]').forEach(element => { element.textContent = t(element.dataset.i18n); });
    if ($('#page-title')) $('#page-title').textContent = t(state.page);
    if ($('#page-subtitle')) $('#page-subtitle').textContent = t('app_tagline');
    if ($('#quick-add')) $('#quick-add').innerHTML = `${icon('plus')}<span>${escape(t('quick_add'))}</span>`;
    if ($('#logout-button')) $('#logout-button').setAttribute('aria-label', t('sign_out'));
    if ($('#mobile-more')) $('#mobile-more').setAttribute('aria-label', t('more_pages'));
    [['#sidebar','main_navigation'],['#sidebar-nav','workspace_pages'],['#mobile-nav','mobile_navigation'],['#sidebar-toggle','toggle_sidebar']].forEach(([selector,key])=> { const element=$(selector); if(element) {element.setAttribute('aria-label',t(key)); if(element.hasAttribute('title')) element.title=t(key);} });
    const skip=$('.skip-link'); if(skip) skip.textContent=t('skip_content');
    if($('#logout-button')) $('#logout-button').title=t('sign_out');
    if($('#theme-toggle')) $('#theme-toggle').title=t('appearance');
    setTheme(state.theme);
  }
  function render() {
    if (!state.user) return;
    destroyCharts();
    if (!owner() && !['transactions', 'categories', 'recurring', 'settings'].includes(state.page)) state.page = 'transactions';
    const views = { dashboard: renderDashboard, accounts: renderAccounts, transactions: renderTransactions, transfers: renderTransfers, budgets: renderBudgets, debts: renderDebts, reports: renderReports, categories: renderCategories, recurring: renderRecurring, settings: renderSettings };
    updateShell(); $('#main-content').innerHTML = (views[state.page] || renderDashboard)(); icons();
    if (['dashboard', 'reports'].includes(state.page)) state.chartFrame = requestAnimationFrame(() => { state.chartFrame = null; renderCharts(); });
  }
  async function refresh(loadAnalytics = true) {
    const revision = ++state.refreshRevision;
    const content = $('#main-content');
    content.inert = true; content.setAttribute('aria-busy', 'true');
    try {
      const data = await api('bootstrap');
      const user = data.user || state.user;
      const analytics = user?.role === 'owner' && loadAnalytics ? await api('analytics', 'GET', undefined, { currency: state.currency }) : data.analytics;
      if (revision !== state.refreshRevision) return;
      state.data = data; state.user = user; state.analytics = analytics;
      if (state.page === 'reports' && owner()) await loadReport(); else render();
    } finally {
      if (revision === state.refreshRevision) { content.inert = false; content.setAttribute('aria-busy', 'false'); }
    }
  }
  async function navigate(page) {
    state.page = page; state.search = ''; state.from = ''; state.to = '';
    if ($('#search-input')) $('#search-input').value = '';
    document.body.classList.remove('sidebar-open'); closeModal();
    history.replaceState(null, '', `#${page}`); render(); window.scrollTo({ top: 0, behavior: 'smooth' });
    if (page === 'reports' && owner()) await loadReport();
  }
  async function changeLocale(locale) {
    await api('locale', 'POST', { locale }); await loadDictionary(locale);
    if (state.user) render(); else showAuth($('#auth-root').dataset.setup === '1');
    icons();
  }
  function renderReportCharts() {
    if (!state.report || state.reportLoading || state.reportError) return;
    if (!window.Chart) {
      $$('.report-chart .chart-wrap').forEach(element => { element.innerHTML = noChart(); });
      return;
    }
    const dark = state.theme === 'dark';
    const text = dark ? '#a2adbf' : '#58657a';
    Chart.defaults.font.family = 'Inter, ui-sans-serif, system-ui, sans-serif';
    Chart.defaults.font.size = 14;
    const rows = reportRows();
    const common = {
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      interaction: { intersect: false, mode: 'index' },
      plugins: {
        legend: { position: 'top', labels: { color: text, font: { size: 14 }, usePointStyle: true, boxWidth: 9, padding: 18 } },
        tooltip: { titleFont: { size: 14 }, bodyFont: { size: 14 }, callbacks: { label: context => `${context.dataset.label}: ${money(context.parsed.y)}` } },
      },
      scales: {
        x: { grid: { display: false }, ticks: { color: text, font: { size: 13 }, maxTicksLimit: 6, maxRotation: 0 } },
        y: { beginAtZero: true, grid: { color: dark ? 'rgba(148,163,184,.12)' : 'rgba(15,23,42,.08)' }, ticks: { color: text, font: { size: 13 }, callback: value => compactMoney(value) } },
      },
    };
    const labels = rows.map(row => row.date ? dateText(row.date) : row.month);
    const comparison = $('#report-comparison-chart');
    if (comparison) state.charts.push(new Chart(comparison, {
      type: 'bar',
      data: { labels, datasets: [
        { label: t('income'), data: rows.map(row => Number(row.income)), backgroundColor: '#10b981', borderRadius: 4, maxBarThickness: 26 },
        { label: t('expense'), data: rows.map(row => Number(row.expense)), backgroundColor: '#a78bfa', borderRadius: 4, maxBarThickness: 26 },
      ] }, options: common,
    }));
    let running = 0;
    const cumulative = rows.map(row => running = Math.round((running + Number(row.net)) * 100) / 100);
    const trend = $('#report-trend-chart');
    if (trend) state.charts.push(new Chart(trend, {
      type: 'line', data: { labels, datasets: [{ label: t('report_cumulative_net'), data: cumulative, borderColor: '#06b6d4', backgroundColor: 'rgba(6,182,212,.10)', fill: true, tension: .2, pointRadius: rows.length > 40 ? 0 : 2, pointHoverRadius: 5 }] }, options: common,
    }));
  }
  function renderCharts() {
    if (state.page === 'reports') { renderReportCharts(); return; }
    const analytics = state.analytics || {};
    const isDark = state.theme === 'dark'; const muted = isDark ? '#a2adbf' : '#58657a'; const grid = isDark ? 'rgba(148,163,184,.08)' : 'rgba(15,23,42,.07)';
    const colors = ['#10b981', '#06b6d4', '#a78bfa', '#f59e0b', '#f472b6'];
    const distribution = (analytics.distribution || []).filter(item => Number(item.balance) > 0);
    const legend = $('#distribution-legend');
    const total = distribution.reduce((sum, item) => sum + Number(item.balance), 0);
    if (legend) legend.innerHTML = distribution.map((item, index) => `<div class="distribution-row"><span><i class="legend-dot" style="background:${colors[index % colors.length]}"></i>${escape(t(item.type))}</span><span class="distribution-value">${escape(money(item.balance))}<small>${Math.round(Number(item.balance) / (total || 1) * 100)}%</small></span></div>`).join('') || noChart();
    if (!window.Chart) {
      $$('.chart-wrap').forEach(element => { if (element.querySelector('canvas')) element.innerHTML = noChart(); }); return;
    }
    Chart.defaults.font.family = 'Inter, ui-sans-serif, system-ui, sans-serif'; Chart.defaults.color = muted; Chart.defaults.font.size = 14;
    const common = { responsive: true, maintainAspectRatio: false, animation: { duration: 500 }, plugins: { legend: { display: false }, tooltip: { backgroundColor: isDark ? '#1c2637' : '#ffffff', titleColor: isDark ? '#f4f7fb' : '#111827', bodyColor: muted, padding: 12, borderColor: grid, borderWidth: 1, displayColors: false, callbacks: { label: context => `${context.dataset.label || ''}: ${money(context.parsed.y ?? context.parsed)}` } } } };
    const axes = { x: { grid: { display: false }, border: { display: false }, ticks: { maxTicksLimit: 7, font: { size: 13 }, maxRotation: 0 } }, y: { position: 'right', grid: { color: grid, drawTicks: false }, border: { display: false }, ticks: { count: 5, padding: 12, font: { size: 13 }, callback: value => compactMoney(value) } } };
    const cashflow = $('#cashflow-chart');
    if (cashflow) {
      const rows = analytics.cashflow || [];
      if (!rows.length) cashflow.parentElement.innerHTML = noChart();
      else {
        const gradient = cashflow.getContext('2d').createLinearGradient(0, 0, 0, 270); gradient.addColorStop(0, 'rgba(16,185,129,.24)'); gradient.addColorStop(1, 'rgba(16,185,129,0)');
        state.charts.push(new Chart(cashflow, { type: 'line', data: { labels: rows.map(row => dateText(row.date)), datasets: [{ label: t('balance'), data: rows.map(row => Number(row.balance)), borderColor: '#10b981', backgroundColor: gradient, fill: true, borderWidth: 2.5, tension: .4, pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: '#10b981' }] }, options: { ...common, interaction: { intersect: false, mode: 'index' }, scales: axes } }));
      }
    }
    const donut = $('#distribution-chart');
    if (donut) {
      if (!distribution.length) { donut.parentElement.innerHTML = noChart(); const center = $('.donut-center'); if (center) center.hidden = true; }
      else state.charts.push(new Chart(donut, { type: 'doughnut', data: { labels: distribution.map(item => t(item.type)), datasets: [{ data: distribution.map(item => Number(item.balance)), backgroundColor: colors, borderWidth: 0, hoverOffset: 5, spacing: 4, borderRadius: 5 }] }, options: { ...common, cutout: '79%', plugins: { ...common.plugins, tooltip: { ...common.plugins.tooltip, callbacks: { label: context => `${context.label}: ${money(context.parsed)}` } } } } }));
    }
    const monthly = $('#monthly-chart');
    if (monthly) {
      const rows = analytics.monthly || [];
      if (!rows.length) monthly.parentElement.innerHTML = noChart();
      else state.charts.push(new Chart(monthly, { type: 'bar', data: { labels: rows.map(row => { const parsed = new Date(`${row.month}-01`); return Number.isNaN(parsed.getTime()) ? row.month : parsed.toLocaleDateString({ en: 'en-US', uz: 'uz-UZ', ru: 'ru-RU' }[state.locale], { month: 'short' }); }), datasets: [{ label: t('income'), data: rows.map(row => Number(row.income)), backgroundColor: '#10b981', borderRadius: 5, maxBarThickness: 26 }, { label: t('expense'), data: rows.map(row => Number(row.expense)), backgroundColor: '#64748b', borderRadius: 5, maxBarThickness: 26 }] }, options: { ...common, scales: axes, plugins: { ...common.plugins, legend: { display: true, position: 'top', align: 'end', labels: { color: muted, usePointStyle: true, pointStyle: 'circle', boxWidth: 6, boxHeight: 6, padding: 20 } } } } }));
    }
  }
  function compactMoney(value) {
    const number = Number(value); const absolute = Math.abs(number);
    return absolute >= 1e9 ? `${(number / 1e9).toFixed(1)}B` : absolute >= 1e6 ? `${(number / 1e6).toFixed(1)}M` : absolute >= 1000 ? `${(number / 1000).toFixed(0)}k` : String(number);
  }
  function formError(form, error) {
    const element = $('.form-error', form) || $('#modal-root .form-error');
    if (element?.isConnected) { element.textContent = error.message || t('error_generic'); element.hidden = false; element.scrollIntoView({ block: 'nearest' }); }
    else toast(error.message || t('error_generic'), 'error');
  }
  async function submitForm(form) {
    const values = Object.fromEntries(new FormData(form).entries());
    const type = form.dataset.form;
    const submit = $('[type="submit"]', form);
    const original = submit?.innerHTML;
    if (submit) { submit.disabled = true; submit.innerHTML = `${icon('loader-circle', 'spin')}<span>${escape(t('loading'))}</span>`; icons(); }
    const errorElement = $('.form-error', form); if (errorElement) errorElement.hidden = true;
    try {
      if (type === 'setup' || type === 'login') {
        if (type === 'setup') values.demo = !!form.elements.demo.checked;
        const session = await api(type, 'POST', values);
        state.csrf = session.csrf || state.csrf; state.user = session.user;
        if (!state.user) { const newSession = await api('session'); state.csrf = newSession.csrf; state.user = newSession.user; }
        if (!state.user) throw new Error(t('error_generic'));
        await loadDictionary(session.locale || state.locale);
        state.page = owner() ? 'dashboard' : 'transactions';
        await refresh();
      } else if (type === 'report-filters') {
        Object.assign(reportFilters(), { from: values.from, to: values.to, preset: 'custom' });
        await loadReport();
      } else if (type === 'financial-reset') {
        if (!owner() || values.confirmation !== form.dataset.confirmation) throw new Error(t('reset_confirmation_invalid'));
        form.dataset.submitting = '1';
        const sampleOnly = form.dataset.resetMode === 'samples';
        const result = await api(sampleOnly ? 'clear_sample_data' : 'reset_finances', 'POST', { current_password: values.current_password, confirmation: values.confirmation });
        closeModal(); state.search = ''; state.from = ''; state.to = ''; state.report = null; state.reportFilters = null; state.reportRequest++;
        if ($('#search-input')) $('#search-input').value = '';
        await refresh();
        toast(t(sampleOnly ? 'sample_removed' : 'reset_workspace_done', { count: Number(result.deleted_records) }));
        if (Number(result.preserved_records)) toast(t('sample_preserved', { count: Number(result.preserved_records) }), 'warning');
      } else if (type === 'password') {
        if (values.new_password !== values.confirm_password) throw new Error(t('password_mismatch'));
        const response = await api('password', 'POST', { current_password: values.current_password, new_password: values.new_password });
        if (response.csrf) state.csrf = response.csrf;
        form.reset(); toast(t('password_changed'));
      } else if (type === 'resource') {
        const resource = form.dataset.resource; const id = form.dataset.id;
        for (const key of ['account_id', 'category_id', 'parent_id']) { if (key in values) values[key] = values[key] ? Number(values[key]) : null; }
        for (const key of ['amount', 'initial_balance', 'target_amount', 'fee', 'received_amount']) {
          if (key in values) values[key] = values[key] === '' ? null : Number(values[key]);
        }
        if (resource === 'transactions' || resource === 'recurring') values.currency = accountCurrency(values.account_id);
        if (resource === 'transactions') values.tags = values.tags.split(',').map(tag => tag.trim()).filter(Boolean);
        if (resource === 'users') { values.active = Number(values.active); if (!values.password) delete values.password; }
        if (resource === 'recurring') values.enabled = Number(values.enabled);
        if (resource === 'transfers') {
          values.from_account_id = Number(values.from_account_id); values.to_account_id = Number(values.to_account_id);
          if (values.from_account_id === values.to_account_id) throw new Error(t('different_accounts_required'));
          if (accountCurrency(values.from_account_id) === accountCurrency(values.to_account_id)) values.received_amount = values.amount;
        }
        if (id) values.id = Number(id);
        await api(resource, id ? 'PUT' : 'POST', values); closeModal(); await refresh(); toast(t(id ? 'saved' : 'created'));
      } else if (type === 'repayment') {
        values.amount = Number(values.amount); values.account_id = values.account_id ? Number(values.account_id) : null;
        values.debt_id = Number(form.dataset.debtId);
        if (form.dataset.id) values.id = Number(form.dataset.id);
        await api('repayments', form.dataset.id ? 'PUT' : 'POST', values); closeModal(); await refresh(); toast(t('payment_saved'));
      }
    } catch (error) { formError(form, error); }
    finally { delete form.dataset.submitting; if (submit?.isConnected) { submit.disabled = false; submit.innerHTML = original; if (type === 'financial-reset') updateResetConfirmation(form); icons(); } }
  }
  document.addEventListener('submit', event => {
    const form = event.target.closest('form[data-form]'); if (!form) return;
    event.preventDefault(); if (form.reportValidity()) submitForm(form);
  });
  document.addEventListener('click', async event => {
    const pageButton = event.target.closest('[data-page]');
    if (pageButton && state.user) { event.preventDefault(); await navigate(pageButton.dataset.page); return; }
    const buttonElement = event.target.closest('[data-action]');
    if (buttonElement) {
      const action = buttonElement.dataset.action, id = Number(buttonElement.dataset.id), resource = buttonElement.dataset.resource;
      try {
        if (action.startsWith('new-')) {
          const resources = { account: 'accounts', transaction: 'transactions', transfer: 'transfers', budget: 'budgets', debt: 'debts', category: 'categories', tag: 'tags', recurring: 'recurring', user: 'users' };
          const selected = resources[action.slice(4)];
          if (selected) resourceForm(selected);
        } else if (action === 'edit') {
          const item = find(resource, id); if (item) resourceForm(resource, item);
        } else if (action === 'delete') confirmDelete(resource, id);
        else if (action === 'confirm-delete') {
          buttonElement.disabled = true;
          try { await api(resource, 'DELETE', { id }); closeModal(); await refresh(); toast(t('deleted')); }
          catch (error) { buttonElement.disabled = false; formError($('#modal-root'), error); }
        } else if (action === 'report-period') {
          const preset = buttonElement.dataset.period;
          if (!['this_month', 'last_month', 'last90', 'custom'].includes(preset)) return;
          reportFilters().preset = preset;
          if (preset === 'custom') { render(); $('[data-report-date="from"]')?.focus(); }
          else { Object.assign(reportFilters(), reportRange(preset)); await loadReport(); }
        } else if (action === 'report-retry') await loadReport();
        else if (action === 'clear-sample-data') await confirmFinancialReset('samples');
        else if (action === 'reset-finances') await confirmFinancialReset('all');
        else if (action === 'close-modal') closeModal();
        else if (action === 'account-history') accountHistory(id);
        else if (action === 'repayment') paymentForm(id);
        else if (action === 'debt-history') paymentHistory(id);
        else if (action === 'edit-repayment') {
          const debt = find('debts', Number(buttonElement.dataset.debtId));
          const payment = (debt?.payments || debt?.repayments || []).find(item => Number(item.id) === id);
          if (payment) paymentForm(debt.id, payment);
        } else if (action === 'process-recurring') {
          buttonElement.disabled = true; await api('process_recurring', 'POST', {}); await refresh(); toast(t('recurring_processed'));
        } else if (action === 'clear-filters') { state.search = ''; state.from = ''; state.to = ''; if ($('#search-input')) $('#search-input').value = ''; render(); }
        else if (action === 'toggle-theme' || action === 'set-theme') {
          setTheme(action === 'set-theme' ? buttonElement.dataset.theme : state.theme === 'dark' ? 'light' : 'dark');
          if (state.user) render(); else showAuth($('#auth-root').dataset.setup === '1');
        } else if (action === 'retry') initialize();
      } catch (error) { toast(error.message, 'error'); if (buttonElement.isConnected) buttonElement.disabled = false; }
      return;
    }
    if (event.target.classList.contains('modal-overlay')) closeModal();
  });
  document.addEventListener('keydown', event => {
    const modal = $('#modal-root .modal');
    if (event.key === 'Escape') { closeModal(); document.body.classList.remove('sidebar-open'); }
    if (event.key === 'Tab' && modal) {
      const focusable = $$('button:not([disabled]),a[href],input:not([disabled]):not([type="hidden"]),select:not([disabled]),textarea:not([disabled]),[tabindex="0"]', modal).filter(element => !element.hidden && element.getClientRects().length);
      if (!focusable.length) { event.preventDefault(); modal.focus(); }
      else if (event.shiftKey && document.activeElement === focusable[0]) { event.preventDefault(); focusable.at(-1).focus(); }
      else if (!event.shiftKey && document.activeElement === focusable.at(-1)) { event.preventDefault(); focusable[0].focus(); }
    }
    if ((event.metaKey || event.ctrlKey) && event.key === 'k') { event.preventDefault(); $('#search-input')?.focus(); }
  });
  document.addEventListener('change', async event => {
    const element = event.target;
    try {
      if (element.matches('[data-currency]')) {
        const selected = state.currency = element.value;
        state.analytics = {}; state.report = null;
        if (state.reportFilters) state.reportFilters.account_id = '';
        const analytics = api('analytics', 'GET', undefined, { currency: selected }).then(data => { if (state.currency === selected) { state.analytics = data; render(); } }).catch(error => toast(error.message, 'error'));
        if (state.page === 'reports') await Promise.all([analytics, loadReport()]); else { render(); await analytics; }
      }
      else if (element.matches('[data-report-account]')) { reportFilters().account_id = element.value; await loadReport(); }
      else if (element.matches('[data-report-date]')) {
        reportFilters()[element.dataset.reportDate] = element.value; reportFilters().preset = 'custom';
        $$('.report-presets button').forEach(button => { button.classList.toggle('btn-primary', button.dataset.period === 'custom'); button.classList.toggle('btn-secondary', button.dataset.period !== 'custom'); button.setAttribute('aria-pressed', String(button.dataset.period === 'custom')); });
        if (element.dataset.reportDate === 'from') { const to = $('[data-report-date="to"]'); if (to) to.min = element.value; }
      }
      else if (element.matches('[data-locale],[data-auth-locale]') || element.id === 'language-select') await changeLocale(element.value);
      else if (element.matches('[data-filter]') && element.dataset.filter !== 'search') { state[element.dataset.filter] = element.value; render(); }
      const form = element.closest('[data-form="resource"]');
      if (!form) return;
      if (element.name === 'type' && ['transactions', 'recurring'].includes(form.dataset.resource)) {
        const category = form.elements.category_id; const oldValue = category.value;
        category.innerHTML = categoryOptions(element.value).map(item => `<option value="${escape(item.value)}">${escape(item.label)}</option>`).join('');
        if ([...category.options].some(option => option.value === oldValue)) category.value = oldValue;
      }
      if (element.name === 'type' && form.dataset.resource === 'categories') {
        form.elements.parent_id.innerHTML = [{ value: '', label: t('no_parent') }, ...categoryOptions(element.value, false, Number(form.dataset.id))].map(item => `<option value="${escape(item.value)}">${escape(item.label)}</option>`).join('');
      }
      if (element.name === 'currency' && form.dataset.resource === 'debts') form.elements.account_id.innerHTML = accountOptions(true, element.value).map(item => `<option value="${escape(item.value)}">${escape(item.label)}</option>`).join('');
      if (form.dataset.resource === 'transfers' && ['from_account_id', 'to_account_id', 'amount'].includes(element.name)) updateTransferForm(form);
    } catch (error) { toast(error.message, 'error'); }
  });
  let searchTimer;
  document.addEventListener('input', event => {
    const input = event.target;
    const resetForm = input.closest('[data-form="financial-reset"]');
    if (resetForm) updateResetConfirmation(resetForm);
    if (input.matches('[data-filter="search"]') || input.id === 'search-input') {
      state.search = input.value;
      if (input.id === 'search-input' && ['dashboard', 'reports', 'settings'].includes(state.page) && state.search) state.page = 'transactions';
      if (input.id !== 'search-input' && $('#search-input')) $('#search-input').value = state.search;
      clearTimeout(searchTimer); searchTimer = setTimeout(() => {
        const position = input.selectionStart; const global = input.id === 'search-input';
        render(); const replacement = global ? $('#search-input') : $('[data-filter="search"]');
        if (replacement) { replacement.focus(); replacement.setSelectionRange(position, position); }
      }, 180);
    }
    const form = input.closest('[data-form="resource"][data-resource="transfers"]');
    if (form && input.name === 'amount') updateTransferForm(form);
  });
  function wireShell() {
    $('#quick-add')?.addEventListener('click', () => resourceForm('transactions'));
    $('#theme-toggle')?.addEventListener('click', () => { setTheme(state.theme === 'dark' ? 'light' : 'dark'); render(); });
    $('#sidebar-toggle')?.addEventListener('click', () => {
      if (window.matchMedia('(max-width: 900px)').matches) document.body.classList.toggle('sidebar-open');
      else document.body.classList.toggle('sidebar-collapsed');
    });
    $('#logout-button')?.addEventListener('click', async () => {
      try { const session = await api('logout', 'POST', {}); state.csrf = session.csrf || state.csrf; showAuth(false); toast(t('signed_out')); }
      catch (error) { toast(error.message, 'error'); }
    });
    $('#mobile-more')?.addEventListener('click', () => {
      const pages = owner() ? ['dashboard', 'transfers', 'reports', 'categories', 'recurring', 'settings'] : ['categories', 'recurring', 'settings'];
      const symbols = { dashboard: 'layout-dashboard', transfers: 'arrow-left-right', reports: 'chart-no-axes-combined', categories: 'shapes', recurring: 'repeat-2', settings: 'settings-2' };
      openModal(t('more'), `<nav class="more-menu">${pages.map(page => `<button class="more-menu-item" data-page="${page}">${icon(symbols[page])}<span>${escape(t(page))}</span>${icon('chevron-right')}</button>`).join('')}</nav>`);
    });
  }
  async function initialize() {
    setTheme(state.theme);
    try {
      const session = await api('session'); state.csrf = session.csrf; state.user = session.user;
      await loadDictionary(session.locale || 'en');
      if (state.user) {
        const initialPage = location.hash.slice(1); state.page = ['dashboard', 'accounts', 'transactions', 'transfers', 'budgets', 'debts', 'reports', 'categories', 'recurring', 'settings'].includes(initialPage) ? initialPage : owner() ? 'dashboard' : 'transactions';
        await refresh();
      } else await showAuth(!!session.needs_setup);
    } catch (error) {
      $('#app-shell').hidden = true; $('#auth-root').hidden = false;
      $('#auth-root').innerHTML = `<div class="initial-error">${icon('cloud-off')}<h1>${escape(t('setup_failed'))}</h1><p>${escape(error.message)}</p>${button('retry', 'retry', 'refresh-cw')}</div>`; icons();
    }
  }
  const start = () => { wireShell(); initialize(); };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
})();
