(function () {
  let gameInterval = null;

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
    const ballRadiusPx = 100;

    // SUNUCU BEKLEMEDEN MASAYI KURMAK İÇİN SABİT YEDEKLER
    const FALLBACK_WHEEL = ["0", "32", "15", "19", "4", "21", "2", "25", "17", "34", "6", "27", "13", "36", "11", "30", "8", "23", "10", "5", "24", "16", "33", "1", "20", "14", "31", "9", "22", "18", "29", "7", "28", "12", "35", "3", "26"];
    const FALLBACK_CHIPS = [10, 50, 100, 500, 1000, 5000];

    function idem(prefix) {
      return prefix + '_' + Date.now() + '_' + Math.random().toString(16).slice(2, 10);
    }

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
      } catch (e) {
        return null;
      }
    }

    function colorClass(num) {
      if (String(num) === '0' || String(num) === '00') return 'green';
      const redNums = ["1", "3", "5", "7", "9", "12", "14", "16", "18", "19", "21", "23", "25", "27", "30", "32", "34", "36"];
      return redNums.includes(String(num)) ? 'red' : 'black';
    }

    function getSpotSum(type, sel) {
      const key = type + ':' + sel.join(',');
      let sum = 0;
      (state?.bets || []).forEach(function (b) {
        const k = b.bet_type + ':' + (b.selection || []).join(',');
        if (k === key) sum += Number(b.amount || 0);
      });
      return sum;
    }

    function buildTable() {
      const grid = [
          [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],
          [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
          [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34]
      ];
      
      let html = '<div class="table-layout">';
      html += '<div class="numbers-section">';
      html += '<div class="zero-wrap"><div class="num-cell green" data-type="straight" data-selection="0">0</div></div>';
      html += '<div style="flex:1;"><div class="table-grid">';
      grid.forEach(function(row) {
          row.forEach(function(n) {
              html += '<div class="num-cell ' + colorClass(n) + '" data-type="straight" data-selection="' + n + '">' + n + '</div>';
          });
      });
      html += '</div></div></div>';

      html += '<div class="outside-grid">';
      const simpleOutsideBets = [['even', 'ÇİFT'], ['odd', 'TEK'], ['red', 'KIRMIZI'], ['black', 'SİYAH']];
      simpleOutsideBets.forEach(function(x) {
          html += '<div class="bet-cell" data-type="' + x[0] + '" data-selection="' + x[0] + '">' + x[1] + '</div>';
      });
      html += '</div></div>';
      tableWrap.innerHTML = html;

      tableWrap.querySelectorAll('[data-type]').forEach(function (el) {
        el.onclick = async function () {
          if (!state || state.state !== 'betting_open' || phaseTimer <= 0) return;
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
    }

    function updateTableBets() {
      tableWrap.querySelectorAll('[data-type]').forEach(function (el) {
        const type = el.getAttribute('data-type');
        const selection = [el.getAttribute('data-selection')];
        const sum = getSpotSum(type, selection);

        let stack = el.querySelector('.chip-stack');
        if (sum > 0) {
          if (!stack) {
            stack = document.createElement('span');
            stack.className = 'chip-stack';
            el.appendChild(stack);
          }
          if (stack.textContent !== String(sum)) stack.textContent = String(sum);
        } else {
          if (stack) stack.remove();
        }
      });

      tableWrap.querySelectorAll('.winner').forEach(function(el) { el.classList.remove('winner'); });
      const canShowWinner = state && state.result_pocket && (state.state === 'finished' || Boolean(state.settled) || state.state === 'result_revealed');
      if (canShowWinner) {
        const pocket = String(state.result_pocket);
        const winEl = tableWrap.querySelector('[data-type="straight"][data-selection="' + pocket + '"]');
        if (winEl) winEl.classList.add('winner');
      }
    }

    function buildChips() {
      const arr = constants?.chips || FALLBACK_CHIPS;
      chipBar.innerHTML = '';
      arr.forEach(function (v) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'chip-btn' + (Number(v) === Number(selectedChip) ? ' active' : '');
        b.textContent = String(v);
        b.setAttribute('data-val', String(v));
        b.onclick = function () {
          selectedChip = Number(v);
          updateChips();
        };
        chipBar.appendChild(b);
      });
    }

    function updateChips() {
      chipBar.querySelectorAll('.chip-btn').forEach(function(btn) {
        if (Number(btn.getAttribute('data-val')) === Number(selectedChip)) {
          btn.classList.add('active');
        } else {
          btn.classList.remove('active');
        }
      });
    }

    function buildWheel() {
      const arr = constants?.wheel || FALLBACK_WHEEL;
      const total = arr.length || 1;
      wheelTrack.innerHTML = '';
      arr.forEach(function (n, idx) {
        const angle = (360 / total) * idx;
        const seg = document.createElement('div');
        seg.className = 'pocket';
        seg.setAttribute('data-num', String(n));
        seg.style.transform = 'rotate(' + angle + 'deg)';
        seg.style.background = colorClass(n) === 'red' ? '#dc2626' : (colorClass(n) === 'green' ? '#059669' : '#111827');
        wheelTrack.appendChild(seg);
      });
    }

    function placeBallOnPocket(pocket) {
      const arr = constants?.wheel || FALLBACK_WHEEL;
      if (!ball || !arr) return;
      const idx = arr.indexOf(String(pocket));
      if (idx < 0) return;
      const angle = (360 / arr.length) * idx;
      ball.style.animation = 'none';
      ball.style.transform = `translate(-50%, -50%) rotate(${angle}deg) translateX(${ballRadiusPx}px) rotate(${-angle}deg)`;
    }

    function resetBallPosition() {
      if (!ball) return;
      ball.style.animation = 'none';
      ball.style.transform = 'translate(-50%, -50%) rotate(0deg) translateX(130px) rotate(0deg)';
    }

    function render() {
      if (!state) return;
      
      balanceText.textContent = String(Number(liveBalance || constants?.balance || 0));
      
      const stMap = {
          'betting_open': 'BAHİSLER AÇIK',
          'betting_locked': 'BAHİSLER KAPALI',
          'spinning': 'ÇEVRİLİYOR',
          'result_revealed': 'SONUÇLANDI',
          'settling': 'SONUÇLANDI',
          'finished': 'SONUÇLANDI'
      };
      
      if (!stateText.textContent.includes("BAŞLIYOR") && !stateText.textContent.includes("BEKLENİYOR")) {
          stateText.textContent = stMap[state.state] || state.state;
      }
      
      let resColorTr = '';
      if(state.result_color === 'red') resColorTr = 'KIRMIZI';
      if(state.result_color === 'black') resColorTr = 'SİYAH';
      if(state.result_color === 'green') resColorTr = 'YEŞİL';
      
      resultText.textContent = state.result_pocket ? (String(state.result_pocket) + ' ' + resColorTr) : '-';
      totalBetText.textContent = String(Number(state.total_bet || 0));
      
      if (!isInitialized) {
        buildChips();
        buildTable();
        buildWheel();
        isInitialized = true;
      }
      
      updateTableBets();
      updateChips();

      if (state.result_pocket && (state.state === 'finished' || Boolean(state.settled) || state.state === 'result_revealed')) {
        placeBallOnPocket(state.result_pocket);
      }

      const bettingOpen = state.state === 'betting_open' && phaseTimer > 0;
      if(btnMin) btnMin.disabled = !bettingOpen;
      if(btnMax) btnMax.disabled = !bettingOpen;
      if(btnUndo) btnUndo.disabled = !bettingOpen;
      if(btnClear) btnClear.disabled = !bettingOpen;
    }

    async function runSpinFlow() {
      if (!state || isSpinningLocal) return;
      isSpinningLocal = true;
      
      stateText.textContent = "BAHİSLER KAPALI";
      render();
      
      const locked = await api('/api/casino/roulette/lock', 'POST', { idempotency_key: idem('lock') });
      if (locked) state = locked.state;
      render();

      stateText.textContent = "ÇEVRİLİYOR";
      const spun = await api('/api/casino/roulette/spin', 'POST', { idempotency_key: idem('spin') });
      if (!spun) { isSpinningLocal = false; return; }
      state = spun.state;
      
      const arr = constants?.wheel || FALLBACK_WHEEL;
      if (state.result_pocket && arr) {
          const targetIdx = arr.indexOf(String(state.result_pocket));
          if (targetIdx >= 0) {
              const targetAngle = (360 / arr.length) * targetIdx;
              const endRot = -2160 + targetAngle;
              ball.style.setProperty('--end-rot', endRot + 'deg');
          }
      }

      wheel.classList.remove('spinfx');
      if (ball) {
        ball.style.animation = '';
        ball.style.transform = '';
      }
      void wheel.offsetWidth;
      wheel.classList.add('spinfx');
      render();
      
      setTimeout(async function () {
        const settled = await api('/api/casino/roulette/settle', 'POST', { idempotency_key: idem('settle') });
        if (settled) state = settled.state;
        isSpinningLocal = false;
        phaseTimer = 6;
        stateText.textContent = "SONUÇLANDI";
        if (state && state.result_pocket) placeBallOnPocket(state.result_pocket);
        render();
      }, 5100);
    }

    async function gameLoop() {
      if (isSpinningLocal) return;

      if (!state) {
          stateText.textContent = "YENİ TUR BAŞLIYOR...";
          const res = await api('/api/casino/roulette/start', 'POST', { idempotency_key: idem('start') });
          if (res) {
            state = res.state;
            phaseTimer = Math.max(0, Number(state.remaining_seconds || 20));
            wheel.classList.remove('spinfx');
            resetBallPosition();
            render();
          }
          return;
      }

      if (state.state === 'settled' || state.state === 'finished' || state.state === 'result_revealed') {
        if (phaseTimer > 0) {
          phaseTimer--;
          timerText.textContent = String(phaseTimer);
          stateText.textContent = "YENİ TUR BEKLENİYOR...";
          render();
        } else {
          stateText.textContent = "YENİ TUR BAŞLIYOR...";
          const res = await api('/api/casino/roulette/start', 'POST', { idempotency_key: idem('start') });
          if (res) {
            state = res.state;
            phaseTimer = Math.max(0, Number(state.remaining_seconds || constants?.betting_timer_seconds || 20));
            wheel.classList.remove('spinfx');
            resetBallPosition();
            render();
          }
        }
      } else if (state.state === 'betting_open') {
        if (phaseTimer > 0) {
          phaseTimer--;
          timerText.textContent = String(phaseTimer);
          stateText.textContent = "BAHİSLER AÇIK";
          render(); // Arayüzü ve butonların açıklığını anında senkronize eder
        } else {
          timerText.textContent = "0";
          render(); // Butonları anında kilitle
          if (Number(state.total_bet || 0) > 0) {
            runSpinFlow();
          } else {
            stateText.textContent = "YENİ TUR BAŞLIYOR...";
            const res = await api('/api/casino/roulette/start', 'POST', { idempotency_key: idem('start') });
            if (res) {
              state = res.state;
              phaseTimer = Math.max(0, Number(state.remaining_seconds || constants?.betting_timer_seconds || 20));
              wheel.classList.remove('spinfx');
              resetBallPosition();
              render();
            }
          }
        }
      } else if (state.state === 'betting_locked' || state.state === 'spinning' || state.state === 'settling') {
          // Oyuncu sayfaya ortasında girdiyse dönüşü anında başlat
          runSpinFlow();
      }
    }

    if(btnMin) btnMin.onclick = function () { selectedChip = Number(constants?.min_bet || 10); updateChips(); };
    if(btnMax) btnMax.onclick = function () {
      if (selectedSpot) {
        const now = getSpotSum(selectedSpot.betType, selectedSpot.selection);
        const cap = Number(constants?.max_bet || 10000);
        selectedChip = Math.max(Number(constants?.min_bet || 10), cap - now);
      } else {
        selectedChip = Number(constants?.max_bet || 10000);
      }
      updateChips();
    };
    if(btnUndo) btnUndo.onclick = async function () { const res = await api('/api/casino/roulette/undo', 'POST', { idempotency_key: idem('undo') }); if(res) { state = res.state; render(); } };
    if(btnClear) btnClear.onclick = async function () { const res = await api('/api/casino/roulette/clear', 'POST', { idempotency_key: idem('clear') }); if(res) { state = res.state; render(); } };

    api('/api/casino/roulette/state', 'GET').then(res => {
        if (res) {
            state = res.state;
            if (state.state === 'betting_open') {
                phaseTimer = Math.max(0, Number(state.remaining_seconds || constants?.betting_timer_seconds || 20));
            } else {
                phaseTimer = 0;
            }
            render(); 
        }
    });

    if (gameInterval) clearInterval(gameInterval);
    gameInterval = setInterval(gameLoop, 1000);
  }

  window.initRoulettePage = function () { return initRoulettePage('.roulette-root'); };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { if (window.initRoulettePage) window.initRoulettePage(); });
  } else if (window.initRoulettePage) {
    window.initRoulettePage();
  }
})();