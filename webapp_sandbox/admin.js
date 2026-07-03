const tg = window.Telegram ? window.Telegram.WebApp : null;
const API_BASE = window.location.origin;

let userId = null;
let isAdmin = false;
let currentAdminTab = 'list';
let activeReplyRequestId = null;

let currentStatusValue = 'pending';
let currentSortValue = 'oldest';

// Константи черги свайпів
let swipeQueue = [];
let swipeActiveCardIndex = 0;

window.addEventListener('DOMContentLoaded', async () => {
  if (tg) {
    tg.ready(); tg.expand();
    const user = tg.initDataUnsafe?.user;
    if (user) userId = user.id;
  } else {
    userId = 684877221; 
  }
  
  if (userId) {
    try {
      const res = await fetch(`${API_BASE}/api/twa/user-info?user_id=${userId}`);
      const data = await res.json();
      if (data.status === 'ok' && data.is_admin) isAdmin = true;
    } catch (e) { console.error('Помилка авторизації адміна', e); }
  }
  
  isAdmin = true; // Для тестування

  if (!isAdmin) {
    document.body.innerHTML = `<div style="text-align:center; padding:48px; color:var(--error);">Доступ обмежено.</div>`;
    return;
  }
  
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-dropdown')) {
      document.querySelectorAll('.custom-dropdown').forEach(d => d.classList.remove('active'));
    }
  });

  switchAdminTab('list');
});

// ВИПРАВЛЕНО: Таб-перемикач тепер коректно ініціює Свайп-панель
function switchAdminTab(tabId) {
  currentAdminTab = tabId;
  
  document.querySelectorAll('.admin-tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `admin-tab-${tabId}`);
  });
  
  document.getElementById('nav-item-list').classList.toggle('active', tabId === 'list');
  document.getElementById('nav-item-swipe').classList.toggle('active', tabId === 'swipe');
  
  if (tabId === 'list') {
    loadAdminRequests();
  } else if (tabId === 'swipe') {
    loadAdminSwipeDeck();
  }
  
  try { lucide.createIcons(); } catch (e) {}
}

function toggleDropdown(dropdownId) {
  const dropdown = document.getElementById(dropdownId);
  const isOpen = dropdown.classList.contains('active');
  document.querySelectorAll('.custom-dropdown').forEach(d => d.classList.remove('active'));
  if (!isOpen) dropdown.classList.add('active');
}

function selectDropdownOption(dropdownId, value, labelText) {
  const dropdown = document.getElementById(dropdownId);
  dropdown.querySelector('.dropdown-selected-text').textContent = labelText;
  dropdown.querySelectorAll('.dropdown-item').forEach(item => {
    item.classList.toggle('active', item.getAttribute('data-value') === value);
  });
  
  if (dropdownId === 'dropdown-status') currentStatusValue = value;
  else if (dropdownId === 'dropdown-sort') currentSortValue = value;
  
  dropdown.classList.remove('active');
  loadAdminRequests();
}

async function loadAdminRequests() {
  const list = document.getElementById('admin-requests-list');
  const empty = document.getElementById('admin-empty');
  list.innerHTML = ''; 
  empty.style.display = 'none';

  try {
    const res = await fetch(`${API_BASE}/api/twa/admin/requests?admin_id=${userId}&status=${currentStatusValue}`);
    let data = await res.json();
    
    if(!data || !data.length) { empty.style.display = 'block'; return; }
    
    if(currentSortValue === 'newest') data.sort((a,b) => new Date(b.created_at) - new Date(a.created_at));
    else data.sort((a,b) => new Date(a.created_at) - new Date(b.created_at));

    data.forEach(req => {
      const card = `
        <div class="request-card">
          <div class="request-header">
            <span style="font-weight:700; font-size:13px;">№ ${req.id} | ${req.name || 'Клієнт'}</span>
            <span class="request-date">${new Date(req.created_at).toLocaleDateString('uk-UA')}</span>
          </div>
          <div style="font-size:13px; margin:8px 0; color:var(--text-muted); line-height:1.5;">${req.text || 'Без опису'}</div>
          <div style="display:flex; gap:8px; margin-top:12px;">
            <button class="btn btn-secondary" style="padding:8px; font-size:12px;" onclick="openReplyModal(${req.id})">Відповісти</button>
            <button class="btn btn-primary" style="padding:8px; font-size:12px; background:#22c55e; color:#fff;" onclick="handleAdminAction(${req.id}, 'accept')">В роботу</button>
          </div>
        </div>
      `;
      list.insertAdjacentHTML('beforeend', card);
    });
  } catch(e) { empty.style.display = 'block'; }
}

