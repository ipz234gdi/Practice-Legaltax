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

// ─── DOM Ready ────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  
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

// ─── Theme Toggling ───────────────────────────
function toggleTheme() {
  const isLight = document.body.classList.toggle('light-theme');
  localStorage.setItem('theme', isLight ? 'light' : 'dark');
  updateThemeIcon();
}

function initTheme() {
  const savedTheme = localStorage.getItem('theme');
  const isSystemLight = window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches;
  if (savedTheme === 'light' || (!savedTheme && isSystemLight)) {
    document.body.classList.add('light-theme');
  } else {
    document.body.classList.remove('light-theme');
  }
  updateThemeIcon();
}

function updateThemeIcon() {
  const isLight = document.body.classList.contains('light-theme');
  const iconPath = document.getElementById('theme-icon-path');
  if (iconPath) {
    if (isLight) {
      iconPath.setAttribute('d', 'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m11.314 11.314l.707.707M12 7a5 5 0 100 10 5 5 0 000-10z');
    } else {
      iconPath.setAttribute('d', 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z');
    }
  }
}

// ─── Navigation ───────────────────────────────
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

// ─── Form Submission (With double-click prevention) ───
async function submitForm() {
  const nameEl = document.getElementById('input-name');
  const phoneEl = document.getElementById('input-phone');
  const textEl = document.getElementById('input-text');
  
  const errName = document.getElementById('error-name');
  const errPhone = document.getElementById('error-phone');
  const errText = document.getElementById('error-text');

  const btn = document.querySelector('#page-form button.btn-primary');
  if (btn && btn.disabled) return; 

  let isValid = true;

  if (!nameEl.value.trim()) { errName.style.display = 'block'; isValid = false; } else { errName.style.display = 'none'; }
  if (!phoneEl.value.trim() || phoneEl.value.replace(/[^\d]/g, '').length < 9) { errPhone.style.display = 'block'; isValid = false; } else { errPhone.style.display = 'none'; }
  if (!textEl.value.trim()) { errText.style.display = 'block'; isValid = false; } else { errText.style.display = 'none'; }

  if (!isValid) return;

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Надсилаємо...';
  }

  try {
    const response = await fetch(`${API_BASE}/api/twa/create-request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: nameEl.value, phone: phoneEl.value, text: textEl.value, user_id: userId })
    });
    if (!response.ok) throw new Error();
    showToast('Заявку успішно надіслано!', 'success');
    nameEl.value = ''; phoneEl.value = ''; textEl.value = '';
    
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Надіслати в LegalTax';
    }
    navigateTo('home');
  } catch (err) {
    showToast('Помилка сервера при відправці', 'error');
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Надіслати в LegalTax';
    }
  }
}

// ─── Tax Calculator ───────────────────────────
function selectGroup(group) {
  selectedGroup = group;
  document.querySelectorAll('.calc-group-card').forEach(card => card.classList.toggle('active', card.dataset.group === String(group)));
  
  const revInput = document.getElementById('calc-revenue');
  const resultCard = document.getElementById('calc-result');
  resultCard.classList.remove('visible');
  
  if (group === '3_5' || group === '3_3') {
    revInput.classList.add('visible'); 
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

// ─── Requests Loader ──────────────────────────
async function loadMyRequests() {
  const list = document.getElementById('requests-list');
  const empty = document.getElementById('requests-empty');
  list.innerHTML = '';
  
  try {
    const res = await fetch(`${API_BASE}/api/twa/my-requests?user_id=${userId}`);
    const data = await res.json();
    
    if(!data || !data.length) {
      empty.style.display = 'block';
      return;
    }
    empty.style.display = 'none';
    
    const statusConfig = {
      pending: { text: 'Очікує ⏳', color: '#f59e0b', bg: '#fef3c7' },
      in_progress: { text: 'В роботі ⚙️', color: '#3b82f6', bg: '#dbeafe' },
      completed: { text: 'Виконано ✅', color: '#10b981', bg: '#d1fae5' },
      rejected: { text: 'Відхилено ❌', color: '#ef4444', bg: '#fee2e2' }
    };

    data.forEach(req => {
      const dateObj = new Date(req.created_at);
      const dateStr = dateObj.toLocaleDateString('uk-UA');
      const timeStr = dateObj.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
      
      const currentStatus = statusConfig[req.status] || { text: req.status, color: '#6c727f', bg: '#f4f6f9' };
      
      let replyBlock = '';
      if (req.reply_text) {
        replyBlock = `
          <div style="margin-top:14px; padding:12px; background:#f8fafc; border-left:3px solid #131316; border-radius:4px;">
            <div style="font-size:11px; font-weight:700; color:#131316; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.3px;">Відповідь LegalTax:</div>
            <div style="font-size:12px; color:#334155; line-height:1.5; white-space:pre-line;">${req.reply_text}</div>
          </div>
        `;
      }

      list.insertAdjacentHTML('beforeend', `
        <div class="request-card" style="margin-bottom:14px; background:#ffffff; padding:16px; border:1px solid #ebeeef; border-radius:16px; box-shadow:0 4px 12px rgba(0,0,0,0.01);">
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <span style="font-size:11px; font-weight:600; padding:4px 10px; border-radius:20px; color:${currentStatus.color}; background:${currentStatus.bg};">
              ${currentStatus.text}
            </span>
            <span style="font-size:11px; color:#9aa1b1; font-weight:500;">${dateStr} о ${timeStr}</span>
          </div>
          <div style="font-size:13px; color:#131316; font-weight:500; line-height:1.5; word-break:break-word;">${req.text}</div>
          ${replyBlock}
        </div>
      `);
    });
  } catch(e){
    empty.style.display = 'block';
  }
}

function showToast(msg) {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  el.style.background = '#131316'; el.style.color = '#fff'; el.style.padding = '10px 16px'; el.style.borderRadius = '8px'; el.style.marginTop = '6px'; el.style.fontSize = '13px';
  el.textContent = msg; container.appendChild(el);
  setTimeout(() => el.remove(), 2500);
}