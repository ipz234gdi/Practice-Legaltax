const tg = window.Telegram ? window.Telegram.WebApp : null;
const API_BASE = window.location.origin;

let userId = null;
let username = null;
let firstName = null;
let lastName = null;

let currentPage = 'home';
let currentStep = 1;
let selectedGroup = null;

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
      firstName = user.first_name;
      lastName = user.last_name;
      
      const welcomeName = firstName || username || 'користувач';
      const welcomeEl = document.getElementById('hero-name');
      if (welcomeEl) {
        welcomeEl.textContent = `${welcomeName}, вітаємо!`;
      }
    }
  } else {
    // Fallback for browser testing
    userId = 999999; 
    username = 'test_user';
    firstName = 'Тест';
  }
  
  // Navigate to initial page
  navigateTo('home');
  
  // Render icons
  try {
    lucide.createIcons();
  } catch (e) {}
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

// ─── Update Icon ──────────────────────────────
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
  
  document.querySelectorAll('.page').forEach(page => {
    page.classList.toggle('active', page.id === `page-${pageId}`);
  });
  
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.dataset.page === pageId);
  });
  
  if (pageId === 'requests') {
    loadMyRequests();
  }
  
  window.scrollTo({ top: 0, behavior: 'smooth' });
  
  try {
    if (tg && tg.HapticFeedback) {
      tg.HapticFeedback.impactOccurred('light');
    }
  } catch (e) {}
}

function scrollToAbout() {
  navigateTo('home');
  setTimeout(() => {
    const el = document.getElementById('about-section');
    if (el) {
      el.scrollIntoView({ behavior: 'smooth' });
    }
  }, 100);
}

// ─── Client Form Multi-step ────────────────────
function nextStep() {
  if (currentStep === 1) {
    const name = document.getElementById('input-name').value.trim();
    if (!name) {
      document.getElementById('error-name').classList.add('visible');
      return;
    }
    document.getElementById('error-name').classList.remove('visible');
  } else if (currentStep === 2) {
    const phone = document.getElementById('input-phone').value.trim();
    const cleanPhone = phone.replace(/[^\d+]/g, '');
    if (!cleanPhone || cleanPhone.length < 9) {
      document.getElementById('error-phone').classList.add('visible');
      return;
    }
    document.getElementById('error-phone').classList.remove('visible');
  }
  
  document.getElementById(`form-step-${currentStep}`).classList.remove('active');
  currentStep++;
  document.getElementById(`form-step-${currentStep}`).classList.add('active');
  
  updateStepIndicators();
  
  try {
    tg.HapticFeedback.impactOccurred('medium');
  } catch (e) {}
}

function prevStep() {
  document.getElementById(`form-step-${currentStep}`).classList.remove('active');
  currentStep--;
  document.getElementById(`form-step-${currentStep}`).classList.add('active');
  
  updateStepIndicators();
  
  try {
    tg.HapticFeedback.impactOccurred('light');
  } catch (e) {}
}

function updateStepIndicators() {
  for (let i = 1; i <= 3; i++) {
    const circle = document.getElementById(`step-circle-${i}`);
    if (circle) {
      circle.classList.toggle('active', i <= currentStep);
    }
    const line = document.getElementById(`step-line-${i}`);
    if (line) {
      line.classList.toggle('active', i < currentStep);
    }
  }
}

async function submitForm() {
  const name = document.getElementById('input-name').value.trim();
  const phone = document.getElementById('input-phone').value.trim();
  const text = document.getElementById('input-text').value.trim();
  
  if (!text) {
    document.getElementById('error-text').classList.add('visible');
    return;
  }
  document.getElementById('error-text').classList.remove('visible');
  
  const btn = document.getElementById('btn-submit');
  const originalText = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Надсилаємо...';
  
  try {
    const response = await apiFetch(`${API_BASE}/api/twa/create-request`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: name,
        phone: phone,
        text: text,
        user_id: userId
      })
    });
    
    if (!response.ok) throw new Error();
    
    document.getElementById(`form-step-${currentStep}`).classList.remove('active');
    document.getElementById('form-success').classList.add('visible');
    
    try {
      tg.HapticFeedback.notificationOccurred('success');
    } catch (e) {}
  } catch (err) {
    console.error(err);
    showToast('Помилка відправки форми. Спробуйте пізніше.', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = originalText;
  }
}

