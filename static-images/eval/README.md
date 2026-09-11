# Diagram evaluations

Start with either notebook in this folder:

- **Recognize diagrams** — [`recognize-diagrams.ipynb`](recognize-diagrams.ipynb): ask a model what structure each image communicates.
- **Compare diagrams** — [`compare-diagrams.ipynb`](compare-diagrams.ipynb): compare Spytial diagrams against CLRS references, then inspect scores, matrices and rankings.

Open a notebook in Jupyter or VS Code and select the `spytial` Python environment as its kernel. Run the cells from top to bottom. Both default to **preview**, which makes no model calls. Change `MODE` to `"evaluate"` for live judgments; set `LIMIT = 1` for a first live check. Settings, progress, results and explanations are available directly in the notebooks. The comparison notebook also displays a colored score matrix.

Each run saves its settings and results in a fresh folder under `results/`. Notebooks are saved without outputs so image judgments and local paths are not accidentally checked in. If you save an executed notebook, clear its outputs before committing.

The notebooks use the tested scripts below. The old `rq1`/`rq2` filenames are retained for compatibility; the everyday names are **recognition** and **comparison**.

## Recognition: command-line usage

Run from the repository root, preferably in the project's `spytial` conda environment:

```sh
conda activate spytial
python -m pip install -r static-images/eval/requirements.txt
python static-images/eval/run_rq1.py --dry-run
python static-images/eval/run_rq1.py --backend claude-code --limit 1
python static-images/eval/run_rq1.py --backend codex --limit 1
python static-images/eval/run_rq1.py --backend claude-api --limit 1
python static-images/eval/run_rq1.py --backend ollama --model qwen2.5vl:7b --limit 1
```

Remove `--limit 1` to evaluate all images. PNG, JPEG, GIF, and WebP are recognized
by content, including extensionless files. Discovery recursively scans
`static-images`, excluding this harness and its outputs. Unsupported files are
listed in the manifest; malformed files with recognized extensions stop discovery.

## Backends

- **claude-code** (default): uses the installed `claude` executable and existing
  Claude Code authentication/subscription or environment credentials. Requires
  `--json-schema`, streaming image input, and `--no-session-persistence` support.
  Each image starts a new process with no tools, MCP servers, skills, or settings
  sources. Auto memory and all CLAUDE.md loading are explicitly disabled through
  environment overrides, and hooks are disabled. These controls are present in
  the locally checked Claude Code 2.1.31; older clients may need updating.
  No API key needs to be added to this project.
- **codex**: uses the installed `codex` executable and existing local authentication
  (`CODEX_HOME` is preserved). Requires the recent CLI options shown in
  `codex exec --help`, including `--ignore-user-config`. Each image starts a new
  ephemeral session. User config is intentionally ignored to avoid repository,
  plugin, or personal instructions affecting recognition. Shell, web search,
  memory use and generation, project instructions, host skill discovery, plugins,
  hooks, apps, and subagents are disabled; any reported tool use fails the sample.
  This requires a CLI with `features.skip_host_skill_discovery` (checked locally
  with Codex 0.153.4). Custom provider/profile settings are not inherited.
- **claude-api**: calls the Anthropic Messages API directly using
  `ANTHROPIC_API_KEY` from your environment. This uses API billing, independently
  of a Claude Code subscription. Use a model supporting vision and structured
  outputs. No Anthropic Python SDK is required.
- **ollama**: calls `/api/chat` at `ollama_url` (default `http://localhost:11434`).
  Start your Ollama server and install a vision-capable model separately. The
  harness does not download models or start servers. Use `ollama list` to choose
  an installed model and pass its exact name with `--model`. The sample model is
  an example, not an assertion that it is installed. Local Ollama supports the
  JSON schema format; not every model or remote service supports these features.

`config.json` sets the backend, per-backend models, prompt path, timeout, token
limit, temperature, shuffle seed, executable locations, and Ollama URL.
`--model` overrides only the selected backend. Set executable locations in config
if they are not on PATH. For the default `codex` command on macOS, the harness
also checks Codex.app and ChatGPT.app in `/Applications` and `~/Applications`.
An explicit executable path always takes precedence and is never silently
replaced. Do not put credentials in config or endpoint URLs.
Config-relative paths resolve relative to that config file; command-line paths
resolve relative to your working directory. Use `--config path/to/config.json`,
`--images-dir path`, or `--output-dir path/to/new-run` as needed.

## Blinding and reproducibility

