/* ============================================

   LegalTax Mini App — Application Logic

   Telegram WebApp + Vanilla JS

   ============================================ */



// ─── Telegram WebApp Init ─────────────────────

const tg = window.Telegram.WebApp;

tg.ready();

tg.expand();



try {

  tg.setHeaderColor('#492232');

  tg.setBackgroundColor('#12090d');

} catch (e) {

  // Fallback: colors not supported in older versions

}



// ─── User Data ────────────────────────────────

const userId = tg.initDataUnsafe?.user?.id || null;

const userFirstName = tg.initDataUnsafe?.user?.first_name || '';



// ─── API Base URL ─────────────────────────────

const API_BASE = '';  // Relative paths — same server

// ─── API Fetch Helper (bypasses localtunnel warning) ───
async function apiFetch(url, options = {}) {
  const headers = {
    'Bypass-Tunnel-Reminder': 'true',
    ...(options.headers || {})
  };
  return fetch(url, { ...options, headers });
}  // Relative paths — same server



// ─── State ────────────────────────────────────

let currentPage = 'home';

let currentStep = 1;

let selectedGroup = null;

let isAdmin = false;

let activeReplyRequestId = null;



// ─── DOM Ready ────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  initApp();

});



function initApp() {

  // Set greeting with user name

  const heroName = document.getElementById('hero-name');

  if (userFirstName) {

    heroName.textContent = `${userFirstName}, раді бачити!`;

  }



  // Pre-fill form name from Telegram

  const nameInput = document.getElementById('input-name');

  if (userFirstName && nameInput) {

    nameInput.value = userFirstName;

  }



  // Initialize ripple effects on buttons

  initRippleEffects();



  // Load user profile details and admin status

  loadUserInfo();

}





/* ============================================

   NAVIGATION

   ============================================ */

function navigateTo(pageId) {

  if (currentPage === pageId) return;



  // Hide all pages

  document.querySelectorAll('.page').forEach(page => {

    page.classList.remove('active');

    page.style.opacity = '0';

  });



  // Show target page

  const targetPage = document.getElementById(`page-${pageId}`);

  if (targetPage) {

    targetPage.classList.add('active');

    // Scroll to top of content

    targetPage.scrollTop = 0;

    window.scrollTo({ top: 0, behavior: 'instant' });

  }



  // Update nav active state

  document.querySelectorAll('.nav-item').forEach(item => {

    item.classList.toggle('active', item.dataset.page === pageId);

  });



  currentPage = pageId;



  // Auto-load requests when navigating to requests page

  if (pageId === 'requests') {

    loadRequests();

  }



  // Auto-load admin pending requests when navigating to admin page

  if (pageId === 'admin') {

    loadAdminPending();

  }



  // Haptic feedback

  try {

    tg.HapticFeedback.impactOccurred('light');

  } catch (e) {}

}



function scrollToAbout() {

  const aboutSection = document.getElementById('about-section');

  if (aboutSection) {

    aboutSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

  }

}





/* ============================================

   TOAST NOTIFICATIONS

   ============================================ */

function showToast(message, type = 'info') {

  const container = document.getElementById('toast-container');



  const icons = {

    success: '✅',

    error: '❌',

    info: 'ℹ️'

  };



  const toast = document.createElement('div');

  toast.className = `toast ${type}`;

  toast.innerHTML = `

    <span class="toast-icon">${icons[type] || icons.info}</span>

    <span>${message}</span>

  `;



  container.appendChild(toast);



  // Auto-hide after 3 seconds

  setTimeout(() => {

    toast.classList.add('hide');

    setTimeout(() => toast.remove(), 300);

  }, 3000);

}





/* ============================================

   MULTI-STEP FORM

   ============================================ */

function updateStepIndicators() {

  for (let i = 1; i <= 3; i++) {

    const circle = document.getElementById(`step-circle-${i}`);

    circle.classList.remove('active', 'completed');



    if (i < currentStep) {

      circle.classList.add('completed');

      circle.textContent = '✓';

    } else if (i === currentStep) {

      circle.classList.add('active');

      circle.textContent = i;

    } else {

      circle.textContent = i;

    }

  }



  // Update step lines

  for (let i = 1; i <= 2; i++) {

    const line = document.getElementById(`step-line-${i}`);

    line.classList.toggle('active', i < currentStep);

  }

}



