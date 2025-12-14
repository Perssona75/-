import unittest



from validators import (
    validate_name,
    validate_last_name,
    validate_birth_date_ddmmyyyy,
    validate_date_not_future,
    validate_diagnosis_text
)

class TestValidators(unittest.TestCase):
    def test_validate_name_correct(self):
        self.assertTrue(validate_name("Иван"))
        self.assertTrue(validate_name("Анна-Мария"))
        self.assertTrue(validate_name("Jean Pierre"))

    def test_validate_name_incorrect(self):
        self.assertFalse(validate_name("123"))
        self.assertFalse(validate_name("!@#"))
        self.assertFalse(validate_name("A"))
        self.assertFalse(validate_name(""))

    def test_validate_last_name(self):
        self.assertTrue(validate_last_name("Петров"))
        self.assertTrue(validate_last_name("де ла Роса"))
        self.assertFalse(validate_last_name("1Петров"))
        self.assertFalse(validate_last_name(" "))

    def test_birth_date_valid(self):
        self.assertTrue(validate_birth_date_ddmmyyyy("01.01.2000"))
        self.assertTrue(validate_birth_date_ddmmyyyy("31.12.1999"))

    def test_birth_date_invalid(self):
        self.assertFalse(validate_birth_date_ddmmyyyy("31.02.2010"))
        self.assertFalse(validate_birth_date_ddmmyyyy("32.01.2010"))
        self.assertFalse(validate_birth_date_ddmmyyyy("10/10/2010"))
        self.assertFalse(validate_birth_date_ddmmyyyy("2050.01.01"))

    def test_date_not_future(self):
        self.assertTrue(validate_date_not_future("2023-10-10"))
        self.assertFalse(validate_date_not_future("3000-01-01"))

    def test_valid_diagnosis(self):
        self.assertTrue(validate_diagnosis_text("ОРВИ"))
        self.assertTrue(validate_diagnosis_text("Грипп, тип А"))

    def test_invalid_diagnosis(self):
        self.assertFalse(validate_diagnosis_text("!!!---"))
        self.assertFalse(validate_diagnosis_text("AB"))
        self.assertFalse(validate_diagnosis_text(""))