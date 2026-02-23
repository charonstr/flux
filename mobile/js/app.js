(function () {
  'use strict';

  let navMask = null;
  let lastRailHash = '';

  function injectShellStyles() {
    if (document.getElementById('mobile-universal-shell-styles')) return;
    const style = document.createElement('style');
    style.id = 'mobile-universal-shell-styles';
    style.textContent = `
      body.shell-active { margin: 0; padding: 0 !important; overflow-x: hidden; }
      .server-shell { min-height: 100dvh; display: block; width: 100%; }
      .server-rail {
        position: fixed;
        left: 0;
        right: 0;
        bottom: 0;
        z-index: 1400;
        height: calc(62px + env(safe-area-inset-bottom));
        padding: 6px 10px calc(6px + env(safe-area-inset-bottom));
        display: flex;
        flex-direction: row;
        align-items: center;
        justify-content: flex-start;
        gap: 8px;
        background: rgba(var(--panel-rgb), 0.78);
        backdrop-filter: blur(18px);
        border-top: 1px solid rgba(var(--line-rgb), 0.35);
        overflow-x: auto;
        overflow-y: hidden;
        white-space: nowrap;
      }
      .server-rail::-webkit-scrollbar {
        height: 0;
        width: 0;
      }
      .server-main {
        min-width: 0;
        width: 100%;
        overflow-x: hidden;
        padding-bottom: calc(78px + env(safe-area-inset-bottom)) !important;
      }
      .rail-btn-wrapper { position: relative; display: flex; align-items: center; justify-content: center; width: auto; flex: 0 0 auto; }
      .rail-btn, .rail-avatar {
        width: 40px !important;
        min-width: 40px !important;
        max-width: 40px !important;
        height: 40px !important;
        min-height: 40px !important;
        max-height: 40px !important;
        border-radius: 50%;
        display: grid;
        place-items: center;
        color: var(--text);
        background: rgba(var(--panel-rgb), 0.8);
        border: 1px solid rgba(var(--line-rgb), 0.65);
        text-decoration: none;
        font-size: 0.9rem !important;
        flex: 0 0 40px !important;
      }
      .rail-avatar { object-fit: cover; }
      .rail-btn.active { background: var(--primary); color: #fff; border-color: var(--primary); }
      .rail-divider { width: 2px; height: 24px; background: rgba(var(--text-rgb), 0.12); border-radius: 4px; margin: 0 2px; flex: 0 0 auto; }
    `;
    document.head.appendChild(style);
  }

  function shouldUseShell(pathname) {
    const p = pathname || window.location.pathname || '';
    if (p.startsWith('/login')) return false;
    if (p.startsWith('/register')) return false;
    return true;
  }

  function ensureServerShell() {
    if (!shouldUseShell()) return;
    injectShellStyles();
    if (document.querySelector('.server-shell')) {
      document.body.classList.add('shell-active');
      return;
    }

    const contentRoot = document.querySelector('main') || document.querySelector('.wrap');
    if (!contentRoot) return;

    const topbar = document.querySelector('.topbar');
    if (topbar) topbar.remove();

    const shell = document.createElement('div');
    shell.className = 'server-shell';

    const rail = document.createElement('aside');
    rail.className = 'server-rail';

    const mainWrap = document.createElement('div');
    mainWrap.className = 'server-main';
    mainWrap.appendChild(contentRoot);

    shell.appendChild(rail);
    shell.appendChild(mainWrap);
    document.body.appendChild(shell);
    document.body.classList.add('shell-active');
  }

  function ensureNavMask() {
    if (navMask) return navMask;
    navMask = document.createElement('div');
    navMask.id = 'navmask';
    navMask.style.position = 'fixed';
    navMask.style.inset = '0';
    navMask.style.background = 'transparent';
    navMask.style.pointerEvents = 'none';
    navMask.style.zIndex = '99999';
    document.body.appendChild(navMask);
    return navMask;
  }

  function showNavMask() {
    const mask = ensureNavMask();
    mask.style.pointerEvents = 'auto';
    mask.style.cursor = 'wait';
  }

  function hideNavMask() {
    if (!navMask) return;
    navMask.style.pointerEvents = 'none';
    navMask.style.cursor = 'default';
  }

  function closeTransientUi() {
    document.querySelectorAll('.modal.active, .context-menu.active, .server-dropdown.active').forEach((el) => {
      el.classList.remove('active');
    });
    document.querySelectorAll('.modal, .context-menu, .server-dropdown').forEach((el) => {
      if (el.id === 'profileModal') {
        el.style.display = 'none';
      } else if (el.classList.contains('context-menu') || el.classList.contains('server-dropdown')) {
        el.style.display = 'none';
      }
    });
    const overlay = document.getElementById('modalOverlay');
    if (overlay) {
      overlay.classList.remove('active');
      overlay.style.display = 'none';
    }
  }

  function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    document.body.setAttribute('data-theme', savedTheme);

    document.querySelectorAll('[data-theme-set]').forEach((btn) => {
      btn.onclick = (e) => {
        e.preventDefault();
        const theme = btn.getAttribute('data-theme-set') === 'light' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', theme);
        document.body.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
      };
    });
  }

  function getIconForType(type) {
    if (type === 'success') return 'fa-circle-check';
    if (type === 'error') return 'fa-circle-exclamation';
    if (type === 'warning') return 'fa-triangle-exclamation';
    return 'fa-circle-info';
  }

  function showNotification(message, type) {
    const toast = document.createElement('div');
    toast.className = 'toast-msg toast-' + (type || 'info');
    toast.innerHTML = '<i class="fa-solid ' + getIconForType(type) + '"></i> <span>' + String(message || '') + '</span>';

    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      document.body.appendChild(container);
    }

    container.appendChild(toast);
    setTimeout(() => {
      toast.classList.add('show');
      setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 260);
      }, 2500);
    }, 40);
  }

  function bindProfileModal() {
    const profileBtn = document.getElementById('profileBtn');
    const profileModal = document.getElementById('profileModal');
    const overlay = document.getElementById('modalOverlay');
    if (!profileBtn || !profileModal || !overlay) return;

    profileBtn.onclick = (e) => {
      e.stopPropagation();
      const isActive = profileModal.classList.contains('active') || profileModal.style.display === 'block';
      if (isActive) {
        profileModal.classList.remove('active');
        profileModal.style.display = 'none';
        overlay.classList.remove('active');
        overlay.style.display = 'none';
      } else {
        profileModal.classList.add('active');
        profileModal.style.display = 'block';
        overlay.classList.add('active');
        overlay.style.display = 'block';
      }
    };

    overlay.onclick = () => {
      closeTransientUi();
    };
  }

  function ensureTopbarCasinoButton() {
    const topbarRight = document.querySelector('.topbar .topbar-right');
    if (!topbarRight) return;
    if (topbarRight.querySelector('a[href="/casino"]')) return;

    const casinoBtn = document.createElement('a');
    casinoBtn.href = '/casino';
    casinoBtn.setAttribute('data-nav', 'soft');
    casinoBtn.className = 'navbtn';
    casinoBtn.title = 'Casino';
    casinoBtn.innerHTML = '<i class="fa-solid fa-dice"></i>';
    topbarRight.insertBefore(casinoBtn, topbarRight.firstChild);
  }

  function syncTopbarAndCoreModals(doc) {
    const currentTopbar = document.querySelector('.topbar');
    const incomingTopbar = doc.querySelector('.topbar');
    if (incomingTopbar && currentTopbar) {
      currentTopbar.replaceWith(incomingTopbar);
    } else if (incomingTopbar && !currentTopbar) {
      document.body.insertAdjacentElement('afterbegin', incomingTopbar);
    } else if (!incomingTopbar && currentTopbar) {
      currentTopbar.remove();
    }

    const currentOverlay = document.getElementById('modalOverlay');
    const incomingOverlay = doc.getElementById('modalOverlay');
    if (incomingOverlay && currentOverlay) {
      currentOverlay.replaceWith(incomingOverlay);
    } else if (incomingOverlay && !currentOverlay) {
      document.body.appendChild(incomingOverlay);
    }

    const currentProfileModal = document.getElementById('profileModal');
    const incomingProfileModal = doc.getElementById('profileModal');
    if (incomingProfileModal && currentProfileModal) {
      currentProfileModal.replaceWith(incomingProfileModal);
    } else if (incomingProfileModal && !currentProfileModal) {
      document.body.appendChild(incomingProfileModal);
    }
  }

  function syncPageStyles(doc) {
    const styleNodes = Array.from(doc.head.querySelectorAll('style')).filter((s) => {
      const text = s.textContent || '';
      if (/themeboot/i.test(text)) return false;
      return true;
    });
    const combinedCss = styleNodes.map((s) => s.textContent || '').join('\n');
    let pageStyle = document.head.querySelector('style#page-style');
    if (!pageStyle) {
      pageStyle = document.createElement('style');
      pageStyle.id = 'page-style';
      document.head.appendChild(pageStyle);
    }
    pageStyle.textContent = combinedCss;
  }

  function syncAmbientLayer(doc) {
    const currentTexture = document.querySelector('.bg-texture');
    const incomingTexture = doc.querySelector('.bg-texture');
    if (incomingTexture && currentTexture) {
      currentTexture.replaceWith(incomingTexture);
    } else if (incomingTexture && !currentTexture) {
      document.body.insertAdjacentElement('afterbegin', incomingTexture);
    }

    const currentOrb1 = document.querySelector('.ambient-orb.orb-1');
    const incomingOrb1 = doc.querySelector('.ambient-orb.orb-1');
    if (incomingOrb1 && currentOrb1) {
      currentOrb1.replaceWith(incomingOrb1);
    } else if (incomingOrb1 && !currentOrb1) {
      document.body.insertAdjacentElement('afterbegin', incomingOrb1);
    }

    const currentOrb2 = document.querySelector('.ambient-orb.orb-2');
    const incomingOrb2 = doc.querySelector('.ambient-orb.orb-2');
    if (incomingOrb2 && currentOrb2) {
      currentOrb2.replaceWith(incomingOrb2);
    } else if (incomingOrb2 && !currentOrb2) {
      document.body.insertAdjacentElement('afterbegin', incomingOrb2);
    }
  }

  function swapBodyFromHtml(html, targetUrl, replaceOnly, isSubmit) {
    closeTransientUi();

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    document.title = doc.title || document.title;
    syncPageStyles(doc);

    const currentShell = document.querySelector('.server-shell');
    const nextShell = doc.querySelector('.server-shell');

    if (currentShell && nextShell) {
      currentShell.replaceWith(nextShell);
    } else if (currentShell && !nextShell) {
      const incomingMain = doc.querySelector('main') || doc.querySelector('.wrap');
      if (incomingMain) {
        currentShell.replaceWith(incomingMain);
      } else {
        document.body.innerHTML = doc.body.innerHTML;
      }
    } else if (!currentShell && nextShell) {
      const oldMain = document.querySelector('main') || document.querySelector('.wrap');
      if (oldMain) {
        oldMain.replaceWith(nextShell);
      } else {
        document.body.appendChild(nextShell);
      }
    } else {
      const oldMain = document.querySelector('main') || document.querySelector('.wrap');
      const incomingMain = doc.querySelector('main') || doc.querySelector('.wrap');
      if (oldMain && incomingMain) {
        oldMain.replaceWith(incomingMain);
      } else if (incomingMain && !oldMain) {
        document.body.appendChild(incomingMain);
      }
    }

    syncTopbarAndCoreModals(doc);
    syncAmbientLayer(doc);

    const scripts = Array.from(doc.querySelectorAll('script'));
    scripts.forEach((script) => {
      if (script.src) {
        if (script.src.includes('/mobile/js/app.js')) return;
        const fullSrc = new URL(script.src, window.location.origin).href;
        const exists = Array.from(document.querySelectorAll('script[src]')).some((node) => {
          try {
            return new URL(node.src, window.location.origin).href === fullSrc;
          } catch {
            return false;
          }
        });
        if (!exists) {
          const s = document.createElement('script');
          s.src = script.src;
          document.body.appendChild(s);
        }
      } else if ((script.textContent || '').trim()) {
        const inline = document.createElement('script');
        inline.textContent = script.textContent;
        document.body.appendChild(inline);
        inline.remove();
      }
    });

    const nextUrl = new URL(targetUrl, window.location.origin);
    const nextPath = nextUrl.pathname + nextUrl.search;
    const nowPath = window.location.pathname + window.location.search;
    if (!replaceOnly && nowPath !== nextPath) {
      history.pushState({}, '', nextPath);
    }

    initTheme();
    bind();
    updateDynamicRail();
    window.dispatchEvent(new CustomEvent('spa-loaded', { detail: { path: nextPath, submit: !!isSubmit } }));
    hideNavMask();

    if (isSubmit) {
      window.scrollTo({ top: window.scrollY });
    } else {
      window.scrollTo({ top: 0, behavior: 'auto' });
      document.querySelectorAll('.server-main, .chat-messages, .chatbox, .dm-wrap, .casino-wrap, .roulette-root, .table-wrap, .mx-wrap').forEach((el) => {
        el.scrollTop = 0;
      });
    }
  }

  async function softNavigate(url, replaceOnly) {
    const target = new URL(url, window.location.origin);
    const path = target.pathname + target.search;
    const current = window.location.pathname + window.location.search;
    if (!replaceOnly && path === current) return;

    try {
      const res = await fetch(target.href, {
        headers: {
          'X-Requested-With': 'fetch',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          Pragma: 'no-cache',
          Expires: '0'
        },
        cache: 'no-store'
      });
      if (!res.ok) throw new Error('Navigation response not ok');
      const html = await res.text();
      swapBodyFromHtml(html, res.url || target.href, !!replaceOnly, false);
    } catch (err) {
      window.location.href = target.href;
    }
  }

  async function softSubmit(form) {
    try {
      const formData = new FormData(form);
      if (form._voiceBlob) {
        formData.append('voice', form._voiceBlob, 'voice.webm');
        form._voiceBlob = null;
      }
      const method = (form.method || 'POST').toUpperCase();
      const res = await fetch(form.action || window.location.href, {
        method,
        body: method === 'GET' ? null : formData,
        headers: {
          'X-Requested-With': 'fetch',
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          Pragma: 'no-cache',
          Expires: '0'
        },
        cache: 'no-store'
      });
      if (!res.ok) throw new Error('Submit response not ok');
      const html = await res.text();
      swapBodyFromHtml(html, res.url || window.location.href, false, true);
    } catch (err) {
      form.submit();
    }
  }

  function updateRailActiveState(pathOverride) {
    const path = pathOverride || window.location.pathname;
    document.querySelectorAll('.server-rail .rail-btn[href]').forEach((btn) => {
      btn.classList.remove('active');
      const href = btn.getAttribute('href');
      if (!href) return;
      if (href === '/' && (path === '/' || path.startsWith('/home'))) {
        btn.classList.add('active');
      } else if (href !== '/' && path.startsWith(href)) {
        btn.classList.add('active');
      }
    });
  }

  async function updateDynamicRail() {
    ensureServerShell();
    const rail = document.querySelector('.server-rail');
    if (!rail) return;

    try {
      const res = await fetch('/api/nav', {
        headers: { 'X-Requested-With': 'fetch', 'Cache-Control': 'no-cache, no-store' },
        cache: 'no-store'
      });
      const data = await res.json();
      if (!data || !data.ok) {
        updateRailActiveState();
        return;
      }

      const hash = JSON.stringify(data.servers || []) + '|' + (data.avatar || '');
      if (hash === lastRailHash && rail.children.length > 0) {
        updateRailActiveState();
        return;
      }
      lastRailHash = hash;

      let html = '';
      html += '<div class="rail-btn-wrapper"><a class="rail-btn" href="/" data-nav="soft" title="Home"><i class="fa-solid fa-house"></i></a></div>';
      html += '<div class="rail-btn-wrapper"><a class="rail-btn" href="/dm" data-nav="soft" title="DM"><i class="fa-solid fa-paper-plane"></i></a></div>';
      html += '<div class="rail-btn-wrapper"><a class="rail-btn" href="/casino" data-nav="soft" title="Casino"><i class="fa-solid fa-dice"></i></a></div>';
      html += '<div class="rail-divider"></div>';

      (data.servers || []).forEach((server) => {
        const sid = encodeURIComponent(String(server.id));
        const sname = String(server.name || 'Server').replace(/"/g, '&quot;');
        const avatar = String(server.avatar || '/mobile/avatar.svg').replace(/"/g, '&quot;');
        html += '<div class="rail-btn-wrapper">';
        html += '<a href="/servers/' + sid + '" class="rail-btn" data-nav="soft" title="' + sname + '" style="padding:0; overflow:hidden;">';
        html += '<img src="' + avatar + '" class="rail-avatar" alt="" style="width:100%; height:100%; border-radius:inherit; object-fit:cover;">';
        html += '</a></div>';
      });

      html += '<div class="rail-btn-wrapper"><a class="rail-btn" href="/servers" data-nav="soft" title="Servers" style="color:#10b981; border-color:rgba(16,185,129,0.35); background:rgba(16,185,129,0.1);"><i class="fa-solid fa-plus"></i></a></div>';
      html += '<div style="flex:1;"></div>';
      html += '<div class="rail-btn-wrapper"><button class="profile-btn rail-btn" id="profileBtn" style="padding:0; overflow:hidden;"><img src="' + String(data.avatar || '/mobile/avatar.svg').replace(/"/g, '&quot;') + '" class="rail-avatar" alt="avatar" style="width:100%; height:100%; border-radius:inherit; object-fit:cover;"></button></div>';

      rail.innerHTML = html;
      bindProfileModal();
      bindSoftLinksIn(rail);
      updateRailActiveState();
    } catch {
      updateRailActiveState();
    }
  }

  function bindSoftLinksIn(scope) {
    scope.querySelectorAll('a[data-nav="soft"]').forEach((link) => {
      link.onclick = async (e) => {
        const href = link.getAttribute('href');
        if (!href) return;
        if (href.startsWith('http') && !href.startsWith(window.location.origin)) return;
        e.preventDefault();
        showNavMask();
        await softNavigate(link.href, false);
      };
    });
  }

  function bindForms() {
    document.querySelectorAll('form[data-nav="soft"]').forEach((form) => {
      form.onsubmit = async (e) => {
        e.preventDefault();
        showNavMask();
        await softSubmit(form);
      };
    });
  }

  function bindBackButtons() {
    document.querySelectorAll('[data-go-back="1"]').forEach((btn) => {
      btn.onclick = () => {
        if (window.history.length > 1) {
          window.history.back();
        } else {
          window.location.href = '/home';
        }
      };
    });
  }

  function bind() {
    ensureServerShell();
    ensureTopbarCasinoButton();
    bindSoftLinksIn(document);
    bindForms();
    bindBackButtons();
    bindProfileModal();

    if (typeof window.initVoicePage === 'function') {
      window.initVoicePage();
    }
    if (typeof window.initRoulettePage === 'function') {
      window.initRoulettePage();
    }
    if (typeof window.initBlackjackPage === 'function') {
      window.initBlackjackPage();
    }
  }

  window.MobileApp = {
    init: function () {
      initTheme();
      bind();
      updateDynamicRail();
    },
    showNotification: function (message, type) {
      showNotification(message, type || 'info');
    },
    navigateTo: function (url, push) {
      showNavMask();
      return softNavigate(url, push === false);
    }
  };

  window.toggleServerDropdown = function (e) {
    if (e && e.stopPropagation) e.stopPropagation();
    const drop = document.getElementById('serverDropdown');
    const icon = document.getElementById('serverHeaderIcon');
    if (!drop) return;

    const willOpen = drop.style.display !== 'flex';
    drop.style.display = willOpen ? 'flex' : 'none';
    if (icon) icon.style.transform = willOpen ? 'rotate(180deg)' : 'rotate(0deg)';

    const overlay = document.getElementById('modalOverlay');
    if (overlay) {
      overlay.style.display = willOpen ? 'block' : 'none';
      overlay.classList.toggle('active', willOpen);
    }
  };

  window.copyInviteCode = function (code, btn) {
    navigator.clipboard.writeText(code).then(() => {
      const original = btn ? btn.innerHTML : '';
      if (btn) btn.innerHTML = '<i class="fa-solid fa-check"></i> Kopyalandi';
      showNotification('Davet kodu panoya kopyalandi', 'success');
      if (btn) {
        setTimeout(() => {
          btn.innerHTML = original;
        }, 1800);
      }
    });
  };

  window.openSpecificModal = function (id) {
    const modal = document.getElementById(id);
    const overlay = document.getElementById('modalOverlay');
    if (modal) {
      modal.style.display = 'block';
      modal.classList.add('active');
    }
    if (overlay) {
      overlay.style.display = 'block';
      overlay.classList.add('active');
    }
  };

  window.closeSpecificModal = function (id) {
    const modal = document.getElementById(id);
    const overlay = document.getElementById('modalOverlay');
    if (modal) {
      modal.style.display = 'none';
      modal.classList.remove('active');
    }
    if (overlay && !document.querySelector('.modal.active')) {
      overlay.style.display = 'none';
      overlay.classList.remove('active');
    }
  };

  window.goback = function () {
    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.location.href = '/home';
    }
  };

  window.togglepass = function (button) {
    if (!button) return;
    const group = button.closest('.passrow') || button.closest('.input-group') || button.parentElement;
    if (!group) return;
    const input = group.querySelector('input[type="password"], input[type="text"]');
    if (!input) return;
    const icon = button.querySelector('i');
    if (input.type === 'password') {
      input.type = 'text';
      if (icon) {
        icon.classList.remove('fa-eye-slash');
        icon.classList.add('fa-eye');
      }
    } else {
      input.type = 'password';
      if (icon) {
        icon.classList.remove('fa-eye');
        icon.classList.add('fa-eye-slash');
      }
    }
  };

  window.addEventListener('popstate', () => {
    window.location.reload();
  });

  window.addEventListener('beforeunload', () => {
    showNavMask();
  });

  document.addEventListener('click', (e) => {
    const drop = document.getElementById('serverDropdown');
    const icon = document.getElementById('serverHeaderIcon');
    if (!drop) return;
    if (e.target.closest('#serverDropdown') || e.target.closest('.server-sidebar-header')) return;
    drop.style.display = 'none';
    if (icon) icon.style.transform = 'rotate(0deg)';
  });

  document.addEventListener('DOMContentLoaded', () => {
    window.MobileApp.init();
  });
})();
