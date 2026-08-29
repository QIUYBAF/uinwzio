# RNGtuber modular face asset replacement — 2026-08-29

Active generic face sprites were replaced with the new reference-specific modular set.

The new set keeps **eye white, iris/pupil, upper lid/lashes, lower lid, closed lid, eyebrow, closed mouth and open mouth as independent transparent PNG layers**.

It also adds real per-expression sprite variants for Neutral / Happy / Unamused / Surprised under both Casual and COS. The renderer should select these variants instead of simulating expressions by aggressively deforming one generic face.

Blink contract: eye white + iris + open upper/lower lids fade out; closed lid fades in. Iris alone receives gaze movement.

The previous active sprite files are retained only in `runtime/archive_original_runtime_before_refined_2026-08-29/` for rollback.
