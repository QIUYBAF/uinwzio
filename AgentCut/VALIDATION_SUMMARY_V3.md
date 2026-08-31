# Validation Summary — AgentCut 3.2.3

- automated regression suite: **145 / 145 passed** (70 + 75 split runs)
- dedicated 3.2.3 dialogue-coverage regression: **10 / 10 passed**
- `agentcut doctor`: pass
- clean 3.2.3 wheel install: pass
- bundled Real-ESRGAN discovery after wheel install: pass
- Cast-aware dialogue coverage from global captions: pass
- coverage from native dialogue segments: pass
- scene-specific staging used by coverage: pass
- group-reset / repeated-speaker variation: pass
- object/action attention insert merge and conflict protection: pass
- Agent aliases for dialogue coverage / attention inserts: preflight pass
- 3.2.2 subtitles/ASR/warm-resume regressions: pass
- 3.0 flexible export/4K60/Alpha cinematic regressions: pass

## EP07 practical validation

The Nether diagnostic exposed a new quality failure: correct speaker tracking could still look template-driven when every static image used one continuous reframe.

On the diagnostic timeline, 3.2.3 reproduced four `LONG_SINGLE_COVERAGE` warnings before semantic coverage. Applying coverage cleared those warnings without retiming subtitles or splitting canonical source assets. An object/action insert handles a long pre-dialogue hold where appropriate.

The validation images are visibly marked **PROXY STORYBOARD**. They are diagnostic assets, not the user's prepared final generated EP07 art. Final-art acceptance must be repeated when that image set is accessible in the active runtime.

## Existing 3.2.2 production validation retained

- structured bilingual subtitle auto-fit: pass
- Cast-aware SRT speaker parsing/alignment: pass
- anonymous staging anchors + explicit-order staging: pass
- Protocol v5 warm/upgrade resume and schema delta: pass
- EP07 warm-resume payload reduction benchmark retained
- optional whisper.cpp installer/checksum/persistent-cache contract: pass in isolated fixture

## Environment note

This cloud has no usable whisper.cpp runtime/model, NVENC runtime, or Vulkan device. Live ASR and neural Real-ESRGAN inference are therefore not claimed as executed here. Existing explicit AI/fallback honesty contracts remain unchanged.