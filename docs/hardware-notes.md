# Hardware Notes

The initial components are readable bounded references. They expose the correct
algorithm and storage boundaries, but do not claim a minimum-area or
maximum-throughput GPT-2 implementation.

## Cost centers

- Pair selection scans every adjacent symbol for each merge iteration.
- Every pair scan performs a merge-table lookup.
- Shifting merged symbols is linear in the piece length.
- Full GPT-2 vocabulary and merge data dominate storage, not the 64-symbol
  working buffers.

## Integration guidance

- Keep tokenizer tables in ROM or shared external memory rather than registers.
- Prefer indexed lookup over a 50,000-way conditional dispatcher.
- Reuse the language-model memory interface when bandwidth and arbitration are
  acceptable.
- Keep input buffering, BPE processing, model inference, and output decoding
  as separate components with observable completion boundaries.
- Measure tokenizer latency separately from model time-to-first-token. For a
  small transformer, model inference is expected to dominate.

An optimized implementation may replace `BpeMergeEngine64` with a specialized
component while continuing to implement `IBpeMergeTable` and preserving the
tokenizer's visible behavior.
