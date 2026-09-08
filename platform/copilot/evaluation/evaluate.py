import argparse
import json
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx


def source_slug(source_uri: str) -> str:
    filename = source_uri.rsplit("/", maxsplit=1)[-1]
    return filename.removesuffix(".md")


def recall_at_five(
    ranked_sources: list[str],
    expected_sources: list[str],
) -> float | None:
    if not expected_sources:
        return None
    found = set(ranked_sources[:5]) & set(expected_sources)
    return len(found) / len(set(expected_sources))


def reciprocal_rank(
    ranked_sources: list[str],
    expected_sources: list[str],
) -> float | None:
    if not expected_sources:
        return None
    for rank, source in enumerate(ranked_sources[:5], start=1):
        if source in expected_sources:
            return 1 / rank
    return 0.0


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def request_payload(item: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "question",
        "component",
        "severity",
        "from_time",
        "to_time",
    )
    return {key: item[key] for key in keys if item.get(key) is not None}


def post_json(
    client: httpx.Client,
    path: str,
    payload: dict[str, Any],
    attempts: int = 10,
) -> dict[str, Any]:
    for attempt in range(1, attempts + 1):
        try:
            response = client.post(path, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.TransportError:
            if attempt == attempts:
                raise
            time.sleep(1)

    raise RuntimeError("Unreachable retry state")


def evaluate(
    questions: list[dict[str, Any]],
    api_url: str,
    retrieval_only: bool,
) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    classification_scores: list[float] = []
    recall_scores: list[float] = []
    reciprocal_ranks: list[float] = []
    citation_scores: list[float] = []
    abstention_scores: list[float] = []

    with httpx.Client(base_url=api_url, timeout=240.0) as client:
        for number, item in enumerate(questions, start=1):
            payload = request_payload(item)
            print(
                f"[{number:02}/{len(questions)}] {item['id']}",
                file=sys.stderr,
            )

            search = post_json(
                client,
                "/api/copilot/search",
                payload,
            )

            ranked_sources = [
                source_slug(result["source_uri"])
                for result in search["results"]
            ]
            retrieved_chunk_ids = {
                result["source_id"]
                for result in search["results"]
            }

            classification_correct = (
                search["classification"]
                == item["expected_classification"]
            )
            classification_scores.append(float(classification_correct))

            recall = recall_at_five(
                ranked_sources,
                item["expected_source_ids"],
            )
            rank_score = reciprocal_rank(
                ranked_sources,
                item["expected_source_ids"],
            )
            if recall is not None:
                recall_scores.append(recall)
            if rank_score is not None:
                reciprocal_ranks.append(rank_score)

            row: dict[str, Any] = {
                "id": item["id"],
                "category": item["category"],
                "classification": search["classification"],
                "expected_classification": item[
                    "expected_classification"
                ],
                "classification_correct": classification_correct,
                "retrieved_sources": ranked_sources,
                "expected_source_ids": item["expected_source_ids"],
                "recall_at_5": recall,
                "reciprocal_rank": rank_score,
            }

            if not retrieval_only:
                answer = post_json(
                    client,
                    "/api/copilot/ask",
                    payload,
                )
                citation_ids = {
                    citation["source_id"]
                    for citation in answer.get("citations", [])
                }
                abstained = bool(answer["insufficient_evidence"])
                citation_valid = (
                    citation_ids <= retrieved_chunk_ids
                    and (
                        abstained
                        or bool(citation_ids)
                    )
                )
                abstention_correct = (
                    abstained == item["should_abstain"]
                )
                citation_scores.append(float(citation_valid))
                abstention_scores.append(float(abstention_correct))
                row.update(
                    {
                        "answer": answer["answer"],
                        "confidence": answer["confidence"],
                        "abstained": abstained,
                        "should_abstain": item["should_abstain"],
                        "abstention_correct": abstention_correct,
                        "citation_ids": sorted(citation_ids),
                        "citation_valid": citation_valid,
                        "expected_facts": item["expected_facts"],
                        "manual_review": {
                            "correct": None,
                            "grounded": None,
                            "notes": "Review against expected_facts and cited passages.",
                        },
                    }
                )

            details.append(row)

    counts = Counter(item["category"] for item in questions)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_url": api_url,
        "question_count": len(questions),
        "category_counts": dict(sorted(counts.items())),
        "retrieval": {
            "recall_at_5": mean(recall_scores),
            "mean_reciprocal_rank": mean(reciprocal_ranks),
            "evaluated_questions": len(recall_scores),
        },
        "classification_accuracy": mean(classification_scores),
        "citation_validity": (
            None if retrieval_only else mean(citation_scores)
        ),
        "abstention_accuracy": (
            None if retrieval_only else mean(abstention_scores)
        ),
        "details": details,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate copilot retrieval and generated answers."
    )
    parser.add_argument(
        "--questions",
        type=Path,
        default=Path(__file__).with_name("questions.json"),
    )
    parser.add_argument(
        "--api-url",
        default="http://copilot-api:8100",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).with_name("report.json"),
    )
    parser.add_argument(
        "--retrieval-only",
        action="store_true",
        help="Skip /ask calls and generation metrics.",
    )
    args = parser.parse_args()

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    report = evaluate(
        questions=questions,
        api_url=args.api_url.rstrip("/"),
        retrieval_only=args.retrieval_only,
    )
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "question_count": report["question_count"],
        "category_counts": report["category_counts"],
        "retrieval": report["retrieval"],
        "classification_accuracy": report["classification_accuracy"],
        "citation_validity": report["citation_validity"],
        "abstention_accuracy": report["abstention_accuracy"],
        "report": str(args.output),
    }, indent=2))


if __name__ == "__main__":
    main()
