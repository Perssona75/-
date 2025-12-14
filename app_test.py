import unittest
import sqlite3
import tempfile
import os
from datetime import date

from app import app


class PatientDiagnosisTestCase(unittest.TestCase):

    def setUp(self):
        app.config["TESTING"] = True

        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        app.config["DATABASE"] = self.db_path

        self.client = app.test_client()

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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
                FOREIGN KEY(patient_id) REFERENCES patients(id),
                FOREIGN KEY(diagnosis_id) REFERENCES diagnoses(id)
            )
        """)

        conn.commit()
        conn.close()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    # ---------------- Пациенты ----------------

    def test_add_patient(self):
        r = self.client.post("/patients/add", data={
            "name": "Иван",
            "last_name": "Петров",
            "birth_date": "01.01.2000",
        }, follow_redirects=True)
        self.assertIn("Пациент добавлен", r.data.decode())

    def test_delete_patient(self):
        self.client.post("/patients/add", data={
            "name": "Анна",
            "last_name": "Сидорова",
            "birth_date": "02.02.2002",
        })

        r = self.client.get("/patients/1/delete", follow_redirects=True)
        self.assertIn("Пациент удалён", r.data.decode())

    # ---------------- Диагнозы пациента ----------------

    def test_add_diagnosis_to_patient(self):
        today = date.today().isoformat()

        self.client.post("/patients/add", data={
            "name": "Петр",
            "last_name": "Иванов",
            "birth_date": "03.03.2003",
        })

        self.client.post("/diagnoses/add", data={"diagnosis": "ОРВИ"})

        r = self.client.post("/patient/1/add_diagnosis", data={
            "diagnosis": "ОРВИ",
            "diagnosis_date": today,
        }, follow_redirects=True)

        self.assertIn("Диагноз добавлен пациенту", r.data.decode())

    def test_delete_diagnosis_from_patient(self):
        today = date.today().isoformat()

        self.client.post("/patients/add", data={
            "name": "Петр",
            "last_name": "Иванов",
            "birth_date": "03.03.2003",
        })

        self.client.post("/diagnoses/add", data={"diagnosis": "ОРВИ"})
        self.client.post("/patient/1/add_diagnosis", data={
            "diagnosis": "ОРВИ",
            "diagnosis_date": today,
        })

        r = self.client.get("/patient/1/delete_diagnosis/1", follow_redirects=True)
        self.assertIn("Диагноз удалён", r.data.decode())

    # ---------------- Справочник диагнозов ----------------

    def test_add_diagnosis(self):
        r = self.client.post("/diagnoses/add", data={"diagnosis": "Грипп"}, follow_redirects=True)
        self.assertIn("Диагноз добавлен", r.data.decode())

    def test_delete_diagnosis(self):
        self.client.post("/diagnoses/add", data={"diagnosis": "Грипп"})

        r = self.client.get("/diagnoses/1/delete", follow_redirects=True)
        self.assertIn("Диагноз удалён", r.data.decode())

    def test_edit_diagnosis(self):
        self.client.post("/diagnoses/add", data={"diagnosis": "Грипп"})

        r = self.client.post("/diagnoses/1/edit", data={"diagnosis": "ОРВИ"}, follow_redirects=True)
        self.assertIn("Диагноз изменён", r.data.decode())


if __name__ == "__main__":
    unittest.main()
