(function () {
  function swapFromHtml(html, url) {
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
    if (window.location.pathname + window.location.search !== new URL(url, window.location.origin).pathname + new URL(url, window.location.origin).search) {
      history.pushState({}, '', url);
    }
    bind();
  }

  async function softNavigate(url) {
    const res = await fetch(url, { headers: { 'X-Requested-With': 'fetch' } });
    const html = await res.text();
    swapFromHtml(html, res.url || url);
  }

  async function softSubmit(form) {
    const res = await fetch(form.action || window.location.href, {
      method: (form.method || 'GET').toUpperCase(),
      body: new FormData(form),
      headers: { 'X-Requested-With': 'fetch' }
    });
    const html = await res.text();
    swapFromHtml(html, res.url || window.location.href);
  }

  function bind() {
    document.querySelectorAll('a[data-nav="soft"]').forEach((a) => {
      a.onclick = async (e) => {
        e.preventDefault();
        await softNavigate(a.href);
      };
    });

    document.querySelectorAll('form[data-nav="soft"]').forEach((form) => {
      form.onsubmit = async (e) => {
        e.preventDefault();
        await softSubmit(form);
      };
    });
  }

  window.togglepass = function () {
    const input = document.getElementById('password');
    if (!input) return;
    input.type = input.type === 'password' ? 'text' : 'password';
  };

  window.addEventListener('popstate', () => softNavigate(window.location.href));
  bind();
})();
