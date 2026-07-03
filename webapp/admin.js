const tg = window.Telegram ? window.Telegram.WebApp : null;
const API_BASE = window.location.origin;

let userId = null;
let username = null;
let isAdmin = false;

let currentAdminTab = 'list';
let adminRequests = [];
let swipeQueue = [];
let swipeActiveCardIndex = 0;
let activeReplyRequestId = null;

let activeStatusFilter = 'pending';
let activeSortOrder = 'oldest';

// Concurrency lock to prevent double-swiping while card animations or modals are active
let isSwipeProcessing = false;

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
    }
  } else {
    // Fallback for browser testing (simulate admin)
    userId = 684877221;
    username = 'admin_test';
  }
  
  // Verify admin status on the server
  if (userId) {
    try {
      const response = await fetch(`${API_BASE}/api/twa/user-info?user_id=${userId}`);
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
      <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100vh; padding:24px; text-align:center; background:#131316; color:#ffffff; font-family:'Inter', sans-serif;">
        <i data-lucide="shield-alert" style="width:64px; height:64px; color:#ef4444; margin-bottom:16px;"></i>
        <h2 style="font-size:20px; font-weight:700; margin-bottom:8px;">Доступ заборонено</h2>
        <p style="font-size:14px; color:#9aa1b1; max-width:280px; line-height:1.5;">Ця панель призначена виключно для адміністраторів компанії LegalTax.</p>
      </div>
    `;
    try { lucide.createIcons(); } catch (e) {}
    return;
  }
  
  switchAdminTab('list');
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

// ─── Dropdown Controls (Using active class) ────
function toggleDropdown(id) {
  const dropdown = document.getElementById(id);
  if (dropdown) {
    dropdown.classList.toggle('active');
  }
  
  document.querySelectorAll('.custom-dropdown').forEach(d => {
    if (d.id !== id) d.classList.remove('active');
  });
}

// ─── Select dropdown filter options ───
function selectDropdownOption(dropdownId, value, text) {
  const dropdown = document.getElementById(dropdownId);
  if (dropdown) {
    const textEl = dropdown.querySelector('.dropdown-selected-text');
    if (textEl) textEl.textContent = text;
    dropdown.classList.remove('active');
    
    dropdown.querySelectorAll('.dropdown-item').forEach(item => {
      item.classList.toggle('active', item.dataset.value === value);
    });
  }
  
  if (dropdownId === 'dropdown-status') {
    activeStatusFilter = value;
  } else if (dropdownId === 'dropdown-sort') {
    activeSortOrder = value;
  }
  
  loadAdminRequests();
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('.custom-dropdown')) {
    document.querySelectorAll('.custom-dropdown').forEach(d => d.classList.remove('active'));
  }
});

// ─── Tab Switching ────────────────────────────
function switchAdminTab(tabId) {
  currentAdminTab = tabId;
  
  document.querySelectorAll('.admin-tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `admin-tab-${tabId}`);
  });
  
  document.querySelectorAll('.nav-item').forEach(item => {
    item.classList.toggle('active', item.id === `nav-item-${tabId}`);
  });
  
  // Reset swipe lock when switching tabs
  isSwipeProcessing = false;
  
  if (tabId === 'list') {
    loadAdminRequests();
  } else {
    loadAdminSwipeDeck();
  }
  
  try {
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
  } catch (e) {}
}

// ─── List Dashboard Loader ────────────────────
async function loadAdminRequests() {
  const list = document.getElementById('admin-requests-list');
  const empty = document.getElementById('admin-empty');

  list.innerHTML = `
    <div style="text-align:center; padding:30px 0; color:var(--text-light); font-size:13px;">Завантаження заяв...</div>
  `;
  empty.style.display = 'none';

  if (!userId || !isAdmin) {
    list.innerHTML = '';
    empty.style.display = 'block';
    return;
  }

  try {
    const response = await fetch(`${API_BASE}/api/twa/admin/requests?admin_id=${userId}&status=${activeStatusFilter}`);
    if (!response.ok) throw new Error();
    
    let requests = await response.json();
    
    if (activeSortOrder === 'newest') {
      requests.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    } else {
      requests.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    }
    
    adminRequests = requests;
    list.innerHTML = '';

    if (!requests || !requests.length) {
      empty.style.display = 'block';
      return;
    }

    requests.forEach(req => {
      const card = renderAdminRequestCard(req);
      list.insertAdjacentHTML('beforeend', card);
    });
    
    try { lucide.createIcons(); } catch (e) {}
  } catch (error) {
    console.error('Error loading admin requests:', error);
    list.innerHTML = '';
    empty.style.display = 'block';
    showToast('Не вдалося завантажити дані');
  }
}

function renderAdminRequestCard(req) {
  const date = new Date(req.created_at).toLocaleDateString('uk-UA');
  const time = new Date(req.created_at).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
  const phone = req.phone ? formatPhone(req.phone) : '';

  const sourceLabels = {
    bot: 'Бот 🤖',
    webapp: 'Mini App 📱',
    admin: 'Адмін ⚙️',
    web: 'Сайт 🌐'
  };

  let actionButtonsHtml = '';
  if (req.status === 'pending') {
    actionButtonsHtml = `
      <button class="btn btn-primary" style="padding:6px 12px; font-size:12px; background:#22c55e;" onclick="handleAdminAction(${req.id}, 'accept')">В роботу</button>
      <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px; color:#ef4444;" onclick="handleAdminAction(${req.id}, 'reject')">Відхилити</button>
      <button class="btn btn-primary" style="padding:6px 12px; font-size:12px;" onclick="openReplyModal(${req.id})">Відповісти</button>
    `;
  } else if (req.status === 'in_progress') {
    actionButtonsHtml = `
      <button class="btn btn-primary" style="padding:6px 12px; font-size:12px;" onclick="openReplyModal(${req.id})">Відповісти</button>
      <button class="btn btn-secondary" style="padding:6px 12px; font-size:12px; color:#ef4444;" onclick="handleAdminAction(${req.id}, 'reject')">Відхилити</button>
    `;
  } else {
    actionButtonsHtml = `
      <span style="font-size:12px; font-weight:600; color:#64748b; padding:4px 8px;">Оброблено</span>
    `;
  }

  return `
    <div class="request-card" style="margin-bottom:14px; background:#ffffff; padding:16px; border:1px solid #ebeeef; border-radius:16px; box-shadow:0 4px 12px rgba(0,0,0,0.01);">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:10px;">
        <span style="font-size:11px; font-weight:600; padding:3px 8px; border-radius:4px; background:#f1f5f9; color:#475569;">
          ${sourceLabels[req.source] || req.source}
        </span>
        <span style="font-size:11px; color:#9aa1b1; font-weight:500;">${date} о ${time}</span>
      </div>
      <div style="font-size:14px; font-weight:700; color:#0f172a; margin-bottom:4px;">
        ${escapeHtml(req.name || 'Без імені')}
      </div>
      ${phone ? `<a href="tel:${phone}" style="font-size:12px; color:#aa4b70; text-decoration:none; display:inline-block; margin-bottom:8px; font-weight:500;">${phone}</a>` : ''}
      <div style="font-size:13px; color:#334155; line-height:1.5; margin-bottom:12px; word-break:break-word;">
        ${escapeHtml(req.text || 'Без опису')}
      </div>
      <div style="display:flex; gap:8px; justify-content:flex-end; border-top:1px solid #f1f5f9; padding-top:10px;">
        ${actionButtonsHtml}
      </div>
    </div>
  `;
}

// ─── Swipe Deck Dashboard ────────────────────
async function loadAdminSwipeDeck() {
  const deck = document.getElementById('swipe-card-deck');
  const empty = document.getElementById('swipe-empty');
  
  deck.innerHTML = '';
  empty.style.display = 'none';
  isSwipeProcessing = false;
  
  try {
    const res = await fetch(`${API_BASE}/api/twa/admin/requests?admin_id=${userId}&status=pending`);
    const requests = await res.json();
    
    if(!requests || !requests.length) {
      empty.style.display = 'block';
      return;
    }
    
    // Sort oldest first for deck queue
    requests.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    
    swipeQueue = requests;
    swipeActiveCardIndex = 0;
    renderSwipeCards();
  } catch(e) {
    empty.style.display = 'block';
  }
}

function renderSwipeCards() {
  const deck = document.getElementById('swipe-card-deck');
  deck.innerHTML = '';
  
  const currentCards = swipeQueue.slice(swipeActiveCardIndex, swipeActiveCardIndex + 3);
  if(!currentCards.length) {
    document.getElementById('swipe-empty').style.display = 'block';
    isSwipeProcessing = false;
    return;
  }
  
  currentCards.forEach((req, idx) => {
    const date = new Date(req.created_at).toLocaleDateString('uk-UA');
    const time = new Date(req.created_at).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
    const phone = req.phone ? formatPhone(req.phone) : '';
    
    const cardHtml = `
      <div class="swipe-card" id="swipe-card-${req.id}" data-id="${req.id}" style="z-index: ${10 - idx}; transform: translateY(${idx * 8}px) scale(${1 - idx * 0.04});">
        
        <div class="swipe-card-inner">
          <div>
            <div style="display:flex; justify-content:space-between; font-size:11px; color:#9aa1b1; margin-bottom:8px;">
              <span>Заявка №${req.id}</span>
              <span>${date} о ${time}</span>
            </div>
            <h3 style="font-size:16px; font-weight:700; margin-bottom:4px; color:#0f172a;">${escapeHtml(req.name || 'Без імені')}</h3>
            ${phone ? `<a href="tel:${phone}" style="font-size:12px; color:#aa4b70; text-decoration:none; display:inline-block; margin-bottom:8px; font-weight:500;">${phone}</a>` : ''}
            <p style="font-size:13px; color:#475569; overflow-y:auto; max-height:160px; line-height:1.5; margin-top:6px; word-break:break-word;">
              ${escapeHtml(req.text || 'Опис відсутній')}
            </p>
          </div>
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

  const bgBadge = document.getElementById('swipe-bg-badge');

  topCard.addEventListener('mousedown', startDrag);
  topCard.addEventListener('touchstart', startDrag, { passive: true });

  function startDrag(e) {
    if (isSwipeProcessing) return; // Prevent double swiping
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

    // Tint card background color and show background badge
    if (currentX > 30) {
      const opacity = Math.min(currentX / 120, 1);
      if (bgBadge) {
        bgBadge.className = 'swipe-bg-badge accept';
        bgBadge.textContent = 'В роботу';
        bgBadge.style.opacity = opacity;
      }
      const greenTint = Math.min(currentX / 240, 0.15);
      topCard.style.backgroundColor = `rgba(34, 197, 94, ${greenTint})`;
    } else if (currentX < -30) {
      const opacity = Math.min(Math.abs(currentX) / 120, 1);
      if (bgBadge) {
        bgBadge.className = 'swipe-bg-badge reject';
        bgBadge.textContent = 'Відхилити';
        bgBadge.style.opacity = opacity;
      }
      const redTint = Math.min(Math.abs(currentX) / 240, 0.15);
      topCard.style.backgroundColor = `rgba(239, 68, 68, ${redTint})`;
    } else if (currentY < -30) {
      const opacity = Math.min(Math.abs(currentY) / 120, 1);
      if (bgBadge) {
        bgBadge.className = 'swipe-bg-badge skip';
        bgBadge.textContent = 'Пропустити';
        bgBadge.style.opacity = opacity;
      }
      const yellowTint = Math.min(Math.abs(currentY) / 240, 0.15);
      topCard.style.backgroundColor = `rgba(245, 158, 11, ${yellowTint})`;
    } else {
      if (bgBadge) {
        bgBadge.style.opacity = '0';
        bgBadge.className = 'swipe-bg-badge';
      }
      topCard.style.backgroundColor = '#ffffff';
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
      isSwipeProcessing = true; // Lock actions
      if (bgBadge) {
        bgBadge.style.opacity = '0';
        bgBadge.className = 'swipe-bg-badge';
      }
      animateSwipeOut(topCard, 'right', () => {
        handleSwipeAction(reqId, 'accept', true);
      });
    } else if (currentX < -thresholdX) {
      isSwipeProcessing = true; // Lock actions
      if (bgBadge) {
        bgBadge.style.opacity = '0';
        bgBadge.className = 'swipe-bg-badge';
      }
      animateSwipeOut(topCard, 'left', () => {
        handleSwipeAction(reqId, 'reject', true);
      });
    } else if (currentY < thresholdY) {
      isSwipeProcessing = true; // Lock actions
      if (bgBadge) {
        bgBadge.style.opacity = '0';
        bgBadge.className = 'swipe-bg-badge';
      }
      animateSwipeOut(topCard, 'up', () => {
        handleSwipeAction(reqId, 'skip', true);
      });
    } else {
      topCard.style.transform = '';
      topCard.style.backgroundColor = '#ffffff';
      if (bgBadge) {
        bgBadge.style.opacity = '0';
        bgBadge.className = 'swipe-bg-badge';
      }
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
    if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('medium');
  } catch (e) {}

  setTimeout(() => {
    card.remove();
    callback();
  }, 400);
}

async function handleSwipeAction(reqId, action, isFromSwipe = false) {
  if (!isFromSwipe && isSwipeProcessing) return;
  isSwipeProcessing = true;

  if (action === 'skip') {
    const req = swipeQueue.find(r => r.id === reqId);
    if (req) {
      swipeQueue.splice(swipeActiveCardIndex, 1);
      swipeQueue.push(req);
      renderSwipeCards();
      showToast('Заявку відкладено ⏳');
    }
    isSwipeProcessing = false; // Reset lock
    return;
  }

  if (action === 'reject') {
    if (!confirm('Ви впевнені, що хочете відхилити цю заявку?')) {
      loadAdminSwipeDeck();
      isSwipeProcessing = false;
      return;
    }
  }

  try {
    const res = await fetch(`${API_BASE}/api/twa/admin/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_id: userId, request_id: reqId, action: action })
    });
    
    if (!res.ok) {
      const errData = await res.json();
      showToast(errData.detail || 'Помилка виконання дії');
      loadAdminSwipeDeck();
      isSwipeProcessing = false;
      return;
    }
    
    if (action === 'accept') {
      showToast('Заявку прийнято в роботу! ⚙️');
      openReplyModal(reqId);
      
      const originalClose = closeReplyModal;
      closeReplyModal = function() {
        originalClose();
        closeReplyModal = originalClose; // restore
        swipeActiveCardIndex++;
        renderSwipeCards();
        isSwipeProcessing = false; // Unlock only when modal closes
      };
      
      const originalSubmit = submitAdminReply;
      submitAdminReply = async function() {
        await originalSubmit();
        submitAdminReply = originalSubmit; // restore
      };
    } else {
      showToast('Заявку відхилено! ❌');
      swipeActiveCardIndex++;
      renderSwipeCards();
      isSwipeProcessing = false; // Unlock
    }
  } catch(e) {
    showToast('Помилка обробки дії');
    loadAdminSwipeDeck();
    isSwipeProcessing = false;
  }
}

async function handleAdminAction(requestId, action) {
  if (action === 'reject') {
    if (!confirm('Ви впевнені, що хочете відхилити цю заявку?')) return;
  }
  
  try {
    const res = await fetch(`${API_BASE}/api/twa/admin/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_id: userId, request_id: requestId, action: action })
    });
    
    if (!res.ok) {
      const errData = await res.json();
      showToast(errData.detail || 'Помилка');
      return;
    }
    
    showToast(action === 'accept' ? 'Заявку прийнято в роботу ⚙️' : 'Заявку відхилено ❌');
    loadAdminRequests();
  } catch(e){
    showToast('Помилка виконання дії');
  }
}

