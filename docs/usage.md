# Usage

## Tokenization call order

`Gpt2BpeTokenizer64` is a bounded callable reference API:

1. Call `Reset()`.
2. Call `AcceptAscii(value)` for every prompt byte.
3. Consume any transport or framing delimiters outside the tokenizer unless
   they belong to the input text.
4. Call `Tokenize()`.
5. Check `HasError()`.
6. Read `GetTokenCount()` and each `GetToken(index)`.

The tokenizer rejects bytes above `0x7f` and inputs longer than 64 bytes. It
does not silently truncate them.

## Decoding call order

1. Call `Gpt2BpeDecoder128.Reset()` before a response.
2. Call `AppendToken(token)` for each generated token.
3. Check the returned value and `HasError()`.
4. Transmit bytes `0 .. GetByteCount() - 1` with `GetByte(index)`.

The decoder returns original bytes rather than Livt strings. This keeps output
handling independent of application-specific text and byte-stream consumers.

## Table-provider contract

`IBpeMergeTable.Lookup(left, right)` updates three readable results:

- `HasMerge()` reports whether the pair exists;
- `GetRank()` returns a non-negative rank, where lower wins;
- `GetMergedToken()` returns the merged vocabulary token.

`IGpt2Vocabulary` has two lookup directions:

- `LookupByte` and `GetByteToken` provide initial byte-level symbols;
- `ReadToken`, `GetTokenLength`, and `GetTokenByte` provide decoded bytes.

Lookups complete before their getter is called. A memory implementation may
therefore schedule multiple cycles internally without changing the caller API.

## Application responsibility

The application must generate table contents from the exact tokenizer revision
paired with its model, verify checksums, and retain the tokenizer's licensing
metadata. The package intentionally carries no third-party vocabulary data.
