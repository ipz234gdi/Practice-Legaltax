const tg = window.Telegram ? window.Telegram.WebApp : null;
const API_BASE = window.location.origin;

let userId = null;
let username = null;
let currentPage = 'home';
let selectedGroup = null;

const TAX_DATA_2026 = {
  minWage: 8647.00,
  subsistenceMinimum: 3328.00,
  esvMonthly: 1902.34, 
  militaryGroup1_2: 864.70, 
};

window.addEventListener('DOMContentLoaded', async () => {
  if (tg) {
    tg.ready();
    tg.expand();
    const user = tg.initDataUnsafe?.user;
    if (user) {
      userId = user.id;
      username = user.username;
      const welcomeEl = document.getElementById('hero-name');
      if (welcomeEl) welcomeEl.textContent = `${user.first_name || username || 'користувач'}, вітаємо!`;
    }
  } else {
    userId = 999999;
    username = 'test_user';
  }
  navigateTo('home');
  try { lucide.createIcons(); } catch (e) {}
});

function navigateTo(pageId) {
  currentPage = pageId;
  document.querySelectorAll('.page').forEach(page => page.classList.toggle('active', page.id === `page-${pageId}`));
  document.querySelectorAll('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.page === pageId));
  if (pageId === 'requests') loadMyRequests();
  window.scrollTo({ top: 0, behavior: 'smooth' });
  try { if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light'); } catch (e) {}
}

function scrollToAbout() {
  navigateTo('home');
  setTimeout(() => {
    const el = document.getElementById('about-section');
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  }, 100);
}

// Повноцінна односторінкова валідація форми
async function submitForm() {
  const nameEl = document.getElementById('input-name');
  const phoneEl = document.getElementById('input-phone');
  const textEl = document.getElementById('input-text');
  
  const errName = document.getElementById('error-name');
  const errPhone = document.getElementById('error-phone');
  const errText = document.getElementById('error-text');

  let isValid = true;

  if (!nameEl.value.trim()) { errName.style.display = 'block'; isValid = false; } else { errName.style.display = 'none'; }
  if (!phoneEl.value.trim() || phoneEl.value.replace(/[^\d]/g, '').length < 9) { errPhone.style.display = 'block'; isValid = false; } else { errPhone.style.display = 'none'; }
  if (!textEl.value.trim()) { errText.style.display = 'block'; isValid = false; } else { errText.style.display = 'none'; }

  if (!isValid) return;

  try {
    const response = await fetch(`${API_BASE}/api/twa/create-request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: nameEl.value, phone: phoneEl.value, text: textEl.value, user_id: userId })
    });
    if (!response.ok) throw new Error();
    showToast('Заявку успішно надіслано!', 'success');
    nameEl.value = ''; phoneEl.value = ''; textEl.value = '';
    navigateTo('home');
  } catch (err) {
    showToast('Помилка сервера при відправці', 'error');
  }
}

function selectGroup(group) {
  selectedGroup = group;
  document.querySelectorAll('.calc-group-card').forEach(card => card.classList.toggle('active', card.dataset.group === String(group)));
  
  const revInput = document.getElementById('calc-revenue');
  const resultCard = document.getElementById('calc-result');
  resultCard.classList.remove('visible');
  
  if (group === '3_5' || group === '3_3') {
    revInput.classList.add('visible'); // Працює синхронно з CSS правилом .calc-revenue.visible
  } else {
    revInput.classList.remove('visible');
    calculateFixedTax(group);
  }
}

function calculateFixedTax(group) {
  const resultCard = document.getElementById('calc-result');
  const resultRows = document.getElementById('calc-result-rows');
  const note = document.getElementById('calc-result-note');
  
  let ep = group === 1 ? (TAX_DATA_2026.subsistenceMinimum * 0.1) : (TAX_DATA_2026.minWage * 0.2);
  let vz = TAX_DATA_2026.militaryGroup1_2;
  let esv = TAX_DATA_2026.esvMonthly;
  
  resultRows.innerHTML = `
    <div class="result-row"><span>Єдиний податок:</span><strong>${ep.toFixed(2)} ₴/міс</strong></div>
    <div class="result-row"><span>Військовий збір:</span><strong>${vz.toFixed(2)} ₴/міс</strong></div>
    <div class="result-row"><span>ЄСВ (соц. внесок):</span><strong>${esv.toFixed(2)} ₴/міс</strong></div>
    <div class="result-row highlight"><span>Всього на місяць:</span><strong> ${(ep + vz + esv).toFixed(2)} ₴</strong></div>
  `;
  note.textContent = 'Звітність подається раз на рік. Сплата — до 20 числа поточного місяця.';
  resultCard.classList.add('visible');
}

function calculateTax() {
  const revenue = parseFloat(document.getElementById('input-revenue').value) || 0;
  if (revenue <= 0) { showToast('Введіть суму доходу', 'warning'); return; }
  
  const resultCard = document.getElementById('calc-result');
  const resultRows = document.getElementById('calc-result-rows');
  const note = document.getElementById('calc-result-note');
  
  let rate = selectedGroup === '3_5' ? 0.05 : 0.03;
  let singleTax = revenue * rate;
  let vz = revenue * 0.01; 
  let esvQuarter = TAX_DATA_2026.esvMonthly * 3;
  
  resultRows.innerHTML = `
    <div class="result-row"><span>Квартальний дохід:</span><strong>${revenue.toFixed(2)} ₴</strong></div>
    <div class="result-row"><span>Єдиний податок (${rate*100}%):</span><strong>${singleTax.toFixed(2)} ₴</strong></div>
    <div class="result-row"><span>Військовий збір (1%):</span><strong>${vz.toFixed(2)} ₴</strong></div>
    <div class="result-row"><span>ЄСВ за квартал:</span><strong>${esvQuarter.toFixed(2)} ₴</strong></div>
    <div class="result-row highlight"><span>Всього за квартал до сплати:</span><strong> ${(singleTax + vz + esvQuarter).toFixed(2)} ₴</strong></div>
  `;
  note.textContent = 'Розрахунок відповідає вимогам Податкового кодексу на 2026 рік.';
  resultCard.classList.add('visible');
}

async function loadMyRequests() {
  const list = document.getElementById('requests-list');
  list.innerHTML = '';
  try {
    const res = await fetch(`${API_BASE}/api/twa/my-requests?user_id=${userId}`);
    const data = await res.json();
    if(!data.length) return;
    data.forEach(req => {
      list.insertAdjacentHTML('beforeend', `
        <div class="request-card">
          <div class="request-header"><span class="request-date">${new Date(req.created_at).toLocaleDateString()}</span></div>
          <div style="font-size:13px;">${req.text}</div>
        </div>
      `);
    });
  } catch(e){}
}

function showToast(msg) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.style.background = '#131316'; el.style.color = '#fff'; el.style.padding = '10px 16px'; el.style.borderRadius = '8px'; el.style.marginTop = '6px'; el.style.fontSize = '13px';
  el.textContent = msg; container.appendChild(el);
  setTimeout(() => el.remove(), 2500);
}