// ─── Modal Operations ─────────────────────────
function openReplyModal(requestId) {
  activeReplyRequestId = requestId;
  document.getElementById('reply-modal').classList.add('active');
  document.getElementById('reply-modal-subtitle').textContent = `Справа № ${requestId}`;
  
  const err = document.getElementById('error-reply-text');
  if (err) err.classList.remove('visible');
  document.getElementById('reply-text-input').value = '';
}

function closeReplyModal() {
  document.getElementById('reply-modal').classList.remove('active');
  // Reset lock if modal closed manually
  isSwipeProcessing = false;
}

async function submitAdminReply() {
  const text = document.getElementById('reply-text-input').value.trim();
  if(!text) return;
  
  const btn = document.getElementById('btn-submit-reply');
  if (btn && btn.disabled) return; // Prevent double clicks on reply sending

  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Надсилаємо...';
  }

  try {
    const res = await fetch(`${API_BASE}/api/twa/admin/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_id: userId, request_id: activeReplyRequestId, action: 'reply', reply_text: text })
    });
    
    if (!res.ok) {
      const errData = await res.json();
      showToast(errData.detail || 'Помилка відправки');
      return;
    }
    
    showToast('Відповідь надіслано користувачу! 💬');
    closeReplyModal();
    if(currentAdminTab === 'list') loadAdminRequests();
  } catch(e){
    showToast('Помилка відправки відповіді');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Відправити в чат';
    }
  }
}

// ─── Helpers ──────────────────────────────────
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

function showToast(msg) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const el = document.createElement('div');
  el.style.background = '#131316';
  el.style.color = '#fff';
  el.style.padding = '10px 16px';
  el.style.borderRadius = '8px';
  el.style.marginTop = '6px';
  el.style.fontSize = '13px';
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => el.remove(), 2500);
}