import unittest

from app.retrieval.sufficiency import evaluate_sufficiency


def evidence(
    source_uri: str = "knowledge://runbook",
    source_type: str = "runbook",
    occurred_at: str | None = "2026-09-03T09:00:00Z",
    semantic_score: float | None = 0.8,
    keyword_score: float | None = None,
) -> dict:
    return {
        "source_uri": source_uri,
        "source_type": source_type,
        "occurred_at": occurred_at,
        "semantic_score": semantic_score,
        "keyword_score": keyword_score,
    }


class SufficiencyTests(unittest.TestCase):
    def test_rejects_irrelevant_results(self):
        decision = evaluate_sufficiency(
            classification="documentation_question",
            results=[evidence(semantic_score=0.2)],
        )

        self.assertFalse(decision.sufficient)
        self.assertEqual(decision.confidence, "low")

    def test_incident_requires_timestamped_log(self):
        decision = evaluate_sufficiency(
            classification="incident_diagnosis",
            results=[evidence(source_type="incident")],
            requested_component="spark",
        )

        self.assertFalse(decision.sufficient)
        self.assertIn(
            "Spark timestamped log",
            decision.missing_evidence,
        )

    def test_incident_accepts_timestamped_log(self):
        decision = evaluate_sufficiency(
            classification="incident_diagnosis",
            results=[evidence(source_type="spark_log")],
            requested_component="spark",
        )

        self.assertTrue(decision.sufficient)
        self.assertEqual(decision.confidence, "medium")

    def test_two_sources_allow_high_confidence(self):
        decision = evaluate_sufficiency(
            classification="documentation_question",
            results=[
                evidence(source_uri="knowledge://one"),
                evidence(source_uri="knowledge://two"),
            ],
        )

        self.assertTrue(decision.sufficient)
        self.assertEqual(decision.confidence, "high")

    def test_missing_filtered_evidence_is_explained(self):
        decision = evaluate_sufficiency(
            classification="documentation_question",
            results=[],
            requested_component="trino",
            date_requested=True,
        )

        self.assertIn(
            "Evidence for component: trino",
            decision.missing_evidence,
        )
        self.assertIn(
            "Evidence in the requested date range",
            decision.missing_evidence,
        )


if __name__ == "__main__":
    unittest.main()
