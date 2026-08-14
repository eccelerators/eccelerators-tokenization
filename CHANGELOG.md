# Changelog

All notable changes to `Eccelerators.Tokenization` are recorded here.

## [0.1.0] - 2026-08-14

- Add a storage-independent, bounded 64-symbol ranked BPE merge engine.
- Add GPT-2-compatible bounded ASCII pre-tokenization and byte-level BPE
  composition.
- Add bounded GPT-2 token-to-byte decoding suitable for byte-stream output.
- Define injectable merge-table and vocabulary contracts for ROM, RAM, or
  external-memory implementations.
- Add deterministic merge, GPT-2 conformance, boundary, decoding, and error
  tests.
- Add a dependency-free vocabulary, merge-table, and golden-vector conformance
  checker for standard and custom GPT-2-style byte-level BPE models.
- Document package architecture, storage ownership, integration, and hardware
  tradeoffs.