Only the shared `prompt.txt` and the image are supplied for recognition. Original
filenames, directory labels, pairings, and ground truth are kept in local result
metadata and never inserted into model input. Each image is independent. Images
are re-encoded as metadata-free RGB PNGs at their original dimensions; orientation
is applied, transparency is composited onto white, and only the first animation
frame is used. Codex receives a neutral `image.png` in a temporary directory.
Claude and Ollama receive base64 image content.

Every image has a fresh request/session, including images within the same run.
No earlier answers or conversation IDs are forwarded. Parent CLI session IDs
are removed from the child environment, and each CLI working directory is deleted
after that image. Authentication stays available without importing chat history.
The same minimal system instruction is supplied to all four backends, including
an explicit Ollama system message. The manifest records these isolation controls.

This is isolation from conversation and local memory, not removal of the model's
trained knowledge, provider-required instructions, or visible image content.
For Ollama, use a standard vision model: custom Modelfiles can embed MESSAGE
examples/history or custom templates, which this harness does not remove.

Visible titles or labels in the image remain visible: inspect/crop those before
running if they would reveal an answer. Fresh CLI sessions and neutral working
directories reduce contextual leakage; managed/global client policies can still
influence CLI behavior. The direct API backends offer more explicit input control.
The providers may internally resize images.

The manifest saves the exact prompt, schema, effective configuration, selected
model, script hash, Python/Pillow/CLI versions, original image hashes, and seeded
image order. Each result also saves the re-encoded image hash. The API raw
response retains the actual reported model and usage where available. Model
aliases/tags may change: pin model versions and retain your Ollama model digest
(e.g. from `ollama list`) when recording an experiment. Temperature applies only
to direct API backends; seed additionally applies to Ollama sampling. CLI
sampling is provider-controlled. Reproducibility here means recording inputs and
settings, not guaranteeing identical model responses.

## Results

Every invocation creates a new timestamped directory under `eval/results/`:

- `manifest.json`: run configuration, prompt, versions, image mapping and order.
- `images/image-NNNN.json`: source metadata, status, timing, validated `result`,
  or an explicit error. `result` contains `identification`, `confidence` (0–100),
  `visual_evidence` (2–4 strings), and `alternatives` (0–2 strings).
- `raw/image-NNNN.json`: provider response or CLI output, saved before validation.
- `results.jsonl`: one complete record per image, including failures.
- `results.csv`: flattened answers; evidence and alternatives are JSON arrays
  inside CSV cells.

Outputs are ignored by Git. Existing run directories are never overwritten.
The harness saves aggregates after every image, continues after individual
failures, and exits nonzero if any image failed. There are no automatic retries
or repairs: these would add unrecorded sampling opportunities. A timeout or
connection failure has an error record but may have no raw response. Interrupted
runs retain already completed records. Dry runs produce records marked `dry-run`
and never contact providers. There is no resume mode; use a new run directory.

This collects recognition responses, not accuracy scores. Judge broader-but-valid
identifications using a separate rubric; exact string equality is insufficient.

## Offline verification

```sh
python -m unittest discover -s static-images/eval -p 'test_*.py' -v
```

Tests cover image discovery and metadata removal, provider payloads, response
validation, blinding, failed-image continuation, CSV/JSONL, and dry-run behavior.
They mock providers and do not use account quota.

