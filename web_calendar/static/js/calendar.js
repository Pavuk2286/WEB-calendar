document.addEventListener('DOMContentLoaded', () => {
  const pad = n => String(n).padStart(2, '0');
  const fmtIso = (y, m, d) => `${y}-${pad(m)}-${pad(d)}`;

  const grid        = document.getElementById('calendar-grid');
  const monthYear   = document.getElementById('month-year');
  const todayBtn    = document.getElementById('today-btn');
  const todayNum    = document.getElementById('today-number');
  const prevBtn     = document.getElementById('prev-month');
  const nextBtn     = document.getElementById('next-month');
  const viewBtns    = document.querySelectorAll('.view-button');
  const viewPanel   = document.getElementById('view-panel');
  const editPanel   = document.getElementById('edit-panel');
  const list        = document.getElementById('events-list');
  const addBtn      = document.getElementById('add-event');
  const form        = document.getElementById('event-form');
  const deleteBtn   = document.getElementById('delete-btn');
  const closeEdit   = document.getElementById('close-edit');
  const closeView   = document.getElementById('close-view');
  const selDateEl   = document.getElementById('selected-date');
  const colorSelect = document.getElementById('color-select');

  let currentDate  = new Date();
  let activeDate;
  let events = [];
  let currentView = 'day';
  let dragData = null;

  function renderCalendar() {
    grid.innerHTML = '';
    const y = currentDate.getFullYear(), m = currentDate.getMonth();
    monthYear.textContent = currentDate.toLocaleString('ru', { month: 'long', year: 'numeric' });

    // Заголовки дней недели
    ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].forEach(l => {
      const h = document.createElement('div');
      h.className = 'day-header';
      h.textContent = l;
      grid.appendChild(h);
    });

    const firstDow = new Date(y, m, 1).getDay() || 7;
    const prevLast = new Date(y, m, 0).getDate();
    // Ячейки предыдущего месяца
    for (let i = firstDow - 1; i > 0; i--) {
      const b = document.createElement('button');
      b.className = 'calendar-day inactive';
      b.textContent = prevLast - i + 1;
      grid.appendChild(b);
    }

    const daysInMonth = new Date(y, m + 1, 0).getDate();
    // Ячейки текущего месяца
    for (let d = 1; d <= daysInMonth; d++) {
      const iso = fmtIso(y, m + 1, d);
      const b = document.createElement('button');
      b.className = 'calendar-day';
      b.textContent = d;
      b.dataset.date = iso;

      // Клик по дате — открытие панели
      b.addEventListener('click', () => onDayClick(iso));
      // Drag-and-drop
      b.addEventListener('dragover', e => e.preventDefault());
      b.addEventListener('drop', async e => {
        e.preventDefault();
        if (!dragData) return;
        const { id, timeStr, color } = dragData;
        const [startT, endT] = timeStr.split('-');
        const newStartIso = `${b.dataset.date}T${startT}`;
        const newEndIso   = endT ? `${b.dataset.date}T${endT}` : null;
        const payload = { start: newStartIso, end: newEndIso, color };
        const res = await fetch(`/api/events/${id}`, {
          method: 'PUT',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          renderCalendar();
          if (activeDate) onDayClick(activeDate);
        } else {
          alert('Ошибка при переносе события');
        }
      });

      grid.appendChild(b);
    }

    // Ячейки следующего месяца
    const total = firstDow - 1 + daysInMonth;
    const rem   = (7 - total % 7) % 7;
    for (let i = 1; i <= rem; i++) {
      const b = document.createElement('button');
      b.className = 'calendar-day inactive';
      b.textContent = i;
      grid.appendChild(b);
    }

    // Кнопка «Сегодня» всегда видна и показывает число
    const today = new Date();
    todayNum.textContent = today.getDate();
    todayBtn.style.display = 'flex';

    fetchEvents();
  }

  async function fetchEvents() {
    const y = currentDate.getFullYear(), m = currentDate.getMonth() + 1;
    events = await fetch(`/api/events?year=${y}&month=${m}`, { credentials: 'same-origin' })
                   .then(r => r.json());
    drawHighlights();
    if (currentView === 'month' && activeDate) showList();
  }

  function drawHighlights() {
    // Сброс фоновых заливок
    document.querySelectorAll('.calendar-day').forEach(b => {
      b.style.background = '';
    });
    // Заливаем дни с событиями
    events.forEach(e => {
      const btn = grid.querySelector(`.calendar-day[data-date="${e.date}"]`);
      if (btn) {
        btn.style.background = e.color;
      }
    });
  }

  function onDayClick(date) {
    activeDate = date;
    document.querySelectorAll('.calendar-day').forEach(b => b.classList.remove('active'));
    const btn = grid.querySelector(`.calendar-day[data-date="${date}"]`);
    if (btn) btn.classList.add('active');
    const dObj = new Date(date);
    selDateEl.textContent =
      `Выбранная дата: ${dObj.getDate()} ${currentDate.toLocaleString('ru',{month:'long'})} ${currentDate.getFullYear()}`;
    showList();
  }

  function showList() {
    viewPanel.style.display = 'flex';
    editPanel.style.display = 'none';
    list.innerHTML = '';

    let items = [];
    if (currentView === 'day') {
      items = events.filter(e => e.date === activeDate);
    } else if (currentView === 'week') {
      const d = new Date(activeDate), dow = d.getDay() || 7;
      const start = new Date(d); start.setDate(d.getDate() - dow + 1);
      const end   = new Date(start); end.setDate(start.getDate() + 6);
      items = events.filter(e => {
        const de = new Date(e.date);
        return de >= start && de <= end;
      });
    } else {
      items = events.filter(e => e.date.startsWith(activeDate.slice(0,7)));
    }

    if (!items.length) {
      list.innerHTML = '<div class="event-item">Нет событий</div>';
      return;
    }

    items.sort((a,b) => (a.date + a.time < b.date + b.time ? -1 : 1));
    items.forEach(e => {
      const item = document.createElement('div');
      item.className = 'event-item';
      item.textContent = `${e.date} ${e.time} — ${e.title}`;

      item.setAttribute('draggable', 'true');
      item.style.cursor = 'grab';

      item.addEventListener('dragstart', ev => {
        dragData = { id: e.id, timeStr: e.time, color: e.color };
      });

      item.addEventListener('click', () => openEdit(e));
      list.appendChild(item);
    });
  }

  // Переключение вида
  viewBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      viewBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentView = btn.dataset.view;
      if (activeDate) showList();
    });
  });

  // Навигация по месяцам
  todayBtn.addEventListener('click', () => {
    currentDate = new Date();
    renderCalendar();
    viewPanel.style.display = 'none';
    editPanel.style.display = 'none';
  });
  prevBtn.addEventListener('click', () => {
    currentDate.setMonth(currentDate.getMonth() - 1);
    renderCalendar();
    viewPanel.style.display = 'none';
    editPanel.style.display = 'none';
  });
  nextBtn.addEventListener('click', () => {
    currentDate.setMonth(currentDate.getMonth() + 1);
    renderCalendar();
    viewPanel.style.display = 'none';
    editPanel.style.display = 'none';
  });

  function openEdit(e) {
    viewPanel.style.display = 'none';
    editPanel.style.display = 'flex';
    form.dataset.id        = e.id;
    form.dataset.parent    = e.parent_id || '';
    form.title.value       = e.title;
    form.description.value = e.description || '';
    const [s, ee] = (e.time || '').split('-');
    form.start_time.value = s;
    form.end_time.value   = ee || '';
    form.frequency.value  = e.frequency;
    colorSelect.value     = e.color;
    deleteBtn.style.display = 'inline-block';
    dragData = null;
  }

  addBtn.addEventListener('click', () => {
    viewPanel.style.display = 'none';
    editPanel.style.display = 'flex';
    form.reset();
    delete form.dataset.id; delete form.dataset.parent;
    deleteBtn.style.display = 'none';
  });

  form.addEventListener('submit', async ev => {
    ev.preventDefault();
    const payload = {
      title:       form.title.value,
      description: form.description.value,
      start:       `${activeDate}T${form.start_time.value}`,
      end:         form.end_time.value ? `${activeDate}T${form.end_time.value}` : null,
      frequency:   form.frequency.value,
      color:       colorSelect.value
    };
    const id     = form.dataset.id;
    const url    = id ? `/api/events/${id}` : '/api/events';
    const method = id ? 'PUT'              : 'POST';
    const res    = await fetch(url, {
      method,
      credentials: 'same-origin',
      headers: { 'Content-Type':'application/json' },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      renderCalendar();
      onDayClick(activeDate);
      editPanel.style.display = 'none';
    } else {
      alert('Ошибка при сохранении события');
    }
  });

  deleteBtn.addEventListener('click', async () => {
    const id     = form.dataset.id;
    const parent = form.dataset.parent;
    if (!id) return;
    // Если подтверждаем удаление одного
    if (confirm('Удалить только это событие?')) {
      await fetch(`/api/events/${id}/delete_single`, { method:'DELETE', credentials:'same-origin' });
    } else {
      const rootId = parent || id;
      // Если подтверждаем удаление всей серии
      if (confirm('Удалить все связанные с этим событием?')) {
        await fetch(`/api/events/${rootId}/delete_all`, { method:'DELETE', credentials:'same-origin' });
      } else {
        return;
      }
    }
    renderCalendar();
    if (activeDate) onDayClick(activeDate);
    editPanel.style.display = 'none';
  });

  closeEdit.addEventListener('click', () => {
    editPanel.style.display = 'none';
    if (activeDate) viewPanel.style.display = 'flex';
  });
  closeView.addEventListener('click', () => {
    viewPanel.style.display = 'none';
    document.querySelectorAll('.calendar-day.active')
            .forEach(b => b.classList.remove('active'));
  });

  // Инициализация
  renderCalendar();
});
