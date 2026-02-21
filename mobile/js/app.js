(function () {
  let dmSource = null;
  let eventSource = null;
  let presenceTimer = null;
  let dmRefreshing = false;
  let navMask = null;
  let lastEventVersion = 0;
  let pullRefreshInit = false;
  let globalRefreshing = false;

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
    navMask.style.background = 'transparent';
    navMask.style.opacity = '0';
    navMask.style.pointerEvents = 'none';
    navMask.style.transition = 'opacity 0.2s ease';
    navMask.style.zIndex = '99999';
    document.body.appendChild(navMask);
    return navMask;
  }

  function showNavMask() {
    const m = ensureNavMask();
    m.style.opacity = '1';
    m.style.pointerEvents = 'auto';
  }
  
  function hideNavMask() {
    if (!navMask) return;
    navMask.style.opacity = '0';
    navMask.style.pointerEvents = 'none';
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
      window.triggerBackgroundRefresh();
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
  
  function swapFromHtml(html, url, replaceOnly, isSubmit) {
    document.querySelectorAll('.modal').forEach(m => m.style.display = 'none');
    document.querySelectorAll('.modal-overlay').forEach(o => o.style.display = 'none');
    
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const nextMain = doc.querySelector('main');
    const currentMain = document.querySelector('main');
    
    if (!nextMain || !currentMain) {
      window.location.href = url;
      return;
    }
    
    document.title = doc.title;
    
    const oldTop = document.querySelector('.topbar');
    if (oldTop) oldTop.remove();

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

    const scripts = doc.querySelectorAll('script');
    scripts.forEach(s => {
        if (!s.src) return;
        if ((s.src.includes('voice.js') || s.src.includes('blackjack.js') || s.src.includes('roulette.js')) && !document.querySelector(`script[src="${s.src}"]`)) {
            const newScript = document.createElement('script');
            newScript.src = s.src;
            document.body.appendChild(newScript);
        }
    });

    const nextUrl = new URL(url, window.location.origin);
    const tgt = nextUrl.pathname + nextUrl.search;
    const now = window.location.pathname + window.location.search;
    
    if (!replaceOnly && now !== tgt) history.pushState({}, '', tgt);
    
    ensureMobileShell();
    updateActiveNav();
    bind();
    hideNavMask();
    
    const newChatContainer = document.querySelector('.chat-messages, .chatbox');
    if (newChatContainer) {
        newChatContainer.scrollTop = newChatContainer.scrollHeight;
    } else if (!replaceOnly && !isSubmit) {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  async function softNavigate(url, replaceOnly) {
    try {
        const res = await fetch(url, { 
            headers: { 
                'X-Requested-With': 'fetch',
                'Cache-Control': 'no-cache, no-store, must-revalidate'
            },
            cache: 'no-store'
        });
        const html = await res.text();
        swapFromHtml(html, res.url || url, !!replaceOnly, false);
    } catch(e) {
        window.location.href = url;
    }
  }

  async function softSubmit(form) {
    try {
        const res = await fetch(form.action || window.location.href, {
          method: (form.method || 'GET').toUpperCase(),
          body: new FormData(form),
          headers: { 
              'X-Requested-With': 'fetch',
              'Cache-Control': 'no-cache, no-store, must-revalidate'
          },
          cache: 'no-store'
        });
        const html = await res.text();
        swapFromHtml(html, res.url || window.location.href, false, true);
    } catch(e) {
        form.submit();
    }
  }

  function ensureMobileShell() {
    const p = window.location.pathname || '';
    if (p.startsWith('/login') || p.startsWith('/register') || p.startsWith('/choose')) return;

    if (document.querySelector('.mobile-nav')) return;

    const nav = document.createElement('nav');
    nav.className = 'mobile-nav';
    nav.innerHTML = `
        <a href="/home" class="nav-item" data-nav="soft">
            <i class="fa-solid fa-house"></i>
            <span>Ana Sayfa</span>
        </a>
        <a href="/dm" class="nav-item" data-nav="soft">
            <i class="fa-solid fa-comment"></i>
            <span>Mesajlar</span>
        </a>
        <a href="/casino" class="nav-item" data-nav="soft">
            <i class="fa-solid fa-dice"></i>
            <span>Casino</span>
        </a>
        <a href="/servers" class="nav-item" data-nav="soft">
            <i class="fa-solid fa-compass"></i>
            <span>Sunucular</span>
        </a>
        <a href="/profile" class="nav-item" data-nav="soft">
            <img src="/mobile/avatar.svg" class="mobile-avatar" id="shellAvatar">
            <span>Profil</span>
        </a>
    `;
    document.body.appendChild(nav);
    
    fetch('/api/nav', { headers: { 'X-Requested-With': 'fetch' } })
        .then(r => r.json())
        .then(d => {
            if(d.avatar) document.getElementById('shellAvatar').src = d.avatar;
        }).catch(()=>{});
        
    updateActiveNav();
  }

  function updateActiveNav() {
      const path = window.location.pathname;
      document.querySelectorAll('.nav-item').forEach(el => {
          el.classList.remove('active');
          const href = el.getAttribute('href');
          if (href === '/home' && (path === '/' || path.startsWith('/home'))) el.classList.add('active');
          else if (href !== '/home' && path.startsWith(href)) el.classList.add('active');
      });
  }

  function bind() {
    ensureMobileShell();
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

    initProfileCrop();
    initDmStream();
    initRecorder();
    initEventStream();
    startPresence();
    initPullToRefresh();
    if (typeof window.initBlackjackPage === 'function') window.initBlackjackPage();
    if (typeof window.initRoulettePage === 'function') window.initRoulettePage();
  }

  function initPullToRefresh() {
    if (pullRefreshInit) return;
    pullRefreshInit = true;

    let startY = 0;
    let pulling = false;
    let triggered = false;
    const threshold = 95;

    let indicator = document.getElementById('pullRefresh');
    if (!indicator) {
      indicator = document.createElement('div');
      indicator.id = 'pullRefresh';
      indicator.innerHTML = '<i class="fa-solid fa-rotate"></i><span>Yenilemek için çek</span>';
      document.body.appendChild(indicator);
    }

    document.addEventListener('touchstart', (e) => {
      if (!e.touches || !e.touches.length) return;
      
      const scrollableNode = e.target.closest('.chatbox, .chat-messages, .server-main, .panel');
      const containerAtTop = scrollableNode ? scrollableNode.scrollTop <= 0 : true;
      const pageAtTop = window.scrollY <= 0 || document.documentElement.scrollTop <= 0;

      if (!pageAtTop || !containerAtTop) return;
      
      startY = e.touches[0].clientY;
      pulling = true;
      triggered = false;
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
      if (!pulling || !e.touches || !e.touches.length) return;
      const dy = e.touches[0].clientY - startY;
      if (dy <= 0) return;
      if (dy > 8) indicator.classList.add('visible');
      if (dy >= threshold && !triggered) {
        triggered = true;
        indicator.innerHTML = '<i class="fa-solid fa-arrows-rotate fa-spin"></i><span>Yenileniyor...</span>';
        showNavMask();
        softNavigate(window.location.href, true)
          .catch(() => { window.location.reload(); })
          .finally(() => {
            indicator.classList.remove('visible');
            indicator.innerHTML = '<i class="fa-solid fa-rotate"></i><span>Yenilemek için çek</span>';
            pulling = false;
            triggered = false;
          });
      }
    }, { passive: true });

    document.addEventListener('touchend', () => {
      if (!triggered) indicator.classList.remove('visible');
      pulling = false;
    }, { passive: true });
  }

  window.triggerBackgroundRefresh = async function() {
      if (globalRefreshing) return;
      const anyModalOpen = Array.from(document.querySelectorAll('.modal')).some(m => m.style.display === 'block');
      if (anyModalOpen) return;
      globalRefreshing = true;
      await softNavigate(window.location.href, true);
      globalRefreshing = false;
  };

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
      window.triggerBackgroundRefresh();
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
  
  document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    if (!document.querySelector('.bg-texture')) {
      document.body.insertAdjacentHTML('afterbegin', '<div class="bg-texture"></div><div class="ambient-orb orb-1"></div><div class="ambient-orb orb-2"></div>');
    }
    document.querySelectorAll('.chat-messages, .chatbox').forEach(b => b.scrollTop = b.scrollHeight);
  });
  
  bind();
})();
