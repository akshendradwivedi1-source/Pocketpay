// ========== PocketPay: Application Initialization & Global Event Wiring ==========

(() => {
  'use strict';

  function initGlobalEvents() {
    // 1. Navigation links with [data-route]
    document.addEventListener('click', (e) => {
      const routeEl = e.target.closest('[data-route]');
      if (routeEl) {
        e.preventDefault();
        const route = routeEl.getAttribute('data-route');
        if (route && window.PP?.navigate) {
          PP.navigate(route);
        }
        // Close dropdown & mobile sidebar on navigation
        document.getElementById('avatarDropdown')?.classList.remove('show');
        document.getElementById('sidebar')?.classList.remove('open');
        return;
      }

      // 2. Avatar Dropdown toggle & outside click
      const avatarBtn = e.target.closest('#avatarBtn');
      const avatarDropdown = document.getElementById('avatarDropdown');
      if (avatarBtn) {
        e.stopPropagation();
        avatarDropdown?.classList.toggle('show');
        return;
      } else if (avatarDropdown && !e.target.closest('#avatarMenu')) {
        avatarDropdown.classList.remove('show');
      }

      // 3. Mobile Sidebar toggle & outside click
      const sidebarToggle = e.target.closest('#sidebarToggle');
      const sidebar = document.getElementById('sidebar');
      if (sidebarToggle) {
        e.stopPropagation();
        sidebar?.classList.toggle('open');
        return;
      } else if (sidebar && sidebar.classList.contains('open') && !e.target.closest('#sidebar')) {
        sidebar.classList.remove('open');
      }

      // 4. QR Actions (TopNav, Sidebar, Dropdown, FAB)
      if (e.target.closest('#topNavScanBtn, #dropScanQrBtn, #sbScanQr')) {
        e.preventDefault();
        avatarDropdown?.classList.remove('show');
        PP.Modals?.scanAndPay?.();
        return;
      }
      if (e.target.closest('#dropMyQrBtn, #sbMyQr')) {
        e.preventDefault();
        avatarDropdown?.classList.remove('show');
        PP.Modals?.showProfileQr?.();
        return;
      }

      // 5. Quick Action Sidebar Buttons
      if (e.target.closest('#sbAddIncome')) {
        e.preventDefault();
        PP.Modals?.addIncome?.();
        return;
      }
      if (e.target.closest('#sbAddExpense')) {
        e.preventDefault();
        PP.Modals?.addExpense?.();
        return;
      }
      if (e.target.closest('#sbTransfer')) {
        e.preventDefault();
        PP.Modals?.transfer?.();
        return;
      }

      // 6. FAB & Mobile Quick Menu
      const fabBtn = e.target.closest('#mobileFab, #bottomCenterFab, #quickAddFab');
      if (fabBtn) {
        e.preventDefault();
        if (PP.Modals?.openQuickAdd) {
          PP.Modals.openQuickAdd();
        } else {
          PP.Modals?.addIncome?.();
        }
        return;
      }

      const fabAction = e.target.closest('#mobileFabMenu [data-action]');
      if (fabAction) {
        e.preventDefault();
        const action = fabAction.getAttribute('data-action');
        if (action === 'scan') PP.Modals?.scanAndPay?.();
        else if (action === 'income') PP.Modals?.addIncome?.();
        else if (action === 'expense') PP.Modals?.addExpense?.();
        else if (action === 'transfer') PP.Modals?.transfer?.();
        else if (action === 'pocket') PP.Modals?.createPocket?.();
        return;
      }

      // 7. Header Theme Toggle
      if (e.target.closest('#themeToggle')) {
        e.preventDefault();
        const curr = document.documentElement.getAttribute('data-theme') || 'dark';
        PP.setTheme?.(curr === 'dark' ? 'light' : 'dark');
        return;
      }

      // 8. Notifications Button
      if (e.target.closest('#notifBtn')) {
        e.preventDefault();
        PP.Modals?.notifications?.();
        return;
      }

      // 9. Setup PIN & Logout in Dropdown
      if (e.target.closest('#setupPinBtn')) {
        e.preventDefault();
        avatarDropdown?.classList.remove('show');
        if (PP.state.user?.has_transaction_pin) {
          PP.Modals?.changePin?.();
        } else {
          PP.Modals?.setupPin?.();
        }
        return;
      }

      if (e.target.closest('#logoutBtn')) {
        e.preventDefault();
        avatarDropdown?.classList.remove('show');
        PP.logout?.();
        return;
      }
    });

    // Global Search box & Shortcut (⌘K / Ctrl+K)
    const searchInput = document.getElementById('globalSearch');
    if (searchInput) {
      searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          const q = searchInput.value.trim();
          if (q) {
            PP.navigate?.('transactions', { search: q });
          }
        }
      });
    }

    document.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (searchInput) {
          searchInput.focus();
          searchInput.select();
        }
      }
    });
  }

  async function initializeApp() {
    try {
      // Initialize theme first
      if (window.PP?.initTheme) {
        PP.initTheme();
      }

      // Initialize router
      if (window.PP?.initRouter) {
        PP.initRouter();
      }

      // Initialize global event listeners
      initGlobalEvents();

      // Set route from URL/hash
      if (window.PP?.handleRoute) {
        PP.handleRoute();
      }

      // Initialize AI Assistant
      if (window.PP?.Assistant?.init) {
        PP.Assistant.init();
      }

      // Register Service Worker for PWA
      if ('serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
        navigator.serviceWorker.register('/static/service-worker.js').catch(err => {
          console.log('[PWA] Service Worker registration skipped/cached:', err.message);
        });
      }

      // Safety watchdog: Guarantee loader dissolves within 4.5s under all circumstances
      const watchdog = setTimeout(() => {
        const loader = document.getElementById('appLoader');
        if (loader && !loader.classList.contains('loaded')) {
          console.warn('[Watchdog] Loader timeout reached - dissolving loader');
          if (window.PP?.hideLoader) PP.hideLoader();
          else {
            loader.classList.add('loaded');
            setTimeout(() => { loader.style.display = 'none'; }, 400);
            const app = document.getElementById('app');
            if (app) app.classList.remove('hidden');
          }
        }
      }, 4500);

      // Try to restore an existing authenticated session.
      if (window.PP?.bootstrap) {
        await PP.bootstrap();
      } else {
        throw new Error('PP.bootstrap is not available');
      }
      clearTimeout(watchdog);
    } catch (error) {
      console.error('PocketPay initialization error:', error);

      // Never leave the user stuck on the loading screen.
      try {
        if (window.PP) {
          PP.state = PP.state || {};
          PP.state.initialized = true;
          PP.state.user = null;
          PP.state.currentRoute = 'login';

          if (PP.renderAuth) {
            PP.renderAuth();
          }

          if (PP.hideLoader) {
            PP.hideLoader();
          }
        }
      } catch (fallbackError) {
        console.error('PocketPay fallback initialization failed:', fallbackError);
      } finally {
        const loader = document.getElementById('appLoader');
        if (loader) {
          loader.classList.add('loaded');
          loader.style.display = 'none';
        }
        const app = document.getElementById('app');
        if (app) app.classList.remove('hidden');
      }
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
  });
})();
