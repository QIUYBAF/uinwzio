# Validation Summary — AgentCut 3.2.2

- automated regression suite: **135 / 135 passed**
- `agentcut doctor`: pass
- Agent Protocol v5 warm/upgrade resume: pass
- checkpoint + last Agent receipt persistence: pass
- operation signature delta on upgrade: pass
- bilingual subtitle auto-fit: pass
- legacy subtitle layout migration without text/timing mutation: pass
- Cast-aware SRT import / bilingual alignment / scene staging: pass
- anonymous visual anchor suggestions + explicit-order staging: pass
- EP07 57.37 s auto-fit diagnostic proxy: render pass, QA pass
- whisper.cpp installer explicit-acceptance/checksum/persistent-model-reuse contract: pass in isolated test fixture
- bundled Real-ESRGAN discovery/regressions: pass
- flexible export/4K60/Alpha cinematic regression: pass
- final Handoff ZIP reverse-recovery smoke: pass

## EP07 practical evidence

The Nether diagnostic exposed production issues that synthetic tests missed: missing SRT speaker metadata, global Cast coordinates across changing compositions, Library effect-ID mismatch, overly expensive previews and dense bilingual captions. 3.2.1/3.2.2 addressed those with Cast-aware import, scene staging, executable Library aliases, proxy rendering, auto-fit bilingual layout and staging anchors.

3.2.2 auto-fit preserves cue text/timing and only changes layout metadata. Visual staging detects anonymous anchors only; character identity is not inferred without explicit Cast order.

## Low-token restart benchmark

On the EP07 diagnostic project:
- full Agent context: ~46.9 KB
- warm resume capsule: ~2.1 KB
- serialized-byte reduction: ~95.5%

This is a payload comparison, not an exact tokenizer guarantee.

## Environment note

This Linux release cloud has no whisper.cpp ASR runtime/model installed, so live speech recognition is **not** claimed as executed here. The one-command binary installer currently targets Windows x64; Linux/macOS can reuse the persistent model but need an external `whisper-cli`.

The cloud also has no usable NVENC/Vulkan runtime despite encoder/bundled AI files being discoverable; existing honest fallback behavior remains unchanged.