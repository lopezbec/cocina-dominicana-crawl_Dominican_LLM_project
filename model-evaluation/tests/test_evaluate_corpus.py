from types import SimpleNamespace

import pytest
import torch

from evaluate_corpus import build_summary, load_input_rows, resolve_context_window, score_document
from run_ollama_runtime_eval import (
    build_text_chunks,
    extract_ollama_context,
    load_documents,
    resolve_context_policy,
)


class UniformCausalModel(torch.nn.Module):
    def __init__(self, vocabulary_size: int, maximum_context_length: int = 16) -> None:
        super().__init__()
        self.anchor = torch.nn.Parameter(torch.zeros(1))
        self.vocabulary_size = vocabulary_size
        self.config = SimpleNamespace(max_position_embeddings=maximum_context_length)

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


def test_extract_ollama_context_and_resolve_80_percent_policy():
    context = extract_ollama_context(
        {
            "model_info": {
                "qwen3.context_length": 40960,
                "qwen3.embedding_length": 2560,
            }
        }
    )
    policy = resolve_context_policy(
        maximum_context_length=context["maximum_context_length"],
        context_utilization=0.8,
        max_new_tokens=64,
        special_token_reserve=8,
        requested_stride=0,
    )

    assert context["maximum_context_length"] == 40960
    assert policy["effective_context_length"] == 32768
    assert policy["prompt_token_budget"] == 32696
    assert policy["stride"] == 16348


def test_build_text_chunks_uses_token_offsets_and_overlap():
    class FakeFastTokenizer:
        def __call__(self, text, add_special_tokens, return_offsets_mapping, verbose):
            assert add_special_tokens is False
            assert return_offsets_mapping is True
            assert verbose is False
            words = text.split()
            offsets = []
            cursor = 0
            for word in words:
                start = text.index(word, cursor)
                end = start + len(word)
                offsets.append((start, end))
                cursor = end
            return {"input_ids": list(range(len(words))), "offset_mapping": offsets}

    text = "uno dos tres cuatro cinco seis"
    chunks = build_text_chunks(text, FakeFastTokenizer(), prompt_token_budget=4, stride=2)

    assert len(chunks) == 2
    assert chunks[0]["token_start_index"] == 0
    assert chunks[0]["token_end_index_exclusive"] == 4
    assert chunks[0]["_prompt"] == "uno dos tres cuatro"
    assert chunks[1]["token_start_index"] == 2
    assert chunks[1]["token_end_index_exclusive"] == 6
    assert chunks[1]["_prompt"] == "tres cuatro cinco seis"


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
    assert len(result["chunks"]) == 3
    assert [chunk["predicted_token_count"] for chunk in result["chunks"]] == [3, 2, 1]
    assert [chunk["token_start_index"] for chunk in result["chunks"]] == [0, 2, 4]
    assert [chunk["token_end_index_exclusive"] for chunk in result["chunks"]] == [4, 6, 7]
    assert [chunk["context_token_count"] for chunk in result["chunks"]] == [0, 2, 2]
    assert [chunk["scored_token_start_index"] for chunk in result["chunks"]] == [1, 4, 6]
    assert sum(chunk["total_negative_log_likelihood"] for chunk in result["chunks"]) == pytest.approx(
        result["total_negative_log_likelihood"]
    )
    assert all(chunk["perplexity"] == pytest.approx(vocabulary_size) for chunk in result["chunks"])


def test_resolve_context_window_uses_80_percent_of_safest_declared_limit():
    tokenizer = SimpleNamespace(model_max_length=32)
    model = UniformCausalModel(vocabulary_size=5, maximum_context_length=40)

    context = resolve_context_window(tokenizer, model, context_utilization=0.8)

    assert context["maximum_context_length"] == 32
    assert context["utilized_context_length"] == 25
    assert context["effective_context_length"] == 25
    assert context["stride"] == 12
    assert context["max_length_hard_cap"] is None


def test_resolve_context_window_ignores_unknown_tokenizer_sentinel_and_applies_hard_cap():
    tokenizer = SimpleNamespace(model_max_length=10**30)
    model = UniformCausalModel(vocabulary_size=5, maximum_context_length=100)

    context = resolve_context_window(
        tokenizer,
        model,
        context_utilization=0.8,
        requested_max_length=64,
        requested_stride=16,
    )

    assert context["maximum_context_length"] == 100
    assert context["utilized_context_length"] == 80
    assert context["effective_context_length"] == 64
    assert context["stride"] == 16
    assert context["max_length_hard_cap"] == 64


def test_build_summary_weights_metrics_by_tokens_bytes_and_words():
    results = [
        {
            "status": "success",
            "total_negative_log_likelihood": 4.0,
            "predicted_token_count": 2,
            "token_count": 3,
            "word_count": 2,
            "utf8_byte_count": 4,
            "maximum_context_length": 100,
            "context_utilization": 0.8,
            "effective_context_length": 80,
            "stride": 40,
            "window_count": 2,
        },
        {
            "status": "success",
            "total_negative_log_likelihood": 3.0,
            "predicted_token_count": 3,
            "token_count": 4,
            "word_count": 2,
            "utf8_byte_count": 6,
            "maximum_context_length": 100,
            "context_utilization": 0.8,
            "effective_context_length": 80,
            "stride": 40,
            "window_count": 3,
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
    assert summary["maximum_context_length"] == 100
    assert summary["context_utilization"] == 0.8
    assert summary["effective_context_length"] == 80
    assert summary["total_chunk_count"] == 5