function showStep(step) {

  document.querySelectorAll('.form-step').forEach(s => s.classList.remove('active'));

  const target = document.getElementById(`form-step-${step}`);

  if (target) {

    target.classList.add('active');

  }

  currentStep = step;

  updateStepIndicators();

}



function nextStep() {

  // Validate current step

  if (!validateStep(currentStep)) return;



  if (currentStep < 3) {

    showStep(currentStep + 1);

    try {

      tg.HapticFeedback.impactOccurred('light');

    } catch (e) {}

  }

}



function prevStep() {

  if (currentStep > 1) {

    showStep(currentStep - 1);

    try {

      tg.HapticFeedback.impactOccurred('light');

    } catch (e) {}

  }

}



function validateStep(step) {

  hideAllErrors();



  switch (step) {

    case 1: {

      const name = document.getElementById('input-name').value.trim();

      if (!name) {

        showError('error-name');

        shakeInput('input-name');

        return false;

      }

      return true;

    }

    case 2: {

      const phone = document.getElementById('input-phone').value.trim();

      const digits = phone.replace(/\D/g, '');

      if (digits.length < 9) {

        showError('error-phone');

        shakeInput('input-phone');

        return false;

      }

      return true;

    }

    case 3: {

      const text = document.getElementById('input-text').value.trim();

      if (!text) {

        showError('error-text');

        shakeInput('input-text');

        return false;

      }

      return true;

    }

    default:

      return true;

  }

}



function showError(id) {

  const el = document.getElementById(id);

  if (el) el.classList.add('visible');

}



function hideAllErrors() {

  document.querySelectorAll('.form-error').forEach(e => e.classList.remove('visible'));

}



function shakeInput(id) {

  const input = document.getElementById(id);

  if (!input) return;

  input.style.animation = 'none';

  input.offsetHeight; // Force reflow

  input.style.animation = '';

  input.style.borderColor = 'var(--error)';

  setTimeout(() => {

    input.style.borderColor = '';

  }, 1500);

}





/* ============================================

   FORM SUBMISSION

   ============================================ */

async function submitForm() {

  if (!validateStep(3)) return;



  const btn = document.getElementById('btn-submit');

  const originalText = btn.textContent;

  btn.disabled = true;

  btn.textContent = 'Надсилаємо...';



  const payload = {

    user_id: userId,

    name: document.getElementById('input-name').value.trim(),

    phone: document.getElementById('input-phone').value.trim(),

    text: document.getElementById('input-text').value.trim()

  };



  try {

    const response = await apiFetch(`${API_BASE}/api/twa/create-request`, {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify(payload)

    });



    if (!response.ok) throw new Error(`HTTP ${response.status}`);



    const data = await response.json();



    // Show success

    document.querySelector('.form-container').style.display = 'none';

    document.querySelector('.step-indicators').style.display = 'none';

    document.querySelector('#page-form .page-subtitle').style.display = 'none';

    document.querySelector('#page-form .page-title').style.display = 'none';

    // Hide step labels row

    const stepLabels = document.querySelector('#page-form .step-indicators + div');

    if (stepLabels) stepLabels.style.display = 'none';



    document.getElementById('form-success').classList.add('active');

    showToast('Заявку успішно надіслано!', 'success');



    try {

      tg.HapticFeedback.notificationOccurred('success');

    } catch (e) {}



  } catch (error) {

    console.error('Submit error:', error);

    showToast('Помилка надсилання. Спробуйте ще раз.', 'error');

    try {

      tg.HapticFeedback.notificationOccurred('error');

    } catch (e) {}

  } finally {

    btn.disabled = false;

    btn.textContent = originalText;

  }

}



function resetForm() {

  // Reset form fields

  document.getElementById('input-name').value = userFirstName || '';

  document.getElementById('input-phone').value = '';

  document.getElementById('input-text').value = '';



  // Reset UI

  document.querySelector('.form-container').style.display = '';

  document.querySelector('.step-indicators').style.display = '';

  document.querySelector('#page-form .page-subtitle').style.display = '';

  document.querySelector('#page-form .page-title').style.display = '';

  const stepLabels = document.querySelector('#page-form .step-indicators + div');

  if (stepLabels) stepLabels.style.display = '';



  document.getElementById('form-success').classList.remove('active');

  hideAllErrors();

  showStep(1);

  navigateTo('home');

}





