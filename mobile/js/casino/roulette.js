(function () {
  let gameInterval = null;

  async function initRoulettePage(rootSelector) {
    const root = document.querySelector(rootSelector);
    if (!root) return;

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
    const ball = document.getElementById('ball');

    const btnMin = document.getElementById('minBtn');
    const btnMax = document.getElementById('maxBtn');
    const btnUndo = document.getElementById('undoBtn');
    const btnClear = document.getElementById('clearBtn');

    let constants = null;
    let liveBalance = 0;
    let state = null;
    let selectedChip = 10;
    let selectedSpot = null;
    
    let isInitialized = false;
    let phaseTimer = 0;
    let isSpinningLocal = false;

    const FALLBACK_WHEEL = ["0", "32", "15", "19", "4", "21", "2", "25", "17", "34", "6", "27", "13", "36", "11", "30", "8", "23", "10", "5", "24", "16", "33", "1", "20", "14", "31", "9", "22", "18", "29", "7", "28", "12", "35", "3", "26"];
    const FALLBACK_CHIPS = [10, 50, 100, 500, 1000, 5000];

    function getSafeConstants() {
        return constants || {
            wheel: FALLBACK_WHEEL,
            chips: FALLBACK_CHIPS,
            min_bet: 10,
            max_bet: 10000,
            betting_timer_seconds: 20
        };
    }

    function getBallRadii() {
      const size = Number(wheel.getBoundingClientRect().width || 320);
      const end = Math.max(58, Math.round(size * 0.3125));
      const start = Math.max(end + 16, Math.round(size * 0.40625));
      return { start, end };
    }

    function idem(prefix) { return prefix + '_' + Date.now() + '_' + Math.random().toString(16).slice(2, 10); }

    async function api(url, method, body) {
      try {
        const opts = { method: method || 'GET', headers: { 'X-Requested-With': 'fetch' } };
        if (body) {
          opts.headers['Content-Type'] = 'application/json';
          opts.body = JSON.stringify(body);
        }
        const res = await fetch(url, opts);
        const data = await res.json();
        if (data.constants) constants = data.constants;
        if (typeof data.balance !== 'undefined') liveBalance = Number(data.balance || 0);
        if (!data.ok) return null;
        return data;
      } catch (e) { return null; }
    }

    function colorClass(num) {
      if (String(num) === '0' || String(num) === '00') return 'green';
      const redNums = ["1", "3", "5", "7", "9", "12", "14", "16", "18", "19", "21", "23", "25", "27", "30", "32", "34", "36"];
      return redNums.includes(String(num))  'red' : 'black';
    }

    function getSpotSum(type, sel) {
      const key = type + ':' + sel.join(',');
      let sum = 0;
      (state.bets || []).forEach(b => { if (b.bet_type + ':' + (b.selection || []).join(',') === key) sum += Number(b.amount || 0); });
      return sum;
    }

    function buildTable() {
      const grid = [[3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],[2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],[1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]];
      let html = '<div class="table-layout"><div class="numbers-section"><div class="zero-wrap"><div class="num-cell green" data-type="straight" data-selection="0">0</div></div><div class="grid-wrap"><div class="table-grid">';
      grid.forEach(row => row.forEach(n => html += `<div class="num-cell ${colorClass(n)}" data-type="straight" data-selection="${n}">${n}</div>`));
      html += '</div></div></div><div class="outside-grid">';
      [['even', 'CIFT'], ['odd', 'TEK'], ['red', 'KIRMIZI'], ['black', 'SIYAH']].forEach(x => html += `<div class="bet-cell" data-type="${x[0]}" data-selection="${x[0]}">${x[1]}</div>`);
      html += '</div></div>';
      tableWrap.innerHTML = html;

      tableWrap.querySelectorAll('[data-type]').forEach(el => {
        el.onclick = async function () {
          if (!state || state.state !== 'betting_open' || phaseTimer <= 0) return;
          const betType = el.getAttribute('data-type');
          const selection = [el.getAttribute('data-selection')];
          selectedSpot = { betType, selection };
          const payload = { bet_type: betType, selection, amount: Number(selectedChip), idempotency_key: idem('place') };
          const res = await api('/api/casino/roulette/place', 'POST', payload);
          if (res) { state = res.state; render(); }
        };
      });
    }

    function updateTableBets() {
      tableWrap.querySelectorAll('[data-type]').forEach(el => {
        const sum = getSpotSum(el.getAttribute('data-type'), [el.getAttribute('data-selection')]);
        let stack = el.querySelector('.chip-stack');
        if (sum > 0) {
          if (!stack) { stack = document.createElement('span'); stack.className = 'chip-stack'; el.appendChild(stack); }
          if (stack.textContent !== String(sum)) stack.textContent = String(sum);
        } else { if (stack) stack.remove(); }
      });
      tableWrap.querySelectorAll('.winner').forEach(el => el.classList.remove('winner'));
      if (state && state.result_pocket && (state.state === 'finished' || Boolean(state.settled) || state.state === 'result_revealed')) {
        const winEl = tableWrap.querySelector(`[data-type="straight"][data-selection="${state.result_pocket}"]`);
        if (winEl) winEl.classList.add('winner');
      }
    }

    function buildChips() {
      const cfg = getSafeConstants();
      const minBet = Number(cfg.min_bet || 100);
      const maxBet = Number(cfg.max_bet || 0);
      let arr = (cfg.chips || []).filter(function(v) { return Number(v) >= minBet && Number(v) <= maxBet; });
      if (!arr.length && maxBet >= minBet) arr = [minBet];
      chipBar.innerHTML = '';
      arr.forEach(v => {
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'chip-btn' + (Number(v) === Number(selectedChip)  ' active' : '');
        b.textContent = String(v); b.setAttribute('data-val', String(v));
        b.onclick = function () { selectedChip = Number(v); updateChips(); };
        chipBar.appendChild(b);
      });
      if (Number(selectedChip) < minBet || Number(selectedChip) > maxBet) selectedChip = Number(arr[0] || minBet);
    }

    function updateChips() {
      chipBar.querySelectorAll('.chip-btn').forEach(btn => {
        if (Number(btn.getAttribute('data-val')) === Number(selectedChip)) btn.classList.add('active');
        else btn.classList.remove('active');
      });
    }

    function buildWheel() {
      const arr = getSafeConstants().wheel;
      const total = arr.length || 1;
      wheelTrack.innerHTML = '';
      arr.forEach((n, idx) => {
        const seg = document.createElement('div');
        seg.className = 'pocket'; seg.setAttribute('data-num', String(n));
        seg.style.transform = `rotate(${(360 / total) * idx}deg)`;
        seg.style.background = colorClass(n) === 'red'  '#dc2626' : (colorClass(n) === 'green'  '#059669' : '#111827');
        wheelTrack.appendChild(seg);
      });
    }

    function placeBallOnPocket(pocket) {
      const arr = getSafeConstants().wheel;
      if (!ball || !arr) return;
      if (ball.getAnimations) ball.getAnimations().forEach(function(a) { a.cancel(); });
      const idx = arr.indexOf(String(pocket));
      if (idx < 0) return;
      const angle = (360 / arr.length) * idx;
      const radii = getBallRadii();
      ball.style.setProperty('--ball-start', `${radii.start}px`);
      ball.style.setProperty('--ball-end', `${radii.end}px`);
      ball.style.animation = 'none';
      ball.style.transform = `translate(-50%, -50%) rotate(${angle}deg) translateX(${radii.end}px) rotate(${-angle}deg)`;
    }

    function resetBallPosition() {
      if (!ball) return;
      if (ball.getAnimations) ball.getAnimations().forEach(function(a) { a.cancel(); });
      const radii = getBallRadii();
      ball.style.setProperty('--ball-start', `${radii.start}px`);
      ball.style.setProperty('--ball-end', `${radii.end}px`);
      ball.style.animation = 'none';
      ball.style.transform = `translate(-50%, -50%) rotate(0deg) translateX(${radii.start}px) rotate(0deg)`;
    }

    function animateBallToPocket(targetAngle, durationMs) {
      if (!ball) return;
      if (ball.getAnimations) ball.getAnimations().forEach(function(a) { a.cancel(); });
      const endRot = -2160 + targetAngle;
      const radii = getBallRadii();
      ball.style.setProperty('--ball-start', `${radii.start}px`);
      ball.style.setProperty('--ball-end', `${radii.end}px`);
      ball.animate(
        [
          { transform: `translate(-50%, -50%) rotate(0deg) translateX(${radii.start}px) rotate(0deg)` },
          { transform: `translate(-50%, -50%) rotate(${endRot}deg) translateX(${radii.end}px) rotate(${-endRot}deg)` }
        ],
        { duration: durationMs, easing: 'cubic-bezier(0.1, 0.7, 0.1, 1)', fill: 'forwards' }
      );
    }

    function render() {
      if (!state) return;
      if(balanceText) balanceText.textContent = String(Number(liveBalance || getSafeConstants().balance || 0));
      
      const stMap = { 'betting_open': 'BAHISLER ACIK', 'betting_locked': 'BAHISLER KAPALI', 'spinning': 'CEVRILIYOR', 'result_revealed': 'SONUCLANDI', 'settling': 'SONUCLANDI', 'finished': 'SONUCLANDI' };
      if (stateText && !stateText.textContent.includes("BASLIYOR") && !stateText.textContent.includes("BEKLENIYOR")) stateText.textContent = stMap[state.state] || state.state;
      if(timerText) timerText.textContent = String(phaseTimer);
      
      let resColorTr = state.result_color === 'red'  'KIRMIZI' : (state.result_color === 'black'  'SIYAH' : (state.result_color === 'green'  'YESIL' : ''));
      if(resultText) resultText.textContent = state.result_pocket  (String(state.result_pocket) + ' ' + resColorTr) : '-';
      if(totalBetText) totalBetText.textContent = String(Number(state.total_bet || 0));
      
      if (!isInitialized) { buildChips(); buildTable(); buildWheel(); isInitialized = true; }
      updateTableBets(); updateChips();

      if (state.result_pocket && (state.state === 'finished' || Boolean(state.settled) || state.state === 'result_revealed')) placeBallOnPocket(state.result_pocket);

      const bettingOpen = state.state === 'betting_open' && phaseTimer > 0;
      if(btnMin) btnMin.disabled = !bettingOpen;
      if(btnMax) btnMax.disabled = !bettingOpen;
      if(btnUndo) btnUndo.disabled = !bettingOpen;
      if(btnClear) btnClear.disabled = !bettingOpen;
    }

    async function runSpinFlow() {
      if (!state || isSpinningLocal) return;
      isSpinningLocal = true;
      if(stateText) stateText.textContent = "BAHISLER KAPALI";
      render();
      
      const locked = await api('/api/casino/roulette/lock', 'POST', { idempotency_key: idem('lock') });
      if (locked) state = locked.state;
      render();

      if(stateText) stateText.textContent = "CEVRILIYOR";
      const spun = await api('/api/casino/roulette/spin', 'POST', { idempotency_key: idem('spin') });
      if (!spun) { isSpinningLocal = false; return; }
      state = spun.state;
      
      const arr = getSafeConstants().wheel;
      let targetAngle = 0;
      if (state.result_pocket && arr) {
          const targetIdx = arr.indexOf(String(state.result_pocket));
          if (targetIdx >= 0 && ball) {
              targetAngle = (360 / arr.length) * targetIdx;
              ball.style.setProperty('--end-rot', (-2160 + targetAngle) + 'deg');
          }
      }

      if(wheel) {
          wheel.classList.remove('spinfx');
          if (ball) { ball.style.animation = ''; ball.style.transform = ''; }
          void wheel.offsetWidth;
          wheel.classList.add('spinfx');
      }
      animateBallToPocket(targetAngle, 5000);
      render();
      
      setTimeout(async function () {
        const settled = await api('/api/casino/roulette/settle', 'POST', { idempotency_key: idem('settle') });
        if (settled) state = settled.state;
        isSpinningLocal = false;
        phaseTimer = 6;
        if(stateText) stateText.textContent = "SONUCLANDI";
        if (state && state.result_pocket) placeBallOnPocket(state.result_pocket);
        render();
      }, 5100);
    }

    async function gameLoop() {
      if (isSpinningLocal) return;

      if (!state) {
          if(stateText) stateText.textContent = "YENI TUR BASLIYOR...";
          const res = await api('/api/casino/roulette/start', 'POST', { idempotency_key: idem('start') });
          if (res) {
            state = res.state;
            phaseTimer = Math.max(0, Number(state.remaining_seconds || getSafeConstants().betting_timer_seconds));
            if(wheel) wheel.classList.remove('spinfx');
            resetBallPosition(); render();
          }
          return;
      }

      if (['settled', 'finished', 'result_revealed'].includes(state.state)) {
        if (phaseTimer > 0) {
          phaseTimer--;
          if(stateText) stateText.textContent = "YENI TUR BEKLENIYOR...";
          render();
        } else {
          if(stateText) stateText.textContent = "YENI TUR BASLIYOR...";
          const res = await api('/api/casino/roulette/start', 'POST', { idempotency_key: idem('start') });
          if (res) {
            state = res.state;
            phaseTimer = Math.max(0, Number(state.remaining_seconds || getSafeConstants().betting_timer_seconds));
            if(wheel) wheel.classList.remove('spinfx');
            resetBallPosition(); render();
          }
        }
      } else if (state.state === 'betting_open') {
        if (phaseTimer > 0) {
          phaseTimer--;
          if(stateText) stateText.textContent = "BAHISLER ACIK";
          render(); 
        } else {
          render(); 
          if (Number(state.total_bet || 0) > 0) {
            runSpinFlow();
          } else {
            if(stateText) stateText.textContent = "YENI TUR BASLIYOR...";
            const res = await api('/api/casino/roulette/start', 'POST', { idempotency_key: idem('start') });
            if (res) {
              state = res.state;
              phaseTimer = Math.max(0, Number(state.remaining_seconds || getSafeConstants().betting_timer_seconds));
              if(wheel) wheel.classList.remove('spinfx');
              resetBallPosition(); render();
            }
          }
        }
      } else if (['betting_locked', 'spinning', 'settling'].includes(state.state)) {
          runSpinFlow();
      }
    }

    if(btnMin) btnMin.onclick = function () { selectedChip = Number(getSafeConstants().min_bet); updateChips(); };
    if(btnMax) btnMax.onclick = function () {
      if (selectedSpot) {
        const now = getSpotSum(selectedSpot.betType, selectedSpot.selection);
        selectedChip = Math.max(Number(getSafeConstants().min_bet), Number(getSafeConstants().max_bet) - now);
      } else { selectedChip = Number(getSafeConstants().max_bet); }
      updateChips();
    };
    if(btnUndo) btnUndo.onclick = async function () { const res = await api('/api/casino/roulette/undo', 'POST', { idempotency_key: idem('undo') }); if(res) { state = res.state; render(); } };
    if(btnClear) btnClear.onclick = async function () { const res = await api('/api/casino/roulette/clear', 'POST', { idempotency_key: idem('clear') }); if(res) { state = res.state; render(); } };

    api('/api/casino/roulette/state', 'GET').then(res => {
        if (res) {
            state = res.state;
            phaseTimer = state.state === 'betting_open'  Math.max(0, Number(state.remaining_seconds || getSafeConstants().betting_timer_seconds)) : 0;
            render(); 
        }
    });

    if (gameInterval) clearInterval(gameInterval);
    gameInterval = setInterval(gameLoop, 1000);
  }

  window.initRoulettePage = function () { initRoulettePage('.roulette-root'); };
  
  // SPA guvenli entegrasyon
  window.addEventListener('spa-loaded', window.initRoulettePage);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', window.initRoulettePage);
  else window.initRoulettePage();
})();
