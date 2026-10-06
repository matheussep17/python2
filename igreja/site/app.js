const defaultMedia = [
  { title: 'Quando a esperança parece pequena', type: 'video', label: 'Vídeo', detail: 'Mensagem · 42 min' },
  { title: 'Uma fé que descansa', type: 'audio', label: 'Áudio', detail: 'Mensagem · 35 min' },
  { title: 'Começos — série especial', type: 'video', label: 'Vídeo', detail: 'Série · 3 episódios' },
  { title: 'Guia de oração semanal', type: 'pdf', label: 'PDF', detail: 'Material · 4 páginas' },
  { title: 'Culto de celebração', type: 'video', label: 'Vídeo', detail: 'Culto · 58 min' },
  { title: 'Devocional: dias de coragem', type: 'audio', label: 'Áudio', detail: 'Devocional · 12 min' },
];
const defaultEvents = [
  { title: 'Almoço da igreja', date: '15 JUN', description: 'Um domingo para compartilhar a mesa e boas conversas.', category: 'Comunidade' },
  { title: 'Encontro de famílias', date: '22 JUN', description: 'Uma noite especial para fortalecer nossos lares.', category: 'Famílias' },
  { title: 'Noite jovem', date: '29 JUN', description: 'Música, amizade e uma palavra que inspira.', category: 'Juventude' },
];

function loadMedia() {
  try { return JSON.parse(localStorage.getItem('igreja-media')) || defaultMedia; } catch { return defaultMedia; }
}
function renderMedia() {
  const grid = document.querySelector('#media-grid');
  if (!grid) return;
  const query = (document.querySelector('#media-search')?.value || '').toLowerCase();
  const filter = document.querySelector('#media-filter')?.value || 'all';
  const items = loadMedia().filter(item => (filter === 'all' || item.type === filter) && item.title.toLowerCase().includes(query));
  grid.innerHTML = items.length ? items.map(item => `<article class="media-card"><div class="media-type">${item.label}</div><h3>${item.title}</h3><p>${item.detail}</p><a href="#contato">Acessar conteúdo →</a></article>`).join('') : '<p>Nenhum conteúdo encontrado.</p>';
}
function renderPublicEvents() {
  const grid = document.querySelector('#public-event-list');
  if (!grid) return;
  let events = defaultEvents;
  try { events = JSON.parse(localStorage.getItem('igreja-events')) || defaultEvents; } catch {}
  grid.innerHTML = events.slice(0, 6).map(item => `<article class="event-card"><div class="date"><b>${String(item.date || '').split(' ')[0] || '—'}</b><span>${String(item.date || '').split(' ')[1] || 'DATA'}</span></div><div><p class="card-tag">${item.category || 'Agenda'}</p><h3>${item.title}</h3><p>${item.description}</p></div></article>`).join('');
}
document.querySelector('#media-search')?.addEventListener('input', renderMedia);
document.querySelector('#media-filter')?.addEventListener('change', renderMedia);
document.querySelector('#contact-form')?.addEventListener('submit', (event) => { event.preventDefault(); const data = Object.fromEntries(new FormData(event.target)); data.createdAt = new Date().toISOString(); const messages = JSON.parse(localStorage.getItem('igreja-messages') || '[]'); messages.push(data); localStorage.setItem('igreja-messages', JSON.stringify(messages)); event.target.reset(); event.target.querySelector('.form-feedback').textContent = 'Recebemos sua mensagem. Obrigado por confiar em nós.'; });
renderMedia();
renderPublicEvents();
