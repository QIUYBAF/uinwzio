from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw

from render_visual_qa import CHARACTER, REPORTS, compose, smootherstep


FPS = 15
DURATION = 5.4
PREVIEWS = REPORTS / "previews"


def blink_envelope(time_s: float, start: float) -> float:
    local = time_s - start
    if local < 0.0 or local > 0.30:
        return 0.0
    if local < 0.085:
        return smootherstep(local / 0.085)
    if local < 0.155:
        return 1.0
    return 1.0 - smootherstep((local - 0.155) / 0.145)


def speech_envelope(time_s: float) -> float:
    active = (0.55 <= time_s <= 2.15) or (2.85 <= time_s <= 4.75)
    if not active:
        return 0.0
    wave = 0.56 + 0.27 * math.sin(time_s * math.tau * 2.35) + 0.17 * math.sin(time_s * math.tau * 4.7 + 0.8)
    return smootherstep(max(0.0, min(1.0, (wave - 0.28) / 0.62)))


def preview_frame(spec: dict, outfit: str, time_s: float) -> Image.Image:
    blink = max(blink_envelope(time_s, 1.46), blink_envelope(time_s, 4.22))
    mouth = speech_envelope(time_s)
    gaze = (
        math.sin(time_s * math.tau / DURATION) * 0.72,
        math.sin(time_s * math.tau / 3.7 + 0.45) * 0.34,
    )
    avatar = compose(spec, outfit, "neutral", mouth_amount=mouth, blink_amount=blink, gaze=gaze)
    avatar = avatar.resize((384, 576), Image.Resampling.LANCZOS)
    wave = math.sin(time_s * 1.65)
    sway = math.sin(time_s * 0.72 + 0.8)
    scaled = avatar.resize(
        (
            max(1, round(avatar.width * (1.0 + wave * 0.0018))),
            max(1, round(avatar.height * (1.0 + wave * 0.0042))),
        ),
        Image.Resampling.BICUBIC,
    )
    rotated = scaled.rotate(-sway * 0.22, Image.Resampling.BICUBIC, expand=True)
    frame = Image.new("RGB", (420, 630), (34, 37, 47))
    x = (frame.width - rotated.width) // 2
    y = (frame.height - rotated.height) // 2 - round(wave * 0.55)
    frame.paste(rotated, (x, y), rotated)
    return frame


def save_gif(spec: dict, outfit: str) -> Path:
    frames = [preview_frame(spec, outfit, index / FPS) for index in range(round(DURATION * FPS))]
    destination = PREVIEWS / f"{outfit}_blink_talk_gaze_preview.gif"
    frames[0].save(
        destination,
        save_all=True,
        append_images=frames[1:],
        duration=round(1000 / FPS),
        loop=0,
        disposal=2,
        optimize=True,
    )
    return destination


def save_state_sheet(spec: dict) -> Path:
    states = (
        ("idle", dict(mouth_amount=0.0, blink_amount=0.0, gaze=(0.0, 0.0))),
        ("talk", dict(mouth_amount=1.0, blink_amount=0.0, gaze=(0.45, -0.2))),
        ("blink", dict(mouth_amount=0.0, blink_amount=1.0, gaze=(0.0, 0.0))),
    )
    card_w, card_h = 340, 300
    sheet = Image.new("RGB", (card_w * len(states), card_h * 2), (28, 30, 39))
    draw = ImageDraw.Draw(sheet)
    for row, outfit in enumerate(("casual", "cos")):
        for col, (label, values) in enumerate(states):
            frame = compose(spec, outfit, "neutral", **values)
            face = frame.crop((360, 45, 650, 305)).resize((card_w, card_h - 30), Image.Resampling.LANCZOS)
            cell = Image.new("RGB", face.size, (42, 45, 55))
            cell.paste(face, mask=face.getchannel("A"))
            sheet.paste(cell, (col * card_w, row * card_h + 30))
            draw.text((col * card_w + 8, row * card_h + 8), f"{outfit} | {label}", fill=(238, 240, 248))
    destination = PREVIEWS / "eye_mouth_registration_v11.png"
    sheet.save(destination, optimize=True)
    return destination


def main() -> None:
    PREVIEWS.mkdir(parents=True, exist_ok=True)
    spec = json.loads((CHARACTER / "character.json").read_text(encoding="utf-8"))
    outputs = [save_gif(spec, outfit) for outfit in ("casual", "cos")]
    outputs.append(save_state_sheet(spec))
    for output in outputs:
        print(output)


if __name__ == "__main__":
    main()
