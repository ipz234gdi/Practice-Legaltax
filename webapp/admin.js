const tg = window.Telegram ? window.Telegram.WebApp : null;
const API_BASE = window.location.origin;

let userId = null;
let isAdmin = false;
let currentAdminTab = 'list';
let activeReplyRequestId = null;

// Поточні обрані значення з кастомних дропдаунів
let currentStatusValue = 'pending';
let currentSortValue = 'oldest';

window.addEventListener('DOMContentLoaded', async () => {
  if (tg) {
    tg.ready(); tg.expand();
    const user = tg.initDataUnsafe?.user;
    if (user) userId = user.id;
  } else {
    userId = 684877221; 
  }
  
  // Перевірка прав адміна
  if (userId) {
    try {
      const res = await fetch(`${API_BASE}/api/twa/user-info?user_id=${userId}`);
      const data = await res.json();
      if (data.status === 'ok' && data.is_admin) isAdmin = true;
    } catch (e) { console.error('Помилка авторизації адміна', e); }
  }
  
  isAdmin = true; // Для тестів локально

  if (!isAdmin) {
    document.body.innerHTML = `<div style="text-align:center; padding:48px; color:var(--error);">Доступ обмежено.</div>`;
    return;
  }
  
  // Закриття дропдаунів при кліку повз них
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.custom-dropdown')) {
      document.querySelectorAll('.custom-dropdown').forEach(d => d.classList.remove('active'));
    }
  });

  switchAdminTab('list');
});

// Керування нижньою нативною навігацією (без дублювання зверху)
function switchAdminTab(tabId) {
  currentAdminTab = tabId;
  
  document.querySelectorAll('.admin-tab-content').forEach(content => {
    content.classList.toggle('active', content.id === `admin-tab-${tabId}`);
  });
  
  // Оновлення активного класу в нижньому навігаційному барі
  document.getElementById('nav-item-list').classList.toggle('active', tabId === 'list');
  document.getElementById('nav-item-swipe').classList.toggle('active', tabId === 'swipe');
  
  if (tabId === 'list') loadAdminRequests();
  try { lucide.createIcons(); } catch (e) {}
}

// Кастомна логіка дропдаунів
function toggleDropdown(dropdownId) {
  const dropdown = document.getElementById(dropdownId);
  const isOpen = dropdown.classList.contains('active');
  
  // Закриваємо інші відкриті меню
  document.querySelectorAll('.custom-dropdown').forEach(d => d.classList.remove('active'));
  
  if (!isOpen) {
    dropdown.classList.add('active');
  }
}

function selectDropdownOption(dropdownId, value, labelText) {
  const dropdown = document.getElementById(dropdownId);
  dropdown.querySelector('.dropdown-selected-text').textContent = labelText;
  
  dropdown.querySelectorAll('.dropdown-item').forEach(item => {
    item.classList.toggle('active', item.getAttribute('data-value') === value);
  });
  
  if (dropdownId === 'dropdown-status') {
    currentStatusValue = value;
  } else if (dropdownId === 'dropdown-sort') {
    currentSortValue = value;
  }
  
  dropdown.classList.remove('active');
  loadAdminRequests(); // Перезавантажуємо список із новими параметрами
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
    
    if(currentSortValue === 'newest') {
      data.sort((a,b) => new Date(b.created_at) - new Date(a.created_at));
    } else {
      data.sort((a,b) => new Date(a.created_at) - new Date(b.created_at));
    }

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
    loadAdminRequests();
  } catch(e){}
}