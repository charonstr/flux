(function () {
  'use strict';

  const MobileApp = {
    init() {
      this.applyTheme();
      this.bindThemeButtons();
      this.bindSoftNav();
      this.bindBackButtons();
      this.bindProfileModal();
      this.bindOutsideDismiss();
      this.markActiveNav();
      this.initViewportVar();
    },

    applyTheme(theme) {
      try {
        const next = theme || localStorage.getItem('theme') || 'dark';
        document.documentElement.setAttribute('data-theme', next);
        document.body && document.body.setAttribute('data-theme', next);
        document.documentElement.style.colorScheme = next === 'light' ? 'light' : 'dark';
        localStorage.setItem('theme', next);
      } catch (_) {}
    },

    bindThemeButtons() {
      document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-theme-set]');
        if (!btn) return;
        e.preventDefault();
        this.applyTheme(btn.getAttribute('data-theme-set'));
        this.showNotification(btn.getAttribute('data-theme-set') === 'light' ? 'Açık tema' : 'Koyu tema');
      });
    },

    bindSoftNav() {
      document.addEventListener('click', (e) => {
        const a = e.target.closest('a[data-nav="soft"]');
        if (!a) return;
        const href = a.getAttribute('href');
        if (!href || href.startsWith('#')) return;
        // Soft nav fallback: normal navigation (stable)
        e.preventDefault();
        window.location.href = href;
      });
    },

    bindBackButtons() {
      document.addEventListener('click', (e) => {
        const btn = e.target.closest('[data-go-back]');
        if (!btn) return;
        e.preventDefault();
        if (history.length > 1) history.back();
        else window.location.href = '/';
      });
    },

    bindProfileModal() {
      const profileBtn = document.getElementById('profileBtn');
      const modal = document.getElementById('profileModal');
      const overlay = document.getElementById('modalOverlay');
      if (!profileBtn || !modal || !overlay) return;

      const open = () => {
        modal.classList.add('open');
        overlay.classList.add('open');
        document.body.classList.add('modal-open');
      };
      const close = () => {
        modal.classList.remove('open');
        overlay.classList.remove('open');
        document.body.classList.remove('modal-open');
      };

      profileBtn.addEventListener('click', (e) => {
        e.preventDefault();
        (modal.classList.contains('open')) ? close() : open();
      });
      overlay.addEventListener('click', close);

      document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') close();
      });

      // Expose for pages that may call it
      this.closeProfileModal = close;
    },

    bindOutsideDismiss() {
      document.addEventListener('click', (e) => {
        const modal = document.getElementById('profileModal');
        if (!modal || !modal.classList.contains('open')) return;
        const profileBtn = document.getElementById('profileBtn');
        const clickedInside = e.target.closest('#profileModal');
        const clickedBtn = profileBtn && (e.target === profileBtn || profileBtn.contains(e.target));
        if (!clickedInside && !clickedBtn) {
          modal.classList.remove('open');
          const overlay = document.getElementById('modalOverlay');
          overlay && overlay.classList.remove('open');
          document.body.classList.remove('modal-open');
        }
      });
    },

    markActiveNav() {
      const normalize = (input) => {
        const cleaned = String(input || '')
          .split('?')[0]
          .split('#')[0]
          .replace(/\/+$/, '');
        return cleaned || '/';
      };

      const currentPath = normalize(location.pathname);

      const isInGroup = (path, group) => {
        if (!path || !group.length) return false;
        return group.some(prefix => path === prefix || path.startsWith(prefix + '/'));
      };

      const navGroups = {
        home: ['/', '/home'],
        dm: ['/dm'],
        friends: ['/friends', '/friendships'],
        servers: ['/servers', '/channel', '/voice'],
        settings: ['/settings', '/profile', '/privacy', '/security', '/language', '/sitesettings', '/changepassword'],
        casino: ['/casino']
      };

      const currentSection = Object.keys(navGroups).find(section => isInGroup(currentPath, navGroups[section]));
      const allLinks = document.querySelectorAll('a[href]');

      allLinks.forEach(a => {
        a.classList.remove('active');
      });

      allLinks.forEach(a => {
        const href = a.getAttribute('href');
        if (!href || href.startsWith('http') || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;

        const linkPath = normalize(href);
        if (linkPath === currentPath) {
          a.classList.add('active');
          return;
        }

        if (!currentSection) return;
        if (!isInGroup(linkPath, navGroups[currentSection])) return;

        const hasNavClass = (
          a.classList.contains('sidebar-link') ||
          a.classList.contains('nav-item') ||
          a.classList.contains('cx-sidebar-link') ||
          a.classList.contains('cx-nav-item')
        );

        if (hasNavClass) {
          a.classList.add('active');
        }
      });
    },

    initViewportVar() {
      const root = document.documentElement;
      let maxVh = 0;
      const apply = () => {
        const vh = Math.round((window.visualViewport && window.visualViewport.height) || window.innerHeight || root.clientHeight || 0);
        if (!maxVh || vh > maxVh) maxVh = vh;
        root.style.setProperty('--app-vh', vh + 'px');
        root.classList.toggle('keyboard-open', (maxVh - vh) > 120);
      };
      apply();
      window.addEventListener('resize', () => requestAnimationFrame(apply), { passive: true });
      if (window.visualViewport) {
        window.visualViewport.addEventListener('resize', () => requestAnimationFrame(apply), { passive: true });
      }
    },

    showNotification(message, type = 'info') {
      let host = document.getElementById('mobileToastHost');
      if (!host) {
        host = document.createElement('div');
        host.id = 'mobileToastHost';
        host.style.cssText = [
          'position:fixed', 'left:12px', 'right:12px',
          'bottom:calc(12px + env(safe-area-inset-bottom, 0px))',
          'z-index:9999', 'display:flex', 'flex-direction:column', 'gap:8px',
          'pointer-events:none'
        ].join(';');
        document.body.appendChild(host);
      }

      const toast = document.createElement('div');
      const bg = type === 'error'
        ? 'rgba(239,68,68,.95)'
        : type === 'success'
          ? 'rgba(16,185,129,.95)'
          : 'rgba(45,55,72,.95)';
      toast.style.cssText = [
        'padding:12px 14px', 'border-radius:12px', 'color:#fff',
        'font:600 14px/1.35 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Arial,sans-serif',
        'background:' + bg, 'box-shadow:0 10px 30px rgba(0,0,0,.2)',
        'backdrop-filter:blur(8px)', '-webkit-backdrop-filter:blur(8px)',
        'pointer-events:auto', 'transform:translateY(8px)', 'opacity:0',
        'transition:all .2s ease'
      ].join(';');
      toast.textContent = String(message || '');
      host.appendChild(toast);

      requestAnimationFrame(() => {
        toast.style.transform = 'translateY(0)';
        toast.style.opacity = '1';
      });

      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(8px)';
        setTimeout(() => toast.remove(), 220);
      }, 2200);
    }
  };

  window.MobileApp = MobileApp;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => MobileApp.init(), { once: true });
  } else {
    MobileApp.init();
  }
})();
