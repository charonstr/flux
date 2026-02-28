(function () {
  let dmSource = null;
  let eventSource = null;
  let presenceTimer = null;
  let navMask = null;
  let lastEventVersion = 0;
  let globalRefreshing = false;
  let lastRailData = null; 
  let literalI18nMap = null;
  let literalI18nObserver = null;
  let literalI18nFetchStarted = false;
  let refreshQueued = false;
  let refreshCooldownUntil = 0;
  let dmReconnectDelay = 2000;
  let eventReconnectDelay = 2000;

  function hexToRgb(hex) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `${r}, ${g}, ${b}`;
  }

  function applyTheme(theme) {
    const mode = theme === 'light' ? 'light' : 'dark';
    document.body.setAttribute('data-theme', mode);
    localStorage.setItem('theme', mode);

    const styles = getComputedStyle(document.body);
    const panelColor = styles.getPropertyValue('--panel').trim();
    const primaryColor = styles.getPropertyValue('--primary').trim();
    
    document.documentElement.style.setProperty('--panel-rgb', hexToRgb(panelColor));
    document.documentElement.style.setProperty('--primary-rgb', hexToRgb(primaryColor));
  }

  function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light' || saved === 'dark') {
      applyTheme(saved);
      return;
    }
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) {
      applyTheme('light');
      return;
    }
    applyTheme('dark');
  }

  function mapLiteralValue(raw, map) {
    if (!raw) return raw;
    const value = String(raw);
    const trimmed = value.trim();
    if (!trimmed) return value;
    const mapped = map[trimmed];
    if (!mapped || mapped === trimmed) return value;
    const start = value.indexOf(trimmed);
    if (start < 0) return mapped;
    const end = start + trimmed.length;
    return value.slice(0, start) + mapped + value.slice(end);
  }

  function applyLiteralTranslations(root, map) {
    if (!root || !map || !Object.keys(map).length) return;
    const base = root.nodeType === 9 ? (root.body || document.body) : root;
    if (!base) return;

    const attrTargets = base.matches ? [base] : [];
    attrTargets.push(...base.querySelectorAll ? Array.from(base.querySelectorAll('[title], [placeholder], [aria-label]')) : []);
    attrTargets.forEach((el) => {
      ['title', 'placeholder', 'aria-label'].forEach((attr) => {
        if (!el.hasAttribute || !el.hasAttribute(attr)) return;
        const prev = el.getAttribute(attr);
        const next = mapLiteralValue(prev, map);
        if (next !== prev) el.setAttribute(attr, next);
      });
    });

    const walker = document.createTreeWalker(base, NodeFilter.SHOW_TEXT);
    let node = walker.nextNode();
    while (node) {
      const parent = node.parentElement;
      if (parent) {
        const tag = (parent.tagName || '').toUpperCase();
        if (tag !== 'SCRIPT' && tag !== 'STYLE') {
          const prev = node.nodeValue;
          const next = mapLiteralValue(prev, map);
          if (next !== prev) node.nodeValue = next;
        }
      }
      node = walker.nextNode();
    }
  }

  async function ensureLiteralLocalization(root = document) {
    const lang = String(document.documentElement.getAttribute('lang') || '').toLowerCase();
    if (!lang || lang.startsWith('tr')) return;

    if (!literalI18nMap && !literalI18nFetchStarted) {
      literalI18nFetchStarted = true;
      try {
        const res = await fetch('/api/i18n/literals', {
          headers: { 'X-Requested-With': 'fetch' },
          cache: 'force-cache',
        });
        const data = await res.json();
        literalI18nMap = data && data.ok ? (data.map || {}) : {};
      } catch (_) {
        literalI18nMap = {};
      }
    }

    if (!literalI18nMap || !Object.keys(literalI18nMap).length) return;
    applyLiteralTranslations(root, literalI18nMap);

    if (!literalI18nObserver && document.body) {
      literalI18nObserver = new MutationObserver((mutations) => {
        mutations.forEach((m) => {
          m.addedNodes.forEach((n) => {
            if (n && n.nodeType === 1) applyLiteralTranslations(n, literalI18nMap);
          });
        });
      });
      literalI18nObserver.observe(document.body, { childList: true, subtree: true });
    }
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
    const m = ensureNavMask();
    m.style.pointerEvents = 'auto'; 
    m.style.cursor = 'wait'; 
  }
  
  function hideNavMask() {
    if (!navMask) return;
    navMask.style.pointerEvents = 'none'; 
    navMask.style.cursor = 'default';
  }

  function startPresence() {
    if (presenceTimer) clearInterval(presenceTimer);
    presenceTimer = setInterval(() => {
      if (document.hidden) return;
      fetch('/presence/ping', { method: 'POST', headers: { 'X-Requested-With': 'fetch' } }).catch(() => {});
    }, 45000);
  }

  function initProfileCrop() {
    const input = document.getElementById('avatarfile');
    const panel = document.getElementById('croppanel');
    const hidden = document.getElementById('cropval');
    if (!input || !panel || !hidden) return;
    window.setcrop = function (v) { hidden.value = String(v); };
    input.onchange = function () {
      panel.style.display = input.files && input.files.length ? 'block' : 'none';
      if (!input.files || !input.files.length) hidden.value = '0';
    };
  }

  window.triggerBackgroundRefresh = async function() {
      const now = Date.now();
      if (globalRefreshing) {
          refreshQueued = true;
          return;
      }
      if (now < refreshCooldownUntil) {
          if (!refreshQueued) {
              refreshQueued = true;
              setTimeout(() => {
                  if (!globalRefreshing) {
                      refreshQueued = false;
                      window.triggerBackgroundRefresh();
                  }
              }, Math.max(50, refreshCooldownUntil - now));
          }
          return;
      }
      const p = window.location.pathname || '';
      if (p.startsWith('/casino/case/')) return;
      
      const anyModalOpen = Array.from(document.querySelectorAll('.modal')).some(m => m.style.display === 'block');
      const ctxOpen = document.getElementById('ctxMenu') && document.getElementById('ctxMenu').style.display === 'flex';
      const dropOpen = document.getElementById('serverDropdown') && document.getElementById('serverDropdown').style.display === 'flex';
      
      if (anyModalOpen || ctxOpen || dropOpen) return;

      globalRefreshing = true;
      refreshCooldownUntil = Date.now() + 2500;
      try {
          await softNavigate(window.location.href, true);
      } finally {
          globalRefreshing = false;
          if (refreshQueued) {
              refreshQueued = false;
              setTimeout(() => window.triggerBackgroundRefresh(), 200);
          }
      }
  };

  function initDmStream() {
    if (dmSource) {
      dmSource.close();
      dmSource = null;
    }
    const box = document.getElementById('dmpage');
    if (!box) return;
    const peer = box.getAttribute('data-peer');
    const convid = box.getAttribute('data-convid');
    const attrLast = Number(box.getAttribute('data-last') || '0');
    let domLast = 0;
    document.querySelectorAll('.chatbox .msg[data-mid], .msg-bubble[data-mid]').forEach((el) => {
      const v = Number(el.getAttribute('data-mid') || '0');
      if (v > domLast) domLast = v;
    });
    const last = String(Math.max(attrLast, domLast));
    if (!peer || !convid) return;

    dmSource = new EventSource(`/dm/stream/${peer}?last=${encodeURIComponent(last)}`);
    dmReconnectDelay = 2000;
    dmSource.onmessage = async (evt) => {
      try {
        const data = JSON.parse(evt.data || '{}');
        if (data.type !== 'update') return;
      } catch {
        return;
      }
      window.triggerBackgroundRefresh();
    };
    dmSource.onerror = () => {
      if (dmSource) dmSource.close();
      dmSource = null;
      dmReconnectDelay = Math.min(dmReconnectDelay * 2, 30000);
      setTimeout(initDmStream, dmReconnectDelay);
    };
  }

  function initRecorder() {
    const startBtn = document.getElementById('voicerecord');
    const wave = document.getElementById('voicewave');
    const form = document.getElementById('dmform');
    if (!startBtn || !wave || !form) return;

    let recorder = null;
    let chunks = [];
    let blob = null;

    startBtn.onclick = async () => {
      if (!recorder || recorder.state === 'inactive') {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        recorder = new MediaRecorder(stream);
        chunks = [];
        recorder.ondataavailable = (e) => chunks.push(e.data);
        recorder.onstop = () => {
          blob = new Blob(chunks, { type: 'audio/webm' });
          form._voiceBlob = blob;
          wave.classList.remove('recording');
        };
        recorder.start();
        wave.classList.add('recording');
        startBtn.textContent = startBtn.getAttribute('data-stop') || 'Stop';
      } else if (recorder.state === 'recording') {
        recorder.stop();
        startBtn.textContent = startBtn.getAttribute('data-start') || 'Record';
      }
    };

    form._voiceBlob = blob;
  }

  function initModal(profileBtn, profileModal, modalOverlay) {
      if (!profileBtn || !profileModal || !modalOverlay) return;

      profileBtn.onclick = (event) => {
          event.stopPropagation();
          const isVisible = profileModal.style.display === 'block';
          if (isVisible) {
              window.closeModal(profileModal, modalOverlay);
          } else {
              profileModal.style.left = '90px'; 
              profileModal.style.top = 'auto';
              profileModal.style.bottom = '20px';
              profileModal.style.display = 'block';
              modalOverlay.style.display = 'block';
          }
      };
  }

  function resetModalStyles(modalElement) {
      if(modalElement) {
          modalElement.style.top = ''; 
          modalElement.style.left = ''; 
          modalElement.style.transform = '';
          modalElement.style.width = '';
          modalElement.style.margin = '';
      }
  }

  window.closeModal = function(profileModal, modalOverlay) {
      if(profileModal) {
          profileModal.style.display = 'none';
          resetModalStyles(profileModal);
      }
      if(modalOverlay) modalOverlay.style.display = 'none';
  };

  window.closeSpecificModal = function(id) {
      const m = document.getElementById(id);
      const o = document.getElementById('modalOverlay');
      if(m) {
          m.style.display = 'none';
          resetModalStyles(m);
      }
      if(o) o.style.display = 'none';
  };

  function ensureProfileLink(doc) {
      const modalContents = doc.querySelectorAll('#profileModal .modal-content');
      modalContents.forEach(content => {
          if (!content.querySelector('a[href="/profile"]')) {
              const profileLink = doc.createElement('a');
              profileLink.href = '/profile';
              profileLink.setAttribute('data-nav', 'soft');
              profileLink.className = 'modal-link';
              profileLink.innerHTML = '<i class="fa-solid fa-user"></i><span>Profilim</span>';
              
              const settingsLink = content.querySelector('a[href="/settings"]');
              if (settingsLink) {
                  content.insertBefore(profileLink, settingsLink);
              } else {
                  content.appendChild(profileLink);
              }
          }
      });
  }

  function injectSPAStyles() {
      if (document.getElementById('spa-styles')) return;
      const style = document.createElement('style');
      style.id = 'spa-styles';
      style.textContent = `
          body.spa-no-anim .panel,
          body.spa-no-anim .tab-content,
          body.spa-no-anim .modern-card,
          body.spa-no-anim .cardrow,
          body.spa-no-anim .modal,
          body.spa-no-anim .dm-panel,
          body.spa-no-anim .chat-panel {
              animation: none !important;
              opacity: 1 !important;
              transform: none !important;
          }
      `;
      document.head.appendChild(style);
  }

  function injectShellStyles() {
      if (document.getElementById('universal-shell-styles')) return;
      const style = document.createElement('style');
      style.id = 'universal-shell-styles';
      style.textContent = `
          body.shell-active { position: relative; overflow: hidden; min-height: 100vh; margin: 0; padding: 0 !important; }
          .server-shell { position: relative; height: 100vh; display: grid; grid-template-columns: 85px 1fr; grid-template-rows: 1fr; }
          .server-rail { grid-row: 1; grid-column: 1; padding: 20px 0; display: flex; flex-direction: column; align-items: center; gap: 15px; background: rgba(var(--panel-rgb), 0.4); backdrop-filter: blur(18px); border-right: 1px solid rgba(var(--line-rgb), 0.5); overflow-y: auto; z-index: 100; }
          .server-rail::-webkit-scrollbar { display: none; }
          .rail-btn-wrapper { position: relative; display: flex; align-items: center; justify-content: center; width: 100%; }
          .rail-btn, .rail-avatar { width: 54px; height: 54px; border-radius: 50%; display: grid; place-items: center; color: var(--text); background: rgba(var(--panel-rgb), 0.8); border: 1px solid rgba(var(--line-rgb), 0.8); transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1); text-decoration: none; font-size: 1.2rem; object-fit: cover; cursor: pointer; }
          .rail-btn-wrapper:hover .rail-btn, .rail-btn-wrapper:hover .rail-avatar, .rail-btn.active { border-radius: 16px; background: var(--primary); color: #fff; border-color: var(--primary); transform: translateY(-2px); box-shadow: 0 8px 20px rgba(var(--primary-rgb), 0.3); }
          .rail-btn-wrapper::before { content: ''; position: absolute; left: 0; width: 4px; height: 0px; background: var(--text); border-radius: 0 4px 4px 0; transition: height 0.3s ease; }
          .rail-btn-wrapper:hover::before { height: 24px; }
          .rail-divider { width: 40px; height: 2px; background: rgba(var(--text-rgb), 0.1); border-radius: 2px; margin: 5px 0; }
          .server-main { grid-row: 1; grid-column: 2; padding: 30px 40px 80px 40px; overflow-y: auto; max-width: 1400px; margin: 0 auto; width: 100%; }
          .server-main::-webkit-scrollbar { width: 8px; }
          .server-main::-webkit-scrollbar-thumb { background: rgba(var(--text-rgb), 0.15); border-radius: 10px; }
          .bg-texture { position: fixed; inset: 0; background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noiseFilter'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.65' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noiseFilter)' opacity='0.05'/%3E%3C/svg%3E"); pointer-events: none; z-index: -1; opacity: 0.5; }
          .ambient-orb { position: fixed; border-radius: 50%; filter: blur(120px); z-index: -2; opacity: 0.25; will-change: transform; }
          .orb-1 { width: 45vw; height: 45vw; background: var(--primary); top: -15%; left: -10%; animation: driftPrimary 30s ease-in-out infinite alternate; }
          .orb-2 { width: 40vw; height: 40vw; background: #818cf8; bottom: -15%; right: -10%; animation: driftPurple 25s ease-in-out infinite alternate; }
          
          /* KUSURSUZ MOBİL UYUM (Alt menü barı) */
          @media(min-width: 901px) {
              .server-shell { display: grid !important; grid-template-columns: 85px 1fr !important; grid-template-rows: 1fr !important; height: 100vh !important; }
              .server-rail { position: relative !important; left: auto !important; top: auto !important; right: auto !important; bottom: auto !important; transform: none !important; width: auto !important; height: auto !important; flex-direction: column !important; margin: 0 !important; border-right: 1px solid rgba(var(--line-rgb), 0.5) !important; border-top: none !important; }
              .server-main { grid-row: 1 !important; grid-column: 2 !important; }
          }
          @media(max-width: 900px) {
              body.shell-active { overflow: auto; padding-bottom: 75px !important; }
              .server-shell { display: block; height: auto; min-height: 100vh;}
              .server-rail { position: fixed; bottom: 0; left: 0; width: 100%; height: 75px; flex-direction: row; justify-content: space-evenly; align-items: center; padding: 0 10px; overflow-x: auto; background: rgba(var(--panel-rgb), 0.95); backdrop-filter: blur(20px); border-top: 1px solid rgba(var(--line-rgb), 0.5); border-right: none; border-bottom: none; z-index: 9999; }
              .rail-divider { width: 2px; height: 30px; margin: 0 2px; }
              .rail-btn-wrapper::before { top: 0; left: 50%; width: 0; height: 4px; border-radius: 0 0 4px 4px; transform: translateX(-50%); transition: width 0.3s ease; }
              .rail-btn-wrapper:hover::before, .rail-btn-wrapper.active::before { width: 24px; height: 4px; }
              .server-main { padding: 15px 15px 20px 15px; }
              .rail-btn, .rail-avatar { width: 46px; height: 46px; font-size: 1.1rem; }
          }
      `;
      document.head.appendChild(style);
  }

  function ensureServerShell() {
      const p = window.location.pathname || '';
      if (p.startsWith('/login') || p.startsWith('/register') || p.startsWith('/choose')) return;

      injectShellStyles();

      if (document.querySelector('.server-shell')) {
          document.body.classList.add('shell-active');
          return;
      }

      document.body.classList.add('shell-active');

      const oldMain = document.querySelector('main');
      const looseContent = Array.from(document.body.children).filter((node) => {
          if (!node || !node.tagName) return false;
          if (node.classList.contains('server-shell')) return false;
          if (node.classList.contains('bg-texture') || node.classList.contains('ambient-orb')) return false;
          if (node.id === 'universal-shell-styles' || node.id === 'spa-styles' || node.id === 'page-style') return false;
          return node.tagName !== 'SCRIPT' && node.tagName !== 'STYLE';
      });
      const oldTopbar = document.querySelector('.topbar');
      
      let avatarSrc = '/pc/avatar.svg';
      if (oldTopbar) {
          const img = oldTopbar.querySelector('.avatar');
          if (img) avatarSrc = img.src;
          oldTopbar.remove(); 
      }

      const shell = document.createElement('div');
      shell.className = 'server-shell';

      const rail = document.createElement('aside');
      rail.className = 'server-rail';
      
      const isHome = p === '/' || p.startsWith('/home') ? 'active' : '';
      const isDm = p.startsWith('/dm') ? 'active' : '';
      const isServers = p.startsWith('/servers') ? 'active' : '';
      const isCasino = p.startsWith('/casino') ? 'active' : '';
      const isFearOfAbyss = p.startsWith('/fear-of-abyss') ? 'active' : '';
      const isAbyssLegacy = p.startsWith('/abyss-legacy') ? 'active' : '';

      rail.innerHTML = `
          <div class="rail-btn-wrapper">
              <a class="rail-btn ${isHome}" href="/" data-nav="soft" title="Ana Sayfa"><i class="fa-solid fa-house"></i></a>
          </div>
          <div class="rail-btn-wrapper">
              <a class="rail-btn ${isDm}" href="/dm" data-nav="soft" title="Mesajlar"><i class="fa-solid fa-paper-plane"></i></a>
          </div>
          <div class="rail-btn-wrapper">
              <a class="rail-btn ${isCasino}" href="/casino" data-nav="soft" title="Casino"><i class="fa-solid fa-dice"></i></a>
          </div>
          <div class="rail-btn-wrapper">
              <a class="rail-btn ${isFearOfAbyss}" href="/fear-of-abyss" data-nav="soft" title="Fear of Abyss"><i class="fa-solid fa-skull"></i></a>
          </div>
          <div class="rail-btn-wrapper">
              <a class="rail-btn ${isAbyssLegacy}" href="/abyss-legacy" data-nav="soft" title="Abyss Legacy"><i class="fa-solid fa-chess"></i></a>
          </div>
          <div class="rail-divider"></div>
          <div class="rail-btn-wrapper">
              <a class="rail-btn ${isServers}" href="/servers" data-nav="soft" title="Sunucular"><i class="fa-solid fa-server"></i></a>
          </div>
          <div style="flex:1;"></div>
          <div class="rail-btn-wrapper">
              <button class="profile-btn rail-btn" id="profileBtn" style="padding:0;">
                  <img src="${avatarSrc}" class="rail-avatar" alt="avatar">
              </button>
          </div>
      `;

      const serverMain = document.createElement('main');
      serverMain.className = 'server-main';
      if (oldMain) {
          oldMain.style.paddingTop = '0';
          serverMain.appendChild(oldMain);
      } else {
          looseContent.forEach((node) => serverMain.appendChild(node));
      }

      shell.appendChild(rail);
      shell.appendChild(serverMain);
      
      if (!document.querySelector('.bg-texture')) {
          document.body.insertAdjacentHTML('afterbegin', `
              <div class="bg-texture"></div>
              <div class="ambient-orb orb-1"></div>
              <div class="ambient-orb orb-2"></div>
          `);
      }

      document.body.appendChild(shell);
  }

  window.updateRailActiveState = function(pathOverride) {
      const newPath = pathOverride || window.location.pathname;
      document.querySelectorAll('.server-rail .rail-btn').forEach(btn => {
          btn.classList.remove('active');
          const href = btn.getAttribute('href');
          if (href) {
              if (href === '/' && (newPath === '/' || newPath.startsWith('/home'))) {
                  btn.classList.add('active');
              } else if (href !== '/' && newPath.startsWith(href)) {
                  btn.classList.add('active');
              }
          }
      });
  };

  async function updateDynamicRail() {
      try {
          const res = await fetch('/api/nav', { 
              headers: { 'X-Requested-With': 'fetch' },
              cache: 'default'
          });
          const data = await res.json();
          if (!data.ok) return;

          const currentDataStr = JSON.stringify(data.servers) + data.avatar;
          if (lastRailData === currentDataStr) {
              window.updateRailActiveState();
              return;
          }
          lastRailData = currentDataStr;

          const rail = document.querySelector('.server-rail');
          if (!rail) return;

          let html = `
              <div class="rail-btn-wrapper">
                  <a class="rail-btn" href="/" data-nav="soft" title="Ana Sayfa"><i class="fa-solid fa-house"></i></a>
              </div>
              <div class="rail-btn-wrapper">
                  <a class="rail-btn" href="/dm" data-nav="soft" title="Mesajlar"><i class="fa-solid fa-paper-plane"></i></a>
              </div>
              <div class="rail-btn-wrapper">
                  <a class="rail-btn" href="/casino" data-nav="soft" title="Casino"><i class="fa-solid fa-dice"></i></a>
              </div>
              <div class="rail-btn-wrapper">
                  <a class="rail-btn" href="/fear-of-abyss" data-nav="soft" title="Fear of Abyss"><i class="fa-solid fa-skull"></i></a>
              </div>
              <div class="rail-btn-wrapper">
                  <a class="rail-btn" href="/abyss-legacy" data-nav="soft" title="Abyss Legacy"><i class="fa-solid fa-chess"></i></a>
              </div>
              <div class="rail-divider"></div>
          `;

          data.servers.forEach(s => {
              html += `
              <div class="rail-btn-wrapper">
                  <a href="/servers/${s.id}" class="rail-btn" data-nav="soft" title="${s.name}" style="padding:0; overflow:hidden;">
                      <img src="${s.avatar}" class="rail-avatar" alt="" style="width:100%; height:100%; border-radius:inherit; object-fit:cover;">
                  </a>
              </div>
              `;
          });

          html += `
              <div class="rail-btn-wrapper">
                  <a class="rail-btn" href="/servers" data-nav="soft" title="Sunucu Keşfet / Oluştur" style="color: #10b981; border-color: rgba(16, 185, 129, 0.3); background: rgba(16, 185, 129, 0.1);"><i class="fa-solid fa-plus"></i></a>
              </div>
              <div style="flex:1;"></div>
              <div class="rail-btn-wrapper">
                  <button class="profile-btn rail-btn" id="profileBtn" style="padding:0; overflow:hidden;">
                      <img src="${data.avatar}" class="rail-avatar" alt="avatar" style="width:100%; height:100%; border-radius:inherit; object-fit:cover;">
                  </button>
              </div>
          `;

          rail.innerHTML = html;

          const profileBtn = document.getElementById('profileBtn');
          const profileModal = document.getElementById('profileModal');
          const modalOverlay = document.getElementById('modalOverlay');
          initModal(profileBtn, profileModal, modalOverlay);

          rail.querySelectorAll('a[data-nav="soft"]').forEach((a) => {
            a.onclick = async (e) => {
              e.preventDefault();
              showNavMask();
              await softNavigate(a.href, false);
            };
          });

          window.updateRailActiveState();
      } catch(e) { }
  }

  function makeDraggable(element) {
      let header = element.querySelector('.modal-header') || element.querySelector('h2') || element;
      if (!header) return;

      header.style.cursor = 'grab';
      
      let pos1 = 0, pos2 = 0, pos3 = 0, pos4 = 0;
      header.onmousedown = dragMouseDown;

      function dragMouseDown(e) {
          if(['INPUT','BUTTON','SELECT','TEXTAREA'].includes(e.target.tagName) || e.target.closest('button')) return;
          e.preventDefault();
          pos3 = e.clientX;
          pos4 = e.clientY;
          document.onmouseup = closeDragElement;
          document.onmousemove = elementDrag;
          header.style.cursor = 'grabbing';
          
          if (element.style.transform !== 'none') {
              let rect = element.getBoundingClientRect();
              element.style.transform = 'none';
              element.style.left = rect.left + 'px';
              element.style.top = rect.top + 'px';
          }
      }

      function elementDrag(e) {
          e.preventDefault();
          pos1 = pos3 - e.clientX;
          pos2 = pos4 - e.clientY;
          pos3 = e.clientX;
          pos4 = e.clientY;
          
          element.style.top = (element.offsetTop - pos2) + "px";
          element.style.left = (element.offsetLeft - pos1) + "px";
      }

      function closeDragElement() {
          document.onmouseup = null;
          document.onmousemove = null;
          header.style.cursor = 'grab';
      }
  }

  window.initDraggableModals = function() {
      document.querySelectorAll('.modal').forEach(modal => {
          if(!modal.dataset.dragInit && modal.id !== 'profileModal') {
              modal.dataset.dragInit = "1";
              makeDraggable(modal);
          }
      });
  };

  // --- KUSURSUZ EVRENSEL SAĞ TIK YÖNETİCİSİ ---
  window.getOrCreateCtxMenu = function() {
      let m = document.getElementById('ctxMenu');
      if (!m) {
          m = document.createElement('div');
          m.id = 'ctxMenu';
          m.className = 'context-menu';
          document.body.appendChild(m);
      } else if (m.parentElement !== document.body) {
          document.body.appendChild(m);
      }
      return m;
  };

  window.closeCtxMenu = function() {
      const m = document.getElementById('ctxMenu');
      if (m) m.style.display = 'none';
  };
  
  window.showChanCtx = function(e, el) {
      e.preventDefault(); e.stopPropagation();
      const m = window.getOrCreateCtxMenu();
      const canManage = el.dataset.canmanage === 'true';
      const sId = location.pathname.split('/')[2];
      let html = '';
      if (canManage) {
          html += `<div class="ctx-item" onclick="window.openEditChan('${el.dataset.id}')"><i class="fa-solid fa-pen"></i> Kanalı Düzenle</div>`;
          html += `<div class="ctx-item" style="color:#ef4444;" onclick="window.deleteChan('${el.dataset.id}', '${sId}')"><i class="fa-solid fa-trash" style="color:#ef4444;"></i> Kanalı Sil</div>`;
      }
      html += `<div class="ctx-item" onclick="window.showInvite()"><i class="fa-solid fa-link"></i> Davet Kodu Al</div>`;
      m.innerHTML = html;
      m.style.display = 'flex'; m.style.left = e.pageX + 'px'; m.style.top = e.pageY + 'px';
  };

  window.showCatCtx = function(e, el) {
      e.preventDefault(); e.stopPropagation();
      const m = window.getOrCreateCtxMenu();
      const canManage = el.dataset.canmanage === 'true';
      const sId = location.pathname.split('/')[2];
      let html = '';
      if (canManage) {
          html += `<div class="ctx-item" onclick="window.openCreateChan('${el.dataset.id}')"><i class="fa-solid fa-hashtag"></i> Kanal Oluştur</div>`;
          html += `<div class="ctx-item" onclick="window.openEditCat('${el.dataset.id}')"><i class="fa-solid fa-pen"></i> Kategoriyi Düzenle</div>`;
          html += `<div class="ctx-item" style="color:#ef4444;" onclick="window.deleteCat('${el.dataset.id}', '${sId}')"><i class="fa-solid fa-trash" style="color:#ef4444;"></i> Kategoriyi Sil</div>`;
      }
      html += `<div class="ctx-item" onclick="window.showInvite()"><i class="fa-solid fa-link"></i> Davet Kodu Al</div>`;
      m.innerHTML = html;
      m.style.display = 'flex'; m.style.left = e.pageX + 'px'; m.style.top = e.pageY + 'px';
  };

  window.showGeneralCtx = function(e, el) {
      if (e.target.closest('.category-block') || e.target.closest('.cat-group')) return; 
      e.preventDefault();
      const m = window.getOrCreateCtxMenu();
      const canManage = el.dataset.canmanage === 'true';
      let html = '';
      if (canManage) {
          html += `<div class="ctx-item" onclick="window.openCreateCat()"><i class="fa-solid fa-folder-plus"></i> Kategori Oluştur</div>`;
      }
      html += `<div class="ctx-item" onclick="window.showInvite()"><i class="fa-solid fa-link"></i> Davet Kodu Al</div>`;
      m.innerHTML = html;
      m.style.display = 'flex'; m.style.left = e.pageX + 'px'; m.style.top = e.pageY + 'px';
  };

  window.deleteChan = async function(id, serverId) {
      if(!confirm("Kanalı silmek istediğinize emin misiniz?")) return;
      window.closeCtxMenu();
      showNavMask();
      await fetch(`/servers/${serverId}/channels/${id}/delete`, { method: 'POST', headers: {'X-Requested-With': 'fetch'} });
      window.triggerBackgroundRefresh();
  };

  window.deleteCat = async function(id, serverId) {
      if(!confirm("Kategoriyi silmek istediğinize emin misiniz? İçindeki kanallar kategorisiz kalacaktır.")) return;
      window.closeCtxMenu();
      showNavMask();
      await fetch(`/servers/${serverId}/categories/${id}/delete`, { method: 'POST', headers: {'X-Requested-With': 'fetch'} });
      window.triggerBackgroundRefresh();
  };

  window.openCreateCat = function() {
      window.closeCtxMenu();
      const m = document.getElementById('createCatModal');
      const o = document.getElementById('modalOverlay');
      if(m && o) { m.style.display = 'block'; o.style.display = 'block'; }
  };

  window.openEditCat = function(id) {
      window.closeCtxMenu();
      const el = document.querySelector(`.category-header[data-id="${id}"]`) || document.querySelector(`.cat-group[data-id="${id}"]`);
      if(!el) return;
      const m = document.getElementById('editCatModal');
      const o = document.getElementById('modalOverlay');
      if(m && o) {
          m.querySelector('form').action = m.querySelector('form').action.replace(/\/categories\/\d+\/edit/, `/categories/${id}/edit`);
          m.querySelector('input[name="name"]').value = el.dataset.name;
          m.querySelector('select[name="kind"]').value = el.dataset.kind;
          m.style.display = 'block'; o.style.display = 'block';
      }
  };

  window.openCreateChan = function(catId) {
      window.closeCtxMenu();
      const m = document.getElementById('createChanModal');
      const o = document.getElementById('modalOverlay');
      if(m && o) {
          if(catId) m.querySelector('select[name="categoryid"]').value = catId;
          m.style.display = 'block'; o.style.display = 'block';
      }
  };

  window.openEditChan = function(id) {
      window.closeCtxMenu();
      const el = document.getElementById(`chan_${id}`);
      if(!el) return;
      const m = document.getElementById('editChanModal');
      const o = document.getElementById('modalOverlay');
      if(m && o) {
          m.querySelector('form').action = m.querySelector('form').action.replace(/\/channels\/\d+\/edit/, `/channels/${id}/edit`);
          m.querySelector('input[name="name"]').value = el.dataset.name;
          m.querySelector('select[name="categoryid"]').value = el.dataset.catid;
          m.querySelector('select[name="kind"]').value = el.dataset.kind;
          m.querySelector('select[name="contentmode"]').value = el.dataset.cm;
          
          const vp = el.dataset.vp.split(',');
          m.querySelectorAll('input[name="visibleperms"]').forEach(cb => cb.checked = vp.includes(cb.value));
          const wp = el.dataset.wp.split(',');
          m.querySelectorAll('input[name="writeperms"]').forEach(cb => cb.checked = wp.includes(cb.value));
          const sp = el.dataset.sp.split(',');
          m.querySelectorAll('input[name="shareperms"]').forEach(cb => cb.checked = sp.includes(cb.value));

          m.style.display = 'block'; o.style.display = 'block';
      }
  };

  window.showInvite = function() {
      window.closeCtxMenu();
      const m = document.getElementById('inviteModal');
      const o = document.getElementById('modalOverlay');
      if(m && o) { m.style.display = 'block'; o.style.display = 'block'; }
  };

  window.copyInviteCode = function(code, btnElement) {
      navigator.clipboard.writeText(code).then(() => {
          const originalHTML = btnElement.innerHTML;
          btnElement.innerHTML = '<i class="fa-solid fa-check"></i> Kopyalandı';
          btnElement.style.background = '#10b981';
          btnElement.style.color = '#fff';
          setTimeout(() => {
              btnElement.innerHTML = originalHTML;
              btnElement.style.background = '';
              btnElement.style.color = '';
          }, 2000);
      }).catch(err => {
          alert("Kopyalama başarısız oldu: " + err);
      });
  };

  window.toggleServerDropdown = function(e) {
      e.preventDefault();
      e.stopPropagation();
      const drop = document.getElementById('serverDropdown');
      const icon = document.getElementById('serverHeaderIcon');
      if(drop) {
          if(drop.style.display === 'flex') {
              drop.style.display = 'none';
              if(icon) icon.style.transform = 'rotate(0deg)';
          } else {
              window.closeCtxMenu();
              drop.style.display = 'flex';
              if(icon) icon.style.transform = 'rotate(180deg)';
          }
      }
  };

  window.openServerSettings = function() {
      const drop = document.getElementById('serverDropdown');
      const icon = document.getElementById('serverHeaderIcon');
      if(drop) drop.style.display = 'none';
      if(icon) icon.style.transform = 'rotate(0deg)';

      const m = document.getElementById('serverSettingsModal');
      const o = document.getElementById('modalOverlay');
      if(m && o) { 
          m.style.display = 'block'; o.style.display = 'block'; 
          const firstBtn = m.querySelector('.tab-side-btn');
          if (firstBtn) firstBtn.click();
      }
  };

  window.switchSettingsTab = function(tabId) {
      document.querySelectorAll('.settings-tab-content').forEach(el => el.classList.remove('active'));
      document.querySelectorAll('.tab-side-btn').forEach(el => el.classList.remove('active'));
      const t = document.getElementById(tabId);
      if(t) t.classList.add('active');
      const b = document.querySelector(`.tab-side-btn[onclick="window.switchSettingsTab('${tabId}')"]`);
      if(b) b.classList.add('active');
  };

  function swapFromHtml(html, url, replaceOnly, isSubmit) {
    injectSPAStyles();
    injectShellStyles();
    
    document.querySelectorAll('.modal').forEach(m => {
        m.style.display = 'none';
        resetModalStyles(m);
    });
    document.querySelectorAll('.modal-overlay').forEach(o => o.style.display = 'none');
    
    document.querySelectorAll('#ctxMenu').forEach(m => m.remove());
    
    const drop = document.getElementById('serverDropdown');
    if (drop) drop.style.display = 'none';

    if (isSubmit || replaceOnly) {
        document.body.classList.add('spa-no-anim');
    } else {
        document.body.classList.remove('spa-no-anim');
    }

    let activeInputName = null;
    let activeInputValue = null;
    if (document.activeElement && document.activeElement.tagName === 'INPUT' && document.activeElement.type === 'text') {
        activeInputName = document.activeElement.name;
        activeInputValue = document.activeElement.value;
    }

    let chatScrollPos = 0;
    let isChatAtBottom = false;
    const oldChatContainer = document.querySelector('.chat-messages, .chatbox');
    if (oldChatContainer) {
        chatScrollPos = oldChatContainer.scrollTop;
        isChatAtBottom = (oldChatContainer.scrollHeight - oldChatContainer.scrollTop - oldChatContainer.clientHeight) < 50;
    }

    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    
    document.title = doc.title;
    ensureProfileLink(doc);
    
    const styleNodes = Array.from(doc.head.querySelectorAll('style'))
      .filter((s) => !/themeboot/i.test(s.textContent || '') && !/html\s*\{\s*background/i.test(s.textContent || ''));
    const combined = styleNodes.map((s) => s.textContent || '').join('\n');
    let pageStyle = document.head.querySelector('style#page-style');
    if (!pageStyle) {
      pageStyle = document.createElement('style');
      pageStyle.id = 'page-style';
      document.head.appendChild(pageStyle);
    }
    pageStyle.textContent = combined;

    const nextShell = doc.querySelector('.server-shell');
    const currentShell = document.querySelector('.server-shell');

    let scrollPos = 0;
    let scrollTargetSelector = null;
    let activeTabId = null;

    if (currentShell && currentShell.querySelector('.server-main')) {
        scrollTargetSelector = '.server-main';
        scrollPos = currentShell.querySelector('.server-main').scrollTop;
    } else {
        scrollPos = window.scrollY;
    }

    if (isSubmit || replaceOnly) {
        const activeTab = document.querySelector('.tab-content.active');
        if (activeTab) activeTabId = activeTab.id;
    }

    if (!nextShell && currentShell) {
        document.body.classList.add('shell-active');
        const incomingMain = doc.querySelector('main');
        if (incomingMain) {
            const currentMain = currentShell.querySelector('.server-main');
            if (currentMain) {
                currentMain.innerHTML = '';
                incomingMain.style.paddingTop = '0';
                currentMain.appendChild(incomingMain);
            }
        }
    } else if (nextShell && currentShell) {
        document.body.classList.add('shell-active');
        const currentRail = currentShell.querySelector('.server-rail');
        const nextRail = nextShell.querySelector('.server-rail');
        currentShell.replaceWith(nextShell);
        if (currentRail && nextRail) {
            nextRail.replaceWith(currentRail);
        }
    } else {
        const oldMain = document.querySelector('main');
        const incMain = doc.querySelector('main');
        if (oldMain && nextShell) oldMain.replaceWith(nextShell);
        else if (oldMain && incMain) oldMain.replaceWith(incMain);
    }

    const nextUrl = new URL(url, window.location.origin);
    const tgt = nextUrl.pathname + nextUrl.search;
    
    window.updateRailActiveState(tgt);

    const orphans = document.querySelectorAll('body > .modal, body > .modal-overlay');
    orphans.forEach(el => {
        if (!document.querySelector('.server-shell').contains(el)) el.remove();
    });

    const newScripts = doc.querySelectorAll('script');
    newScripts.forEach(s => {
        if (s.src) {
            if (s.src.includes('app.js')) return; 
            const srcUrl = new URL(s.src, window.location.origin).href;
            const existing = Array.from(document.querySelectorAll('script')).find(ex => ex.src && new URL(ex.src, window.location.origin).href === srcUrl);
            
            if (!existing) {
                const newScript = document.createElement('script');
                newScript.src = s.src;
                document.body.appendChild(newScript);
            }
        } else {
            const newScript = document.createElement('script');
            newScript.textContent = s.textContent;
            document.body.appendChild(newScript);
            newScript.remove(); 
        }
    });

    // Ensure page-level initializers run after SPA swaps even if scripts load a bit later.
    const triggerSpaInit = () => {
      try { window.dispatchEvent(new Event('spa-loaded')); } catch (_) {}
      if (typeof window.initVoicePage === 'function') window.initVoicePage();
      if (typeof window.initBlackjackPage === 'function') window.initBlackjackPage();
      if (typeof window.initRoulettePage === 'function') window.initRoulettePage();
      if (typeof window.initCasinoAchievementsPage === 'function') window.initCasinoAchievementsPage();
    };
    triggerSpaInit();
    setTimeout(triggerSpaInit, 60);
    setTimeout(triggerSpaInit, 180);
    setTimeout(triggerSpaInit, 420);

    const now = window.location.pathname + window.location.search;
    if (!replaceOnly && now !== tgt) history.pushState({}, '', tgt);
    
    updateDynamicRail();
    bind();
    hideNavMask();

    if (activeInputName) {
        const newInput = document.querySelector(`input[name="${activeInputName}"]`);
        if (newInput && activeInputValue !== null) {
            newInput.value = activeInputValue;
            newInput.focus({preventScroll: true});
        }
    }

    if (!isSubmit && !replaceOnly) {
        if (scrollTargetSelector) {
            const newMain = document.querySelector(scrollTargetSelector);
            if (newMain) newMain.scrollTop = 0;
        } else {
            window.scrollTo(0, 0);
        }
    }

    const newChatContainer = document.querySelector('.chat-messages, .chatbox');
    if (newChatContainer) {
        if (isSubmit || isChatAtBottom || (!isSubmit && !replaceOnly)) {
            newChatContainer.scrollTop = newChatContainer.scrollHeight;
        } else {
            newChatContainer.scrollTop = chatScrollPos;
        }
    }

    if (!newChatContainer) {
        if (isSubmit || replaceOnly) {
            if (scrollTargetSelector) {
                const newMain = document.querySelector(scrollTargetSelector);
                if (newMain) newMain.scrollTop = scrollPos;
            } else {
                window.scrollTo(0, scrollPos);
            }
        } else {
            if (scrollTargetSelector) {
                const newMain = document.querySelector(scrollTargetSelector);
                if (newMain) newMain.scrollTop = 0;
            } else {
                window.scrollTo(0, 0);
            }
        }
    }
  }

  async function softNavigate(url, replaceOnly) {
    try {
        const res = await fetch(url, { 
            headers: { 
                'X-Requested-With': 'fetch'
            },
            cache: 'default'
        });
        if (!res.ok) throw new Error('Not OK');
        const html = await res.text();
        swapFromHtml(html, res.url || url, !!replaceOnly, false);
    } catch(e) {
        window.location.href = url;
    }
  }

  async function softSubmit(form) {
    try {
        const fd = new FormData(form);
        if (form._voiceBlob) {
            fd.append('voice', form._voiceBlob, 'voice.webm');
            form._voiceBlob = null;
        }
        const res = await fetch(form.action || window.location.href, {
          method: (form.method || 'GET').toUpperCase(),
          body: fd,
          headers: { 
              'X-Requested-With': 'fetch'
          },
          cache: 'default'
        });
        if (!res.ok) throw new Error('Not OK');
        const html = await res.text();
        swapFromHtml(html, res.url || window.location.href, false, true);
    } catch(e) {
        form.submit();
    }
  }

  function bind() {
    ensureServerShell();
    ensureProfileLink(document); 
    ensureLiteralLocalization(document);
    window.initDraggableModals(); 
    
    document.querySelectorAll('.invite-link-span').forEach(span => {
        span.innerText = window.location.origin + '/join/' + span.dataset.code;
    });

    document.querySelectorAll('a[data-nav="soft"]').forEach((a) => {
      a.onclick = async (e) => {
        e.preventDefault();
        showNavMask();
        await softNavigate(a.href, false);
      };
    });
    
    document.querySelectorAll('form[data-nav="soft"]').forEach((form) => {
        form.onsubmit = async (e) => {
          e.preventDefault();
          window.closeCtxMenu();
          const drop = document.getElementById('serverDropdown');
          if (drop) drop.style.display = 'none';
          showNavMask();
          await softSubmit(form);
        };
    });

    document.querySelectorAll('[data-go-back="1"]').forEach((btn) => {
      btn.onclick = () => window.goback();
    });
    document.querySelectorAll('[data-theme-set]').forEach((btn) => {
      btn.onclick = (e) => {
        e.preventDefault();
        applyTheme(btn.getAttribute('data-theme-set'))
      };
    });

    const profileBtn = document.getElementById('profileBtn');
    const profileModal = document.getElementById('profileModal');
    const modalOverlay = document.getElementById('modalOverlay');
    
    initModal(profileBtn, profileModal, modalOverlay);
    
    const globalClose = () => {
        window.closeModal(profileModal, modalOverlay);
        document.querySelectorAll('.modal').forEach(m => {
            m.style.display = 'none';
            resetModalStyles(m);
        });
    };
    if(modalOverlay) modalOverlay.onclick = globalClose;
    window.onscroll = globalClose;

    initProfileCrop();
    initDmStream();
    initRecorder();
    initEventStream();
    startPresence();
    initTabs();
    
    if (typeof window.initVoicePage === 'function') window.initVoicePage();
    if (typeof window.initBlackjackPage === 'function') window.initBlackjackPage();
    if (typeof window.initRoulettePage === 'function') window.initRoulettePage();
  }

  function initTabs() {
    const links = Array.from(document.querySelectorAll('[data-tab]')).filter((el) => el.classList.contains('tab-link') || el.classList.contains('tab-btn') || el.classList.contains('rail-btn'));
    if (!links.length) return;
    const contents = Array.from(document.querySelectorAll('.tab-content'));
    const activate = (name) => {
      contents.forEach((c) => c.classList.toggle('active', c.id === name));
      links.forEach((l) => {
        if (l.classList.contains('tab-link') || l.classList.contains('tab-btn')) {
          l.classList.toggle('active', l.getAttribute('data-tab') === name);
        }
      });
    };
    links.forEach((link) => {
      link.onclick = (e) => {
        e.preventDefault();
        activate(link.getAttribute('data-tab'));
      };
    });
    const current = links.find((l) => l.classList.contains('active')) || links[0];
    if (current) activate(current.getAttribute('data-tab'));
  }

  function initEventStream() {
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }
    eventSource = new EventSource(`/events/stream?last=${encodeURIComponent(String(lastEventVersion || 0))}`);
    eventReconnectDelay = 2000;
    eventSource.onmessage = async (evt) => {
      try {
        const data = JSON.parse(evt.data || '{}');
        if (data.type !== 'refresh') return;
        lastEventVersion = Number(data.version || lastEventVersion || 0);
      } catch {
        return;
      }
      window.triggerBackgroundRefresh();
    };
    eventSource.onerror = () => {
      if (eventSource) eventSource.close();
      eventSource = null;
      eventReconnectDelay = Math.min(eventReconnectDelay * 2, 30000);
      setTimeout(initEventStream, eventReconnectDelay);
    };
  }

  window.goback = function () {
    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.location.href = '/home';
    }
  };

  window.togglepass = function (button) {
    const input = document.getElementById('password');
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

  window.addEventListener('popstate', () => window.location.reload());
  window.addEventListener('beforeunload', () => showNavMask());
  
  document.addEventListener('click', (e) => { 
      if(window.closeCtxMenu) window.closeCtxMenu(); 
      const drop = document.getElementById('serverDropdown');
      const icon = document.getElementById('serverHeaderIcon');
      if (drop && e.target.closest('#serverDropdown') === null && e.target.closest('.server-sidebar-header') === null) {
          drop.style.display = 'none';
          if(icon) icon.style.transform = 'rotate(0deg)';
      }
  });
  
  document.addEventListener('DOMContentLoaded', () => {
      initTheme();
      ensureProfileLink(document);
      updateDynamicRail();
      document.querySelectorAll('.chat-messages, .chatbox').forEach(b => b.scrollTop = b.scrollHeight);
  });
  
  bind();
})();

