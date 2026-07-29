# Casting delivery bundle transfer

This directory stores a Base64 text transfer of `casting_delivery_bundle.zip`.
The source audio has not been regenerated.

## Bundle contents and order

1. `broadcast.mp3`
2. `chito.mp3`
3. `combined_preview.mp3`
4. `coser.mp3`
5. `yuuri.mp3`
6. `casting_samples.zip`

## Integrity

- Original ZIP filename: `casting_delivery_bundle.zip`
- SHA-256: `75ce84a6ca11ff6248379fc38fb4b48ae6b92691f4f72217b93d5a3b6061a28b`
- Parts must be concatenated in lexical order: `part_001.txt`, `part_002.txt`, and so on.
- Each part is at most 200 KB (200,000 bytes).

## Restore

From the repository root:

```bash
cat transfer/casting_delivery_bundle_parts/part_*.txt \
  | base64 --decode \
  > casting_delivery_bundle.zip
sha256sum casting_delivery_bundle.zip
```

The reported digest must exactly match the SHA-256 above. The restored ZIP can then be
inspected with `unzip -l casting_delivery_bundle.zip` or extracted with
`unzip casting_delivery_bundle.zip`.
