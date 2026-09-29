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
time. Reset invalidates the complete request; BeginSegment invalidates just the current segment.
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

The GPT-2 fixtures use named byte constants for readable input arrays. Their
inputs, assertions and expected IDs retain the established cases; production
BPE/GPT-2 files are unchanged. The full suite checks this compatibility alongside
the storage-backed Unigram cases.

## Injected working storage

`StoredUnigramSegmenter<MAX_BYTES, MAX_TOKENS, VOCAB, STORAGE>` takes
`(vocab, storage)` and preserves the segmentation API and algorithm. Its provider
implements `IUnigramStorage`: `Read`/`Write` transact exact 64-bit words and
`IsValidAddress` validates a contiguous address range. Required capacity is
`5*MAX_BYTES + 3 + 2*MAX_TOKENS` words. Insufficient capacity fails admission.
Only the segmenter may own this workspace during a request.

Cells may start uninitialized and survive reset. The engine initializes each
reachable cell before reading it; reset invalidates lengths/counts rather than
clearing payload memory. Hardware reset must cancel in-flight provider and
segmenter operations together. Backtracking uses at most MAX_TOKENS words and
rejects excess output before writing beyond that bound, including accumulated
output across segments. Unknown fusion and strict tie ordering are unchanged.

The original `UnigramSegmenter` API remains available as a composition of the
same core with dependency-free `ArrayUnigramStorage`. Larger FPGA designs can
adapt existing RAM APIs to `IUnigramStorage`; no Livt.IO dependency is imposed on
this library. FLAN-T5 injects `BlockRam<logic[64], 3920>` through its application
adapter. Physical RAM mapping and whole-design closure must still be measured.

`StoredUnigramTest` adds a delayed provider which rejects reads before writes,
poisons storage between requests, exercises exact high-bit cost ordering and
full-capacity reuse, and rejects a provider one word too short. Explicit vector
intermediates preserve signed 32-bit sentinels and high cost limbs on the current
compiler (tracked compiler issues 578 and 576).

## Normalization and decoded-byte storage

`StoredAsciiMetaspace<MAX_INPUT, MAX_BYTES, MAP, STORAGE>` and
`StoredMetaspaceDecoder<MAX_OUTPUT, MAX_PIECE, VOCAB, STORAGE>` accept their
existing map/vocabulary followed by an injected storage provider. `STORAGE`
implements `Eccelerators.Tokenization.Storage.IStorage<byte>`, a generic,
scheduled `Read`/`Write`/`IsValidAddress` contract. The valid range is contiguous
from zero; each consumer checks its required capacity before writing. Providers
are exclusive to their consumer, may have delayed transactions, and need not
initialize or clear payload cells. Reset must cancel provider and consumer
operations together. Metadata prevents access to stale/unwritten bytes.

`AsciiMetaspace` and `MetaspaceDecoder` retain their original type parameters,
constructors and methods through `ArrayStorage<byte, CAPACITY>` compatibility
adapters. The library still has no Livt.IO dependency. FLAN-T5 supplies byte-wide
`BlockRam` adapters for its input, normalized-text and decoded-text buffers.
`StoredByteBuffersTest` checks delayed/poisoned storage, UTF-8 bytes, normalization,
capacity errors, undersized providers and reset/reuse. Actual RAM inference and
latency are hardware-integration measurements, not guarantees of the interface.

## Consumer and provider responsibilities

| Consumer | Borrowed dependencies | Owned by its compatibility wrapper | Minimum storage |
| --- | --- | --- | --- |
| `StoredAsciiMetaspace` | Normalization map and exclusive `IStorage<byte>` | `AsciiMetaspace` owns `ArrayStorage` and the core | `MAX_BYTES` byte elements |
| `StoredMetaspaceDecoder` | Vocabulary and exclusive `IStorage<byte>` | `MetaspaceDecoder` owns `ArrayStorage` and the core | `MAX_OUTPUT` byte elements |
| `StoredUnigramSegmenter` | Vocabulary and exclusive `IUnigramStorage` | `UnigramSegmenter` owns `ArrayUnigramStorage` and the core | `5*MAX_BYTES+3+2*MAX_TOKENS` 64-bit words |

Addresses are zero-based **element indices**, not physical byte addresses:
`IStorage<byte>` uses byte elements, while `IUnigramStorage` uses 64-bit words.
If the last required address is valid, every address below it must also be valid.
Consumers check capacity before payload access. `IsValidAddress` is a query, not
a reservation or arbitration primitive; only one consumer may use a workspace.

A scheduled `Read` or `Write` may span many cycles. Return from `Write` means
completion, so a subsequent serialized `Read` sees the written bits. Vocabulary,
normalization and storage providers must remain bound for the consumer lifetime.
No component creates platform RAM, applies DDR addresses, or selects a model image.

Logical `Reset()` must be called between completed operations. It invalidates
lengths, token counts and consumer error state; it neither erases payload cells
nor cancels a concurrently running transaction. It also does not clear errors in
a borrowed vocabulary or map. The caller owns provider recovery. Hardware context
reset, by contrast, must cancel outstanding work in consumer and provider together.
Call `MetaspaceDecoder.Reset()` or `StoredMetaspaceDecoder.Reset()` before the first
append as well as at every new sequence, to establish first-piece marker handling.

The segmenter reserves input bytes, path costs, signed predecessor indices,
token IDs, UTF-8 widths, bounded reverse-path scratch and accumulated output in
one workspace. Every reachable location is initialized before reading it.
`BeginSegment()` retains output and sticky failure; only `Reset()` starts a new
request. Capacity failure invalidates all output even if earlier segments succeeded.
Byte consumers similarly hide all bytes on failure; partially written physical
storage is not a usable partial result.

## Source conventions and verification

The storage/Unigram sources and affected tests follow the
[Livt Design Guide](../../livt-book/internal/design/DESIGN_GUIDE.md): tabs, expanded
control flow, declaration doc comments and field groups describing purpose and
ownership. Public API comments state preconditions, units, completion, failure
and reset behavior. The workspace capacity constant precedes the stored fields.
Large Viterbi and fixture lookup bodies retain their established scheduling and
lookup order; the guide's size threshold is a review prompt, not a reason to
extract scheduled methods without measuring their hardware effect.

The compatibility wrappers keep the original public names and type parameters.
The design-guide pass preserves executable tokens apart from relocating two
uninitialized field declarations after constants in `StoredUnigramSegmenter`.
It preserves every explicit delay state in test providers, assertion, fixture
value and test registration. Existing helper components remain beside their tests
because those files are also copied by application integration runners.

From the package root:

```sh
env -u _JAVA_OPTIONS livt test --junit /tmp/tokenization-tests.xml
```

The manifest explicitly registers BPE merge, GPT-2 tokenizer/decoder, compatibility
Unigram and both injected-storage test components. Test methods share component
instances: reset each exercised subject and initialize its live storage in setup.
The poisoned/delayed providers assert bounds and initialization before reads;
those delay states are intentional behavior, not formatting placeholders.

Use `livt format` for mechanical formatting, then check declaration-comment spacing
and multiline guards against the guide. The current formatter preserves some
compact empty blocks and rejects certain continued expressions/array closings;
manual layout adjustments preserve their executable tokens. No algorithm, capacity,
public signature, dependency or package-version change belongs to this style pass.

Design-guide review on 2026-09-29: all 28 tests across the six registered test
components passed, with zero failures or skips, using an isolated copy of the
reviewed sources. This checks library behavior; RAM mapping and board timing
remain application integration measurements.
