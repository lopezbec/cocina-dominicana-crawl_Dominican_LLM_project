# Model evaluation

## Corpus metrics

`evaluate_corpus.py` evaluates every input text file independently and writes one JSON object per file to a JSONL output.

```bash
cd model-evaluation
uv run python evaluate_corpus.py \
  --model-id Qwen/Qwen3-4B-Instruct-2507 \
  --input-path ../crawler/data/processed \
  --output-jsonl outputs/qwen3_metrics.jsonl \
  --overwrite
```

### Context-window policy

By default, every model uses 80% of its safely declared maximum context length. The evaluator reads context limits from the model configuration and tokenizer, ignores Hugging Face's sentinel "unknown" tokenizer limits, and uses the smallest valid declared limit.

- `effective_context_length = floor(maximum_context_length * 0.80)`
- Windows overlap by 50% by default (`stride = effective_context_length // 2`).
- Overlap tokens provide context but are masked from scoring.
- Every document token after the first is scored exactly once.

`--context-utilization` changes the utilization ratio. `--max-length` can impose a lower operational hard cap, and `--stride` can override the automatic stride.

### Per-file and per-chunk JSON

Each JSONL line contains aggregate document metrics and a nested `chunks` array:

```json
{
  "record_type": "document",
  "sample_id": "0001_example",
  "maximum_context_length": 32768,
  "context_utilization": 0.8,
  "effective_context_length": 26214,
  "stride": 13107,
  "window_count": 2,
  "total_negative_log_likelihood": 123.45,
  "per_token_cross_entropy_loss": 2.34,
  "perplexity": 10.38,
  "chunks": [
    {
      "chunk_index": 1,
      "token_start_index": 0,
      "token_end_index_exclusive": 26214,
      "window_token_count": 26214,
      "context_token_count": 0,
      "scored_token_start_index": 1,
      "scored_token_end_index_exclusive": 26214,
      "predicted_token_count": 26213,
      "total_negative_log_likelihood": 100.0,
      "per_token_cross_entropy_loss": 2.3,
      "perplexity": 9.97,
      "runtime_seconds": 12.5,
      "scoring_tokens_per_second": 2097.04
    }
  ]
}
```

Token indexes are zero-based and end indexes are exclusive. The first token cannot be scored by a causal language model because it has no preceding context.

### How Hugging Face quality metrics are produced

The corpus evaluator uses **teacher-forced causal next-token scoring**. It does not calculate quality from only the first token after a chunk, and it does not generate a free-running continuation for perplexity.

If a chunk contains these tokenizer tokens:

```text
[A, B, C, D]
```

the causal model makes these predictions in one forward pass:

```text
A       -> predicts B
A B     -> predicts C
A B C   -> predicts D
```

The evaluator looks up the probability assigned to each actual next token from the source document:

```text
log P(B | A)
log P(C | A, B)
log P(D | A, B, C)
```

This is next-**token** prediction, not necessarily next-word prediction. Depending on the tokenizer, one word may contain several tokens. The first token in the document cannot be scored because it has no preceding token context.

For each scored source token `x_t`, the evaluator calculates:

```text
token_nll = -log P(x_t | preceding tokens in the current window)
```

It then derives the chunk metrics as follows:

```text
chunk_total_nll = sum(token_nll)
chunk_cross_entropy = chunk_total_nll / chunk_predicted_token_count
chunk_perplexity = exp(chunk_cross_entropy)
```

Lower NLL, cross-entropy, and perplexity mean that the model assigned more probability to the actual document tokens. These are confidence/predictability measurements; they are not exact-match generation accuracy.

#### Scoring across overlapping windows

Assume an effective context of 32,768 tokens and a stride of 16,384:

```text
Window 1: tokens     0..32767
          context:   none
          scored:    1..32767

Window 2: tokens 16384..49151
          context: 16384..32767
          scored:  32768..49151
```

The overlapping prefix in each later window is provided to the model as context, but its labels are masked with `-100` and excluded from the loss. Only tokens not scored by a previous window contribute new NLL. The evaluator verifies that every document token after the first was scored exactly once.

The file-level NLL is the sum of all chunk NLL values. File-level cross-entropy and perplexity are calculated from that sum and the number of uniquely scored tokens—not by averaging chunk perplexities:

```text
file_cross_entropy = sum(chunk_total_nll) / sum(chunk_predicted_token_count)
file_perplexity = exp(file_cross_entropy)
```

The corpus summary follows the same weighted rule across successful files. A long file therefore contributes proportionally more scored tokens than a short file. The summary is written beside the JSONL output as `<output-stem>_summary.json`.

#### Single next-token prediction field

