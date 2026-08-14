#!/usr/bin/env python3
"""Tests for the standalone GPT-2 vocabulary conformance checker."""

from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from check_gpt2_vocabulary import (
    ConformanceError,
    Gpt2AsciiReference,
    VocabularyAssets,
    bytes_to_unicode,
    load_merges_file,
    load_vectors,
    run,
    validate_assets,
    validate_vectors,
)


def byte_vocabulary() -> dict[str, int]:
    """Create a complete base-byte vocabulary in canonical GPT-2 order."""

    return {token: index for index, token in enumerate(bytes_to_unicode().values())}


class VocabularyConformanceTest(unittest.TestCase):
    """Verifies asset validation, BPE behavior, and the public tool report."""

    def test_accepts_complete_byte_vocabulary_and_merge(self) -> None:
        vocabulary = byte_vocabulary()
        encoder = bytes_to_unicode()
        merged = encoder[ord("a")] + encoder[ord("b")]
        vocabulary[merged] = len(vocabulary)
        assets = VocabularyAssets(
            vocabulary, ((encoder[ord("a")], encoder[ord("b")]),), ()
        )

        counts = validate_assets(assets)
        reference = Gpt2AsciiReference(vocabulary, assets.merges)

        self.assertEqual(counts["byte_symbols"], 256)
        self.assertEqual(reference.encode("ab"), [vocabulary[merged]])
        self.assertEqual(reference.decode([vocabulary[merged]]), "ab")

    def test_rejects_merge_result_missing_from_vocabulary(self) -> None:
        vocabulary = byte_vocabulary()
        encoder = bytes_to_unicode()
        assets = VocabularyAssets(
            vocabulary, ((encoder[ord("a")], encoder[ord("b")]),), ()
        )

        with self.assertRaisesRegex(ConformanceError, "result token"):
            validate_assets(assets)

    def test_rejects_incorrect_golden_vector(self) -> None:
        vocabulary = byte_vocabulary()
        reference = Gpt2AsciiReference(vocabulary, ())

        with self.assertRaisesRegex(ConformanceError, "encoding mismatch"):
            validate_vectors(reference, [("a", [999])])

    def test_preserves_merge_records_whose_left_token_is_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "merges.txt"
            path.write_text("#version: 0.2\n# token\n", encoding="utf-8")

            merges = load_merges_file(path)

        self.assertEqual(merges, (("#", "token"),))

    def test_loads_vectors_and_builds_complete_report(self) -> None:
        vocabulary = byte_vocabulary()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vocab_path = root / "vocab.json"
            merges_path = root / "merges.txt"
            vectors_path = root / "vectors.json"
            vocab_path.write_text(json.dumps(vocabulary), encoding="utf-8")
            merges_path.write_text("#version: 0.2\n", encoding="utf-8")
            vectors_path.write_text(
                json.dumps({"vectors": [{"text": "a", "token_ids": [64]}]}),
                encoding="utf-8",
            )

            vectors = load_vectors(vectors_path)
            report = run(
                argparse.Namespace(
                    tokenizer_json=None,
                    vocab_json=vocab_path,
                    merges=merges_path,
                    vectors=vectors_path,
                    report=None,
                    expected_vocabulary_size=256,
                    expected_merge_count=0,
                )
            )

        self.assertEqual(vectors, [("a", [64])])
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["checks"]["golden_vectors"], 1)
        self.assertEqual(report["checks"]["ascii_round_trips"], 136)


if __name__ == "__main__":
    unittest.main()
