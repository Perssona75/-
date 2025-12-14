import sqlite3
import json
import os
import logging
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, request, redirect, flash, abort, jsonify

from validators import (
    validate_name,
    validate_last_name,
    validate_birth_date_ddmmyyyy,
    validate_date_not_future,
    validate_diagnosis_text
)

# -----------------------------------------------------------
# БЛОК 2. Загрузка конфигурации из файла
# -----------------------------------------------------------
with open("config.json", encoding="utf-8") as f:
    CONFIG = json.load(f)

DATABASE = CONFIG["database"]

# -----------------------------------------------------------
# БЛОК 3. Создание Flask-приложения
# -----------------------------------------------------------
app = Flask(__name__)
app.secret_key = "supersecret123"

# -----------------------------------------------------------
# БЛОК 4. Настройка логирования
# -----------------------------------------------------------
os.makedirs("logs", exist_ok=True)

log_cfg = CONFIG.get("LOGGING", {})
log_file = log_cfg.get("LOG_FILE", "logs/service.log")
max_bytes = log_cfg.get("MAX_BYTES", 100_000)
backup_count = log_cfg.get("BACKUP_COUNT", 10)

handler = RotatingFileHandler(
    log_file,
    maxBytes=max_bytes,
    backupCount=backup_count,
    encoding="utf-8"
)
handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s (%(pathname)s:%(lineno)d)"
)
handler.setFormatter(formatter)

app.logger.addHandler(handler)
app.logger.info("Сервис запущен")

# -----------------------------------------------------------
# БЛОК 5. Работа с базой данных
# -----------------------------------------------------------
def get_db():
    """Возвращает соединение с SQLite."""
    path = app.config.get("DATABASE", DATABASE)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создание всех таблиц, если отсутствуют."""
    conn = get_db()
    cur = conn.cursor()

    # таблица пациентов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            birth_date TEXT NOT NULL
        )
    """)

    # таблица диагнозов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnosis TEXT NOT NULL UNIQUE
        )
    """)

    # таблица назначений пациентам
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patient_diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER NOT NULL,
            diagnosis_id INTEGER NOT NULL,
            diagnosis_date TEXT NOT NULL,
            FOREIGN KEY(patient_id) REFERENCES patients(id),
            FOREIGN KEY(diagnosis_id) REFERENCES diagnoses(id)
        )
    """)

    conn.commit()
    conn.close()
    app.logger.info("База данных инициализирована")

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к колонкам по имени
    return conn

# -----------------------------------------------------------
# БЛОК 6. Health-check
# -----------------------------------------------------------
@app.route("/health")
def health_check():
    db_status = "ok"
    try:
        conn = sqlite3.connect(app.config.get("DATABASE", DATABASE))
        conn.execute("SELECT 1")
        conn.close()
        db_status = "connected"
    except Exception as e:
        db_status = "error"

    return jsonify({
        "status": "ok",
        "database": db_status
    })

# -----------------------------------------------------------
# БЛОК 7. Главная страница
# -----------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")

