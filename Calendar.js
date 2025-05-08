document.addEventListener('DOMContentLoaded', () => {
    // ===========================
    // Вспомогательные функции
    // ===========================
    const pad = n => String(n).padStart(2, '0');
    function formatLocalDate(y, m, d) {
      return `${y}-${pad(m)}-${pad(d)}`;
    }
    function parseLocalDate(str) {
      const [y, m, d] = str.split('-').map(Number);
      return new Date(y, m - 1, d);
    }
  
    // ===========================
    // Получаем элементы страницы
    // ===========================
    const monthYearEl    = document.getElementById('month-year');
    const gridEl         = document.getElementById('calendar-grid');
    const prevBtn        = document.getElementById('prev-month');
    const nextBtn        = document.getElementById('next-month');
    const viewPanel      = document.getElementById('view-panel');
    const editPanel      = document.getElementById('edit-panel');
    const selectedDateEl = document.getElementById('selected-date');
    const eventsList     = document.getElementById('events-list');
    const addBtn         = document.getElementById('add-event');
    const form           = document.getElementById('event-form');
    const deleteBtn      = document.getElementById('delete-btn');
    const closeEdit      = document.getElementById('close-edit');
    const todayBtn       = document.getElementById('today-btn');
    const closeViewBtn   = document.getElementById('close-view');
  
    // ===========================
    // Состояние
    // ===========================
    let currentDate = new Date();
    let currentView = 'day';
    let activeDate;
    let allEvents = [];
    let occEvents = [];
  
    // ===========================
    // Today‑button
    // ===========================
    const realToday  = new Date();
    const todayYear  = realToday.getFullYear();
    const todayMonth = realToday.getMonth();
    const todayDate  = realToday.getDate();
    todayBtn.textContent = todayDate;
    function updateTodayButton() {
      if (currentDate.getFullYear() !== todayYear ||
          currentDate.getMonth()    !== todayMonth) {
        todayBtn.style.display = 'flex';
      } else {
        todayBtn.style.display = 'none';
      }
    }
    todayBtn.addEventListener('click', () => {
      currentDate = new Date(todayYear, todayMonth, 1);
      renderCalendar(currentDate);
    });
  
    // ===========================
    // 1) Render calendar
    // ===========================
    function renderCalendar(date) {
      gridEl.innerHTML = '';
      const y = date.getFullYear(), m = date.getMonth();
      monthYearEl.textContent = date.toLocaleString('ru', { month:'long', year:'numeric' });
  
      // weekdays
      ['Пн','Вт','Ср','Чт','Пт','Сб','Вс'].forEach(lbl => {
        const div = document.createElement('div');
        div.className = 'day-header';
        div.textContent = lbl;
        gridEl.appendChild(div);
      });
  
      // prev month
      const firstDow   = (new Date(y, m, 1).getDay() || 7);
      const daysInPrev = new Date(y, m, 0).getDate();
      for (let i = firstDow - 1; i > 0; i--) {
        const d = daysInPrev - i + 1;
        const btn = document.createElement('button');
        btn.className = 'calendar-day inactive';
        btn.textContent = d;
        gridEl.appendChild(btn);
      }
  
      // current month
      const daysInMonth = new Date(y, m+1, 0).getDate();
      for (let d = 1; d <= daysInMonth; d++) {
        const btn = document.createElement('button');
        btn.className = 'calendar-day';
        btn.textContent = d;
        const iso = formatLocalDate(y, m+1, d);
        btn.dataset.date = iso;
        btn.addEventListener('click', () => onDayClick(iso));
        gridEl.appendChild(btn);
      }
  
      // next month
      const total = firstDow - 1 + daysInMonth;
      const rem   = (7 - total % 7) % 7;
      for (let i = 1; i <= rem; i++) {
        const btn = document.createElement('button');
        btn.className = 'calendar-day inactive';
        btn.textContent = i;
        gridEl.appendChild(btn);
      }
  
      // load events + today btn
      fetchAndProcessEvents();
      updateTodayButton();
    }
  
    // ===========================
    // 2) Fetch + generate occurrences
    // ===========================
    async function fetchAndProcessEvents() {
      const y = currentDate.getFullYear(), m = currentDate.getMonth() + 1;
      // обязательно передаём куки!
      allEvents = await fetch(`/api/events?year=${y}&month=${m}`, {
        credentials: 'same-origin'
      }).then(r => r.json());
  
      occEvents = [];
      const daysInMonth = new Date(y, currentDate.getMonth()+1, 0).getDate();
  
      allEvents.forEach(e => {
        const [ey, em, ed] = e.date.split('-').map(Number);
        const origDow = new Date(ey, em-1, ed).getDay();
        for (let d = 1; d <= daysInMonth; d++) {
          const dateStr = formatLocalDate(y, m, d);
          if (dateStr < e.date) continue;
          let include = false;
          if (e.frequency === 'none'   && dateStr === e.date)           include = true;
          if (e.frequency === 'daily'  )                                 include = true;
          if (e.frequency === 'weekly' && new Date(y, m-1, d).getDay() === origDow) include = true;
          if (e.frequency === 'monthly'&& d === ed)                     include = true;
          if (include) occEvents.push({ ...e, date: dateStr });
        }
      });
  
      // dots
      document.querySelectorAll('.calendar-day .dot').forEach(el => el.remove());
      occEvents.forEach(e => {
        const btn = gridEl.querySelector(`.calendar-day[data-date="${e.date}"]`);
        if (btn) {
          const dot = document.createElement('div');
          dot.className = 'dot';
          btn.appendChild(dot);
        }
      });
    }
  
    // ===========================
    // 3) Day click
    // ===========================
    function onDayClick(dateStr) {
      document.querySelectorAll('.calendar-day').forEach(b => b.classList.remove('active'));
      const btn = gridEl.querySelector(`.calendar-day[data-date="${dateStr}"]`);
      if (!btn) return;
      btn.classList.add('active');
  
      activeDate = dateStr;
      editPanel.style.display = 'none';
      viewPanel.style.display = 'flex';
      selectedDateEl.textContent =
        `Выбранная дата: ${btn.textContent} ${currentDate.toLocaleString('ru',{month:'long'})} ${currentDate.getFullYear()}`;
      renderViewList();
    }
  
    // ===========================
    // 4) Render list
    // ===========================
    function renderViewList() {
      eventsList.innerHTML = '';
      let list = [];
  
      if (currentView === 'day') {
        list = occEvents.filter(e => e.date === activeDate);
      } else if (currentView === 'week') {
        const sel = parseLocalDate(activeDate);
        const dow = sel.getDay() || 7;
        const start = new Date(sel); start.setDate(sel.getDate() - dow + 1);
        const end   = new Date(start); end.setDate(start.getDate() + 6);
        list = occEvents.filter(e => {
          const d = parseLocalDate(e.date);
          return d >= start && d <= end;
        });
      } else {
        list = occEvents.filter(e => e.date.startsWith(activeDate.slice(0,7)));
      }
  
      if (!list.length) {
        eventsList.innerHTML = '<div class="event-item">Нет событий</div>';
        return;
      }
  
      list.forEach(e => {
        const div = document.createElement('div');
        div.className = 'event-item';
        if (currentView === 'day') {
          div.textContent = `${e.time} — ${e.title}`;
        } else if (currentView === 'week') {
          div.textContent = `${e.date} ${e.time} — ${e.title}`;
        } else {
          div.textContent = `${e.date} — ${e.title}`;
        }
        const edit = document.createElement('button');
        edit.textContent = '✎';
        edit.style.marginLeft = '10px';
        edit.addEventListener('click', () => openEdit(e));
        div.appendChild(edit);
        eventsList.appendChild(div);
      });
    }
  
    // ===========================
    // 5) Create / edit panel
    // ===========================
    function openEdit(evt) {
      viewPanel.style.display = 'none';
      editPanel.style.display = 'flex';
      form.dataset.id        = evt.id;
      form.title.value       = evt.title;
      form.description.value = evt.description;
      const [s, e]           = (evt.time || '').split('-');
      form.start_time.value  = s || '';
      form.end_time.value    = e || '';
      form.frequency.value   = evt.frequency;
      deleteBtn.style.display = 'inline-block';
    }
  
    addBtn.addEventListener('click', () => {
      viewPanel.style.display = 'none';
      editPanel.style.display = 'flex';
      form.reset();
      form.dataset.id = '';
      deleteBtn.style.display = 'none';
    });
  
    closeViewBtn.addEventListener('click', () => {
      viewPanel.style.display = 'none';
      document.querySelectorAll('.calendar-day.active').forEach(b => b.classList.remove('active'));
    });
  
    closeEdit.addEventListener('click', () => {
      editPanel.style.display = 'none';
      viewPanel.style.display = activeDate ? 'flex' : 'none';
    });
  
    form.addEventListener('submit', async e => {
      e.preventDefault();
      const payload = {
        title:       form.title.value,
        description: form.description.value,
        start:       `${activeDate}T${form.start_time.value}`,
        end:         form.end_time.value ? `${activeDate}T${form.end_time.value}` : null,
        frequency:   form.frequency.value
      };
      const id     = form.dataset.id;
      const url    = id ? `/api/events/${id}` : '/api/events';
      const method = id ? 'PUT' : 'POST';
      const res    = await fetch(url, {
        method,
        credentials: 'same-origin',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });
      if (res.ok) {
        editPanel.style.display = 'none';
        renderCalendar(currentDate);
        onDayClick(activeDate);
      } else {
        alert('Ошибка при сохранении');
      }
    });
  
    deleteBtn.addEventListener('click', async () => {
        const id = form.dataset.id;
        if (!id) return;
    
        //Сначала подтверждаем удаление основного события
        const confirmDelete = confirm('Удалить событие?');
        if (!confirmDelete) return;
    
        //Делаем запрос на удаление события
        const res = await fetch(/api/events/${id}, {
            method: 'DELETE',
            credentials: 'same-origin'
        });
    
        //Проверяем ответ сервера
        if (res.ok) {
            const data = await res.json();
    
            //Если сервер вернул сообщение о связанных событиях
            if (data.delete_all) {
                //Запрашиваем у пользователф подтверждение для удаления всех связанных событий
                const confirmDeleteAll = confirm(data.message);
                if (confirmDeleteAll) {
                    //Если пользователь подтвердил, то отправляем запрос на удаление всех связанных событий
                    const deleteAllRes = await fetch(/api/events/${id}?delete_all=yes, {
                        method: 'DELETE',
                        credentials: 'same-origin'
                    });
                    if (deleteAllRes.ok) {
                        alert("Все связанные события удалены.");
                    } else {
                        alert("Ошибка при удалении связанных событий.");
                    }
                } else {
                    alert("Удаление связанных событий отменено.");
                }
            } else {
                // Если событие не периодическое, обновляем
                editPanel.style.display = 'none';
                renderCalendar(currentDate);
                onDayClick(activeDate);
            }
        } else {
            alert("Ошибка при удалении события.");
        }
    });
    
    // Навигация по месяцам
    prevBtn.addEventListener('click', () => {
      currentDate.setMonth(currentDate.getMonth() - 1);
      renderCalendar(currentDate);
    });
    nextBtn.addEventListener('click', () => {
      currentDate.setMonth(currentDate.getMonth() + 1);
      renderCalendar(currentDate);
    });
  
    // Переключение вида
    document.querySelectorAll('.view-button').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.view-button').forEach(x => x.classList.remove('active'));
        btn.classList.add('active');
        currentView = btn.dataset.view;
        renderViewList();
      });
    });
  
    // Первый рендер
    renderCalendar(currentDate);
  });
