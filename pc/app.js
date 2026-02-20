(function () {
  let dmSource = null;
  let presenceTimer = null;
  let dmRefreshing = false;

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

    form.addEventListener('submit', async (e) => {
      if (!blob) return;
      e.preventDefault();
      const fd = new FormData(form);
      fd.append('voice', blob, 'voice.webm');
      const res = await fetch(form.action || window.location.href, { method: 'POST', body: fd, headers: { 'X-Requested-With': 'fetch' } });
      const html = await res.text();
      blob = null;
      swapFromHtml(html, res.url || window.location.href, false);
    });
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
    currentMain.replaceWith(nextMain);
    document.title = doc.title;

    const nextUrl = new URL(url, window.location.origin);
    const tgt = nextUrl.pathname + nextUrl.search;
    const now = window.location.pathname + window.location.search;
    if (!replaceOnly && now !== tgt) history.pushState({}, '', tgt);
    bind();
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
    document.querySelectorAll('a[data-nav="soft"]').forEach((a) => {
      a.onclick = async (e) => { e.preventDefault(); await softNavigate(a.href, false); };
    });
    document.querySelectorAll('form[data-nav="soft"]').forEach((form) => {
      form.onsubmit = async (e) => { e.preventDefault(); await softSubmit(form); };
    });
    document.querySelectorAll('[data-go-back="1"]').forEach((btn) => {
      btn.onclick = () => window.goback();
    });

    initProfileCrop();
    initDmStream();
    initRecorder();
    startPresence();
  }

  window.goback = function () {
    if (window.history.length > 1) {
      window.history.back();
    } else {
      softNavigate('/', false);
    }
  };

  window.togglepass = function () {
    const input = document.getElementById('password');
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
  };

  window.addEventListener('popstate', () => softNavigate(window.location.href, true));
  bind();
})();

