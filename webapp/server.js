// Загружаем переменные окружения из файла .env
require('dotenv').config();

const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const ExcelJS = require('exceljs');
const axios = require('axios');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;

// Конфигурация для отправки сообщения в Telegram
// В файле .env переменные:
//   TOKEN – токен вашего бота
//   CHAT_ID – ваш chat_id (куда отправлять сообщение)
//   APP_URL – публичный URL вашего приложения
const TELEGRAM_BOT_TOKEN = process.env.TOKEN || 'YOUR_TELEGRAM_BOT_TOKEN';
const TELEGRAM_CHAT_ID = process.env.CHAT_ID || 'YOUR_TELEGRAM_CHAT_ID';
const APP_URL = process.env.APP_URL || 'https://your-domain.com';

// Для парсинга JSON и urlencoded данных
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Подключаем статические файлы (например, для css или js)
app.use(express.static(path.join(__dirname, 'public')));

// Инициализация базы данных SQLite
const db = new sqlite3.Database('./database.db', (err) => {
  if (err) console.error("Ошибка подключения к базе:", err);
  else console.log("Подключение к SQLite установлено.");
});

// Создание таблиц, если их ещё нет
db.serialize(() => {
  // Таблица пользователей (telegram_id, username и роль: waiter/admin)
  db.run(`CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id TEXT,
    username TEXT,
    role TEXT
  )`);

  // Таблица с графиками работы
  db.run(`CREATE TABLE IF NOT EXISTS schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    date TEXT,
    shift TEXT,
    approved INTEGER DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id)
  )`);

  // Таблица с данными (часы, ставка, премия) для администраторов
  db.run(`CREATE TABLE IF NOT EXISTS work_details (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_id INTEGER,
    hours REAL,
    rate REAL,
    bonus REAL,
    FOREIGN KEY(schedule_id) REFERENCES schedules(id)
  )`);
});

// ====================================================================
// Роуты для официантов
// ====================================================================

// Страница для официантов с календарём для выбора графика
app.get('/waiter', (req, res) => {
  res.send(`<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>График работы официанта</title>
    <!-- Telegram WebApp SDK -->
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <!-- Flatpickr для выбора даты -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css">
    <script src="https://cdn.jsdelivr.net/npm/flatpickr"></script>
    <!-- Axios для AJAX запросов -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/axios/0.21.1/axios.min.js"></script>
  </head>
  <body>
    <h1>Выберите график работы</h1>
    <form id="scheduleForm">
      <label for="date">Дата:</label>
      <input type="text" id="date" name="date" placeholder="Выберите дату">
      <br><br>
      <label for="shift">Смена:</label>
      <select id="shift" name="shift">
        <option value="утро">Утро</option>
        <option value="день">День</option>
        <option value="вечер">Вечер</option>
      </select>
      <br><br>
      <button type="submit">Отправить график</button>
    </form>
    <script>
      // Инициализируем Telegram WebApp
      const tg = window.Telegram.WebApp;
      tg.expand();

      // Инициализируем Flatpickr для выбора даты
      flatpickr("#date", { dateFormat: "Y-m-d" });
      
      document.getElementById('scheduleForm').addEventListener('submit', async function(e) {
        e.preventDefault();
        const date = document.getElementById('date').value;
        const shift = document.getElementById('shift').value;
        try {
          const response = await axios.post('/waiter/schedule', { date, shift });
          alert(response.data.message);
        } catch (error) {
          alert("Ошибка при отправке графика");
        }
      });
    </script>
  </body>
</html>`);
});

// Обработка отправки графика от официанта
app.post('/waiter/schedule', (req, res) => {
  const { date, shift } = req.body;
  // Здесь должна быть авторизация пользователя через Telegram.
  // Для простоты используем фиктивный user_id = 1 (в реальном приложении данные берутся из Telegram WebApp initData)
  const userId = 1;
  const query = "INSERT INTO schedules (user_id, date, shift) VALUES (?, ?, ?)";
  db.run(query, [userId, date, shift], function(err) {
    if (err) {
      console.error(err);
      return res.status(500).json({ message: "Ошибка при сохранении графика" });
    }
    res.json({ message: "График отправлен на утверждение" });
  });
});

// ====================================================================
// Роуты для администраторов
// ====================================================================

