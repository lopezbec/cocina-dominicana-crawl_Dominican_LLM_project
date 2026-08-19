from types import SimpleNamespace

import pytest
import torch

from evaluate_corpus import build_summary, load_input_rows, score_document
from run_ollama_runtime_eval import load_documents


class UniformCausalModel(torch.nn.Module):
    def __init__(self, vocabulary_size: int) -> None:
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1))
        self.vocabulary_size = vocabulary_size

    def forward(self, input_ids, use_cache=False, return_dict=True):
        del use_cache, return_dict
        logits = torch.zeros(
            (*input_ids.shape, self.vocabulary_size),
            dtype=torch.float32,
            device=input_ids.device,
        )
        return SimpleNamespace(logits=logits)


def test_load_input_rows_reads_processed_text_files_in_stable_order(tmp_path):
    (tmp_path / "b.txt").write_text("segundo", encoding="utf-8")
    (tmp_path / "a.txt").write_text("primero", encoding="utf-8")
    (tmp_path / "ignored.md").write_text("no", encoding="utf-8")

    rows = load_input_rows(tmp_path, "text", "document_id", limit=0)

    assert [row["sample_id"] for row in rows] == ["a", "b"]
    assert [row["text"] for row in rows] == ["primero", "segundo"]


def test_load_documents_limits_ollama_corpus_in_stable_order(tmp_path):
    (tmp_path / "b.txt").write_text("segundo", encoding="utf-8")
    (tmp_path / "a.txt").write_text("primero", encoding="utf-8")

    rows = load_documents(tmp_path, limit=1)

    assert [row["sample_id"] for row in rows] == ["a"]
    assert rows[0]["text"] == "primero"


def test_score_document_scores_every_token_after_the_first_across_windows():
    vocabulary_size = 5
    token_ids = [0, 1, 2, 3, 4, 0, 1]

    result = score_document(
        token_ids=token_ids,
        model=UniformCausalModel(vocabulary_size),
        input_device=torch.device("cpu"),
        max_length=4,
        stride=2,
        collect_token_logprobs=True,
    )

    assert result["predicted_token_count"] == len(token_ids) - 1
    assert result["total_negative_log_likelihood"] == pytest.approx(
        (len(token_ids) - 1) * torch.log(torch.tensor(vocabulary_size)).item()
    )
    assert [row["position"] for row in result["token_logprobs"]] == [2, 3, 4, 5, 6, 7]


def test_build_summary_weights_metrics_by_tokens_bytes_and_words():
    results = [
        {
            "status": "success",
            "total_negative_log_likelihood": 4.0,
            "predicted_token_count": 2,
            "token_count": 3,
            "word_count": 2,
            "utf8_byte_count": 4,
        },
        {
            "status": "success",
            "total_negative_log_likelihood": 3.0,
            "predicted_token_count": 3,
            "token_count": 4,
            "word_count": 2,
            "utf8_byte_count": 6,
        },
    ]
    args = SimpleNamespace(
        model_id="test/model",
        revision="main",
        input_path="crawler/data/processed",
    )

    summary = build_summary(results, args)

    assert summary["per_token_cross_entropy_loss"] == pytest.approx(7.0 / 5.0)
    assert summary["perplexity"] == pytest.approx(torch.exp(torch.tensor(7.0 / 5.0)).item())
    assert summary["bits_per_byte"] == pytest.approx(7.0 / (torch.log(torch.tensor(2.0)).item() * 10))
    assert summary["tokenizer_fertility"] == pytest.approx(7.0 / 4.0)
