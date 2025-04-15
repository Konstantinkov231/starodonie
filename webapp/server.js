// server.js
const express = require('express');
const path = require('path');
const app = express();
const port = 5000;

// Пример данных о рабочих сменах официантов
const schedule = [
  {
    id: 1,
    title: "Иван (Официант)",
    start: "2025-04-16T08:00:00",
    end: "2025-04-16T16:00:00"
  },
  {
    id: 2,
    title: "Пётр (Официант)",
    start: "2025-04-16T12:00:00",
    end: "2025-04-16T20:00:00"
  },
  {
    id: 3,
    title: "Мария (Официант)",
    start: "2025-04-17T09:30:00",
    end: "2025-04-17T17:30:00"
  }
];

// Обслуживаем статические файлы из текущей директории.
// Предполагается, что index.html находится в той же папке, что и server.js
app.use(express.static(path.join(__dirname)));

// API эндпоинт для возвращения расписания
app.get('/api/schedule', (req, res) => {
  res.json(schedule);
});

// Запускаем сервер на адресе 0.0.0.0 чтобы он был доступен извне
app.listen(port, '0.0.0.0', () => {
  console.log(`Server is running at http://0.0.0.0:${port}`);
});
