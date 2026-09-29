# Changelog

All notable changes to `Eccelerators.Tokenization` are recorded here.

## Unreleased

- Add generic scheduled `IStorage<T>` and array-backed default storage.
- Add injected-storage normalization and Metaspace decoding while preserving
  their original APIs; cover delayed/poisoned storage and capacity/reset reuse.

- Add generic injected Unigram working storage, retaining the existing API as a
  local-array composition of the same algorithm.
- Allow uninitialized/reset-retained RAM, bound backtracking by output capacity,
  and test delayed storage, read-before-write safety and insufficient capacity.
- Preserve signed predecessor sentinels and high-bit cost ordering with explicit
  vector-width conversions on the current compiler.
- Apply the Livt design guide to storage/Unigram contracts and affected tests;
  clarify ownership, address units, transaction completion and reset semantics.

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

## 0.2.0-dev

- Add generic exact-cost Unigram segmentation and vocabulary providers.
- Add bounded ASCII normalization/Metaspace processing and UTF-8 decoding.
- Add two-configuration regressions; retain existing GPT-2/BPE behavior.
- Use equivalent literal bytes in two existing test arrays for compiler compatibility.
