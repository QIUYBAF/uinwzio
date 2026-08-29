# RNGtuber Refined Modular Assets — 2026-08-29

> **ACTIVE REPLACEMENT SET** — this supersedes the earlier `additional_assets_2026-08-29` supplemental-only batch.

This batch is built for the current RNGtuber V1 Modular renderer and replaces the generic facial runtime sprites with reference-specific modular layers based on the Casual/COS 周婉晴 masters.

## Layer contract

Each eye is split into independent transparent PNG layers:

- eye white / sclera
- iris + pupil (the only part that receives gaze movement)
- upper lid + lashes
- lower lid
- closed lid + lashes
- eyebrow

Mouth is split into closed/open variants. Neutral / Happy / Unamused / Surprised now have real sprite variants for both Casual and COS instead of relying mainly on scale/rotation deformation.

Blink rule: eye white + iris + open upper/lower lids are hidden while the closed-lid sprite is shown.

## Current package status

- 112 expression/outfit variant sprites
- 14 active face layers per state
- transparent RGBA assets
- old generic runtime assets archived only for rollback
- renderer updated to select outfit/expression sprite variants
- 13/13 tests passing
- visual QA matrix generated

## Google Drive source of truth

Full binary assets and updated project checkpoint are stored in the RNGtuber project folder:

- Refined asset folder: https://drive.google.com/drive/folders/1RQVOjoexWAI39JfPjnVq2Q3zWPKzCeVh
- Refined asset ZIP: https://drive.google.com/file/d/1eqSxWT7dtXuKK5oKgMZNCeSizOaSSAIa/view
- Updated full checkpoint: https://drive.google.com/file/d/1hhRTL7SQCOJU_JWyOTYZLSrHbMEYipg9/view
- Face QA matrix: https://drive.google.com/file/d/1764TuOa5u4V6jVtQIulImJDfNZePwslA/view

Binary PNGs remain in Drive because this connected GitHub repository is not the original RNGtuber repository. This branch stores the integration manifest and source patch pointers without modifying `master`.
