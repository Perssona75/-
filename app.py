import os
import json
import logging
import sqlite3
from datetime import datetime, date
from logging.handlers import RotatingFileHandler

from flask import (
    Flask, render_template, request,
    redirect, flash, abort
)

from validators import (
    validate_name,
    validate_last_name,
    validate_birth_date_ddmmyyyy,
    validate_date_not_future,
    validate_diagnosis_text
)

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
with open("config.json", encoding="utf-8") as f:
    CONFIG = json.load(f)

# ============================================================
# FLASK
# ============================================================
app = Flask(__name__)
app.secret_key = "supersecret123"
app.config["DATABASE"] = CONFIG["database"]

# ============================================================
# ЛОГИРОВАНИЕ
# ============================================================
os.makedirs("logs", exist_ok=True)

log_cfg = CONFIG["LOGGING"]
log_level = getattr(logging, log_cfg.get("LEVEL", "INFO").upper(), logging.INFO)

handler = RotatingFileHandler(
    log_cfg["LOG_FILE"],
    maxBytes=log_cfg["MAX_BYTES"],
    backupCount=log_cfg["BACKUP_COUNT"],
    encoding="utf-8"
)
handler.setLevel(log_level)
handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))

app.logger.setLevel(log_level)
app.logger.addHandler(handler)

# ============================================================
# БАЗА ДАННЫХ
# ============================================================
def get_db():
    conn = sqlite3.connect(app.config["DATABASE"], timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            last_name TEXT NOT NULL,
            birth_date TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            diagnosis TEXT NOT NULL UNIQUE
        )
    """)

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

# ============================================================
# СЕРВИСНЫЙ СЛОЙ
# ============================================================
def create_patient(name, last_name, birth_date):
    if not validate_name(name):
        raise ValueError("Некорректное имя")
    if not validate_last_name(last_name):
        raise ValueError("Некорректная фамилия")
    if not validate_birth_date_ddmmyyyy(birth_date):
        raise ValueError("Некорректная дата рождения")

    birth_iso = datetime.strptime(birth_date, "%d.%m.%Y").strftime("%Y-%m-%d")

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO patients (name, last_name, birth_date) VALUES (?, ?, ?)",
        (name, last_name, birth_iso)
    )
    conn.commit()
    conn.close()


def delete_patient(pid: int):
    conn = get_db()
    cur = conn.cursor()

    # удаляем связи диагнозов пациента (чтобы не было "висящих" строк)
    cur.execute("DELETE FROM patient_diagnoses WHERE patient_id=?", (pid,))
    cur.execute("DELETE FROM patients WHERE id=?", (pid,))

    conn.commit()
    conn.close()


def create_diagnosis(name: str):
    if not validate_diagnosis_text(name):
        raise ValueError("Некорректное название диагноза")

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM diagnoses WHERE diagnosis=?", (name,))
    if cur.fetchone():
        conn.close()
        raise ValueError("Такой диагноз уже существует")

    cur.execute("INSERT INTO diagnoses (diagnosis) VALUES (?)", (name,))
    conn.commit()
    conn.close()


def update_diagnosis(did: int, name: str):
    if not validate_diagnosis_text(name):
        raise ValueError("Некорректное название диагноза")

    conn = get_db()
    cur = conn.cursor()

    # запрещаем переименование в уже существующий диагноз
    cur.execute("SELECT id FROM diagnoses WHERE diagnosis=? AND id!=?", (name, did))
    if cur.fetchone():
        conn.close()
        raise ValueError("Диагноз с таким названием уже существует")

    cur.execute("UPDATE diagnoses SET diagnosis=? WHERE id=?", (name, did))
    conn.commit()
    conn.close()


def delete_diagnosis(did: int):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM diagnoses WHERE id=?", (did,))
    conn.commit()
    conn.close()


def add_diagnosis_to_patient(pid: int, diagnosis: str, diag_date: str):
    if not validate_diagnosis_text(diagnosis):
        raise ValueError("Некорректный диагноз")
    if not validate_date_not_future(diag_date):
        raise ValueError("Некорректная дата")

    conn = get_db()
    cur = conn.cursor()

    # диагноз: берём существующий или создаём новый
    cur.execute("SELECT id FROM diagnoses WHERE diagnosis=?", (diagnosis,))
    row = cur.fetchone()
    if row:
        diag_id = row["id"]
    else:
        cur.execute("INSERT INTO diagnoses (diagnosis) VALUES (?)", (diagnosis,))
        diag_id = cur.lastrowid

    cur.execute("""
        INSERT INTO patient_diagnoses (patient_id, diagnosis_id, diagnosis_date)
        VALUES (?, ?, ?)
    """, (pid, diag_id, diag_date))

    conn.commit()
    conn.close()


def delete_patient_diagnosis(pd_id: int) -> int:
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT patient_id FROM patient_diagnoses WHERE id=?", (pd_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError("Диагноз не найден")

    pid = row["patient_id"]
    cur.execute("DELETE FROM patient_diagnoses WHERE id=?", (pd_id,))
    conn.commit()
    conn.close()
    return pid

# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    return render_template("index.html")


# --------------------- PATIENTS ---------------------
@app.route("/patients")
def patients():
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM patients")
    total = cur.fetchone()[0]
    pages = (total + per_page - 1) // per_page if total else 1

    cur.execute("""
        SELECT * FROM patients
        ORDER BY last_name ASC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    data = cur.fetchall()

    conn.close()

    return render_template(
        "patients.html",
        patients=data,
        page=page,
        pages=pages
    )


