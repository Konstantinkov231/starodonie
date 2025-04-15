const express = require('express');
const path = require('path');
const sqlite3 = require('sqlite3').verbose();
const ExcelJS = require('exceljs');

const app = express();
const port = 5000;

// Подключение к базе данных SQLite (используется база schedule.db)
const db = new sqlite3.Database('schedule.db', (err) => {
  if (err) {
    console.error('Ошибка подключения к SQLite:', err.message);
  } else {
    console.log('Подключение к базе schedule.db успешно!');
  }
});

// Инициализация таблиц, если они не существуют
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS staff (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    role TEXT NOT NULL,
    rate REAL DEFAULT 0
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS shifts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staff_id INTEGER,
    title TEXT,
    start TEXT,
    end TEXT,
    FOREIGN KEY(staff_id) REFERENCES staff(id)
  )`);
});

// Middleware для парсинга JSON
app.use(express.json());
// Раздача статических файлов из текущей директории (index.html, admin.html и т.д.)
app.use(express.static(path.join(__dirname)));

// ===== API для управления сменами (shifts) =====
app.get('/api/schedule', (req, res) => {
  const sql = `SELECT * FROM shifts`;
  db.all(sql, [], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    const events = rows.map((row) => ({
      id: row.id,
      staff_id: row.staff_id,
      title: row.title,
      start: row.start,
      end: row.end,
    }));
    res.json(events);
  });
});

app.post('/api/schedule', (req, res) => {
  const { staff_id, title, start, end } = req.body;
  const sql = `INSERT INTO shifts (staff_id, title, start, end) VALUES (?, ?, ?, ?)`;
  db.run(sql, [staff_id, title, start, end], function (err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ id: this.lastID });
  });
});

app.put('/api/schedule/:id', (req, res) => {
  const { id } = req.params;
  const { staff_id, title, start, end } = req.body;
  const sql = `UPDATE shifts SET staff_id = ?, title = ?, start = ?, end = ? WHERE id = ?`;
  db.run(sql, [staff_id, title, start, end, id], function (err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ changed: this.changes });
  });
});

app.delete('/api/schedule/:id', (req, res) => {
  const { id } = req.params;
  const sql = `DELETE FROM shifts WHERE id = ?`;
  db.run(sql, [id], function (err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ deleted: this.changes });
  });
});

// ===== API для управления сотрудниками (staff) =====
app.get('/api/staff', (req, res) => {
  const sql = `SELECT * FROM staff`;
  db.all(sql, [], (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    res.json(rows);
  });
});

app.post('/api/staff', (req, res) => {
  const { name, role, rate } = req.body;
  const sql = `INSERT INTO staff (name, role, rate) VALUES (?, ?, ?)`;
  db.run(sql, [name, role, rate], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ id: this.lastID });
  });
});

app.put('/api/staff/:id', (req, res) => {
  const { id } = req.params;
  const { name, role, rate } = req.body;
  const sql = `UPDATE staff SET name = ?, role = ?, rate = ? WHERE id = ?`;
  db.run(sql, [name, role, rate, id], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ changed: this.changes });
  });
});

app.delete('/api/staff/:id', (req, res) => {
  const { id } = req.params;
  const sql = `DELETE FROM staff WHERE id = ?`;
  db.run(sql, [id], function(err) {
    if (err) return res.status(500).json({ error: err.message });
    res.json({ deleted: this.changes });
  });
});

// ===== API для экспорта данных в Excel =====
app.get('/api/export', (req, res) => {
  const sql = `
    SELECT shifts.id, shifts.title, shifts.start, shifts.end,
           staff.name AS staff_name, staff.role AS staff_role, staff.rate AS staff_rate
    FROM shifts
    LEFT JOIN staff ON shifts.staff_id = staff.id
  `;
  db.all(sql, [], async (err, rows) => {
    if (err) return res.status(500).json({ error: err.message });
    const workbook = new ExcelJS.Workbook();
    const worksheet = workbook.addWorksheet('Отчёт по сменам');
    worksheet.columns = [
      { header: 'ID смены', key: 'id', width: 10 },
      { header: 'Сотрудник', key: 'staff_name', width: 20 },
      { header: 'Роль', key: 'staff_role', width: 20 },
      { header: 'Ставка (руб/час)', key: 'staff_rate', width: 15 },
      { header: 'Начало', key: 'start', width: 20 },
      { header: 'Конец', key: 'end', width: 20 },
      { header: 'Часы', key: 'hours', width: 10 },
      { header: 'Сумма (руб)', key: 'sum_rub', width: 15 },
    ];
    rows.forEach((row) => {
      const start = new Date(row.start);
      const end = new Date(row.end);
      const hoursDiff = (end - start) / (1000 * 60 * 60);
      const pay = row.staff_rate * hoursDiff;
      worksheet.addRow({
        id: row.id,
        staff_name: row.staff_name || '',
        staff_role: row.staff_role || '',
        staff_rate: row.staff_rate || 0,
        start: row.start,
        end: row.end,
        hours: hoursDiff.toFixed(2),
        sum_rub: pay.toFixed(2),
      });
    });
    res.setHeader('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
    res.setHeader('Content-Disposition', 'attachment; filename=report.xlsx');
    await workbook.xlsx.write(res);
    res.end();
  });
});

// Запуск сервера (доступен извне по порту 5000)
app.listen(port, '0.0.0.0', () => {
  console.log(`Server is running at http://0.0.0.0:${port}`);
});