// ВИПРАВЛЕНО: Повний цикл завантаження Експрес-черги (Swipe Deck)
async function loadAdminSwipeDeck() {
  const deck = document.getElementById('swipe-card-deck');
  const empty = document.getElementById('swipe-empty');
  
  deck.innerHTML = '';
  empty.style.display = 'none';
  
  try {
    const res = await fetch(`${API_BASE}/api/twa/admin/requests?admin_id=${userId}&status=pending`);
    const requests = await res.json();
    
    if(!requests || !requests.length) {
      empty.style.display = 'block';
      return;
    }
    
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
    return;
  }
  
  currentCards.forEach((req, idx) => {
    const cardHtml = `
      <div class="swipe-card" id="swipe-card-${req.id}" data-id="${req.id}" style="position: absolute; width: 100%; background: #fff; border: 1px solid #ebeeef; border-radius: 16px; padding: 20px; box-shadow: 0 8px 24px rgba(0,0,0,0.04); height: 320px; display: flex; flex-direction: column; justify-content: space-between; z-index: ${10 - idx}; transform: translateY(${idx * 8}px) scale(${1 - idx * 0.04}); transition: transform 0.3s ease;">
        <div>
          <div style="display:flex; justify-content:between; font-size:11px; color:#9aa1b1; margin-bottom:8px;">
            <span>Заявка №${req.id}</span>
            <span style="margin-left:auto;">${new Date(req.created_at).toLocaleDateString()}</span>
          </div>
          <h3 style="font-size:16px; font-weight:700; margin-bottom:4px;">${req.name || 'Без імені'}</h3>
          <p style="font-size:13px; color:#475569; overflow-y:auto; max-height:160px; line-height:1.5;">${req.text || 'Опис відсутній'}</p>
        </div>
        <div style="display:flex; gap:10px;">
          <button class="btn btn-secondary" style="padding:10px; font-size:12px;" onclick="handleSwipeAction(${req.id}, 'reject')">Відхилити ❌</button>
          <button class="btn btn-primary" style="padding:10px; font-size:12px; background:#22c55e;" onclick="handleSwipeAction(${req.id}, 'accept')">В роботу ✅</button>
        </div>
      </div>
    `;
    deck.insertAdjacentHTML('beforeend', cardHtml);
  });
}

async function handleSwipeAction(reqId, action) {
  try {
    await fetch(`${API_BASE}/api/twa/admin/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_id: userId, request_id: reqId, action: action })
    });
    
    if(action === 'accept') {
      openReplyModal(reqId);
    }
    
    swipeActiveCardIndex++;
    renderSwipeCards();
  } catch(e) {
    showToast('Помилка обробки дії');
  }
}

async function handleAdminAction(requestId, action) {
  try {
    await fetch(`${API_BASE}/api/twa/admin/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_id: userId, request_id: requestId, action: action })
    });
    loadAdminRequests();
  } catch(e){}
}

function openReplyModal(requestId) {
  activeReplyRequestId = requestId;
  document.getElementById('reply-modal').classList.add('active');
  document.getElementById('reply-modal-subtitle').textContent = `Справа № ${requestId}`;
}

function closeReplyModal() {
  document.getElementById('reply-modal').classList.remove('active');
}

async function submitAdminReply() {
  const text = document.getElementById('reply-text-input').value.trim();
  if(!text) return;
  try {
    await fetch(`${API_BASE}/api/twa/admin/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_id: userId, request_id: activeReplyRequestId, action: 'reply', reply_text: text })
    });
    closeReplyModal();
    if(currentAdminTab === 'list') loadAdminRequests();
  } catch(e){}
}