#!/usr/bin/env python3
"""Blind image recognition via Claude Code, Claude API, Codex, or Ollama."""
import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

from PIL import Image, ImageOps, UnidentifiedImageError, __version__ as PILLOW_VERSION

HERE = Path(__file__).resolve().parent
BACKENDS = ("claude-code", "claude-api", "codex", "ollama")
SYSTEM_PROMPT = "Identify only the supplied diagram. Do not use tools or external context."
CLAUDE_ISOLATION_ENV = {
    "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
    "CLAUDE_CODE_DISABLE_CLAUDE_MDS": "1",
}
CODEX_ISOLATION_CONFIG = {
    "approval_policy": "never",
    "web_search": "disabled",
    "features.shell_tool": False,
    "features.memories": False,
    "memories.use_memories": False,
    "memories.generate_memories": False,
    "features.context_management": False,
    "features.skip_host_skill_discovery": True,
    "features.skill_search": False,
    "features.plugins": False,
    "features.hooks": False,
    "features.apps": False,
    "features.multi_agent": False,
    "project_doc_max_bytes": 0,
}
ISOLATION = {
    "unit": "one independent request/session per image",
    "system_prompt": SYSTEM_PROMPT,
    "claude_environment_overrides": CLAUDE_ISOLATION_ENV,
    "claude_settings": {"disableAllHooks": True},
    "codex_config_overrides": CODEX_ISOLATION_CONFIG,
    "history_forwarded": False,
}

SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "identification": {"type": "string"},
        "confidence": {"type": "number"},
        "visual_evidence": {"type": "array", "items": {"type": "string"}},
        "alternatives": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["identification", "confidence", "visual_evidence", "alternatives"],
}
# Keep the provider schema to the common supported subset; enforce bounds locally.



def resolve_executable(command):
    """Prefer PATH/explicit paths; also find the macOS desktop app's Codex CLI."""
    executable = shutil.which(os.path.expanduser(command))
    if executable or command != "codex":
        return executable
    if sys.platform == "darwin":
        for applications in (Path("/Applications"), Path.home() / "Applications"):
            for app_name in ("Codex.app", "ChatGPT.app"):
                candidate = applications / app_name / "Contents/Resources/codex"
                if candidate.is_file() and os.access(candidate, os.X_OK):
                    return str(candidate)
    return None

def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")
    temp.replace(path)


def validate(value):
    if not isinstance(value, dict) or set(value) != set(SCHEMA["required"]):
        raise ValueError("Response must have exactly the four required fields")
    if not isinstance(value["identification"], str) or not value["identification"].strip():
        raise ValueError("identification must be a nonempty string")
    confidence = value["confidence"]
    if (type(confidence) not in (int, float) or not math.isfinite(confidence)
            or not 0 <= confidence <= 100):
        raise ValueError("confidence must be a finite number from 0 to 100")
    for key, lower, upper in (("visual_evidence", 2, 4), ("alternatives", 0, 2)):
        items = value[key]
        if (not isinstance(items, list) or not lower <= len(items) <= upper
                or any(not isinstance(x, str) or not x.strip() for x in items)):
            raise ValueError(f"{key} must contain {lower} to {upper} nonempty strings")
    return value


def discover(root, excluded):
    """Sniff image content, including extensionless PNGs; fail on broken images."""
    found, skipped = [], []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(p == path or p in path.parents for p in excluded):
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        try:
            with Image.open(path) as img:
                if img.format not in {"PNG", "JPEG", "GIF", "WEBP"}:
                    skipped.append(str(path.relative_to(root)))
                    continue
                img.verify()
            found.append(path)
        except UnidentifiedImageError:
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".webp"}:
                raise ValueError(f"Unreadable image: {path}")
            skipped.append(str(path.relative_to(root)))
    return found, skipped


def prepare_image(path):
    """Re-encode the first frame as metadata-free RGB PNG, with white alpha."""
    with Image.open(path) as source:
        rgba = ImageOps.exif_transpose(source).convert("RGBA")
        clean = Image.new("RGB", rgba.size, "white")
        clean.paste(rgba, mask=rgba.getchannel("A"))
        output = io.BytesIO()
        clean.save(output, format="PNG")
        return output.getvalue()


def post_json(url, payload, timeout, headers=None):
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={
        "Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # Do not persist headers, credentials, or untrusted server error bodies.
        raise RuntimeError(f"HTTP {exc.code} from provider; check model, auth, and server") from None


def image_blocks(png):
    """Accept one PNG (RQ1) or an ordered sequence of PNGs (RQ2)."""
    images = [png] if isinstance(png, bytes) else png
    return [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
            "data": base64.b64encode(data).decode()}} for data in images]