/* ============================================

   REQUESTS

   ============================================ */

async function loadRequests() {

  const skeleton = document.getElementById('requests-skeleton');

  const list = document.getElementById('requests-list');

  const empty = document.getElementById('requests-empty');



  // Show loading state

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

    if (!response.ok) throw new Error(`HTTP ${response.status}`);



    const data = await response.json();

    const requests = data.requests || data || [];



    skeleton.classList.remove('visible');



    if (!requests.length) {

      empty.classList.add('visible');

      return;

    }



    // Render request cards

    requests.forEach((req, index) => {

      const card = renderRequestCard(req, index);

      list.insertAdjacentHTML('beforeend', card);

    });



  } catch (error) {

    console.error('Load requests error:', error);

    skeleton.classList.remove('visible');

    empty.classList.add('visible');

    showToast('Не вдалося завантажити заявки', 'error');

  }

}



function renderRequestCard(req, index) {

  const status = getStatusInfo(req.status || 'pending');

  const date = formatDate(req.created_at || req.date);

  const phone = req.phone ? formatPhone(req.phone) : '';

  const source = req.source || 'webapp';

  const sourceLabels = {

    bot: 'Бот',

    webapp: 'Додаток',

    admin: 'Адмін',

    web: 'Сайт'

  };

  const delay = index * 0.06;



  return `

    <div class="request-card" style="animation-delay: ${delay}s">

      <div class="request-header">

        <div class="status-badge status-${req.status || 'pending'}">

          <span class="status-dot"></span>

          <span>${status.label}</span>

        </div>

        <span class="request-date">${date}</span>

      </div>

      <div class="request-body">

        <div class="request-name">${escapeHtml(req.name || 'Без імені')}</div>

        <div class="request-text">${escapeHtml(req.text || req.description || 'Без опису')}</div>

      </div>

      <div class="request-footer">

        <span class="source-badge">${sourceLabels[source] || source}</span>

        ${phone ? `<span class="request-phone">${phone}</span>` : ''}

      </div>

    </div>

  `;

}





/* ============================================

   STATUS HELPERS

   ============================================ */

function getStatusInfo(status) {

  const statuses = {

    pending: { label: 'Очікує', color: 'var(--warning)', icon: '⏳' },

    in_progress: { label: 'В роботі', color: 'var(--accent)', icon: '🔄' },

    completed: { label: 'Виконано', color: 'var(--success)', icon: '✅' },

    rejected: { label: 'Відхилено', color: 'var(--error)', icon: '❌' }

  };

  return statuses[status] || statuses.pending;

}





/* ============================================

   CALCULATOR

   ============================================ */

function selectGroup(group) {

  selectedGroup = group;



  // Update card selection

  document.querySelectorAll('.calc-group-card').forEach(card => {

    card.classList.toggle('selected', card.dataset.group === String(group));

  });



  // Show/hide revenue input based on group

  const revenueSection = document.getElementById('calc-revenue');

  const resultSection = document.getElementById('calc-result');



  if (group === '3_5' || group === '3_3') {

    revenueSection.classList.add('visible');

    resultSection.classList.remove('visible');

  } else {

    revenueSection.classList.remove('visible');

    // For groups 1 & 2, calculate immediately

    calculateFixedGroup(group);

  }



  try {

    tg.HapticFeedback.selectionChanged();

  } catch (e) {}

}



