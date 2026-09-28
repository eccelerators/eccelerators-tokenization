# Bounded Unigram and Metaspace

The additive API in 0.2.0-dev leaves GPT-2/BPE public interfaces and behavior
unchanged. It supports exact-cost Unigram over valid UTF-8 segments, printable
ASCII normalization through an injected one-byte mapping provider, and UTF-8
Metaspace decoding. It does not implement unrestricted Unicode normalization,
byte fallback, sampling, or added-token recognition. Model admission policy and
special-token insertion remain in the application.

`IUnigramVocabulary` supplies a byte trie, additive nonnegative costs, unknown ID
and cost, UTF-8 piece bytes and flags. No model assets or DDR addresses belong to
the library. `Next` returns -1 for no edge; providers expose sticky I/O/table errors
through `Failed`. Trie node 0 is the root. Bits 0/1 of token flags mark special
and unassigned entries; both are skipped by the decoder. Invalid IDs must return
negative flags, not impersonate unassigned slots.

`UnigramSegmenter<MAX_BYTES, MAX_TOKENS, VOCAB>` consumes one UTF-8 segment at a
time. Reset clears the complete request; BeginSegment clears just the segment.
Accept appends bytes and EncodeSegment appends selected token IDs. Pre-tokenizer
boundaries must be respected. The engine minimizes exact integer costs, preserving
the first path on ties by scanning starts and trie prefix lengths in ascending
order and updating only on strict improvement. Unknown fallback is inserted only
when no single-codepoint vocabulary piece exists; consecutive unknowns fuse within
a segment. All output is invalidated on any failure; Reset is required to recover.

Costs must be <= 2^40 and segment lengths <= 4096, so an accumulated path is <=
2^52. Four 16-bit limbs implement exact addition without relying on Livt's 32-bit
int arithmetic. Providers must choose a common exact scale; approximate score
conversion is not implicit in this API. UTF-8 validation rejects overlong forms,
surrogates, invalid continuation bytes and values beyond U+10FFFF. Output token
capacity is independent of input byte capacity and cannot exceed 4096.

`AsciiMetaspace<MAX_INPUT, MAX_BYTES, MAP>` maps printable ASCII through
`IAsciiNormalization`, collapses runs of spaces, adds an initial U+2581 when
necessary, and replaces spaces with UTF-8 U+2581. It preserves a single leading
or trailing space. MAX_BYTES must accommodate 3*MAX_INPUT+3. This is an explicit
normalization subset, not a replacement for arbitrary SentencePiece charsmap
processing. A model adapter must prove its one-byte domain mapping is valid.

`MetaspaceDecoder<MAX_OUTPUT, MAX_PIECE, VOCAB>` skips flagged entries, removes
U+2581 from the first non-skipped piece and replaces it with ASCII space in later
pieces. It preserves other UTF-8 bytes and performs no cleanup. Providers must
supply valid UTF-8 strings. Errors invalidate the complete output, preventing
partial UTF-8 exposure. Reset is required before the first append and every new
sequence. Bounds are checked statically and dynamically.

All calls are serialized; callers own providers for the operation duration. Local
arrays are bounded correctness storage, not a claim of FPGA BRAM inference or
resource closure. Replacing storage with explicit RAM and measuring synthesis
remain integration work where required.

The tests cover two bound configurations and array/branch providers, Viterbi ties,
unknown fusion, UTF-8, rejection, limits, reset/reuse and normalization. The FLAN-T5
project adds real-image RTL parity and TinyStories integration regressions.

Two existing GPT-2 test array initializers use identical literal bytes instead of
named byte constants to avoid a compiler VHDL aggregate error. Inputs, assertions
and expected IDs are unchanged; production BPE/GPT-2 files are unchanged.
