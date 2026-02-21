(function () {
  let dmSource = null;
  let eventSource = null;
  let presenceTimer = null;
  let dmRefreshing = false;
  let navMask = null;
  let lastEventVersion = 0;

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

  function ensureNavMask() {
    if (navMask) return navMask;
    navMask = document.createElement('div');
    navMask.id = 'navmask';
    navMask.style.position = 'fixed';
    navMask.style.inset = '0';
    navMask.style.background = getComputedStyle(document.body).getPropertyValue('--bg') || '#1a202c';
    navMask.style.opacity = '0';
    navMask.style.pointerEvents = 'none';
    navMask.style.transition = 'opacity 120ms ease';
    navMask.style.zIndex = '99999';
    document.body.appendChild(navMask);
    return navMask;
  }

  function showNavMask() {
    const m = ensureNavMask();
    m.style.background = getComputedStyle(document.body).getPropertyValue('--bg') || '#1a202c';
    m.style.opacity = '1';
  }
  
  function hideNavMask() {
    if (!navMask) return;
    navMask.style.opacity = '0';
  }

  function startPresence() {
    if (presenceTimer) clearInterval(presenceTimer);
    presenceTimer = setInterval(() => {
      fetch('/presence/ping', { method: 'POST', headers: { 'X-Requested-With': 'fetch' } }).catch(() => {});
    }, 20000);
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
    document.querySelectorAll('.chatbox .msg[data-mid]').forEach((el) => {
      const v = Number(el.getAttribute('data-mid') || '0');
      if (v > domLast) domLast = v;
    });
    const last = String(Math.max(attrLast, domLast));
    if (!peer || !convid) return;

    dmSource = new EventSource(`/dm/stream/${peer}?last=${encodeURIComponent(last)}`);
    dmSource.onmessage = async (evt) => {
      try {
        const data = JSON.parse(evt.data || '{}');
        if (data.type !== 'update') return;
      } catch {
        return;
      }
      if (dmRefreshing) return;
      dmRefreshing = true;
      await softNavigate(window.location.href, true);
      dmRefreshing = false;
    };
    dmSource.onerror = () => {
      if (dmSource) dmSource.close();
      dmSource = null;
      setTimeout(initDmStream, 2000);
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

  function ensureGlobalSidebarStyle() {
    if (document.getElementById('globalsidebarstyle')) return;
    const style = document.createElement('style');
    style.id = 'globalsidebarstyle';
    style.textContent = `
      body { padding-top: 0 !important; padding-left: 86px !important; }
      #globalsidebar {
        position: fixed;
        top: 0;
        left: 0;
        bottom: 0;
        width: 86px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
        padding: 14px 0;
        background: rgba(var(--panel-rgb), 0.55);
        backdrop-filter: blur(18px);
        border-right: 1px solid rgba(var(--line-rgb), 0.6);
        z-index: 1100;
      }
      #globalsidebar .railbtn {
        width: 52px;
        height: 52px;
        border-radius: 16px;
        display: grid;
        place-items: center;
        text-decoration: none;
        border: 1px solid rgba(var(--line-rgb), 0.75);
        color: var(--text);
        background: rgba(var(--bg-rgb), 0.45);
        transition: all .2s ease;
      }
      #globalsidebar .railbtn:hover,
      #globalsidebar .railbtn.active {
        border-color: var(--primary);
        color: var(--primary);
      }
      #globalsidebar .profilebtn {
        width: 52px;
        height: 52px;
        border-radius: 16px;
        border: 1px solid rgba(var(--line-rgb), 0.75);
        background: rgba(var(--bg-rgb), 0.45);
        padding: 0;
        cursor: pointer;
      }
      #globalsidebar .profilebtn img {
        width: 100%;
        height: 100%;
        border-radius: 16px;
        object-fit: cover;
      }
      #globalsidebar .spacer { flex: 1; }
      main, .wrap { margin-left: auto !important; margin-right: auto !important; }
      .server-rail, .side-rail { display: none !important; }
      @media (max-width: 900px) {
        body { padding-left: 0 !important; }
        #globalsidebar {
          position: static;
          width: 100%;
          height: auto;
          flex-direction: row;
          justify-content: flex-start;
          padding: 10px 12px;
          border-right: none;
          border-bottom: 1px solid rgba(var(--line-rgb), 0.6);
        }
        #globalsidebar .spacer { display: none; }
        main, .wrap { margin-left: auto !important; margin-right: auto !important; }
      }
    `;
    document.head.appendChild(style);
  }

  function ensureGlobalSidebar() {
    const p = window.location.pathname || '';
    if (p.startsWith('/login') || p.startsWith('/register') || p.startsWith('/choose')) return;

    document.querySelectorAll('.topbar').forEach((el) => el.remove());
    ensureGlobalSidebarStyle();
    let bar = document.getElementById('globalsidebar');
    if (bar) return;

    const sourceImg = document.querySelector('.profile-btn img, .avatar');
    const avatar = sourceImg ? sourceImg.getAttribute('src') : '/pc/avatar.svg';
    bar = document.createElement('aside');
    bar.id = 'globalsidebar';
    const onHome = p === '/' || p.startsWith('/home');
    const onDm = p.startsWith('/dm');
    const onServers = p.startsWith('/servers');
    bar.innerHTML = `
      <a class="railbtn ${onHome ? 'active' : ''}" href="/" data-nav="soft" title="Home"><i class="fa-solid fa-house"></i></a>
      <a class="railbtn ${onDm ? 'active' : ''}" href="/dm" data-nav="soft" title="DM"><i class="fa-solid fa-paper-plane"></i></a>
      <a class="railbtn ${onServers ? 'active' : ''}" href="/servers" data-nav="soft" title="Servers"><i class="fa-solid fa-server"></i></a>
      <div class="spacer"></div>
      <button class="profilebtn" id="profileBtn" type="button" title="Profile"><img src="${avatar}" alt="avatar"></button>
    `;
    document.body.prepend(bar);

    if (!document.getElementById('modalOverlay')) {
      const overlay = document.createElement('div');
      overlay.className = 'modal-overlay';
      overlay.id = 'modalOverlay';
      document.body.appendChild(overlay);
    }
    if (!document.getElementById('profileModal')) {
      const modal = document.createElement('div');
      modal.className = 'modal';
      modal.id = 'profileModal';
      modal.innerHTML = `
        <div class="modal-content">
          <div class="lang-switcher">
            <button data-theme-set="light" class="navbtn"><i class="fa-solid fa-sun"></i></button>
            <button data-theme-set="dark" class="navbtn"><i class="fa-solid fa-moon"></i></button>
          </div>
          <a href="/settings" data-nav="soft" class="modal-link"><i class="fa-solid fa-cog"></i><span>Settings</span></a>
          <a href="/logout" data-nav="soft" class="modal-link"><i class="fa-solid fa-right-from-bracket"></i><span>Logout</span></a>
        </div>
      `;
      document.body.appendChild(modal);
    }
  }
  
  function initModal(profileBtn, profileModal, modalOverlay) {
      if (!profileBtn || !profileModal || !modalOverlay) return;

      profileBtn.onclick = (event) => {
          event.stopPropagation();
          const isVisible = profileModal.style.display === 'block';
          if (isVisible) {
              closeModal(profileModal, modalOverlay);
          } else {
              const rect = profileBtn.getBoundingClientRect();
              profileModal.style.left = rect.left + 'px';
              profileModal.style.top = rect.bottom + 5 + 'px';
              profileModal.style.display = 'block';
              modalOverlay.style.display = 'block';
          }
      };
  }

  function closeModal(profileModal, modalOverlay) {
      profileModal.style.display = 'none';
      modalOverlay.style.display = 'none';
  }

  function swapFromHtml(html, url, replaceOnly) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const nextMain = doc.querySelector('main');
    const currentMain = document.querySelector('main');
    if (!nextMain || !currentMain) {
      window.location.href = url;
      return;
    }
    document.title = doc.title;
    
    const nextTopBar = doc.querySelector('.topbar');
    const currentTopBar = document.querySelector('.topbar');
    if(nextTopBar && currentTopBar) currentTopBar.replaceWith(nextTopBar);

    const nextModal = doc.querySelector('.modal');
    const currentModal = document.querySelector('.modal');
    if(nextModal && currentModal) currentModal.replaceWith(nextModal);

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
    
    currentMain.replaceWith(nextMain);

    const nextUrl = new URL(url, window.location.origin);
    const tgt = nextUrl.pathname + nextUrl.search;
    const now = window.location.pathname + window.location.search;
    if (!replaceOnly && now !== tgt) history.pushState({}, '', tgt);
    bind();
    hideNavMask();
  }

  async function softNavigate(url, replaceOnly) {
    const res = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
    const html = await res.text();
    swapFromHtml(html, res.url || url, !!replaceOnly);
  }

  async function softSubmit(form) {
    const res = await fetch(form.action || window.location.href, {
      method: (form.method || 'GET').toUpperCase(),
      body: new FormData(form),
      headers: { 'X-Requested-With': 'fetch' }
    });
    const html = await res.text();
    swapFromHtml(html, res.url || window.location.href, false);
  }

  function bind() {
    ensureGlobalSidebar();
    document.querySelectorAll('a[data-nav="soft"]').forEach((a) => {
      a.onclick = async (e) => {
        e.preventDefault();
        showNavMask();
        await softNavigate(a.href, false);
      };
    });
    document.querySelectorAll('form[data-nav="soft"]').forEach((form) => {
      if (form.id === 'dmform') {
        form.onsubmit = async (e) => {
          e.preventDefault();
          const fd = new FormData(form);
          if (form._voiceBlob) {
            fd.append('voice', form._voiceBlob, 'voice.webm');
            form._voiceBlob = null;
          }
          await fetch(form.action || window.location.href, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'fetch' } });
          const textInput = form.querySelector('input[name="text"]');
          if (textInput) textInput.value = '';
          const fileInput = form.querySelector('input[type="file"]');
          if (fileInput) fileInput.value = '';
        };
      } else {
        form.onsubmit = async (e) => {
          e.preventDefault();
          showNavMask();
          await softSubmit(form);
        };
      }
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
    
    const globalClose = () => closeModal(profileModal, modalOverlay);
    if(modalOverlay) modalOverlay.onclick = globalClose;
    window.onscroll = globalClose;

    initProfileCrop();
    initDmStream();
    initRecorder();
    initEventStream();
    startPresence();
    initTabs();
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
    eventSource.onmessage = async (evt) => {
      try {
        const data = JSON.parse(evt.data || '{}');
        if (data.type !== 'refresh') return;
        lastEventVersion = Number(data.version || lastEventVersion || 0);
      } catch {
        return;
      }
      if (document.hidden) return;
      const tag = (document.activeElement && document.activeElement.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (window.location.pathname.startsWith('/dm')) return;
      await softNavigate(window.location.href, true);
    };
    eventSource.onerror = () => {
      if (eventSource) eventSource.close();
      eventSource = null;
      setTimeout(initEventStream, 2000);
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
  document.addEventListener('DOMContentLoaded', initTheme);
  bind();
})();