function calculateFixedGroup(group) {

  const resultSection = document.getElementById('calc-result');

  const resultRows = document.getElementById('calc-result-rows');

  const resultNote = document.getElementById('calc-result-note');



  let esv, ep, total, note;



  // 2025 rates

  const minWage = 8000;

  const esvRate = 0.22;

  const esvMonth = minWage * esvRate; // 1760



  if (group === 1) {

    ep = 302.80; // Fixed EP for group 1

    esv = esvMonth;

    total = ep + esv;

    note = 'ФОП 1 група: фіксований ЄП + ЄСВ (22% від мін. зарплати). Ліміт доходу — 1 185 900 ₴/рік.';

  } else if (group === 2) {

    ep = 1600; // Fixed EP for group 2

    esv = esvMonth;

    total = ep + esv;

    note = 'ФОП 2 група: фіксований ЄП + ЄСВ (22% від мін. зарплати). Ліміт доходу — 7 905 900 ₴/рік.';

  }



  resultRows.innerHTML = `

    <div class="calc-result-row">

      <span class="calc-result-label">Єдиний податок (ЄП)</span>

      <span class="calc-result-value">${formatMoney(ep)} ₴/міс</span>

    </div>

    <div class="calc-result-row">

      <span class="calc-result-label">ЄСВ (22%)</span>

      <span class="calc-result-value">${formatMoney(esv)} ₴/міс</span>

    </div>

    <div class="calc-result-row">

      <span class="calc-result-label">Разом за місяць</span>

      <span class="calc-result-value">${formatMoney(total)} ₴</span>

    </div>

    <div class="calc-result-row">

      <span class="calc-result-label">Разом за квартал</span>

      <span class="calc-result-value">${formatMoney(total * 3)} ₴</span>

    </div>

    <div class="calc-result-row">

      <span class="calc-result-label" style="font-weight:600; color:var(--text-primary)">Разом за рік</span>

      <span class="calc-result-value" style="font-size:18px; color:var(--accent)">${formatMoney(total * 12)} ₴</span>

    </div>

  `;

  resultNote.textContent = note;

  resultSection.classList.add('visible');

}



function calculateTax() {

  const revenueInput = document.getElementById('input-revenue');

  const revenue = parseFloat(revenueInput.value);



  if (!revenue || revenue <= 0) {

    showToast('Вкажіть суму доходу', 'error');

    shakeInput('input-revenue');

    return;

  }



  const resultSection = document.getElementById('calc-result');

  const resultRows = document.getElementById('calc-result-rows');

  const resultNote = document.getElementById('calc-result-note');



  const minWage = 8000;

  const esvMonth = minWage * 0.22; // 1760

  const esvQuarter = esvMonth * 3;



  let ep, pdv = 0, total, note;



  if (selectedGroup === '3_5') {

    // 5% of revenue, no VAT

    ep = revenue * 0.05;

    total = ep + esvQuarter;

    note = 'ФОП 3 група (5%): ЄП 5% від доходу без ПДВ + ЄСВ за квартал. Ліміт — 7 905 900 ₴/рік.';



    resultRows.innerHTML = `

      <div class="calc-result-row">

        <span class="calc-result-label">Дохід за квартал</span>

        <span class="calc-result-value">${formatMoney(revenue)} ₴</span>

      </div>

      <div class="calc-result-row">

        <span class="calc-result-label">ЄП (5%)</span>

        <span class="calc-result-value">${formatMoney(ep)} ₴</span>

      </div>

      <div class="calc-result-row">

        <span class="calc-result-label">ЄСВ за квартал</span>

        <span class="calc-result-value">${formatMoney(esvQuarter)} ₴</span>

      </div>

      <div class="calc-result-row">

        <span class="calc-result-label" style="font-weight:600; color:var(--text-primary)">Разом за квартал</span>

        <span class="calc-result-value" style="font-size:18px; color:var(--accent)">${formatMoney(total)} ₴</span>

      </div>

    `;

  } else if (selectedGroup === '3_3') {

    // 3% of revenue + 20% VAT

    ep = revenue * 0.03;

    pdv = revenue * 0.2;

    total = ep + pdv + esvQuarter;

    note = 'ФОП 3 група (3%+ПДВ): ЄП 3% від доходу + ПДВ 20% + ЄСВ за квартал. Ліміт — 7 905 900 ₴/рік.';



    resultRows.innerHTML = `

      <div class="calc-result-row">

        <span class="calc-result-label">Дохід за квартал</span>

        <span class="calc-result-value">${formatMoney(revenue)} ₴</span>

      </div>

      <div class="calc-result-row">

        <span class="calc-result-label">ЄП (3%)</span>

        <span class="calc-result-value">${formatMoney(ep)} ₴</span>

      </div>

      <div class="calc-result-row">

        <span class="calc-result-label">ПДВ (20%)</span>

        <span class="calc-result-value">${formatMoney(pdv)} ₴</span>

      </div>

      <div class="calc-result-row">

        <span class="calc-result-label">ЄСВ за квартал</span>

        <span class="calc-result-value">${formatMoney(esvQuarter)} ₴</span>

      </div>

      <div class="calc-result-row">

        <span class="calc-result-label" style="font-weight:600; color:var(--text-primary)">Разом за квартал</span>

        <span class="calc-result-value" style="font-size:18px; color:var(--accent)">${formatMoney(total)} ₴</span>

      </div>

    `;

  }



  resultNote.textContent = note;

  resultSection.classList.add('visible');



  // Scroll to result

  resultSection.scrollIntoView({ behavior: 'smooth', block: 'nearest' });



  try {

    tg.HapticFeedback.notificationOccurred('success');

  } catch (e) {}

}





