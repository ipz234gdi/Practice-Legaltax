const tg = window.Telegram ? window.Telegram.WebApp : null;
const API_BASE = window.location.origin;

let userId = null;
let username = null;
let firstName = null;
let lastName = null;
let isAdmin = false;

let currentAdminTab = 'list';
let adminRequests = [];
let swipeQueue = [];
let swipeActiveCardIndex = 0;
let activeReplyRequestId = null;

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
    }
  } else {
    // Fallback for browser testing (simulate admin)
    userId = 684877221; // Simulate admin ID
    username = 'admin_test';
    firstName = 'Адмін';
  }
  
  // Verify admin status on the server
  if (userId) {
    try {
      const response = await apiFetch(`${API_BASE}/api/twa/user-info?user_id=${userId}`);
      if (response.ok) {
        const data = await response.json();
        if (data.status === 'ok' && data.is_admin) {
          isAdmin = true;
        }
      }
    } catch (e) {
      console.error('Error verifying admin status:', e);
    }
  }
  
  if (!isAdmin) {
    document.body.innerHTML = `
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; padding:24px; text-align:center; background:#12090d; color:#ffffff; font-family:'Inter', sans-serif;">
        <i data-lucide="shield-alert" style="width:64px; height:64px; color:#ef5350; margin-bottom:16px;"></i>
        <h2 style="font-size:20px; font-weight:700; margin-bottom:8px;">Доступ заборонено</h2>
        <p style="font-size:14px; color:#a38d96; max-width:280px; line-height:1.5;">Ця панель призначена виключно для адміністраторів компанії LegalTax.</p>
      </div>
    `;
    try {
      lucide.createIcons();
    } catch (e) {}
    return;
  }
  
  // Initialize initial tab
  switchAdminTab('list');
  
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

// ─── Tab Switching ────────────────────────────
function switchAdminTab(tabId) {
  currentAdminTab = tabId;
  
  document.querySelectorAll('.admin-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.id === `admin-btn-${tabId}`);
  });
  
  document.querySelectorAll('.admin-tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `admin-tab-${tabId}`);
  });
  
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.id === `admin-btn-${tabId}`);
  });
  
  if (tabId === 'list') {
    loadAdminRequests();
  } else {
    loadAdminSwipeDeck();
  }
  
  try {
    tg.HapticFeedback.impactOccurred('light');
  } catch (e) {}
}

function reloadActiveAdminTab() {
  if (currentAdminTab === 'list') {
    loadAdminRequests();
  } else {
    loadAdminSwipeDeck();
  }
}

