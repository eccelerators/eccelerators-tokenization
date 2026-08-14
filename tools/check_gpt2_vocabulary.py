#!/usr/bin/env python3
"""Validate GPT-2-style byte-level BPE assets and optional golden vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence


ASCII_PRETOKEN_PATTERN = re.compile(
    r"'s|'t|'re|'ve|'m|'ll|'d| ?[A-Za-z]+| ?[0-9]+| ?[^\sA-Za-z0-9]+|\s+(?!\S)|\s+",
    re.IGNORECASE,
)

DEFAULT_SMOKE_TEXTS = (
    "",
    "a",
    "Hello world",
    " Hello world",
    "Hello, world!",
    "  repeated spaces",
    "12345!?",
    "tabs\tand\nlines",
)


class ConformanceError(RuntimeError):
    """Reports an invalid asset or a failed conformance check."""


@dataclass(frozen=True)
class VocabularyAssets:
    """Normalized vocabulary and ranked merge data loaded from disk."""

    vocabulary: dict[str, int]
    merges: tuple[tuple[str, str], ...]
    source_paths: tuple[Path, ...]


def bytes_to_unicode() -> dict[int, str]:
    """Return the reversible byte mapping used by the GPT-2 tokenizer."""

    byte_values = list(range(ord("!"), ord("~") + 1))
    byte_values += list(range(ord("¡"), ord("¬") + 1))
    byte_values += list(range(ord("®"), ord("ÿ") + 1))
    unicode_values = byte_values.copy()
    extra = 0
    for value in range(256):
        if value not in byte_values:
            byte_values.append(value)
            unicode_values.append(256 + extra)
            extra += 1
    return dict(zip(byte_values, (chr(value) for value in unicode_values), strict=True))


def file_sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest of one input file."""

    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_json_object(path: Path) -> dict[str, Any]:
    """Load one JSON object with a path-aware error."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConformanceError(f"Cannot read JSON object {path}: {error}") from error
    if not isinstance(value, dict):
        raise ConformanceError(f"Expected a JSON object in {path}")
    return value


def normalize_vocabulary(value: Any, source: Path) -> dict[str, int]:
    """Validate and normalize a token-to-ID JSON mapping."""

    if not isinstance(value, dict) or not value:
        raise ConformanceError(f"Expected a non-empty vocabulary object in {source}")

    vocabulary: dict[str, int] = {}
    ids: dict[int, str] = {}
    for token, token_id in value.items():
        if not isinstance(token, str) or not token:
            raise ConformanceError(f"Vocabulary token names must be non-empty strings in {source}")
        if isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0:
            raise ConformanceError(f"Token {token!r} has invalid ID {token_id!r} in {source}")
        if token_id in ids:
            raise ConformanceError(
                f"Tokens {ids[token_id]!r} and {token!r} share ID {token_id} in {source}"
            )
        vocabulary[token] = token_id
        ids[token_id] = token

    expected_ids = set(range(len(vocabulary)))
    actual_ids = set(ids)
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        unexpected = sorted(actual_ids - expected_ids)
        raise ConformanceError(
            "Vocabulary IDs must form the contiguous range "
            f"0..{len(vocabulary) - 1}; missing={missing[:8]}, unexpected={unexpected[:8]}"
        )
    return vocabulary


def normalize_merges(value: Any, source: Path) -> tuple[tuple[str, str], ...]:
    """Normalize merge records from a tokenizer JSON array."""

    if not isinstance(value, list):
        raise ConformanceError(f"Expected a merge array in {source}")

    merges: list[tuple[str, str]] = []
    for rank, record in enumerate(value):
        if isinstance(record, str):
            parts = record.split()
        elif isinstance(record, list) and all(isinstance(part, str) for part in record):
            parts = record
        else:
            raise ConformanceError(f"Merge rank {rank} has unsupported shape in {source}")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ConformanceError(f"Merge rank {rank} is not one token pair in {source}")
        merges.append((parts[0], parts[1]))
    return tuple(merges)


def load_merges_file(path: Path) -> tuple[tuple[str, str], ...]:
    """Load the conventional GPT-2 merges.txt representation."""

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as error:
        raise ConformanceError(f"Cannot read merge table {path}: {error}") from error

    records: list[str] = []
    for line_number, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not (line_number == 0 and stripped.startswith("#version:")):
            records.append(stripped)
    return normalize_merges(records, path)


def load_assets(
    tokenizer_json: Path | None,
    vocab_json: Path | None,
    merges_path: Path | None,
) -> VocabularyAssets:
    """Load either Hugging Face tokenizer JSON or standalone GPT-2 files."""

    source_paths: list[Path] = []
    embedded_merges: Any = None
    if tokenizer_json is not None:
        document = load_json_object(tokenizer_json)
        model = document.get("model")
        if not isinstance(model, dict) or model.get("type") != "BPE":
            raise ConformanceError(f"Expected model.type == 'BPE' in {tokenizer_json}")
        vocabulary = normalize_vocabulary(model.get("vocab"), tokenizer_json)
        embedded_merges = model.get("merges")
        source_paths.append(tokenizer_json)
    elif vocab_json is not None:
        vocabulary = normalize_vocabulary(load_json_object(vocab_json), vocab_json)
        source_paths.append(vocab_json)
    else:
        raise ConformanceError("Specify --tokenizer-json or --vocab-json")

    if merges_path is not None:
        merges = load_merges_file(merges_path)
        source_paths.append(merges_path)
    elif embedded_merges is not None:
        if tokenizer_json is None:
            raise ConformanceError("Internal error: embedded merges without tokenizer JSON")
        merges = normalize_merges(embedded_merges, tokenizer_json)
    else:
        raise ConformanceError("No merge table found; specify --merges")

    return VocabularyAssets(vocabulary, merges, tuple(source_paths))


class Gpt2AsciiReference:
    """Dependency-free GPT-2 byte-level BPE reference for ASCII conformance."""

    def __init__(self, vocabulary: dict[str, int], merges: Sequence[tuple[str, str]]) -> None:
        self.vocabulary = vocabulary
        self.tokens = {token_id: token for token, token_id in vocabulary.items()}
        self.merge_ranks = {pair: rank for rank, pair in enumerate(merges)}
        self.byte_encoder = bytes_to_unicode()
        self.byte_decoder = {encoded: value for value, encoded in self.byte_encoder.items()}

    @lru_cache(maxsize=8192)
    def bpe(self, encoded_piece: str) -> tuple[str, ...]:
        """Apply ranked merges to one byte-encoded pre-tokenized piece."""

        word = tuple(encoded_piece)
        if len(word) < 2:
            return word
        while True:
            pairs = {(word[index], word[index + 1]) for index in range(len(word) - 1)}
            best = min(pairs, key=lambda pair: self.merge_ranks.get(pair, 1 << 62))
            if best not in self.merge_ranks:
                break
            merged: list[str] = []
            index = 0
            while index < len(word):
                if index + 1 < len(word) and word[index : index + 2] == best:
                    merged.append(word[index] + word[index + 1])
                    index += 2
                else:
                    merged.append(word[index])
                    index += 1
            word = tuple(merged)
            if len(word) == 1:
                break
        return word

    def encode(self, text: str) -> list[int]:
        """Encode one ASCII string with GPT-2 pre-tokenization and ranked BPE."""

        try:
            raw = text.encode("ascii")
        except UnicodeEncodeError as error:
            raise ConformanceError(
                f"Conformance vectors must contain ASCII text: {text!r}"
            ) from error
        if not raw:
            return []

        result: list[int] = []
        for piece in ASCII_PRETOKEN_PATTERN.findall(text):
            encoded = "".join(self.byte_encoder[value] for value in piece.encode("ascii"))
            for token in self.bpe(encoded):
                if token not in self.vocabulary:
                    raise ConformanceError(f"BPE produced token absent from vocabulary: {token!r}")
                result.append(self.vocabulary[token])
        return result

    def decode(self, token_ids: Sequence[int]) -> str:
        """Decode token IDs to ASCII and reject unsupported output bytes."""

        decoded = bytearray()
        for token_id in token_ids:
            token = self.tokens.get(token_id)
            if token is None:
                raise ConformanceError(f"Token ID {token_id} is outside the vocabulary")
            for character in token:
                value = self.byte_decoder.get(character)
                if value is None:
                    raise ConformanceError(
                        f"Token ID {token_id} contains non-GPT-2 byte symbol {character!r}"
                    )
                decoded.append(value)
        try:
            return decoded.decode("ascii")
        except UnicodeDecodeError as error:
            raise ConformanceError(
                f"Decoded token sequence contains non-ASCII byte 0x{decoded[error.start]:02x}"
            ) from error


def validate_assets(assets: VocabularyAssets) -> dict[str, int]:
    """Validate byte coverage, merge integrity, and deterministic ranks."""

    vocabulary = assets.vocabulary
    byte_encoder = bytes_to_unicode()
    missing_bytes = [value for value, token in byte_encoder.items() if token not in vocabulary]
    if missing_bytes:
        raise ConformanceError(f"Vocabulary lacks GPT-2 symbols for bytes: {missing_bytes[:16]}")

    seen_pairs: dict[tuple[str, str], int] = {}
    for rank, pair in enumerate(assets.merges):
        if pair in seen_pairs:
            raise ConformanceError(
                f"Duplicate merge pair {pair!r} at ranks {seen_pairs[pair]} and {rank}"
            )
        seen_pairs[pair] = rank
        left, right = pair
        result = left + right
        for role, token in (("left", left), ("right", right), ("result", result)):
            if token not in vocabulary:
                raise ConformanceError(
                    f"Merge rank {rank} {role} token {token!r} is absent from the vocabulary"
                )

    return {
        "byte_symbols": len(byte_encoder),
        "merge_records": len(assets.merges),
        "vocabulary_tokens": len(vocabulary),
    }


def load_vectors(path: Path) -> list[tuple[str, list[int]]]:
    """Load golden vectors from a list or an object containing `vectors`."""

    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ConformanceError(f"Cannot read conformance vectors {path}: {error}") from error
    if isinstance(document, dict):
        document = document.get("vectors")
    if not isinstance(document, list):
        raise ConformanceError(f"Expected a vector list in {path}")

    vectors: list[tuple[str, list[int]]] = []
    for index, record in enumerate(document):
        if not isinstance(record, dict):
            raise ConformanceError(f"Vector {index} must be an object in {path}")
        text = record.get("text")
        token_ids = record.get("token_ids")
        if not isinstance(text, str) or not isinstance(token_ids, list):
            raise ConformanceError(f"Vector {index} requires text and token_ids in {path}")
        if any(isinstance(value, bool) or not isinstance(value, int) for value in token_ids):
            raise ConformanceError(f"Vector {index} contains a non-integer token ID in {path}")
        vectors.append((text, token_ids))
    return vectors


def validate_round_trips(reference: Gpt2AsciiReference) -> int:
    """Run built-in text and complete single-byte ASCII round trips."""

    checked = 0
    for text in DEFAULT_SMOKE_TEXTS:
        token_ids = reference.encode(text)
        if reference.decode(token_ids) != text:
            raise ConformanceError(f"Built-in ASCII round trip failed for {text!r}")
        checked += 1
    for value in range(128):
        text = chr(value)
        token_ids = reference.encode(text)
        if reference.decode(token_ids) != text:
            raise ConformanceError(f"Single-byte ASCII round trip failed for 0x{value:02x}")
        checked += 1
    return checked


def validate_vectors(
    reference: Gpt2AsciiReference,
    vectors: Sequence[tuple[str, list[int]]],
) -> int:
    """Compare encoding and decoding with caller-provided golden vectors."""

    for index, (text, expected) in enumerate(vectors):
        actual = reference.encode(text)
        if actual != expected:
            raise ConformanceError(
                f"Vector {index} encoding mismatch for {text!r}: expected {expected}, got {actual}"
            )
        decoded = reference.decode(expected)
        if decoded != text:
            raise ConformanceError(
                f"Vector {index} decoding mismatch: expected {text!r}, got {decoded!r}"
            )
    return len(vectors)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(
        description="Validate GPT-2-style byte-level BPE vocabulary and merge assets."
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tokenizer-json", type=Path, help="Hugging Face tokenizer.json")
    source.add_argument("--vocab-json", type=Path, help="Standalone GPT-2 vocab.json")
    parser.add_argument(
        "--merges", type=Path, help="merges.txt; optional when tokenizer.json embeds model.merges"
    )
    parser.add_argument("--vectors", type=Path, help="Optional JSON golden-vector file")
    parser.add_argument("--report", type=Path, help="Optional JSON result path")
    parser.add_argument("--expected-vocabulary-size", type=int)
    parser.add_argument("--expected-merge-count", type=int)
    return parser


def run(arguments: argparse.Namespace) -> dict[str, Any]:
    """Execute all conformance checks and return the report object."""

    assets = load_assets(arguments.tokenizer_json, arguments.vocab_json, arguments.merges)
    counts = validate_assets(assets)
    if (
        arguments.expected_vocabulary_size is not None
        and counts["vocabulary_tokens"] != arguments.expected_vocabulary_size
    ):
        raise ConformanceError(
            "Expected vocabulary size "
            f"{arguments.expected_vocabulary_size}, got {counts['vocabulary_tokens']}"
        )
    if (
        arguments.expected_merge_count is not None
        and counts["merge_records"] != arguments.expected_merge_count
    ):
        raise ConformanceError(
            f"Expected merge count {arguments.expected_merge_count}, got {counts['merge_records']}"
        )

    reference = Gpt2AsciiReference(assets.vocabulary, assets.merges)
    smoke_count = validate_round_trips(reference)
    vectors = load_vectors(arguments.vectors) if arguments.vectors is not None else []
    vector_count = validate_vectors(reference, vectors)

    return {
        "checks": {
            **counts,
            "ascii_round_trips": smoke_count,
            "golden_vectors": vector_count,
        },
        "inputs": [
            {"path": str(path), "sha256": file_sha256(path)} for path in assets.source_paths
        ],
        "status": "passed",
    }


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return a process exit status."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        report = run(arguments)
        if arguments.report is not None:
            arguments.report.parent.mkdir(parents=True, exist_ok=True)
            arguments.report.write_text(
                json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    except ConformanceError as error:
        print(f"conformance failed: {error}", file=sys.stderr)
        return 1

    checks = report["checks"]
    print(
        "conformance passed: "
        f"vocabulary={checks['vocabulary_tokens']} "
        f"merges={checks['merge_records']} "
        f"ascii_round_trips={checks['ascii_round_trips']} "
        f"golden_vectors={checks['golden_vectors']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