/* ============================================

   FORMATTING HELPERS

   ============================================ */

function formatDate(dateStr) {

  if (!dateStr) return '—';

  try {

    const d = new Date(dateStr);

    if (isNaN(d.getTime())) return dateStr;

    const day = String(d.getDate()).padStart(2, '0');

    const month = String(d.getMonth() + 1).padStart(2, '0');

    const year = d.getFullYear();

    const hours = String(d.getHours()).padStart(2, '0');

    const minutes = String(d.getMinutes()).padStart(2, '0');

    return `${day}.${month}.${year} ${hours}:${minutes}`;

  } catch (e) {

    return dateStr;

  }

}



function formatPhone(phone) {

  if (!phone) return '';

  const digits = phone.replace(/\D/g, '');

  if (digits.length === 12) {

    // +380XXXXXXXXX

    return `+${digits.slice(0, 2)} (${digits.slice(2, 5)}) ${digits.slice(5, 8)}-${digits.slice(8, 10)}-${digits.slice(10, 12)}`;

  } else if (digits.length === 10) {

    // 0XXXXXXXXX

    return `+38 (${digits.slice(0, 3)}) ${digits.slice(3, 6)}-${digits.slice(6, 8)}-${digits.slice(8, 10)}`;

  }

  return phone;

}



function formatMoney(amount) {

  return new Intl.NumberFormat('uk-UA', {

    minimumFractionDigits: 2,

    maximumFractionDigits: 2

  }).format(amount);

}



function escapeHtml(text) {

  const div = document.createElement('div');

  div.textContent = text;

  return div.innerHTML;

}





/* ============================================

   RIPPLE EFFECT

   ============================================ */

function initRippleEffects() {

  document.addEventListener('click', (e) => {

    const btn = e.target.closest('.btn');

    if (!btn) return;



    const ripple = document.createElement('span');

    ripple.classList.add('ripple');

    const rect = btn.getBoundingClientRect();

    const size = Math.max(rect.width, rect.height);

    ripple.style.width = ripple.style.height = `${size}px`;

    ripple.style.left = `${e.clientX - rect.left - size / 2}px`;

    ripple.style.top = `${e.clientY - rect.top - size / 2}px`;

    btn.appendChild(ripple);



    ripple.addEventListener('animationend', () => ripple.remove());

  });

}



/* ============================================

   ADMIN USER & PANEL LOGIC

   ============================================ */

async function loadUserInfo() {

  if (!userId) return;

  try {

    const response = await apiFetch(`${API_BASE}/api/twa/user-info?user_id=${userId}`);

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();

    if (data.status === 'ok') {

      if (data.is_admin) {

        isAdmin = true;

        const cardAdmin = document.getElementById('card-admin');

        const navAdmin = document.getElementById('nav-item-admin');

        if (cardAdmin) cardAdmin.style.display = 'flex';

        if (navAdmin) navAdmin.style.display = 'flex';

      }

    }

  } catch (error) {

    console.error('Error loading user info:', error);

  }

}



async function loadAdminPending() {

  const skeleton = document.getElementById('admin-skeleton');

  const list = document.getElementById('admin-requests-list');

  const empty = document.getElementById('admin-empty');



  skeleton.classList.add('visible');

  list.innerHTML = '';

  empty.classList.remove('visible');



  if (!userId || !isAdmin) {

    skeleton.classList.remove('visible');

    empty.classList.add('visible');

    return;

  }



  try {

    const response = await apiFetch(`${API_BASE}/api/twa/admin/pending?admin_id=${userId}`);

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const requests = await response.json();



    skeleton.classList.remove('visible');



    if (!requests || !requests.length) {

      empty.classList.add('visible');

      return;

    }



    requests.forEach((req, index) => {

      const card = renderAdminRequestCard(req, index);

      list.insertAdjacentHTML('beforeend', card);

    });



  } catch (error) {

    console.error('Error loading pending requests:', error);

    skeleton.classList.remove('visible');

    empty.classList.add('visible');

    showToast('Не вдалося завантажити очікуючі заявки', 'error');

  }

}



