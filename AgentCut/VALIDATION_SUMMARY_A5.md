# Validation Summary — v0.2.0-alpha.5

- Automated tests: **42 / 42 passed**
- `agentcut doctor`: **PASS**
- FFmpeg: 7.1.5
- Required filters: xfade, concat, ASS, blend, amix, alimiter, perspective, colorkey, overlay — present
- Required encoders: libx264, AAC, qtrle — present
- Noto Sans CJK — present
- Library entries: **129**
- Reference promo: **1920x1080 / 30fps / 20.000s / H.264 + AAC**
- Promo video duration: 20.000s
- Promo audio duration: 20.000s
- Promo QA: **PASS**
- Promo audio peak: approximately -20.8 dBFS
- Camera backend: subpixel perspective+cubic

Known informational limitation: particle depth hints affect size/speed/density but are not yet subject-aware occlusion/depth segmentation.
