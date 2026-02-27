(function () {
  window.initBlackjackPage = async function initBlackjackPage() {
    const root = document.querySelector('.table-wrap');
    if (!root) return;
    if (root.dataset.bjInit === '1') return;
    root.dataset.bjInit = '1';

    const dealerWrap = document.getElementById('dealerCards');
    const playerWrap = document.getElementById('playerCards');
    const phaseEl = document.getElementById('phase');
    const resultEl = document.getElementById('result');
    const msgEl = document.getElementById('msg');
    const playerTotalEl = document.getElementById('playerTotal');
    const playerTotalBottom = document.getElementById('playerTotalBottom');
    const dealerTotalEl = document.getElementById('dealerTotal');
    const balanceText = document.getElementById('balanceText');
    const betInput = document.getElementById('betInput');
    const betMinBtn = document.getElementById('betMinBtn');
    const betMaxBtn = document.getElementById('betMaxBtn');
    const newBtn = document.getElementById('newBtn');
    const hitBtn = document.getElementById('hitBtn');
    const standBtn = document.getElementById('standBtn');

    let limits = { min_bet: 100, max_bet: 500 };
    let reqSeq = 0;
    let actionEngine = null;
    if (typeof window !== 'undefined' && window.createActionEngine) {
      actionEngine = window.createActionEngine({ retries: 2 });
    }
    
    // SPA Bug Fix: Kapalı veya asılı kalan buton durumu sıfırlanıyor
    let pending = false;
    function idem(prefix) { return prefix + '_' + Date.now() + '_' + Math.random().toString(16).slice(2, 10); }

    function suitChar(s) { if (s === 'H') return '♥'; if (s === 'D') return '♦'; if (s === 'C') return '♣'; return '♠'; }
    
    function cardHtml(c, forcedRot) {
      const rot = forcedRot !== undefined ? forcedRot : (Math.random() * 6 - 3).toFixed(1);
      const rotDeg = rot + 'deg';
      if (c.hidden) return '<div class="card back" data-rot="' + rot + '" style="--rot-deg:' + rotDeg + '"><i class="fa-brands fa-monero"></i></div>';
      const red = c.suit === 'H' || c.suit === 'D';
      const char = suitChar(c.suit);
      return '<div class="card ' + (red ? 'red' : 'black') + '" data-rot="' + rot + '" style="--rot-deg:' + rotDeg + '"><div class="rank">' + c.rank + '</div><div class="suit">' + char + '</div><div class="suit-small">' + char + '</div></div>';
    }

    function animateAllCards() {
      const cards = document.querySelectorAll('.card:not(.in)');
      cards.forEach(function (card, idx) {
        setTimeout(function () {
          card.classList.add('in');
        }, idx * 150 + 50);
      });
    }

    function updateHand(container, hand) {
      if (!hand || hand.length === 0) {
        container.innerHTML = '';
        return;
      }
      if (hand.length < container.children.length) {
        container.innerHTML = '';
      }

      hand.forEach(function(card, i) {
        const existing = container.children[i];
        if (existing) {
          const isBack = existing.classList.contains('back');
          if (isBack && !card.hidden) {
            const oldRot = existing.getAttribute('data-rot');
            const temp = document.createElement('div');
            temp.innerHTML = cardHtml(card, oldRot);
            const newCard = temp.firstChild;
            newCard.classList.add('in');
            newCard.classList.add('flip');
            container.replaceChild(newCard, existing);
          }
        } else {
          const temp = document.createElement('div');
          temp.innerHTML = cardHtml(card);
          container.appendChild(temp.firstChild);
        }
      });
    }

    function setControlState() {
      const phase = String(phaseEl.textContent || 'idle');
      const turn = phase === 'player_turn';
      const activeRound = phase === 'player_turn' || phase === 'dealer_turn';
      hitBtn.disabled = !turn || pending;
      standBtn.disabled = !turn || pending;
      newBtn.disabled = pending || activeRound;
      betInput.disabled = turn || pending;
      if (betMinBtn) betMinBtn.disabled = turn || pending;
      if (betMaxBtn) betMaxBtn.disabled = turn || pending;
    }

    function renderState(state) {
      if (!state) return;
      const ph = state.phase || 'idle';
      phaseEl.textContent = ph;
      msgEl.textContent = state.message || '';
      playerTotalEl.textContent = String(state.player_total ?? 0);
      playerTotalBottom.textContent = String(state.player_total ?? 0);
      dealerTotalEl.textContent = String(state.dealer_visible_total ?? '?');
      const res = String(state.result || '-');
      resultEl.textContent = res;
      resultEl.className = '';
      if (res === 'win' || res === 'blackjack') resultEl.classList.add('result-win');
      else if (res === 'lose') resultEl.classList.add('result-lose');
      else if (res === 'push') resultEl.classList.add('result-push');

      updateHand(dealerWrap, state.dealer_hand);
      updateHand(playerWrap, state.player_hand);
      
      requestAnimationFrame(function() {
          animateAllCards();
      });
      setControlState();
    }

    function applyLimits(next) {
      if (!next) return;
      limits = next;
      if (balanceText) balanceText.textContent = String(Number(limits.balance || 0));
      betInput.min = String(limits.min_bet || 100);
      const maxBet = Number(limits.max_bet || 100);
      if (maxBet < Number(betInput.min)) {
        newBtn.disabled = true;
        msgEl.textContent = 'Bakiye yetersiz';
        return;
      }
      const cur = Number(betInput.value || 0);
      if (!cur || cur < Number(betInput.min)) betInput.value = String(betInput.min);
      if (cur > maxBet) betInput.value = String(maxBet);
      newBtn.disabled = false;
    }

    async function req(url, method, body, actionName) {
      const seq = ++reqSeq;
      pending = true;
      setControlState();
      try {
        const runFetch = async function () {
          const opts = { method: method || 'GET', headers: { 'X-Requested-With': 'fetch' } };
          if (body) {
            opts.headers['Content-Type'] = 'application/json';
            opts.body = JSON.stringify(body);
          }
          const res = await fetch(url, opts);
          return res.json();
        };
        const useEngine = actionEngine && String(method || 'GET').toUpperCase() === 'POST' && actionName && body && body.idempotency_key;
        const data = useEngine
          ? await actionEngine.run(
              'blackjack:' + actionName + ':' + body.idempotency_key,
              async function () { return runFetch(); }
            )
          : await runFetch();
        applyLimits(data.limits);
        if (seq !== reqSeq) return null;
        if (!data.ok) {
          console.log('blackjack error', data);
          if (data.error === 'invalid_bet' || data.error === 'invalid_bet_min') msgEl.textContent = 'Minimum bahis 100';
          if (data.error === 'invalid_bet_max') msgEl.textContent = 'Maksimum bahis limiti aşıldı';
          if (data.error === 'round_in_progress') msgEl.textContent = 'Aktif tur bitmeden tekrar dağıtamazsın';
          return null;
        }
        return data.state;
      } catch (e) {
        console.log('blackjack request error', e);
        return null;
      } finally {
        if (seq === reqSeq) {
          pending = false;
          setControlState();
        }
      }
    }

    newBtn.onclick = async function () {
      msgEl.textContent = 'Kartlar dağıtılıyor...';
      const raw = parseInt(betInput.value || '0', 10);
      const bet = Math.max(Number(limits.min_bet || 100), Math.min(Number(limits.max_bet || 100), Number(raw || 0)));
      betInput.value = String(bet);
      dealerWrap.innerHTML = '';
      playerWrap.innerHTML = '';
      const state = await req('/api/casino/blackjack/new', 'POST', { bet: bet, idempotency_key: idem('bj_new') }, 'new');
      if (state) renderState(state);
    };
    hitBtn.onclick = async function () { const state = await req('/api/casino/blackjack/hit', 'POST', { idempotency_key: idem('bj_hit') }, 'hit'); if (state) renderState(state); };
    standBtn.onclick = async function () { const state = await req('/api/casino/blackjack/stand', 'POST', { idempotency_key: idem('bj_stand') }, 'stand'); if (state) renderState(state); };
    if (betMinBtn) betMinBtn.onclick = function () { betInput.value = String(limits.min_bet || 100); };
    if (betMaxBtn) betMaxBtn.onclick = function () { betInput.value = String(limits.max_bet || 100); };

    const state = await req('/api/casino/blackjack/state', 'GET');
    if (state) renderState(state);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { if (window.initBlackjackPage) window.initBlackjackPage(); });
  } else if (window.initBlackjackPage) {
    window.initBlackjackPage();
  }
})();