function renderAdminRequestCard(req, index) {

  const date = formatDate(req.created_at);

  const phone = req.phone ? formatPhone(req.phone) : '';

  const delay = index * 0.06;

  const sourceLabels = {

    bot: 'Бот',

    webapp: 'Додаток',

    admin: 'Адмін',

    web: 'Сайт'

  };



  return `

    <div class="request-card" style="animation-delay: ${delay}s">

      <div class="request-header">

        <span class="source-badge">${sourceLabels[req.source] || req.source || 'Заявка'}</span>

        <span class="request-date">${date}</span>

      </div>

      <div class="request-body">

        <div class="request-name" style="font-weight: 600; color: var(--text-primary); margin-bottom: 4px;">

          ${escapeHtml(req.name || 'Без імені')}

        </div>

        ${phone ? `<div style="font-size: 12px; color: var(--accent); margin-bottom: 8px;">${phone}</div>` : ''}

        <div class="request-text" style="font-size: 13px; line-height: 1.5;">${escapeHtml(req.text || 'Без опису')}</div>

      </div>

      <div class="admin-actions">

        <button class="btn-admin btn-accept" onclick="handleAdminAction(${req.id}, 'accept')">В роботу</button>

        <button class="btn-admin btn-reject" onclick="handleAdminAction(${req.id}, 'reject')">Відхилити</button>

        <button class="btn-admin btn-reply" onclick="openReplyModal(${req.id})">Відповісти</button>

      </div>

    </div>

  `;

}



async function handleAdminAction(requestId, action) {

  if (action === 'reject') {

    if (!confirm('Ви впевнені, що хочете відхилити цю заявку?')) return;

  }



  try {

    const response = await apiFetch(`${API_BASE}/api/twa/admin/action`, {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify({

        admin_id: userId,

        request_id: requestId,

        action: action

      })

    });



    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    showToast('Статус успішно оновлено', 'success');

    loadAdminPending();



    try {

      tg.HapticFeedback.notificationOccurred('success');

    } catch (e) {}



  } catch (error) {

    console.error('Error performing admin action:', error);

    showToast('Помилка оновлення статусу', 'error');

  }

}



function openReplyModal(requestId) {

  activeReplyRequestId = requestId;

  const modal = document.getElementById('reply-modal');

  const title = document.getElementById('reply-modal-subtitle');

  const textarea = document.getElementById('reply-text-input');

  

  if (title) title.textContent = `Заявка №${requestId}`;

  if (textarea) textarea.value = '';

  

  const err = document.getElementById('error-reply-text');

  if (err) err.classList.remove('visible');



  if (modal) {

    modal.classList.add('active');

  }

  

  try {

    tg.HapticFeedback.impactOccurred('light');

  } catch (e) {}

}



function closeReplyModal() {

  activeReplyRequestId = null;

  const modal = document.getElementById('reply-modal');

  if (modal) {

    modal.classList.remove('active');

  }

}



async function submitAdminReply() {

  const textarea = document.getElementById('reply-text-input');

  const text = textarea ? textarea.value.trim() : '';

  const err = document.getElementById('error-reply-text');



  if (!text) {

    if (err) err.classList.add('visible');

    return;

  }



  const btn = document.getElementById('btn-submit-reply');

  const originalText = btn.textContent;

  btn.disabled = true;

  btn.textContent = 'Надсилаємо...';



  try {

    const response = await apiFetch(`${API_BASE}/api/twa/admin/action`, {

      method: 'POST',

      headers: { 'Content-Type': 'application/json' },

      body: JSON.stringify({

        admin_id: userId,

        request_id: activeReplyRequestId,

        action: 'reply',

        reply_text: text

      })

    });



    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    

    showToast('Відповідь надіслано користувачу', 'success');

    closeReplyModal();

    loadAdminPending();



    try {

      tg.HapticFeedback.notificationOccurred('success');

    } catch (e) {}



  } catch (error) {

    console.error('Error submitting admin reply:', error);

    showToast('Помилка надсилання відповіді', 'error');

  } finally {

    btn.disabled = false;

    btn.textContent = originalText;

  }

}

