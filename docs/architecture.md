# Architecture

## Package boundary

`Eccelerators.Tokenization` separates tokenization behavior from tokenizer
data. The package supplies bounded algorithms and lookup contracts. A consuming
application supplies the concrete vocabulary and merge-rank storage generated
from its tokenizer assets.

```text
                         Eccelerators.Tokenization
                  ┌───────────────────────────────────┐
ASCII bytes ─────►│ Gpt2BpeTokenizer64                │──► token IDs
                  │   pre-tokenizer                   │
                  │          │                        │
                  │          ▼                        │
                  │   BpeMergeEngine64                │
                  └──────────┬───────────────┬────────┘
                             │               │
                      IGpt2Vocabulary  IBpeMergeTable
                             │               │
                  ┌──────────▼───────────────▼────────┐
                  │ Application-owned table storage   │
                  └───────────────────────────────────┘
```

The same `IGpt2Vocabulary` provider is shared with `Gpt2BpeDecoder128`, which
maps predicted token IDs back to their original bytes.

## Bounded data flow

The first implementation deliberately fixes these capacities:

| Boundary | Capacity |
|---|---:|
| Application input text | 64 ASCII bytes |
| One pre-tokenized BPE piece | 64 symbols |
| Tokenizer output | 64 token IDs |
| Accumulated decoder output | 128 bytes |

The GPT-2 tokenizer itself does not require all 64 output tokens to be retained
by a language model. A generation controller may select the newest context
tokens after tokenization.

## Merge behavior

For each piece, the merge engine scans adjacent token pairs, asks
`IBpeMergeTable` for their ranks, selects the lowest rank, and merges every
non-overlapping occurrence of that pair. It repeats until the table reports no
remaining pair. This favors a small, readable reference architecture. A future
optimized component can preserve the public table contract while adding cached
lookups or parallel pair comparisons.

## Storage implementations

Production GPT-2 data is large enough that generated chains of conditional
statements are inappropriate. Recommended implementations are:

- packed initialized ROM for small FPGAs with sufficient block RAM;
- indexed external memory when the language-model weights already live there;
- a two-level hash or trie index backed by ROM;
- a small combinational provider only for unit-test fixtures.

Simulation-only file I/O is not a synthesis strategy. Applications should use
the same lookup contracts with a synthesizable memory backend for FPGA builds.
