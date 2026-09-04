# AI 4K Quadrant Reconstruction Workflow

A small deterministic helper for ChatGPT Work / Codex workflows that use image generation to create higher-information 4K stills.

## Why

A direct AI image generation may have a relatively low output-resolution ceiling. Pure super-resolution increases pixel count but cannot reliably recreate all missing scene information. This workflow spends generative effort on four smaller regions while keeping a single master image as the structural anchor.

For a 1536x864 master:

`1536x864 master -> four 768x432 crops -> reconstruct each crop at 1536x864 -> stitch -> 3072x1728 -> optional 1.25x AI super-resolution -> 3840x2160 UHD`

Use this selectively for important backgrounds/key art; ordinary shots may not justify four reconstruction calls.

## 1. Split

```bash
python tools/ai_4k_quadrants.py split master.png -o quadrants --format jpg --quality 95
```

Outputs:

- `TL.jpg` — top-left
- `TR.jpg` — top-right
- `BL.jpg` — bottom-left
- `BR.jpg` — bottom-right

The split is exact: no overlap, blending, scaling, or resampling.

## 2. AI reconstruction prompt

Give the model both the current quadrant and, when possible, the complete master image for positional context.

Suggested prompt:

> Treat the quadrant image as the direct reconstruction target and the complete master image only as structural and edge-continuity reference. Produce a high-information, high-detail reconstruction rather than a redesign. Strictly preserve the quadrant's composition, perspective, subject positions, terrain/building silhouettes, lighting direction and dominant palette. Protect all four image edges: objects, horizons, terrain contours, architecture and other structures touching an edge must remain in the same position and shape so the four reconstructed quadrants can later be hard-stitched. Add only plausible micro-detail, material texture, surface definition, local lighting detail and clarity. Do not add or remove major objects, move subjects, alter camera viewpoint, change large silhouettes, or reinterpret the scene. The desired result is a faithful higher-resolution reconstruction of the same crop, not a new image.

Add one short task-specific sentence such as:

> Priority detail: improve End Stone and chorus-plant material definition without changing their silhouettes.

### Priority order

1. Edge continuity / geometry
2. Composition and perspective
3. Major object identity and position
4. Lighting/color continuity
5. Added micro-detail

If extra detail conflicts with continuity, preserve continuity.

## 3. Stitch

After the four reconstructed images have identical dimensions:

```bash
python tools/ai_4k_quadrants.py stitch \
  --tl TL_reconstructed.png \
  --tr TR_reconstructed.png \
  --bl BL_reconstructed.png \
  --br BR_reconstructed.png \
  -o reconstructed_3072x1728.jpg
```

Stitching is deliberately hard/seamless-by-coordinate: no crossfade, overlap, resize, or AI modification. This makes generation mismatches visible instead of hiding them with ghosting.

## 4. Inspect seams

Inspect at 100–200% around the center vertical/horizontal seams. Look for:

- duplicated shadows or objects;
- horizon/terrain discontinuities;
- different local exposure or hue;
- geometry that changes at the boundary.

If a seam is structurally wrong, regenerate the offending quadrant with stronger edge-preservation instructions rather than using a wide blend that creates double images.

## 5. Final 4K

A 3072x1728 reconstruction needs only 1.25x linear enlargement to reach UHD 3840x2160. A final AI super-resolution pass is therefore a finishing step, not the main source of detail.

Recommended order:

`master -> split -> faithful AI quadrant reconstruction -> hard stitch -> seam QA/fix -> final 1.25x AI upscale -> 3840x2160`

## Requirements

```bash
pip install pillow
```

The helper itself never calls an AI service; Work/Codex/image-generation tools handle reconstruction and final super-resolution.
