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
    let pending = false;

    function suitChar(s) { if (s === 'H') return '♥'; if (s === 'D') return '♦'; if (s === 'C') return '♣'; return '♠'; }
    function cardHtml(c) {
      if (c.hidden) return '<div class="card back"><i class="fa-solid fa-diamond"></i></div>';
      const red = c.suit === 'H' || c.suit === 'D';
      return '<div class="card ' + (red ? 'red' : 'black') + '"><div class="rank">' + c.rank + '</div><div class="suit">' + suitChar(c.suit) + '</div></div>';
    }
    function animateCards(container) {
      const cards = container.querySelectorAll('.card');
      cards.forEach(function (card, idx) { setTimeout(function () { card.classList.add('in'); }, idx * 85); });
    }

    function setControlState() {
      const turn = phaseEl.textContent === 'player_turn';
      hitBtn.disabled = !turn || pending;
      standBtn.disabled = !turn || pending;
      newBtn.disabled = pending;
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

      dealerWrap.innerHTML = (state.dealer_hand || []).map(cardHtml).join('');
      playerWrap.innerHTML = (state.player_hand || []).map(cardHtml).join('');
      animateCards(dealerWrap);
      animateCards(playerWrap);
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

    async function req(url, method, body) {
      const seq = ++reqSeq;
      pending = true;
      setControlState();
      try {
        const opts = { method: method || 'GET', headers: { 'X-Requested-With': 'fetch' } };
        if (body) {
          opts.headers['Content-Type'] = 'application/json';
          opts.body = JSON.stringify(body);
        }
        const res = await fetch(url, opts);
        const data = await res.json();
        applyLimits(data.limits);
        if (seq !== reqSeq) return null;
        if (!data.ok) {
          console.log('blackjack error', data);
          if (data.error === 'invalid_bet' || data.error === 'invalid_bet_min') msgEl.textContent = 'Minimum bahis 100';
          if (data.error === 'invalid_bet_max') msgEl.textContent = 'Maksimum bahis limiti asildi';
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
      msgEl.textContent = 'dealing';
      const raw = parseInt(betInput.value || '0', 10);
      const bet = Math.max(Number(limits.min_bet || 100), Math.min(Number(limits.max_bet || 100), Number(raw || 0)));
      betInput.value = String(bet);
      const state = await req('/api/casino/blackjack/new', 'POST', { bet: bet });
      if (state) renderState(state);
    };
    hitBtn.onclick = async function () { const state = await req('/api/casino/blackjack/hit', 'POST'); if (state) renderState(state); };
    standBtn.onclick = async function () { const state = await req('/api/casino/blackjack/stand', 'POST'); if (state) renderState(state); };
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