(function () {
  if (window.createActionEngine) return;

  function wait(ms) {
    return new Promise(function (resolve) { setTimeout(resolve, ms); });
  }

  function isRetryableError(err) {
    const msg = String((err && err.message) || '').toLowerCase();
    return msg.includes('failed to fetch') || msg.includes('network') || msg.includes('timeout');
  }

  window.createActionEngine = function createActionEngine(options) {
    const cfg = options || {};
    const retries = Number(cfg.retries ?? 2);
    const delays = cfg.backoff_ms || [250, 700, 1400];
    const inFlight = new Map();

    async function run(key, task, hooks) {
      const runKey = String(key || '');
      if (!runKey) throw new Error('missing_action_key');
      if (inFlight.has(runKey)) return inFlight.get(runKey);
      const h = hooks || {};
      const runner = (async function () {
        if (typeof h.onPending === 'function') h.onPending();
        let attempt = 0;
        while (true) {
          try {
            const out = await task(attempt);
            if (typeof h.onSettled === 'function') h.onSettled(out);
            return out;
          } catch (err) {
            if (attempt >= retries || !isRetryableError(err)) {
              if (typeof h.onError === 'function') h.onError(err);
              throw err;
            }
            await wait(Number(delays[Math.min(attempt, delays.length - 1)] || 250));
            attempt += 1;
          }
        }
      })().finally(function () { inFlight.delete(runKey); });
      inFlight.set(runKey, runner);
      return runner;
    }

    return { run: run };
  };
})();