function resetForm() {
  document.getElementById('input-name').value = '';
  document.getElementById('input-phone').value = '';
  document.getElementById('input-text').value = '';
  
  document.getElementById('form-success').classList.remove('visible');
  
  currentStep = 1;
  document.getElementById('form-step-1').classList.add('active');
  updateStepIndicators();
  navigateTo('home');
}

// ─── Tax Calculator ───────────────────────────
function selectGroup(group) {
  selectedGroup = group;
  
  document.querySelectorAll('.calc-group-card').forEach(card => {
    card.classList.toggle('active', card.dataset.group === String(group));
  });
  
  const revInput = document.getElementById('calc-revenue');
  const resultCard = document.getElementById('calc-result');
  
  resultCard.classList.remove('visible');
  
  if (group === '3_5' || group === '3_3') {
    revInput.classList.add('visible');
  } else {
    revInput.classList.remove('visible');
    calculateFixedTax(group);
  }
  
  try {
    tg.HapticFeedback.impactOccurred('light');
  } catch (e) {}
}

function calculateFixedTax(group) {
  const resultCard = document.getElementById('calc-result');
  const resultRows = document.getElementById('calc-result-rows');
  const note = document.getElementById('calc-result-note');
  
  let rows = '';
  if (group === 1) {
    rows = `
      <div class="result-row"><span>Єдиний податок (10% ПМ):</span><strong>302.80 ₴/міс</strong></div>
      <div class="result-row"><span>ЄСВ (22% мін. зп, добровільно):</span><strong>1 760.00 ₴/міс</strong></div>
    `;
    note.textContent = 'Звільнення від сплати ЄСВ діє тимчасово на період воєнного стану.';
  } else if (group === 2) {
    rows = `
      <div class="result-row"><span>Єдиний податок (20% МЗП):</span><strong>1 600.00 ₴/міс</strong></div>
      <div class="result-row"><span>ЄСВ (22% мін. зп, добровільно):</span><strong>1 760.00 ₴/міс</strong></div>
    `;
    note.textContent = 'Звільнення від сплати ЄСВ діє тимчасово на період воєнного стану.';
  }
  
  resultRows.innerHTML = rows;
  resultCard.classList.add('visible');
}

// ─── Calculate Tax ────────────────────────────
function calculateTax() {
  const revEl = document.getElementById('input-revenue');
  const revenue = parseFloat(revEl.value) || 0;
  
  if (revenue <= 0) {
    showToast('Будь ласка, введіть коректну суму доходу', 'warning');
    return;
  }
  
  const resultCard = document.getElementById('calc-result');
  const resultRows = document.getElementById('calc-result-rows');
  const note = document.getElementById('calc-result-note');
  
  let singleTax = 0;
  let taxRateLabel = '';
  
  if (selectedGroup === '3_5') {
    singleTax = revenue * 0.05;
    taxRateLabel = 'Єдиний податок (5% від доходу):';
  } else if (selectedGroup === '3_3') {
    singleTax = revenue * 0.03;
    taxRateLabel = 'Єдиний податок (3% + ПДВ):';
  }
  
  const esv = 1760 * 3; // ЕСВ за квартал
  
  resultRows.innerHTML = `
    <div class="result-row"><span>Квартальний дохід:</span><strong>${revenue.toFixed(2)} ₴</strong></div>
    <div class="result-row"><span>${taxRateLabel}</span><strong>${singleTax.toFixed(2)} ₴</strong></div>
    <div class="result-row"><span>ЄСВ за квартал (добровільно):</span><strong>${esv.toFixed(2)} ₴</strong></div>
    <div class="result-row highlight"><span>Всього до сплати (мін.):</span><strong>${(singleTax + esv).toFixed(2)} ₴</strong></div>
  `;
  note.textContent = 'Розрахунок є орієнтовним. ЄСВ сплачується до 20 числа місяця, наступного за кварталом.';
  resultCard.classList.add('visible');
  
  try {
    tg.HapticFeedback.notificationOccurred('success');
  } catch (e) {}
}