def request_http(backend, settings, model, prompt, png, *, schema=SCHEMA,
                 system_prompt=SYSTEM_PROMPT):
    blocks = image_blocks(png)
    if backend == "ollama":
        payload = {"model": model, "stream": False, "format": schema,
                   "messages": [{"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt, "images": [b["source"]["data"] for b in blocks]}],
                   "options": {"temperature": settings["temperature"],
                               "seed": settings["seed"], "num_predict": settings["max_tokens"]}}
        raw = post_json(settings["ollama_url"].rstrip("/") + "/api/chat", payload,
                        settings["timeout_seconds"])
        def parse_ollama():
            if not raw.get("done") or raw.get("done_reason") == "length":
                raise ValueError("Incomplete Ollama response; check token limit")
            return json.loads(raw["message"]["content"])
        return raw, parse_ollama
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ValueError("claude-api requires ANTHROPIC_API_KEY in the environment")
    payload = {"model": model, "system": system_prompt, "max_tokens": settings["max_tokens"],
               "temperature": settings["temperature"],
               "messages": [{"role": "user", "content": blocks + [{"type": "text", "text": prompt}]}],
               "output_config": {"format": {"type": "json_schema", "schema": schema}}}
    raw = post_json("https://api.anthropic.com/v1/messages", payload,
                    settings["timeout_seconds"], {"x-api-key": key, "anthropic-version": "2023-06-01"})

    def parse():
        if raw.get("stop_reason") != "end_turn":
            raise ValueError(f"Incomplete/refused response: {raw.get('stop_reason')}")
        return json.loads("".join(x["text"] for x in raw["content"] if x["type"] == "text"))
    return raw, parse


def request_cli(backend, settings, model, prompt, png, *, schema=SCHEMA,
                system_prompt=SYSTEM_PROMPT):
    # A fresh neutral directory prevents loading this repository's instructions.
    with tempfile.TemporaryDirectory(prefix="recognition-") as directory:
        cwd = Path(directory)
        environment = os.environ.copy()
        # Keep authentication but never inherit the parent client's session identity.
        for key in list(environment):
            if key.startswith(("CODEX_THREAD_", "CODEX_SESSION_", "CLAUDE_CODE_SESSION_")):
                environment.pop(key)
        environment["PWD"] = str(cwd)
        environment.pop("OLDPWD", None)
        images = [png] if isinstance(png, bytes) else png
        image_paths = []
        for index, data in enumerate(images):
            image_path = cwd / ("image.png" if len(images) == 1 else f"image-{index + 1}.png")
            image_path.write_bytes(data)
            image_paths.append(image_path)
        if backend == "claude-code":
            environment.update(CLAUDE_ISOLATION_ENV)
            command = [settings["claude_command"], "-p", "--model", model,
                       "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
                       "--json-schema", json.dumps(schema), "--tools", "",
                       "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
                       "--setting-sources", "", "--disable-slash-commands",
                       "--no-session-persistence", "--system-prompt", system_prompt,
                       "--settings", json.dumps(ISOLATION["claude_settings"]), "--no-chrome"]
            stdin = json.dumps({"type": "user", "message": {"role": "user", "content": image_blocks(images) + [{"type": "text", "text": prompt}]}}) + "\n"
        else:
            write_json(cwd / "schema.json", schema)
            (cwd / "instructions.txt").write_text(system_prompt)
            command = [settings["codex_command"], "exec", "--model", model,
                       "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
                       "--sandbox", "read-only", "--json", "--color", "never",
                       "-c", 'model_instructions_file="' + str(cwd / "instructions.txt") + '"',
                       *[arg for path in image_paths for arg in ("--image", str(path))], "--output-schema", str(cwd / "schema.json"),
                       "--output-last-message", str(cwd / "answer.json"), "-"]
            # CLI -c values use TOML; JSON scalars have the same syntax here.
            overrides = []
            for key, value in CODEX_ISOLATION_CONFIG.items():
                overrides.extend(["-c", f"{key}={json.dumps(value)}"])
            command[-1:-1] = overrides
            stdin = prompt
        result = subprocess.run(command, input=stdin, text=True, capture_output=True,
                                cwd=cwd, env=environment, timeout=settings["timeout_seconds"])
        raw = {"returncode": result.returncode, "stdout": result.stdout, "stderr": result.stderr}
        if backend == "codex" and (cwd / "answer.json").exists():
            raw["answer"] = (cwd / "answer.json").read_text()

    def parse():
        if raw["returncode"]:
            raise RuntimeError(f"{backend} exited with {raw['returncode']}; see raw response")
        if backend == "claude-code":
            events = [json.loads(line) for line in raw["stdout"].splitlines() if line.strip()]
            for event in events:
                if event.get("type") == "assistant":
                    for block in event.get("message", {}).get("content", []):
                        if block.get("type") == "tool_use" and block.get("name") != "StructuredOutput":
                            raise ValueError("Claude Code used a tool; result excluded from blind evaluation")
            results = [event for event in events if event.get("type") == "result"]
            if not results:
                raise ValueError("Claude Code omitted its result event; see raw response")
            response = results[-1]
            if response.get("is_error"):
                raise ValueError("Claude Code returned an error; see raw response")
            if "structured_output" not in response:
                raise ValueError("Claude Code omitted structured_output; check CLI version")
            return response["structured_output"]
        events = [json.loads(line) for line in raw["stdout"].splitlines() if line.strip()]
        allowed_items = {"agent_message", "reasoning"}
        for event in events:
            if event.get("type") in {"error", "turn.failed"}:
                raise ValueError("Codex reported a failed turn; see raw response")
            item = event.get("item")
            if item and item.get("type") not in allowed_items:
                raise ValueError("Codex used a tool; result excluded from blind evaluation")
        return json.loads(raw["answer"])
    return raw, parse


def aggregate(output, records):
    with (output / "results.jsonl").open("w") as file:
        for row in records:
            file.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
    fields = ["image_id", "source", "backend", "model", "status", *SCHEMA["required"], "error"]
    with (output / "results.csv").open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {k: record.get(k, "") for k in fields}
            row.update(record.get("result") or {})
            for key in ("visual_evidence", "alternatives"):
                row[key] = json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], list) else ""
            writer.writerow(row)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "config.json")
    parser.add_argument("--backend", choices=BACKENDS)
    parser.add_argument("--model")
    parser.add_argument("--images-dir", type=Path)
    parser.add_argument("--output-dir", type=Path, help="New run directory; must not exist")
    parser.add_argument("--limit", type=int, help="Evaluate only this many images")
    parser.add_argument("--dry-run", action="store_true", help="Prepare manifest without provider calls")
    args = parser.parse_args(argv)
    config_path = args.config.resolve()
    settings = json.loads(config_path.read_text())
    backend = args.backend or settings["backend"]
    if backend not in BACKENDS:
        parser.error("Unknown backend in config")
    model = args.model or settings["models"][backend]
    if not isinstance(model, str) or not model.strip():
        parser.error("Set a nonempty model in config or with --model")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive")
    for key in ("timeout_seconds", "max_tokens"):
        if type(settings[key]) not in (int, float) or settings[key] <= 0:
            parser.error(f"{key} must be positive")
    base = config_path.parent
    root = (args.images_dir or base / settings["images_dir"]).resolve()
    if not root.is_dir():
        parser.error(f"Images directory does not exist: {root}")
    prompt = (base / settings["prompt_file"]).read_text()
    if not prompt.strip():
        parser.error("Prompt must not be empty")
    output_base = (base / settings["output_dir"]).resolve()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output = (args.output_dir or output_base / f"{timestamp}-{backend}").resolve()
    images, skipped = discover(root, [HERE, output_base, output])
    random.Random(settings["seed"]).shuffle(images)
    if args.limit:
        images = images[:args.limit]
    if not images:
        parser.error("No supported images found")
    executable_version = None
    if not args.dry_run and backend in {"claude-code", "codex"}:
        key = "claude_command" if backend == "claude-code" else "codex_command"
        executable = resolve_executable(settings[key])
        if not executable:
            parser.error(f"Executable not found: {settings[key]}. "
                         f"Set {key} to the executable’s full path in {config_path}")
        settings[key] = executable
        executable_version = subprocess.run([executable, "--version"], text=True,
                                            capture_output=True, timeout=15).stdout.strip()
    if not args.dry_run and backend == "claude-api" and not os.environ.get("ANTHROPIC_API_KEY"):
        parser.error("Set ANTHROPIC_API_KEY for the claude-api backend")
    output.mkdir(parents=True, exist_ok=False)
    (output / "images").mkdir()
    (output / "raw").mkdir()
    manifest = {"created_at": timestamp, "backend": backend, "model": model,
                "config": settings, "prompt": prompt, "prompt_sha256": digest(prompt.encode()),
                "schema": SCHEMA, "script_sha256": digest(Path(__file__).read_bytes()),
                "python": sys.version, "pillow": PILLOW_VERSION, "cli_version": executable_version,
                "dry_run": args.dry_run, "isolation": ISOLATION, "skipped_files": skipped, "images": []}
    records = []
    write_json(output / "manifest.json", manifest)
    for index, path in enumerate(images, 1):
        record = {"image_id": f"image-{index:04d}", "source": str(path.relative_to(root)),
                  "source_sha256": digest(path.read_bytes()), "backend": backend, "model": model,
                  "status": "error", "result": None, "error": None}
        start = time.monotonic()
        try:
            png = prepare_image(path)
            record["sent_sha256"] = digest(png)
            if args.dry_run:
                record["status"] = "dry-run"
            else:
                request = request_cli if backend in {"claude-code", "codex"} else request_http
                raw, parse = request(backend, settings, model, prompt, png)
                write_json(output / "raw" / (record["image_id"] + ".json"), raw)
                record["result"] = validate(parse())
                record["status"] = "ok"
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
            # TimeoutExpired includes the command (and schema); keep only a short diagnostic.
            record["error"] = (f"Timed out after {settings['timeout_seconds']} seconds"
                               if isinstance(exc, subprocess.TimeoutExpired) else str(exc))
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        records.append(record)
        write_json(output / "images" / (record["image_id"] + ".json"), record)
        manifest["images"].append({k: record[k] for k in
                                   ("image_id", "source", "source_sha256", "status")})
        write_json(output / "manifest.json", manifest)
        aggregate(output, records)
        print(f"[{index}/{len(images)}] {record['source']}: {record['status']}", flush=True)
    print(f"Results: {output}")
    return int(any(row["status"] == "error" for row in records))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as error:
        sys.exit(str(error))
