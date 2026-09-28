# Eccelerators.Tokenization

Hardware-oriented tokenization components for processor-free text processing
and language-model inference with Livt.

> 🧪 **A Livt and Livt Agents experiment**
>
> This repository explores bounded text tokenization as explicit hardware. It
> provides reusable algorithm components and storage contracts rather than a
> software runtime. The first implementation targets the GPT-2 byte-level BPE
> contract needed by small transformer showcases.

## 🗺️ Project Scope

The initial package provides:

- a reusable ranked BPE merge engine for pieces containing up to 64 symbols;
- GPT-2-compatible ASCII pre-tokenization and byte-level BPE composition;
- token-to-byte decoding for buffered text and byte-stream outputs;
- storage-independent interfaces for generated vocabulary and merge tables;
- deterministic tests using small inspectable fixtures.

The package deliberately does not redistribute GPT-2 vocabulary or merge
assets. Applications generate or provide their own table implementations from
appropriately licensed tokenizer files.

## 📦 Package

```toml
[dependencies]
"Eccelerators.Tokenization" = "0.2.0-dev"
```

The package has no runtime dependency on a processor or software tokenizer.
Its table contracts can be implemented with FPGA ROM, RAM, external memory, or
small combinational fixtures.

## 📚 Namespaces

| Namespace | Purpose |
|---|---|
| `Eccelerators.Tokenization.Bpe` | Ranked BPE merge algorithm and merge-table contract |
| `Eccelerators.Tokenization.Gpt2` | ASCII pre-tokenization, byte-level vocabulary contract, tokenizer, and decoder |

## 🧩 API Overview

| Component or interface | Purpose |
|---|---|
| `IBpeMergeTable` | Looks up the rank and result token for one adjacent token pair |
| `BpeMergeEngine64` | Repeatedly applies the best ranked merge to a bounded piece |
| `IGpt2Vocabulary` | Maps original bytes to initial symbols and tokens back to bytes |
| `Gpt2BpeTokenizer64` | Converts up to 64 ASCII bytes into up to 64 GPT-2 token IDs |
| `Gpt2BpeDecoder128` | Appends decoded bytes for GPT-2 token IDs into a 128-byte buffer |

`Gpt2BpeTokenizer64` uses the GPT-2 ASCII subset of the original
pre-tokenization expression, including optional leading spaces, letter/digit/
punctuation runs, whitespace handling, and case-insensitive contraction pieces.
It then delegates each piece to `BpeMergeEngine64`.

## 💡 Usage Shape

A parent application owns concrete table providers and injects them into the
tokenizer and decoder:

```livt
using Eccelerators.Tokenization.Bpe
using Eccelerators.Tokenization.Gpt2

component TextFrontend
{
	vocabulary: ApplicationGpt2Vocabulary
	merges: ApplicationGpt2MergeTable
	tokenizer: Gpt2BpeTokenizer64
	decoder: Gpt2BpeDecoder128

	new()
	{
		this.vocabulary = new ApplicationGpt2Vocabulary()
		this.merges = new ApplicationGpt2MergeTable()
		this.tokenizer = new Gpt2BpeTokenizer64(this.vocabulary, this.merges)
		this.decoder = new Gpt2BpeDecoder128(this.vocabulary)
	}
}
```

One processor-free application path is:

```text
ASCII text → bounded byte buffer → Gpt2BpeTokenizer64 → token context
           → language model → predicted token → Gpt2BpeDecoder128
           → decoded byte stream
```

See [usage](docs/usage.md) for call order and
[architecture](docs/architecture.md) for the storage and hardware boundaries.

## 🧪 Build and Test

Build the package:

```sh
livt build
```

Run all configured tests:

```sh
livt test
```

Run the vocabulary-tool tests:

```sh
python3 -B -m unittest discover -s tools -p 'test_*.py'
```

The tests cover merge ranking, repeated pairs, exact capacity boundaries,
Reset recovery, the standard `Hello, world!` GPT-2 token vector, every GPT-2
contraction alternative, whitespace and character-class boundaries, atomic
decoder overflow, token decoding, and invalid input.