// ─── List Dashboard Loader ────────────────────
async function loadAdminRequests() {
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

  const statusFilter = document.getElementById('filter-status').value;
  const sortOrder = document.getElementById('sort-order').value;

  try {
    const response = await apiFetch(`${API_BASE}/api/twa/admin/requests?admin_id=${userId}&status=${statusFilter}`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    let requests = await response.json();
    
    if (sortOrder === 'newest') {
      requests.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    } else {
      requests.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    }
    
    adminRequests = requests;
    skeleton.classList.remove('visible');

    if (!requests || !requests.length) {
      empty.classList.add('visible');
      return;
    }

    requests.forEach((req, index) => {
      const card = renderAdminRequestCard(req, index);
      list.insertAdjacentHTML('beforeend', card);
    });
    
    // Rerender Lucide icons for status labels or badges
    try {
      lucide.createIcons();
    } catch (e) {}
  } catch (error) {
    console.error('Error loading admin requests:', error);
    skeleton.classList.remove('visible');
    empty.classList.add('visible');
    showToast('Не вдалося завантажити заявки', 'error');
  }
}

function filterAdminRequests() {
  loadAdminRequests();
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

  const statusLabels = {
    pending: 'Очікує ⏳',
    in_progress: 'В роботі ⚙️',
    completed: 'Виконано ✅',
    rejected: 'Відхилено ❌'
  };

  let actionButtonsHtml = '';
  if (req.status === 'pending') {
    actionButtonsHtml = `
      <button class="btn-admin btn-accept" onclick="handleAdminAction(${req.id}, 'accept')">В роботу</button>
      <button class="btn-admin btn-reject" onclick="handleAdminAction(${req.id}, 'reject')">Відхилити</button>
      <button class="btn-admin btn-reply" onclick="openReplyModal(${req.id})">Відповісти</button>
    `;
  } else if (req.status === 'in_progress') {
    actionButtonsHtml = `
      <button class="btn-admin btn-reply" onclick="openReplyModal(${req.id})">Відповісти</button>
      <button class="btn-admin btn-reject" onclick="handleAdminAction(${req.id}, 'reject')">Відхилити</button>
    `;
  } else {
    actionButtonsHtml = `
      <span style="font-size: 13px; font-weight: 600; color: var(--text-muted); padding: 6px 12px;">Оброблено</span>
    `;
  }

  return `
    <div class="request-card" style="animation-delay: ${delay}s">
      <div class="request-header">
        <span class="source-badge">${sourceLabels[req.source] || req.source || 'Заявка'}</span>
        <span style="font-size: 11px; font-weight: 600; padding: 4px 8px; border-radius: 4px; background: rgba(255,255,255,0.05); color: var(--text-secondary)">
          ${statusLabels[req.status] || req.status}
        </span>
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
        ${actionButtonsHtml}
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
    reloadActiveAdminTab();

    try {
      tg.HapticFeedback.notificationOccurred('success');
    } catch (e) {}
  } catch (error) {
    console.error('Error performing admin action:', error);
    showToast('Помилка оновлення статусу', 'error');
  }
}

// ─── Swipe Deck Dashboard ────────────────────
async function loadAdminSwipeDeck() {
  const deck = document.getElementById('swipe-card-deck');
  const empty = document.getElementById('swipe-empty');

  deck.innerHTML = '';
  empty.style.display = 'none';
  deck.style.display = 'block';

  if (!userId || !isAdmin) {
    deck.style.display = 'none';
    empty.style.display = 'block';
    return;
  }

  try {
    const response = await apiFetch(`${API_BASE}/api/twa/admin/requests?admin_id=${userId}&status=pending`);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    const requests = await response.json();
    requests.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    
    swipeQueue = requests;
    swipeActiveCardIndex = 0;

    if (!requests || !requests.length) {
      deck.style.display = 'none';
      empty.style.display = 'block';
      document.getElementById('swipe-empty-title').textContent = 'Заявки закінчились';
      return;
    }

    renderSwipeCards();
  } catch (error) {
    console.error('Error loading swipe deck:', error);
    deck.style.display = 'none';
    empty.style.display = 'block';
    document.getElementById('swipe-empty-title').textContent = 'Помилка завантаження';
    showToast('Не вдалося завантажити картки', 'error');
  }
}

function renderSwipeCards() {
  const deck = document.getElementById('swipe-card-deck');
  deck.innerHTML = '';

  const cardsToRender = swipeQueue.slice(swipeActiveCardIndex, swipeActiveCardIndex + 3);

  if (cardsToRender.length === 0) {
    deck.style.display = 'none';
    document.getElementById('swipe-empty').style.display = 'block';
    document.getElementById('swipe-empty-title').textContent = 'Заявки закінчились';
    return;
  }

  cardsToRender.forEach((req, idx) => {
    const date = formatDate(req.created_at);
    const phone = req.phone ? formatPhone(req.phone) : '';
    
    const sourceLabels = {
      bot: 'Бот',
      webapp: 'Додаток',
      admin: 'Адмін',
      web: 'Сайт'
    };

    const cardHtml = `
      <div class="swipe-card" id="swipe-card-${req.id}" data-id="${req.id}">
        <div class="swipe-card-badge badge-accept">В роботу</div>
        <div class="swipe-card-badge badge-reject">Відхилити</div>
        <div class="swipe-card-badge badge-skip">Пропустити</div>
        
        <div class="swipe-card-header">
          <span class="source-badge">${sourceLabels[req.source] || req.source || 'Заявка'}</span>
          <span style="font-size: 11px; color: var(--text-muted); font-weight: 500;">№${req.id}</span>
        </div>
        
        <div class="swipe-card-body">
          <div class="swipe-card-name">${escapeHtml(req.name || 'Без імені')}</div>
          ${phone ? `<a href="tel:${phone}" class="swipe-card-phone" onclick="event.stopPropagation()">${phone}</a>` : ''}
          <div class="swipe-card-desc">${escapeHtml(req.text || 'Без опису')}</div>
        </div>
        
        <div class="swipe-card-footer">
          Створено: ${date}
        </div>
      </div>
    `;

    deck.insertAdjacentHTML('afterbegin', cardHtml);
  });

  bindSwipeEvents();
}

function bindSwipeEvents() {
  const cards = document.querySelectorAll('.swipe-card');
  if (cards.length === 0) return;

  const topCard = cards[cards.length - 1];
  const reqId = parseInt(topCard.dataset.id);

  let startX = 0;
  let startY = 0;
  let currentX = 0;
  let currentY = 0;
  let isDragging = false;

  const badgeAccept = topCard.querySelector('.badge-accept');
  const badgeReject = topCard.querySelector('.badge-reject');
  const badgeSkip = topCard.querySelector('.badge-skip');

  topCard.addEventListener('mousedown', startDrag);
  topCard.addEventListener('touchstart', startDrag, { passive: true });

  function startDrag(e) {
    isDragging = true;
    topCard.classList.add('dragging');

    const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
    const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY;

    startX = clientX;
    startY = clientY;

    document.addEventListener('mousemove', dragMove);
    document.addEventListener('touchmove', dragMove, { passive: false });

    document.addEventListener('mouseup', endDrag);
    document.addEventListener('touchend', endDrag);
  }

  function dragMove(e) {
    if (!isDragging) return;

    if (e.cancelable) e.preventDefault();

    const clientX = e.type.includes('touch') ? e.touches[0].clientX : e.clientX;
    const clientY = e.type.includes('touch') ? e.touches[0].clientY : e.clientY;

    currentX = clientX - startX;
    currentY = clientY - startY;

    const rotate = currentX * 0.08;
    topCard.style.transform = `translate3d(${currentX}px, ${currentY}px, 0) rotate(${rotate}deg)`;

    if (currentX > 30) {
      const opacity = Math.min(currentX / 120, 1);
      badgeAccept.style.opacity = opacity;
      badgeReject.style.opacity = '0';
      badgeSkip.style.opacity = '0';
    } else if (currentX < -30) {
      const opacity = Math.min(Math.abs(currentX) / 120, 1);
      badgeReject.style.opacity = opacity;
      badgeAccept.style.opacity = '0';
      badgeSkip.style.opacity = '0';
    } else if (currentY < -30) {
      const opacity = Math.min(Math.abs(currentY) / 120, 1);
      badgeSkip.style.opacity = opacity;
      badgeAccept.style.opacity = '0';
      badgeReject.style.opacity = '0';
    } else {
      badgeAccept.style.opacity = '0';
      badgeReject.style.opacity = '0';
      badgeSkip.style.opacity = '0';
    }
  }

  function endDrag() {
    if (!isDragging) return;
    isDragging = false;
    topCard.classList.remove('dragging');

    document.removeEventListener('mousemove', dragMove);
    document.removeEventListener('touchmove', dragMove);
    document.removeEventListener('mouseup', endDrag);
    document.removeEventListener('touchend', endDrag);

    const thresholdX = 120;
    const thresholdY = -120;

    if (currentX > thresholdX) {
      animateSwipeOut(topCard, 'right', () => {
        handleSwipeAction(reqId, 'accept');
      });
    } else if (currentX < -thresholdX) {
      animateSwipeOut(topCard, 'left', () => {
        handleSwipeAction(reqId, 'reject');
      });
    } else if (currentY < thresholdY) {
      animateSwipeOut(topCard, 'up', () => {
        handleSwipeAction(reqId, 'skip');
      });
    } else {
      topCard.style.transform = '';
      badgeAccept.style.opacity = '0';
      badgeReject.style.opacity = '0';
      badgeSkip.style.opacity = '0';
    }
  }
}

function animateSwipeOut(card, direction, callback) {
  card.style.transition = 'transform 0.4s ease, opacity 0.4s ease';

  if (direction === 'right') {
    card.style.transform = 'translate3d(1000px, 0, 0) rotate(45deg)';
  } else if (direction === 'left') {
    card.style.transform = 'translate3d(-1000px, 0, 0) rotate(-45deg)';
  } else if (direction === 'up') {
    card.style.transform = 'translate3d(0, -1000px, 0) scale(0.8)';
  }

  card.style.opacity = '0';

  try {
    tg.HapticFeedback.impactOccurred('medium');
  } catch (e) {}

  setTimeout(() => {
    card.remove();
    callback();
  }, 400);
}

async function handleSwipeAction(reqId, action) {
  if (action === 'accept') {
    try {
      const response = await apiFetch(`${API_BASE}/api/twa/admin/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_id: userId,
          request_id: reqId,
          action: 'accept'
        })
      });
      if (!response.ok) throw new Error();

      showToast('Заявку взято в роботу', 'success');
      
      openReplyModal(reqId);
      
      // Temporary override modal close/submit behaviors for swipe workflow
      const originalClose = closeReplyModal;
      closeReplyModal = function() {
        originalClose();
        closeReplyModal = originalClose; // restore
        swipeActiveCardIndex++;
        renderSwipeCards();
      };

      const originalSubmit = submitAdminReply;
      submitAdminReply = async function() {
        await originalSubmit();
        submitAdminReply = originalSubmit; // restore
      };

    } catch (err) {
      console.error(err);
      showToast('Помилка оновлення статусу', 'error');
      loadAdminSwipeDeck();
    }
  } else if (action === 'reject') {
    if (!confirm('Ви впевнені, що хочете відхилити цю заявку?')) {
      loadAdminSwipeDeck();
      return;
    }

    try {
      const response = await apiFetch(`${API_BASE}/api/twa/admin/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          admin_id: userId,
          request_id: reqId,
          action: 'reject'
        })
      });
      if (!response.ok) throw new Error();

      showToast('Заявку відхилено', 'success');
      swipeActiveCardIndex++;
      renderSwipeCards();
    } catch (err) {
      console.error(err);
      showToast('Помилка відхилення заявки', 'error');
      loadAdminSwipeDeck();
    }
  } else if (action === 'skip') {
    const req = swipeQueue.find(r => r.id === reqId);
    if (req) {
      swipeQueue.splice(swipeActiveCardIndex, 1);
      swipeQueue.push(req);
      renderSwipeCards();
      showToast('Заявку пропущено', 'info');
    }
  }
}

// ─── Modal Operations ─────────────────────────
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
    reloadActiveAdminTab();

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
