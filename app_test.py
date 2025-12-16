import unittest
import sqlite3
import tempfile
import os
from datetime import date

from app import app, get_db

class AppTestCase(unittest.TestCase):

    # --------------------------------------------------
    # Подготовка тестовой среды
    # --------------------------------------------------
    def setUp(self):
        # создаём временный файл базы данных
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")

        app.config["DATABASE"] = self.db_path
        app.config["TESTING"] = True

        self.client = app.test_client()

        # создаём таблицы
        self._create_tables()

    def tearDown(self):
        try:
            os.close(self.db_fd)
            os.unlink(self.db_path)
        except PermissionError:
            pass

    # --------------------------------------------------
    # Создание таблиц базы данных
    # --------------------------------------------------
    def _create_tables(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE patients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                birth_date TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE diagnoses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                diagnosis TEXT NOT NULL UNIQUE
            )
        """)

        cur.execute("""
            CREATE TABLE patient_diagnoses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                diagnosis_id INTEGER NOT NULL,
                diagnosis_date TEXT NOT NULL,
                FOREIGN KEY (patient_id) REFERENCES patients (id),
                FOREIGN KEY (diagnosis_id) REFERENCES diagnoses (id)
            )
        """)

        conn.commit()
        conn.close()

    def test_add_patient(self):
        self.client.post("/patients/add", data={
            "first_name": "Иван",
            "last_name": "Петров",
            "birth_year": "01.01.2000"
        })

        # используем ТО ЖЕ подключение, что и приложение
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT name, last_name, birth_date FROM patients")
        patient = cur.fetchone()

        conn.close()

        self.assertIsNotNone(patient)
        self.assertEqual(patient[0], "Иван")
        self.assertEqual(patient[1], "Петров")
        self.assertEqual(patient[2], "2000-01-01")

    # --------------------------------------------------
    # 1. Удаление пациента
    # --------------------------------------------------
    def test_delete_patient(self):
        self.client.post("/patients/add", data={
            "name": "Иван",
            "last_name": "Петров",
            "birth_year": "01.01.2000"
        })

        self.client.get("/patients/1/delete")

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM patients")
        row = cur.fetchone()
        conn.close()

        self.assertIsNone(row)

    # --------------------------------------------------
    # 2. Добавление диагноза через карточку пациента
    # --------------------------------------------------
    def test_add_diagnosis_to_patient_card(self):
        self.client.post("/patients/add", data={
            "name": "Анна",
            "last_name": "Иванова",
            "birth_year": "02.02.2002"
        })

        today = date.today().isoformat()

        self.client.post("/patients/1/assign", data={
            "diagnosis": "ОРВИ",
            "diagnosis_date": today
        })

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("""
            SELECT d.diagnosis
            FROM patient_diagnoses pd
            JOIN diagnoses d ON d.id = pd.diagnosis_id
        """)
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "ОРВИ")

    # --------------------------------------------------
    # 3. Удаление диагноза из карточки пациента
    # --------------------------------------------------
    def test_delete_diagnosis_from_patient_card(self):
        self.client.post("/patients/add", data={
            "name": "Петр",
            "last_name": "Сидоров",
            "birth_year": "03.03.2003"
        })

        today = date.today().isoformat()

        self.client.post("/patients/1/assign", data={
            "diagnosis": "Грипп",
            "diagnosis_date": today
        })

        self.client.get("/patient_diagnosis/1/delete")

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM patient_diagnoses")
        row = cur.fetchone()
        conn.close()

        self.assertIsNone(row)

    # --------------------------------------------------
    # 4. Добавление диагноза через страницу диагнозов
    # --------------------------------------------------
    def test_add_diagnosis_from_list(self):
        self.client.post("/diagnoses/add", data={
            "diagnosis": "Бронхит"
        })

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT diagnosis FROM diagnoses")
        row = cur.fetchone()
        conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "Бронхит")

    # --------------------------------------------------
    # 5. Удаление диагноза через страницу диагнозов
    # --------------------------------------------------
    def test_delete_diagnosis_from_list(self):
        self.client.post("/diagnoses/add", data={
            "diagnosis": "Пневмония"
        })

        self.client.get("/diagnoses/1/delete")

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM diagnoses")
        row = cur.fetchone()
        conn.close()

        self.assertIsNone(row)


if __name__ == "__main__":
    unittest.main()