// Страница для администраторов (панель управления)
app.get('/admin', (req, res) => {
  res.send(`<!DOCTYPE html>
<html>
  <head>
    <meta charset="UTF-8">
    <title>Панель администратора</title>
    <!-- Telegram WebApp SDK -->
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <!-- Axios для AJAX запросов -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/axios/0.21.1/axios.min.js"></script>
  </head>
  <body>
    <h1>Панель администратора</h1>
    <button onclick="fetchSchedules()">Загрузить графики</button>
    <br><br>
    <table border="1" id="schedulesTable">
      <thead>
        <tr>
          <th>ID</th>
          <th>Дата</th>
          <th>Смена</th>
          <th>Официант</th>
          <th>Утверждение</th>
          <th>Часы работы</th>
          <th>Ставка</th>
          <th>Премия</th>
          <th>Действия</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
    <br>
    <button onclick="window.location.href='/admin/export'">Экспортировать в Excel</button>
    <script>
      const tg = window.Telegram.WebApp;
      tg.expand();

      async function fetchSchedules() {
        try {
          const response = await axios.get('/admin/schedules');
          const tableBody = document.querySelector('#schedulesTable tbody');
          tableBody.innerHTML = '';
          response.data.forEach(schedule => {
            const row = document.createElement('tr');
            row.innerHTML = '<td>' + schedule.id + '</td>' +
                            '<td>' + schedule.date + '</td>' +
                            '<td>' + schedule.shift + '</td>' +
                            '<td>' + schedule.username + '</td>' +
                            '<td><button onclick="approveSchedule(' + schedule.id + ')">Утвердить</button></td>' +
                            '<td><input type="number" id="hours_' + schedule.id + '" placeholder="Часы"></td>' +
                            '<td><input type="number" id="rate_' + schedule.id + '" placeholder="Ставка"></td>' +
                            '<td><input type="number" id="bonus_' + schedule.id + '" placeholder="Премия"></td>' +
                            '<td><button onclick="updateDetails(' + schedule.id + ')">Сохранить</button></td>';
            tableBody.appendChild(row);
          });
        } catch (error) {
          alert("Ошибка загрузки графиков");
        }
      }
      
      async function approveSchedule(id) {
        try {
          await axios.post('/admin/schedule/approve', { scheduleId: id });
          alert("График утвержден");
          fetchSchedules();
        } catch (error) {
          alert("Ошибка утверждения графика");
        }
      }
      
      async function updateDetails(id) {
        const hours = document.getElementById('hours_' + id).value;
        const rate = document.getElementById('rate_' + id).value;
        const bonus = document.getElementById('bonus_' + id).value;
        try {
          await axios.post('/admin/schedule/update', { scheduleId: id, hours, rate, bonus });
          alert("Данные обновлены");
        } catch (error) {
          alert("Ошибка обновления данных");
        }
      }
    </script>
  </body>
</html>`);
});

// API для получения графиков (ожидающих утверждения)
app.get('/admin/schedules', (req, res) => {
  const query = `
    SELECT s.id, s.date, s.shift, s.approved, u.username
    FROM schedules s
    JOIN users u ON s.user_id = u.id
    WHERE s.approved = 0
  `;
  db.all(query, [], (err, rows) => {
    if (err) {
      console.error(err);
      return res.status(500).json({ message: "Ошибка при получении данных" });
    }
    res.json(rows);
  });
});

// API для утверждения графика
app.post('/admin/schedule/approve', (req, res) => {
  const { scheduleId } = req.body;
  const query = "UPDATE schedules SET approved = 1 WHERE id = ?";
  db.run(query, [scheduleId], function(err) {
    if (err) {
      console.error(err);
      return res.status(500).json({ message: "Ошибка при утверждении графика" });
    }
    res.json({ message: "График утвержден" });
  });
});

// API для сохранения рабочих данных (часы, ставка, премия)
app.post('/admin/schedule/update', (req, res) => {
  const { scheduleId, hours, rate, bonus } = req.body;
  const querySelect = "SELECT * FROM work_details WHERE schedule_id = ?";
  db.get(querySelect, [scheduleId], (err, row) => {
    if (err) {
      console.error(err);
      return res.status(500).json({ message: "Ошибка при обновлении данных" });
    }
    if (row) {
      const queryUpdate = "UPDATE work_details SET hours = ?, rate = ?, bonus = ? WHERE schedule_id = ?";
      db.run(queryUpdate, [hours, rate, bonus, scheduleId], function(err) {
        if (err) {
          console.error(err);
          return res.status(500).json({ message: "Ошибка обновления" });
        }
        res.json({ message: "Данные обновлены" });
      });
    } else {
      const queryInsert = "INSERT INTO work_details (schedule_id, hours, rate, bonus) VALUES (?, ?, ?, ?)";
      db.run(queryInsert, [scheduleId, hours, rate, bonus], function(err) {
        if (err) {
          console.error(err);
          return res.status(500).json({ message: "Ошибка вставки данных" });
        }
        res.json({ message: "Данные сохранены" });
      });
    }
  });
});

// ====================================================================
// Экспорт данных в Excel для администратора
// ====================================================================
app.get('/admin/export', (req, res) => {
  const query = `
    SELECT s.date, u.username, s.shift, w.hours, w.rate, w.bonus
    FROM schedules s
    LEFT JOIN users u ON s.user_id = u.id
    LEFT JOIN work_details w ON s.id = w.schedule_id
  `;
  db.all(query, [], (err, rows) => {
    if (err) {
      console.error(err);
      return res.status(500).send('Ошибка при получении данных');
    }
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Work Data');

    // Определяем колонки Excel
    worksheet.columns = [
      { header: 'Дата', key: 'date', width: 15 },
      { header: 'Официант', key: 'username', width: 20 },
      { header: 'Смена', key: 'shift', width: 15 },
      { header: 'Часы', key: 'hours', width: 10 },
      { header: 'Ставка', key: 'rate', width: 10 },
      { header: 'Премия', key: 'bonus', width: 10 }
    ];

    rows.forEach(row => {
      worksheet.addRow(row);
    });

    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', 'attachment; filename="work_data.xlsx"');
    workbook.xlsx.write(res)
      .then(() => res.end())
      .catch(err => {
        console.error(err);
        res.status(500).send('Ошибка формирования Excel файла');
      });
  });
});

// ====================================================================
// Запуск сервера и отправка сообщения в Telegram
// ====================================================================
app.listen(PORT, () => {
  console.log(`Сервер запущен на порту ${PORT}`);

  // Формируем текст сообщения с ссылкой на приложение
  const messageText = `Ваше приложение запущено и доступно по адресу: ${APP_URL}`;

  // Отправляем сообщение через Telegram Bot API
  axios.post(`https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`, {
      chat_id: TELEGRAM_CHAT_ID,
      text: messageText
  })
  .then(response => {
      console.log('Сообщение отправлено в Telegram:', response.data);
  })
  .catch(error => {
      console.error('Ошибка при отправке сообщения в Telegram:', error.response ? error.response.data : error.message);
  });
});