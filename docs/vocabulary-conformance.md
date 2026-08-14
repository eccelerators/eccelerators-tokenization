# Vocabulary Conformance

`tools/check_gpt2_vocabulary.py` validates the immutable tokenizer assets that
a consuming application converts into ROM, RAM, or external-memory tables. It
does not generate hardware and does not redistribute a vocabulary.

The checker uses only the Python standard library. Its reference path follows
the package's supported contract: GPT-2-style byte-level BPE with ASCII input.

## Accepted asset formats

Use one of these vocabulary inputs:

- `--tokenizer-json`: a Hugging Face tokenizer object whose `model.type` is
  `BPE` and whose `model.vocab` contains the token-to-ID mapping;
- `--vocab-json`: a standalone JSON object mapping token strings to IDs.

Supply `--merges path/to/merges.txt` for a conventional merge file. The option
may be omitted when `tokenizer.json` contains a `model.merges` array. An
explicit merge file takes precedence over embedded merges.

Token IDs must be unique and contiguous from zero. Every one of the 256
reversible GPT-2 byte symbols must exist, and each merge's left token, right
token, and concatenated result must occur in the vocabulary. Duplicate merge
pairs are rejected because their rank would be ambiguous.

## Standard GPT-2 example

```sh
python3 -B tools/check_gpt2_vocabulary.py \
  --tokenizer-json path/to/tokenizer.json \
  --merges path/to/merges.txt \
  --expected-vocabulary-size 50257 \
  --expected-merge-count 50000 \
  --report vocabulary-conformance.json
```

Expected sizes are optional. They are useful for detecting an accidentally
mixed or truncated asset set but should be changed to match a custom model.

## Custom vocabulary example

```sh
python3 -B tools/check_gpt2_vocabulary.py \
  --vocab-json model/vocab.json \
  --merges model/merges.txt \
  --vectors model/conformance-vectors.json
```

The golden-vector file can be a JSON array or an object containing `vectors`:

```json
{
  "vectors": [
    {
      "text": "Hello world",
      "token_ids": [15496, 995]
    },
    {
      "text": " Hello world",
      "token_ids": [18435, 995]
    }
  ]
}
```

Vector text must be ASCII. Each vector is encoded and compared with the exact
expected token IDs. Those token IDs are then decoded and compared with the
original text. This detects mismatched vocabulary revisions, merge ranks, and
model token-ID assignments.

## Built-in checks

Every invocation checks:

- JSON structure and BPE model type;
- non-empty tokens and unique, contiguous token IDs;
- complete GPT-2 byte-symbol coverage;
- merge shape, rank order, uniqueness, operands, and result tokens;
- representative ASCII prompts and whitespace boundaries;
- all 128 individual ASCII byte values as encode/decode round trips;
- optional golden vectors and expected asset sizes;
- SHA-256 digests for every loaded asset.

With `--report`, successful results are written as deterministic JSON suitable
for a model manifest. A failed check writes a concise reason to standard error
and exits with status one.

## Tool tests

Run the standalone checker tests with:

```sh
python3 -B -m unittest discover -s tools -p 'test_*.py'
```

These tests construct an inspectable complete byte vocabulary, exercise a
ranked merge, reject an incomplete merge result, detect a wrong golden vector,
and verify report construction from standalone files.
