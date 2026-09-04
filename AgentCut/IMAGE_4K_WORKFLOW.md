# AgentCut Image 4K Tile Workflow

Purpose: let Codex / ChatGPT Work turn one coherent ~1080p generated composition into a higher-resolution master without asking the image model to reinvent the whole scene.

## Canonical flow

1. Generate one complete composition master first. Composition, perspective, lighting and character/object placement are locked here.
2. Split deterministically: `agentcut image-split4 master.png tiles/`.
3. Refine `r1c1`, `r1c2`, `r2c1`, `r2c2` separately with the image model.
4. Every tile instruction must preserve composition, camera/perspective, geometry, crop boundary, lighting direction and continuity; add detail/resolution only.
5. Keep tile order and aspect ratio. Never independently reframe a tile.
6. Stitch: `agentcut image-stitch4 master_4k.png r1c1.png r1c2.png r2c1.png r2c2.png`.
7. Inspect seams/global geometry once. If dimensions remain below UHD, use only a modest final upscale.

## Accuracy note

Four processed tiles do not mathematically guarantee 4K. Final dimensions depend on each returned tile. AgentCut reports the stitched dimensions; UHD target is 3840×2160.

## Work-mode rationale

The model spends its available output pixels on a smaller region while the original master remains composition authority. Deterministic split/stitch prevents layout drift between stages.