`top_k_next_token_predictions` is different from the teacher-forced document metrics. It uses the logits at the final position of the final window and reports the most likely tokens immediately following that last input token. This is the only corpus-evaluator field specifically representing one next token beyond the supplied input.

Optional `target_token_logprobs` artifacts contain the individual teacher-forced log probability for every scored source token. Optional final-logit and probability-vector artifacts correspond only to the position after the final token in the final window.

### Hugging Face metric definitions

| Metric | Meaning |
|---|---|
| `total_negative_log_likelihood` | Sum of `-log P(actual next token)` across uniquely scored source tokens. |
| `per_token_cross_entropy_loss` | Total NLL divided by predicted-token count. |
| `mean_negative_log_likelihood` | Alias of per-token cross-entropy. |
| `perplexity` | `exp(per_token_cross_entropy_loss)`. Lower is better. |
| `bits_per_byte` | Total NLL normalized by the number of original UTF-8 bytes and `log(2)`. |
| `tokenizer_fertility` | Token count divided by whitespace-delimited word count. |
| `runtime_seconds` | Wall-clock duration for scoring the file. |
| `scoring_tokens_per_second` | Uniquely scored source tokens divided by runtime. |

## Ollama runtime metrics

`run_ollama_runtime_eval.py` applies the same 80% context policy and nested per-file `chunks` structure to metrics that Ollama exposes directly:

```bash
uv run python run_ollama_runtime_eval.py \
  --model qwen3:4b \
  --tokenizer-id Qwen/Qwen3-4B \
  --input-path ../crawler/data/processed \
  --output-jsonl outputs/qwen3_ollama_runtime.jsonl \
  --overwrite
```

The evaluator reads the model capacity from Ollama's `/api/show`, reserves space for generated and special tokens, sets `options.num_ctx` to 80% of that capacity, and uses the corresponding Hugging Face fast tokenizer to build overlapping chunks from original-text character offsets. The tokenizer must match the Ollama model.

For example, for a model with a 40,960-token maximum context, 64 requested output tokens, and the default 32-token safety reserve:

```text
effective_context_length = floor(40960 * 0.80) = 32768
prompt_token_budget = 32768 - 64 - 32 = 32672
```

`num_ctx` is set to 32,768, while each planned source-text chunk is limited to 32,672 tokenizer tokens. The reserve leaves room for generated tokens, BOS tokens, model templates, and small tokenizer-boundary differences. The actual `prompt_eval_count` returned by Ollama is validated so that the prompt plus reserved generation does not exceed the effective context allocation.

### How Ollama metrics are produced

Each chunk is submitted as a prompt to `/api/generate`. Ollama first performs **prompt evaluation** (also called prefill), then generates a free-running continuation autoregressively:

```text
source chunk -> generated token 1 -> generated token 2 -> ...
```

Ollama returns counts and durations for both phases. The evaluator stores those native values inside the corresponding chunk:

| Metric | Meaning |
|---|---|
| `prompt_eval_count` | Number of prompt tokens processed by Ollama for the chunk. |
| `prompt_eval_duration_seconds` | Time spent processing the source prompt. |
| `prompt_tokens_per_second` | Prompt tokens divided by prompt-evaluation duration. |
| `eval_count` / `generated_token_count` | Number of continuation tokens generated. |
| `eval_duration_seconds` / `generation_duration_seconds` | Time spent generating continuation tokens. |
| `tokens_per_second` / `generation_tokens_per_second` | Generated tokens divided by generation duration. |
| `load_duration_seconds` | Time Ollama spent loading or preparing the model. |
| `total_duration_seconds` | Total duration reported by Ollama for that request. |
| `wall_clock_seconds` | Client-observed request duration. |
| `response` | Free-running generated continuation for that chunk. |

The file-level Ollama counts and durations are sums across successful chunks. Throughput is recomputed from the summed counts and durations. Because chunks overlap, aggregate `prompt_eval_count` measures total computational workload and can be greater than the number of unique source tokens.

### Why Ollama does not report Hugging Face quality metrics

Ollama internally performs next-token prediction, but the `/api/generate` response used here does not expose the complete logits or probability assigned to every actual source token. Its `prompt_eval_count` reports how many prompt tokens were processed, not how probable those tokens were.

Consequently, the evaluator does not invent or approximate NLL, cross-entropy, perplexity, or bits per byte for Ollama. The two backends are intentionally complementary:

- **Hugging Face** provides teacher-forced source-token quality metrics and scoring throughput.
- **Ollama** provides native prompt-processing, continuation-generation, and runtime metrics.

Both use the same 80% capacity policy and nested per-file `chunks` organization, while each stores the metrics its backend exposes reliably.

## Other evaluator

`run_hf_math_eval.py` scores fixed prompt/continuation samples rather than complete corpus files.