// ─── API Requests Loader ──────────────────────
async function loadMyRequests() {
  const skeleton = document.getElementById('requests-skeleton');
  const list = document.getElementById('requests-list');
  const empty = document.getElementById('requests-empty');
  
  skeleton.classList.add('visible');
  list.innerHTML = '';
  empty.classList.remove('visible');
  
  if (!userId) {
    skeleton.classList.remove('visible');
    empty.classList.add('visible');
    return;
  }
  
  try {
    const response = await apiFetch(`${API_BASE}/api/twa/my-requests?user_id=${userId}`);
    if (!response.ok) throw new Error();
    
    const requests = await response.json();
    skeleton.classList.remove('visible');
    
    if (!requests || requests.length === 0) {
      empty.classList.add('visible');
      return;
    }
    
    requests.forEach((req, idx) => {
      const card = renderRequestCard(req, idx);
      list.insertAdjacentHTML('beforeend', card);
    });
    
    // Rerender Lucide icons for the dynamic HTML elements
    try {
      lucide.createIcons();
    } catch (e) {}
  } catch (err) {
    console.error(err);
    skeleton.classList.remove('visible');
    empty.classList.add('visible');
    showToast('Не вдалося завантажити заявки', 'error');
  }
}

function renderRequestCard(req, index) {
  const date = formatDate(req.created_at);
  const phone = req.phone ? formatPhone(req.phone) : '';
  const delay = index * 0.05;
  
  const statusLabels = {
    pending: 'Очікує ⏳',
    in_progress: 'В роботі ⚙️',
    completed: 'Виконано ✅',
    rejected: 'Відхилено ❌'
  };
  
  const statusClasses = {
    pending: 'status-pending',
    in_progress: 'status-in-progress',
    completed: 'status-completed',
    rejected: 'status-rejected'
  };
  
  const statusClass = statusClasses[req.status] || 'status-pending';
  const statusLabel = statusLabels[req.status] || req.status;
  
  return `
    <div class="request-card" style="animation-delay: ${delay}s">
      <div class="request-header">
        <span class="request-status ${statusClass}">${statusLabel}</span>
        <span class="request-date">${date}</span>
      </div>
      <div class="request-body">
        <div class="request-name">${escapeHtml(req.name || 'Без імені')}</div>
        ${phone ? `<div style="font-size: 12px; color: var(--accent); margin-bottom: 6px;">${phone}</div>` : ''}
        <div class="request-text">${escapeHtml(req.text || 'Без опису')}</div>
      </div>
    </div>
  `;
}

// ─── Helpers ──────────────────────────────────
function formatDate(isoStr) {
  if (!isoStr) return '';
  try {
    const d = new Date(isoStr);
    return d.toLocaleString('uk-UA', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch (e) {
    return isoStr;
  }
}

function formatPhone(phone) {
  const clean = phone.replace(/[^\d]/g, '');
  if (clean.startsWith('380') && clean.length === 12) {
    return `+38 (0${clean.slice(3, 5)}) ${clean.slice(5, 8)}-${clean.slice(8, 10)}-${clean.slice(10, 12)}`;
  }
  return phone;
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;
  
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  
  container.appendChild(toast);
  
  setTimeout(() => toast.classList.add('visible'), 50);
  setTimeout(() => {
    toast.classList.remove('visible');
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

async function apiFetch(url, options = {}) {
  return fetch(url, options);
}