# -----------------------------------------------------------
# БЛОК 8. Список пациентов
# -----------------------------------------------------------
@app.route("/patients")
def patients():
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor()

    # общее количество записей
    cur.execute("SELECT COUNT(*) FROM patients")
    total = cur.fetchone()[0]
    pages = (total + per_page - 1) // per_page

    # выборка текущей страницы
    cur.execute("""
        SELECT * FROM patients
        ORDER BY last_name ASC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    pts = cur.fetchall()

    conn.close()

    return render_template("patients.html",
                           patients=pts,
                           page=page,
                           pages=pages)

# -----------------------------------------------------------
# БЛОК 9. Добавление пациента
# -----------------------------------------------------------
@app.route("/patients/add", methods=["POST"])
def add_patient():
    # принимаем поля и от формы, и от тестов
    name = (request.form.get("name") or request.form.get("first_name") or "").strip()
    last_name = request.form.get("last_name", "").strip()
    birth_date = (request.form.get("birth_date") or request.form.get("birth_year") or "").strip()

    if not validate_name(name):
        flash("Некорректное имя.")
        return redirect("/patients")

    if not validate_last_name(last_name):
        flash("Некорректная фамилия.")
        return redirect("/patients")

    if not validate_birth_date_ddmmyyyy(birth_date):
        flash("Дата рождения некорректнен")
        return redirect("/patients")

    birth_iso = datetime.strptime(birth_date, "%d.%m.%Y").strftime("%Y-%m-%d")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO patients (name, last_name, birth_date) VALUES (?, ?, ?)",
                (name, last_name, birth_iso))
    conn.commit()
    conn.close()

    flash("Пациент добавлен")
    return redirect("/patients")

# -----------------------------------------------------------
# БЛОК 10. Удаление пациента
# -----------------------------------------------------------
@app.route("/patients/<int:pid>/delete")
def delete_patient(pid):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM patients WHERE id = ?", (pid,))
    patient = cur.fetchone()

    if not patient:
        conn.close()
        flash("Пациент не найден.", "warning")
        return redirect("/patients")

    cur.execute("DELETE FROM patients WHERE id = ?", (pid,))
    conn.commit()
    conn.close()

    flash("Пациент удалён.", "success")
    return redirect("/patients")

# -----------------------------------------------------------
# БЛОК 11. Карточка пациента
# -----------------------------------------------------------
@app.route("/patients/<int:pid>")
def patient_card(pid):
    page = int(request.args.get("page", 1))
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor()

    # сами данные пациента
    cur.execute("SELECT * FROM patients WHERE id=?", (pid,))
    patient = cur.fetchone()
    if not patient:
        abort(404)

    # считаем диагнозы
    cur.execute("SELECT COUNT(*) FROM patient_diagnoses WHERE patient_id=?", (pid,))
    total = cur.fetchone()[0]
    pages = (total + per_page - 1) // per_page

    # берём текущую страницу диагнозов
    cur.execute("""
        SELECT pd.id, d.diagnosis, pd.diagnosis_date
        FROM patient_diagnoses pd
        JOIN diagnoses d ON d.id = pd.diagnosis_id
        WHERE pd.patient_id=?
        ORDER BY pd.diagnosis_date DESC
        LIMIT ? OFFSET ?
    """, (pid, per_page, offset))
    diagnosis_list = cur.fetchall()

    # подсказки
    cur.execute("SELECT diagnosis FROM diagnoses ORDER BY diagnosis ASC")
    suggestions = [r["diagnosis"] for r in cur.fetchall()]

    conn.close()

    return render_template(
        "patient_card.html",
        patient=patient,
        diagnoses=diagnosis_list,
        diag_suggestions=suggestions,
        page=page,
        pages=pages,
        current_date=str(date.today())
    )

# -----------------------------------------------------------
# БЛОК 12. Добавление диагноза пациенту
# -----------------------------------------------------------
@app.route("/patients/<int:pid>/assign", methods=["POST"])
@app.route("/patient/<int:pid>/add_diagnosis", methods=["POST"])
def add_diag_to_patient(pid):
    diag_text = request.form.get("diagnosis", "").strip()
    diag_date = request.form.get("diagnosis_date", "").strip()

    if not validate_diagnosis_text(diag_text):
        flash("Некорректное название диагноза.")
        return redirect(f"/patients/{pid}")

    if not validate_date_not_future(diag_date):
        flash("Некорректная дата.")
        return redirect(f"/patients/{pid}")

    conn = get_db()
    cur = conn.cursor()

    # ищем или добавляем диагноз
    cur.execute("SELECT id FROM diagnoses WHERE diagnosis=?", (diag_text,))
    row = cur.fetchone()
    diag_id = row["id"] if row else None

    if not diag_id:
        cur.execute("INSERT INTO diagnoses (diagnosis) VALUES (?)", (diag_text,))
        diag_id = cur.lastrowid

    cur.execute("INSERT INTO patient_diagnoses (patient_id, diagnosis_id, diagnosis_date) VALUES (?, ?, ?)",
                (pid, diag_id, diag_date))

    conn.commit()
    conn.close()

    flash("Диагноз добавлен пациенту")
    return redirect(f"/patients/{pid}")


# -----------------------------------------------------------
# БЛОК 13. Удаление диагноза у пациента
# -----------------------------------------------------------
@app.route("/patient/<int:pid>/delete_diagnosis/<int:pdid>")
@app.route("/patient_diagnosis/<int:pdid>/delete")
def delete_diag_from_patient(pid=None, pdid=None):
    conn = get_db()
    cur = conn.cursor()

    if pid is None:
        # если вызвали старый вариант /patient_diagnosis/<id>/delete
        cur.execute("SELECT patient_id FROM patient_diagnoses WHERE id=?", (pdid,))
        row = cur.fetchone()
        if not row:
            abort(404)
        pid = row["patient_id"]

    cur.execute("DELETE FROM patient_diagnoses WHERE id=?", (pdid,))
    conn.commit()
    conn.close()

    flash("Диагноз удалён")
    return redirect(f"/patients/{pid}")

# -----------------------------------------------------------
# БЛОК 14. Справочник диагнозов
# -----------------------------------------------------------
@app.route("/diagnoses")
def diagnoses_list():
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM diagnoses")
    total = cur.fetchone()[0]
    pages = (total + per_page - 1) // per_page

    cur.execute("""
        SELECT * FROM diagnoses
        ORDER BY diagnosis ASC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    diags = cur.fetchall()

    conn.close()

    return render_template(
        "diagnoses.html",
        diagnoses=diags,
        page=page,
        pages=pages
    )

# -----------------------------------------------------------
# БЛОК 15. Добавление диагноза в справочник
# -----------------------------------------------------------
@app.route("/diagnoses/add", methods=["POST"])
def add_diagnosis():
    name = request.form.get("diagnosis", "").strip()

    if not validate_diagnosis_text(name):
        flash("Некорректное название диагноза.")
        return redirect("/diagnoses")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM diagnoses WHERE diagnosis=?", (name,))
    if cur.fetchone():
        flash("Такой диагноз уже существует.")
        conn.close()
        return redirect("/diagnoses")

    cur.execute("INSERT INTO diagnoses (diagnosis) VALUES (?)", (name,))
    conn.commit()
    conn.close()

    flash("Диагноз добавлен")
    app.logger.info(f"Добавлен диагноз {name}")
    return redirect("/diagnoses")

# -----------------------------------------------------------
# БЛОК 16. Редактирование диагноза
# -----------------------------------------------------------
@app.route("/diagnoses/<int:id>/edit", methods=["POST"])
def edit_diagnosis(id):
    name = request.form.get("diagnosis", "").strip()

    if not validate_diagnosis_text(name):
        flash("Некорректное название диагноза.")
        return redirect("/diagnoses")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE diagnoses SET diagnosis=? WHERE id=?", (name, id))
    conn.commit()
    conn.close()

    flash("Диагноз изменён")
    app.logger.info(f"Диагноз ID={id} изменён на {name}")
    return redirect("/diagnoses")

# -----------------------------------------------------------
# БЛОК 17. Удаление диагноза
# -----------------------------------------------------------
@app.route("/diagnoses/<int:did>/delete")
def delete_diagnosis(did):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM diagnoses WHERE id = ?", (did,))
    diagnosis = cur.fetchone()

    if not diagnosis:
        conn.close()
        flash("Диагноз не найден.", "warning")
        return redirect("/diagnoses")

    cur.execute("DELETE FROM diagnoses WHERE id = ?", (did,))
    conn.commit()
    conn.close()

    flash("Диагноз удалён.", "success")
    return redirect("/diagnoses")

# -----------------------------------------------------------
# БЛОК 18. Запуск сервиса
# -----------------------------------------------------------
if __name__ == "__main__":
    init_db()
    app.run(
        host=CONFIG.get("host", "127.0.0.1"),
        port=CONFIG.get("port", 5000),
        debug=CONFIG.get("debug", False)
    )