@app.route("/patients/add", methods=["POST"])
def add_patient():
    try:
        create_patient(
            request.form.get("first_name"),
            request.form.get("last_name"),
            request.form.get("birth_year")
        )
        flash("Пациент добавлен")
    except ValueError as e:
        flash(str(e))
    return redirect("/patients")


@app.route("/patients/<int:pid>/delete")
def remove_patient(pid):
    delete_patient(pid)
    flash("Пациент удалён")
    return redirect("/patients")


@app.route("/patients/<int:pid>")
def patient_card(pid):
    page = int(request.args.get("page", 1))
    per_page = 5
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM patients WHERE id=?", (pid,))
    patient = cur.fetchone()
    if not patient:
        conn.close()
        abort(404)

    # считаем историю диагнозов
    cur.execute("SELECT COUNT(*) FROM patient_diagnoses WHERE patient_id=?", (pid,))
    total = cur.fetchone()[0]
    pages = (total + per_page - 1) // per_page if total else 1

    # берём текущую страницу диагнозов
    cur.execute("""
        SELECT pd.id, d.diagnosis, pd.diagnosis_date
        FROM patient_diagnoses pd
        JOIN diagnoses d ON d.id = pd.diagnosis_id
        WHERE pd.patient_id=?
        ORDER BY pd.diagnosis_date DESC
        LIMIT ? OFFSET ?
    """, (pid, per_page, offset))
    diagnoses = cur.fetchall()

    # подсказки диагнозов
    cur.execute("SELECT diagnosis FROM diagnoses ORDER BY diagnosis ASC")
    suggestions = [r["diagnosis"] for r in cur.fetchall()]

    conn.close()

    return render_template(
        "patient_card.html",
        patient=patient,
        diagnoses=diagnoses,
        diag_suggestions=suggestions,
        page=page,
        pages=pages,
        current_date=str(date.today())
    )


@app.route("/patients/<int:pid>/assign", methods=["POST"])
def assign_diagnosis(pid):
    try:
        add_diagnosis_to_patient(
            pid,
            request.form.get("diagnosis"),
            request.form.get("diagnosis_date")
        )
        flash("Диагноз добавлен пациенту")
    except ValueError as e:
        flash(str(e))
    return redirect(f"/patients/{pid}")


@app.route("/patient_diagnosis/<int:pd_id>/delete")
def remove_patient_diagnosis(pd_id):
    try:
        pid = delete_patient_diagnosis(pd_id)
        flash("Диагноз удалён")
        return redirect(f"/patients/{pid}")
    except ValueError as e:
        flash(str(e))
        return redirect("/patients")


# --------------------- DIAGNOSES ---------------------
@app.route("/diagnoses")
def diagnoses():
    page = int(request.args.get("page", 1))
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM diagnoses")
    total = cur.fetchone()[0]
    pages = (total + per_page - 1) // per_page if total else 1

    cur.execute("""
        SELECT * FROM diagnoses
        ORDER BY diagnosis ASC
        LIMIT ? OFFSET ?
    """, (per_page, offset))
    data = cur.fetchall()

    conn.close()

    return render_template(
        "diagnoses.html",
        diagnoses=data,
        page=page,
        pages=pages
    )


@app.route("/diagnoses/add", methods=["POST"])
def add_diagnosis():
    try:
        create_diagnosis(request.form.get("diagnosis"))
        flash("Диагноз добавлен")
    except ValueError as e:
        flash(str(e))
    return redirect("/diagnoses")


@app.route("/diagnoses/<int:did>/edit", methods=["POST"])
def edit_diagnosis(did):
    try:
        update_diagnosis(did, request.form.get("diagnosis"))
        flash("Диагноз изменён")
    except ValueError as e:
        flash(str(e))
    return redirect("/diagnoses")


@app.route("/diagnoses/<int:did>/delete")
def remove_diagnosis(did):
    delete_diagnosis(did)
    flash("Диагноз удалён")
    return redirect("/diagnoses")


# ============================================================
# RUN
# ============================================================
if __name__ == "__main__":
    init_db()
    app.run(
        host=CONFIG["host"],
        port=CONFIG["port"],
        debug=CONFIG["debug"]
    )