Provider references: [Claude Code](https://code.claude.com/docs/en/headless),
[Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs),
[Codex non-interactive mode](https://developers.openai.com/codex/noninteractive),
[Ollama vision](https://docs.ollama.com/capabilities/vision),
[Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs).

## Comparison: command-line usage

`run_rq2.py` compares every Spytial query against every CLRS reference within the
same image variant. It reuses RQ1's image preparation, isolated Claude invocation,
authentication, raw-response parsing and logging utilities. RQ1 behavior and
configuration remain compatible. No additional dependencies are needed.

From the repository root in the `spytial` conda environment:

```sh
python static-images/eval/run_rq2.py --dry-run
python static-images/eval/run_rq2.py --backend claude-code --limit 1
python static-images/eval/run_rq2.py --backend claude-code
# Alternatively, with ANTHROPIC_API_KEY set in the environment:
python static-images/eval/run_rq2.py --backend claude-api
# Recompute matrices and retrieval from saved responses, without model calls:
python static-images/eval/run_rq2.py --analyze static-images/eval/results/RUN_DIRECTORY
```

A full run makes Q × R requests per variant (currently 14 × 15 = 210 original
pairs). `--limit` limits pairs, not queries, and is intended for smoke tests.
No live provider requests are made by dry runs or the offline tests. Direct API
runs use API billing; CLI runs use the existing Claude authentication. No retries,
answer repair, resume or concurrent calls are performed. Individual failures are
saved and the remaining pairs continue; any failed pair makes the exit code 1.
Each invocation requires a new output directory, just like RQ1.

### Prompt and configuration

`rq2-prompt-v1.txt` is the versioned rubric. It independently scores underlying
structure and meaningful diagrammatic organization on 0–100 scales. It excludes
literal value/label matches and superficial visual similarity while preserving
semantic roles such as ordering, containment, directed links, red/black categories
and augmentation fields. The response also includes shared cues, the important
mismatch, confidence and a justification of both scores. Numeric bounds and JSON
fields are validated locally, after preserving the raw response.

`rq2-config.json` sets models, prompt, seed, sampling settings, paths, variants,
ground truth and Top-k cutoffs. Config paths resolve relative to the config file;
CLI paths resolve relative to the working directory. Model defaults match RQ1.
The manifest records the exact prompt/schema, effective backend/model, both script
hashes, image hashes, environment versions and seeded pair order. CLI sampling
remains provider-controlled; recorded settings do not guarantee identical answers.

Only the ordered image contents (query first, reference second), rubric and system
instruction reach Claude. Paths, pair IDs, ground truth and previous judgments are
never supplied. Visible labels are still visible in originals: rubric instructions
alone cannot guarantee elimination of label leakage, so compare neutral variants
when available. The harness does not create masks or alter visible content.

### Discovery, ground truth and variants

Default naming is `<key>-spytial.png` and `<key>-clrs.png` in the same directory.
Supported formats and extensionless image discovery match RQ1. Directory plus key
provides the inferred ground-truth mapping; every query must have a valid match.
Extra CLRS references remain candidates even if they have no corresponding query.
Unrecognized names are listed in `skipped_files` in the manifest.

Variants use suffixes before the extension, for example:

```text
bst/bst-spytial-label-masked.png
bst/bst-clrs-label-masked.png
bst/bst-spytial-content-neutral.png
bst/bst-clrs-content-neutral.png
```

The config enables `original`, `label-masked`, and `content-neutral`; absent
variants are skipped. Both sides of an included variant must have images and each
query needs ground truth in that variant. Variants form separate experiments with
separate candidate pools; originals are never silently substituted. Additional
variant suffixes can be declared in `variants`. To evaluate only neutral images,
remove `original` from that list.

Override inferred matches with `ground_truth`, whose keys and values are exact
image paths relative to `images_dir`, including extensions. Multiple relevant
references are supported. For example, inside a custom config:

```json
"ground_truth": {
  "bst/bst-spytial.png": ["bst/bst-clrs.png"],
  "bst/bst-spytial-label-masked.png": ["bst/bst-clrs-label-masked.png"]
}
```

Unknown query paths, missing references, duplicate entries and cross-variant
mappings fail before any model calls. Config overrides affect retrieval only.
Candidate discovery still requires the naming convention above.

### Outputs and retrieval interpretation

Each run writes `manifest.json`, `pairs/pair-NNNNNN.json`, `raw/pair-NNNNNN.json`,
`results.json`, `results.jsonl`, and flattened `results.csv`. Arrays are JSON within
CSV cells. Aggregates are refreshed after every pair. `analysis.json` contains
labeled score matrices, every candidate ranking, first relevant ranks, coverage,
and Top-1, configured Top-k and MRR for each score and variant. The two scores are
not blended and confidence does not affect ranks. CSV matrices are also saved as
`matrix-VARIANT-SCORE.csv`, with queries as rows and references as columns.

A tie is scored conservatively: every tied non-relevant reference precedes the
first relevant reference. Display rankings use filename order for equal scores,
but metric ranks use this explicit pessimistic policy. With multiple relevant
references, retrieval measures the first relevant result. K larger than the
candidate count naturally covers every candidate.

Failed, unattempted and dry-run cells are null (blank in CSV), never zero. Metrics
exclude incomplete query rows: `metrics_complete_rows` reports that subset and
its coverage, while `metrics` remains null until all rows for that variant are
complete. Limited or interrupted runs must not be interpreted as full evaluations.
`--analyze` can regenerate analysis from an interrupted run's saved JSONL records.

Filename identity is an experimental retrieval target, not proof that other
references are semantically wrong. Related structures can legitimately score
high; inspect explanations and mismatches alongside retrieval metrics. Variant
comparisons are meaningful only when their query/reference coverage is comparable.
