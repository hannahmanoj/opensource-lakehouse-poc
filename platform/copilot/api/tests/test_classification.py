import unittest
from app.classification import classify_question


class ClassificationTests(unittest.TestCase):
    def test_incident_diagnosis(self):
        result = classify_question(
            "Why did yesterday's Spark ingestion fail?"
        )

        self.assertEqual(result, "incident_diagnosis")

    def test_incident_diagnosis_with_fail(self):
        result = classify_question(
            "Why did the Spark ingestion fail?"
        )

        self.assertEqual(result, "incident_diagnosis")

    def test_documentation_question(self):
        result = classify_question(
            "What is an Apache Iceberg snapshot?"
        )

        self.assertEqual(result, "documentation_question")

    def test_operational_checklist(self):
        result = classify_question(
            "What should I check before restarting MinIO?"
        )

        self.assertEqual(result, "operational_checklist")

    def test_table_health(self):
        result = classify_question(
            "Which Iceberg tables have too many small files?"
        )

        self.assertEqual(result, "table_health")

    def test_access_control(self):
        result = classify_question(
            "Why did Trino return PERMISSION_DENIED?"
        )

        self.assertEqual(result, "access_control")

    def test_unknown(self):
        result = classify_question(
            "Can you look at this?"
        )

        self.assertEqual(result, "unknown")

    def test_normalizes_error_code(self):
        result = classify_question(
            "What does permission_denied mean?"
        )

        self.assertEqual(result, "access_control")


if __name__ == "__main__":
    unittest.main()