## 🔍 Vocabulary Conformance

Validate a Hugging Face tokenizer with an embedded or separate merge table:

```sh
python3 -B tools/check_gpt2_vocabulary.py \
  --tokenizer-json path/to/tokenizer.json \
  --merges path/to/merges.txt \
  --expected-vocabulary-size 50257 \
  --expected-merge-count 50000 \
  --report vocabulary-conformance.json
```

Custom models can provide standalone `vocab.json` and `merges.txt` files. An
optional golden-vector file verifies exact token IDs in both directions:

```sh
python3 -B tools/check_gpt2_vocabulary.py \
  --vocab-json path/to/vocab.json \
  --merges path/to/merges.txt \
  --vectors path/to/vectors.json
```

The tool validates contiguous token IDs, all 256 GPT-2 byte symbols, merge
operands and results, duplicate pairs, built-in ASCII round trips, optional
expected table sizes, caller-provided golden vectors, and input SHA-256
digests. See [vocabulary conformance](docs/vocabulary-conformance.md) for the
asset contracts and vector format.

## ✅ References and Conformance

The primary behavioral reference is OpenAI's original
[`gpt-2/src/encoder.py`](https://github.com/openai/gpt-2/blob/master/src/encoder.py).
It defines the reversible byte-to-Unicode mapping, pre-tokenization expression,
ranked pair-merging loop, token lookup, and decoding procedure implemented by
this package's bounded hardware components.

The official Hugging Face
[`GPT2Tokenizer` documentation](https://huggingface.co/docs/transformers/model_doc/gpt2#transformers.GPT2Tokenizer)
provides an independent implementation and documents the important distinction
between a word at the beginning of a string and one preceded by a space. Its
published vectors include:

```text
"Hello world"  → [15496, 995]
" Hello world" → [18435, 995]
```

Conformance tests should use both references against the exact `vocab.json` and
`merges.txt` revision supplied by the consuming application. For every vector,
verify encoding and the reverse token-to-byte result. The suite should cover:

- empty and single-byte input;
- leading, repeated, trailing, tab, and newline whitespace;
- contractions, capitalization, numbers, and punctuation runs;
- all printable ASCII bytes and the 64-byte capacity boundary;
- unknown table entries and invalid token IDs;
- round trips through `encode(text)`, hardware token IDs, and `decode(ids)`.

The small checked-in fixtures exercise the algorithms without redistributing a
third-party vocabulary. Full 50,257-token conformance belongs to the generated
table implementation paired with the application's pinned tokenizer assets.

## 🗂️ Layout

```text
src/Bpe/       generic bounded BPE engine and storage contract
src/Gpt2/      GPT-2 vocabulary contract, ASCII tokenizer, and decoder
tests/Bpe/     generic merge behavior and bounds
tests/Gpt2/    GPT-2 fixtures, conformance vectors, and decoding
docs/          architecture, usage, and hardware notes
tools/         vocabulary conformance checker and its Python tests
```

Source namespaces mirror their folders. Test namespaces use
`Eccelerators.Tokenization.Tests.<domain>`.

## 📝 Design Notes

- Input and output capacities are explicit hardware bounds, not dynamic
  software containers.
- The reusable package owns algorithms; applications own generated tokenizer
  data and its redistribution obligations.
- Lookup interfaces intentionally hide whether tables are local ROMs or
  external-memory datapaths.
- ASCII is the input contract. Decoding remains byte-oriented so consuming
  applications control how supported output bytes are handled.

## 🚀 Outlook

- Add generated full GPT-2 vocabulary and merge-table implementations in the
  consuming TinyStories application.
- Add streaming command/valid handshakes around the bounded callable API.
- Add table indexes optimized for BRAM latency and resource use.
- Add other BPE tokenizer families without changing the generic merge engine.

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

## Unigram extension (0.2.0-dev)

See [the generic Unigram contracts and bounds](docs/unigram.md) for exact-cost
segmentation, injectable ASCII normalization and UTF-8 Metaspace decoding.
Existing GPT-2/BPE APIs remain available unchanged. The development version is
used by the FLAN-T5 integration and awaits user publication.
