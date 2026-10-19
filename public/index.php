<?php
header('X-Content-Type-Options: nosniff');
header('X-Frame-Options: DENY');
header('Referrer-Policy: same-origin');
header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'");
?>
<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
    <meta name="theme-color" content="#090d16">
    <meta name="description" content="Vela — a clearer view of your personal and business finances. Manage accounts, transactions, budgets and your financial future in one place.">
    <title>Vela — Your money, in focus</title>
    <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E%3Crect width='40' height='40' rx='12' fill='%2310b981'/%3E%3Cpath d='m10 12 10 18 10-18h-6l-4 8-4-8z' fill='%23090d16'/%3E%3C/svg%3E">
    <link rel="stylesheet" href="/assets/app.css">
    <script defer src="/assets/vendor/lucide.min.js"></script>
    <script defer src="/assets/vendor/chart.umd.min.js"></script>
    <script defer src="/assets/app.js"></script>
</head>
<body>
<a class="skip-link" href="#main-content">Skip to content</a>

<div id="auth-root" class="auth-root" aria-live="polite">
    <div class="initial-loading">
        <span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 28 28" fill="none"><path d="m5 7 9 16 9-16h-5l-4 8-4-8H5Z" fill="currentColor"/></svg></span>
        <span class="loading-wordmark">vela<span>.</span></span>
        <span class="loading-spinner" aria-label="Loading your workspace"></span>
    </div>
</div>

<div id="app-shell" class="app-shell" hidden>
    <aside id="sidebar" class="sidebar" aria-label="Main navigation">
        <a class="brand" href="/" aria-label="Vela home">
            <span class="brand-mark" aria-hidden="true"><svg viewBox="0 0 28 28" fill="none"><path d="m5 7 9 16 9-16h-5l-4 8-4-8H5Z" fill="currentColor"/></svg></span>
            <span class="brand-wordmark">vela<span>.</span></span>
        </a>

        <div class="workspace-card">
            <span class="workspace-icon"><i data-lucide="layers-2"></i></span>
            <span class="workspace-text"><strong data-i18n="workspace">My workspace</strong><span data-i18n="personal_business">Personal & business</span></span>
            <span class="workspace-status" title="Private workspace"></span>
        </div>

        <div class="nav-section-label" data-i18n="workspace_navigation">WORKSPACE</div>
        <nav id="sidebar-nav" class="sidebar-nav" aria-label="Workspace pages">
            <button type="button" class="nav-item active" data-page="dashboard"><i data-lucide="layout-dashboard"></i><span data-i18n="overview">Overview</span><span class="nav-active-indicator"></span></button>
            <button type="button" class="nav-item" data-page="accounts"><i data-lucide="wallet-cards"></i><span data-i18n="accounts">Accounts</span></button>
            <button type="button" class="nav-item" data-page="transactions"><i data-lucide="arrow-left-right"></i><span data-i18n="transactions">Transactions</span></button>
            <button type="button" class="nav-item" data-page="transfers"><i data-lucide="repeat-2"></i><span data-i18n="transfers">Transfers</span></button>
            <button type="button" class="nav-item" data-page="budgets"><i data-lucide="chart-no-axes-combined"></i><span data-i18n="budgets">Budgets</span></button>
            <button type="button" class="nav-item" data-page="debts"><i data-lucide="hand-coins"></i><span data-i18n="debts">Debts & loans</span></button>
            <button type="button" class="nav-item" data-page="reports"><i data-lucide="chart-pie"></i><span data-i18n="reports">Reports</span></button>
            <div class="nav-divider"></div>
            <button type="button" class="nav-item" data-page="categories"><i data-lucide="shapes"></i><span data-i18n="categories">Categories & tags</span></button>
            <button type="button" class="nav-item" data-page="recurring"><i data-lucide="calendar-clock"></i><span data-i18n="recurring">Recurring</span></button>
            <button type="button" class="nav-item" data-page="settings"><i data-lucide="settings-2"></i><span data-i18n="settings">Settings</span></button>
        </nav>

        <div class="sidebar-bottom">
            <div class="sidebar-note"><span class="sidebar-note-icon"><i data-lucide="shield-check"></i></span><div><strong data-i18n="private_by_design">Private by design</strong><span data-i18n="your_data_your_control">Your data. Your control.</span></div><span class="status-dot"></span></div>
            <div class="user-profile">
                <span id="user-avatar" class="avatar">V</span>
                <div class="profile-info"><strong id="user-name">Your workspace</strong><span id="user-role">Owner</span></div>
                <button id="logout-button" class="icon-btn" type="button" aria-label="Sign out" title="Sign out"><i data-lucide="log-out"></i></button>
            </div>
        </div>
    </aside>

    <div class="app-main">
        <header class="topbar">
            <div class="topbar-leading">
                <button id="sidebar-toggle" class="icon-btn sidebar-toggle" type="button" aria-label="Toggle sidebar" title="Toggle sidebar"><i data-lucide="panel-left"></i></button>
                <div class="topbar-divider"></div>
                <div class="breadcrumb"><span class="breadcrumb-parent" data-i18n="workspace">Workspace</span><i data-lucide="chevron-right"></i><span id="page-title" data-i18n="overview">Overview</span></div>
                <span id="page-subtitle" class="sr-only"></span>
            </div>
            <div id="header-actions" class="header-actions">
                <label class="header-search"><i data-lucide="search"></i><input id="search-input" type="search" placeholder="Search anything..." autocomplete="off" aria-label="Search current page"><span class="search-shortcut">⌕</span></label>
                <label class="language-control"><i data-lucide="globe-2"></i><select id="language-select" aria-label="Language"><option value="en">EN</option><option value="uz">UZ</option><option value="ru">RU</option></select></label>
                <button id="theme-toggle" class="icon-btn theme-toggle" type="button" aria-label="Toggle color theme" title="Toggle color theme"><i data-lucide="sun"></i></button>
                <span class="header-divider"></span>
                <button id="quick-add" class="btn btn-primary header-add" type="button"><i data-lucide="plus"></i><span data-i18n="add_transaction">Add transaction</span></button>
            </div>
        </header>

        <main id="main-content" class="main-content" tabindex="-1" aria-live="polite"></main>
        <footer class="app-footer"><span>Vela <span class="footer-dot">·</span> <span data-i18n="clarity_for_every_currency">Clarity for every currency.</span></span><span class="footer-secure"><i data-lucide="lock-keyhole"></i><span data-i18n="private_workspace">Private workspace</span></span></footer>
    </div>

    <nav id="mobile-nav" class="mobile-nav" aria-label="Mobile navigation">
        <button type="button" data-page="accounts"><i data-lucide="wallet-cards"></i><span data-i18n="accounts">Accounts</span></button>
        <button type="button" data-page="transactions"><i data-lucide="arrow-left-right"></i><span data-i18n="transactions">Transactions</span></button>
        <button type="button" data-page="debts"><i data-lucide="hand-coins"></i><span data-i18n="debts">Debts</span></button>
        <button type="button" data-page="budgets"><i data-lucide="chart-no-axes-combined"></i><span data-i18n="budgets">Budgets</span></button>
        <button id="mobile-more" type="button" aria-label="More pages"><i data-lucide="menu"></i><span data-i18n="more">More</span></button>
    </nav>
</div>

<div id="modal-root"></div>
<div id="toast-root" class="toast-root" role="status" aria-live="polite" aria-atomic="false"></div>
<noscript><div class="noscript-message">Vela needs JavaScript enabled to manage your finances securely. Please enable it in your browser and reload.</div></noscript>
</body>
</html>
