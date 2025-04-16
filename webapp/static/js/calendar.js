document.addEventListener('DOMContentLoaded', function() {
  const calendarEl = document.getElementById('calendar');
  if(!calendarEl) return;

  // Инициализация FullCalendar
  const calendar = new FullCalendar.Calendar(calendarEl, {
    initialView: 'dayGridMonth',
    selectable: true,
    events: '/api/calendar/events',
    // Добавление события при клике по пустому дню:
    dateClick: function(info) {
      const dayType = prompt("Введите тип дня (fixed/approximate/none)", "approximate");
      const hours = prompt("Введите часы работы (например 10:00-18:00)", "");
      if(dayType) {
        fetch('/api/calendar/add', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            date: info.dateStr,
            day_type: dayType,
            hours: hours
          })
        })
        .then(r => r.json())
        .then(data => {
          if(data.ok) {
            calendar.refetchEvents();
          } else {
            alert("Ошибка при добавлении события");
          }
        })
      }
    },
    // Редактирование/Удаление события при клике на само событие:
    eventClick: function(info) {
      const eventObj = info.event;
      const scheduleId = eventObj.id;  // id из БД
      const newType = prompt("Изменить тип дня (fixed/approximate/none) или 'delete' для удаления:", eventObj.backgroundColor);
      const newHours = prompt("Изменить рабочие часы:", eventObj.title);

      if(newType === "delete") {
        // Удаляем
        fetch('/api/calendar/delete', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id: scheduleId})
        })
        .then(r => r.json())
        .then(data => {
          if(data.ok) {
            calendar.refetchEvents();
          } else {
            alert("Ошибка при удалении события");
          }
        })
      } else {
        // Обновляем
        fetch('/api/calendar/update', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            id: scheduleId,
            date: eventObj.startStr,
            day_type: newType,
            hours: newHours
          })
        })
        .then(r => r.json())
        .then(data => {
          if(data.ok) {
            calendar.refetchEvents();
          } else {
            alert("Ошибка при обновлении события");
          }
        })
      }
    }
  });

  calendar.render();
});
