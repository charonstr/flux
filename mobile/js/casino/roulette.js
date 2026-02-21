(function () {
  async function initRoulettePage(rootSelector) {
    const root = document.querySelector(rootSelector);
    if (!root) return;
    if (root.dataset.rtInit === '1') return;
    root.dataset.rtInit = '1';

    const tableWrap = document.getElementById('rouletteTable');
    if (!tableWrap) return;
    const chipBar = document.getElementById('chipBar');
    const balanceText = document.getElementById('balanceText');
    const stateText = document.getElementById('stateText');
    const timerText = document.getElementById('timerText');
    const resultText = document.getElementById('resultText');
    const totalBetText = document.getElementById('totalBetText');
    const wheel = document.getElementById('wheel');
    const wheelTrack = document.getElementById('wheelTrack');

    const btnNew = document.getElementById('newRoundBtn');
    const btnMin = document.getElementById('minBtn');
    const btnMax = document.getElementById('maxBtn');
    const btnUndo = document.getElementById('undoBtn');
    const btnClear = document.getElementById('clearBtn');
    const btnLock = document.getElementById('lockBtn');
    const btnSpin = document.getElementById('spinBtn');

    let constants = null;\n    let liveBalance = 0;
    let state = null;
    let selectedChip = 10;
    let selectedSpot = null;
    let polling = null;
    let reqLock = false;

    function idem(prefix) {
      return prefix + '_' + Date.now() + '_' + Math.random().toString(16).slice(2, 10);
    }

    async function api(url, method, body) {
      if (reqLock) return null;
      reqLock = true;
      try {
        const opts = { method: method || 'GET', headers: { 'X-Requested-With': 'fetch' } };
        if (body) {
          opts.headers['Content-Type'] = 'application/json';
          opts.body = JSON.stringify(body);
        }
        const res = await fetch(url, opts);
        const data = await res.json();
        if (data.constants) constants = data.constants;\n        if (typeof data.balance !== 'undefined') liveBalance = Number(data.balance || 0);
        if (!data.ok) {
          console.log('roulette error', data);
          return null;
        }
        return data;
      } catch (e) {
        console.log('roulette request error', e);
        return null;
      } finally {
        reqLock = false;
      }
    }

    function colorClass(num) {
      if (!constants || !constants.colors) return 'black';
      const c = constants.colors[String(num)] || 'black';
      return c === 'red' ? 'red' : (c === 'green' ? 'green' : 'black');
    }

    function numberRows() {
      const rows = [];
      for (let i = 0; i < 12; i++) {
        const a = i * 3 + 1;
        rows.push([a, a + 1, a + 2]);
      }
      return rows.reverse();
    }

    function currentSpotTotal(type, selection) {
      const key = type + ':' + selection.join(',');
      let sum = 0;
      (state?.bets || []).forEach(function (b) {
        const k = b.bet_type + ':' + (b.selection || []).join(',');
        if (k === key) sum += Number(b.amount || 0);
      });
      return sum;
    }

    function buildTable() {
      const rows = numberRows();
      let html = '<div class="num-cell green" data-type="straight" data-selection="0">0<span class="chip-stack">' + (currentSpotTotal('straight', ['0']) || '') + '</span></div>';
      html += '<div class="table-grid">';
      rows.forEach(function (r) {
        r.forEach(function (n) {
          const val = currentSpotTotal('straight', [String(n)]);
          html += '<div class="num-cell ' + colorClass(n) + '" data-type="straight" data-selection="' + n + '">' + n + '<span class="chip-stack">' + (val || '') + '</span></div>';
        });
      });
      html += '</div>';
      html += '<div class="outside">';
      [
        ['low', '1-18'], ['even', 'Even'], ['red', 'Red'], ['black', 'Black'], ['odd', 'Odd'], ['high', '19-36'],
        ['dozen1', '1st12'], ['dozen2', '2nd12'], ['dozen3', '3rd12'], ['col1', 'Col1'], ['col2', 'Col2'], ['col3', 'Col3']
      ].forEach(function (x) {
        const val = currentSpotTotal(x[0], [x[0]]);
        html += '<div class="bet-cell" data-type="' + x[0] + '" data-selection="' + x[0] + '">' + x[1] + '<span class="chip-stack">' + (val || '') + '</span></div>';
      });
      html += '</div>';
      tableWrap.innerHTML = html;

      tableWrap.querySelectorAll('[data-type]').forEach(function (el) {
        el.onclick = async function () {
          if (!state || state.state !== 'betting_open') return;
          const betType = el.getAttribute('data-type');
          const selection = [el.getAttribute('data-selection')];
          selectedSpot = { betType: betType, selection: selection };
          const payload = { bet_type: betType, selection: selection, amount: Number(selectedChip), idempotency_key: idem('place') };
          const res = await api('/api/casino/roulette/place', 'POST', payload);
          if (!res) return;
          state = res.state;
          render();
        };
      });

      if (state && state.result_pocket) {
        const pocket = String(state.result_pocket);
        const winEl = tableWrap.querySelector('[data-type="straight"][data-selection="' + pocket + '"]');
        if (winEl) winEl.classList.add('winner');
      }
    }

    function buildChips() {
      if (!constants) return;
      chipBar.innerHTML = '';
      (constants.chips || []).forEach(function (v) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'chip-btn' + (Number(v) === Number(selectedChip) ? ' active' : '');
        b.textContent = String(v);
        b.onclick = function () {
          selectedChip = Number(v);
          buildChips();
        };
        chipBar.appendChild(b);
      });
    }

    function buildWheel() {
      if (!constants) return;
      const wheelOrder = constants.wheel || [];
      const total = wheelOrder.length || 1;
      wheelTrack.innerHTML = '';
      wheelOrder.forEach(function (n, idx) {
        const angle = (360 / total) * idx;
        const seg = document.createElement('div');
        seg.className = 'pocket';
        seg.setAttribute('data-num', String(n));
        seg.style.transform = 'rotate(' + angle + 'deg)';
        const clr = colorClass(n);
        seg.style.background = clr === 'red' ? '#ef4444' : (clr === 'green' ? '#22c55e' : '#111827');
        wheelTrack.appendChild(seg);
      });
    }

    function render() {
      if (!state || !constants) return;
      balanceText.textContent = String(Number(liveBalance || constants.balance || 0));
      stateText.textContent = String(state.state || '-');
      timerText.textContent = String(Number(state.remaining_seconds || 0));
      resultText.textContent = state.result_pocket ? (String(state.result_pocket) + ' ' + (state.result_color || '')) : '-';
      totalBetText.textContent = String(Number(state.total_bet || 0));
      buildChips();
      buildTable();
      buildWheel();

      const bettingOpen = state.state === 'betting_open';
      btnMin.disabled = !bettingOpen;
      btnMax.disabled = !bettingOpen;
      btnUndo.disabled = !bettingOpen;
      btnClear.disabled = !bettingOpen;
      btnLock.disabled = !(state.state === 'betting_open' || state.state === 'betting_locked');
      btnSpin.disabled = !(state.state === 'betting_locked' || state.state === 'result_revealed');
    }

    async function refreshState() {
      const res = await api('/api/casino/roulette/state', 'GET');
      if (!res) return;
      state = res.state;
      render();
    }

    async function runSpinFlow() {
      if (!state) return;
      if (state.state === 'betting_open') {
        const locked = await api('/api/casino/roulette/lock', 'POST', { idempotency_key: idem('lock') });
        if (!locked) return;
        state = locked.state;
        render();
      }
      const spun = await api('/api/casino/roulette/spin', 'POST', { idempotency_key: idem('spin') });
      if (!spun) return;
      state = spun.state;
      wheel.classList.remove('spinfx');
      void wheel.offsetWidth;
      wheel.classList.add('spinfx');
      setTimeout(async function () {
        const settled = await api('/api/casino/roulette/settle', 'POST', { idempotency_key: idem('settle') });
        if (!settled) return;
        state = settled.state;
        render();
      }, 4700);
      render();
    }

    btnNew.onclick = async function () {
      const res = await api('/api/casino/roulette/start', 'POST', { idempotency_key: idem('start') });
      if (!res) return;
      state = res.state;
      render();
    };

    btnMin.onclick = function () {
      selectedChip = Number(constants?.min_bet || 10);
      buildChips();
    };
    btnMax.onclick = function () {
      if (selectedSpot) {
        const now = currentSpotTotal(selectedSpot.betType, selectedSpot.selection);
        const cap = Number(constants?.max_bet || 0);
        const left = Math.max(Number(constants?.min_bet || 0), cap - now);
        selectedChip = left;
      } else {
        selectedChip = Number(constants?.max_bet || 10000);
      }
      buildChips();
    };

    btnUndo.onclick = async function () {
      const res = await api('/api/casino/roulette/undo', 'POST', { idempotency_key: idem('undo') });
      if (!res) return;
      state = res.state;
      render();
    };

    btnClear.onclick = async function () {
      const res = await api('/api/casino/roulette/clear', 'POST', { idempotency_key: idem('clear') });
      if (!res) return;
      state = res.state;
      render();
    };

    btnLock.onclick = async function () {
      const res = await api('/api/casino/roulette/lock', 'POST', { idempotency_key: idem('lock') });
      if (!res) return;
      state = res.state;
      render();
    };

    btnSpin.onclick = runSpinFlow;

    await refreshState();
    if (polling) clearInterval(polling);
    polling = setInterval(function () {
      if (!state || state.state !== 'betting_open') return;
      refreshState();
    }, 500);
  }

  window.initRoulettePage = function () { return initRoulettePage('.wrap'); };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { if (window.initRoulettePage) window.initRoulettePage(); });
  } else if (window.initRoulettePage) {
    window.initRoulettePage();
  }
})();
