# CT-01 FILM-HISTORY V003 — Archive manifest

**DATE:** 2026-09-24  
**PROJECT:** CT-01  
**TRACK:** FILM-HISTORY  
**VERSION:** V003  
**STATUS:** CURRENT source archive + current final delivery

## Retained Drive assets

- Source project package: [CT-01__FILM-HISTORY__SOURCE__V003.zip](https://drive.google.com/file/d/1FSKo3XArBMRo_k_P3Vi2xL-h7gWFjC1x/view)
  - bytes: 695325995
  - SHA-256: `b0cf8f7061fc48a38ef10c663e0ec6f38d25480ec9265ee44483dfe63407207f`
  - 440 files; CRC passed.
- Current 4K master: [4K master](https://drive.google.com/file/d/19pI0KjrkXCkR9Ze2xmce_aQVUwIka7C6/view)
  - bytes: 139269027
  - SHA-256: `1d728a820fa94d9335871c853fdb2589d5c0306ad4a0155c7a1d2958ba7103bf`
  - technical QA passed.
- Current 1080p viewing copy: [1080p copy](https://drive.google.com/file/d/1ElinY7uVKdbPW_TAOcfD2sqp_RJ9c5in/view)
  - bytes: 48925860.
- Publishing package: [publishing package](https://drive.google.com/file/d/15ZXwBABiE2wik-41_IGfTzQ5w8vJBpCb/view)
  - bytes: 8942690.
- Canonical delivery folder: [CT-01__FILM-HISTORY__V003__CURRENT](https://drive.google.com/drive/folders/1-Q_a97Jcwf2sIEvNU2Q-rIXtdqBPfjBt).
- Source archive folder: [2026-09-24 local-space archive](https://drive.google.com/drive/folders/1CDgH1KBosniAXu_Aj6v65GAQ-D27XbNQ).

## Rebuild evidence

The source package contains the required Blender scenes, Remotion/spec sources, image/audio inputs, scripts, lockfile, and the selected rebuild/import dependencies. The archived receipt reported no missing local entrypoint/import and no credential candidates. Python, Blender, FFmpeg, Node and `node_modules` are external installable dependencies and are intentionally not bundled.

## Cleanup decision

The separate 450-frame native 4K PNG archive
`STT_FilmHistory_v003_S07_native_4K_PNG.zip`
(3711797439 bytes; SHA-256 `bfb563a555059be3287978862fd67b05152a22f26a00ad5f67ddd59503849f3b`) was deleted from Drive after the source package and final masters were verified. It was a regenerable render intermediate, not the unique source or final release.

The standalone Drive copies of `README_V003.md`, `DELIVERY_RECEIPT.json`, and the recovery guide were also removed after their durable restore facts and hashes were consolidated here. The source ZIP remains the recovery asset; the final masters remain the delivery assets.
