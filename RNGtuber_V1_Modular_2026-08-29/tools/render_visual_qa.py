from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
CHARACTER = ROOT / "assets" / "characters" / "zhou_wanqing"
REPORTS = ROOT / "reports"


def compose(spec: dict, outfit: str, expression: str, *, talk: bool, blink: bool) -> Image.Image:
    base = Image.open(CHARACTER / spec["outfits"][outfit]["base"]).convert("RGBA")
    expression_data = spec["expressions"][expression]
    mouth = 1.0 if talk or float(expression_data.get("mouth_bias", 0.0)) >= 0.5 else 0.0
    prepared: list[tuple[float, int, Image.Image, tuple[int, int]]] = []
    for index, layer in enumerate(spec["layers"]):
        layer_id = layer["id"]
        transform = dict(spec["outfits"][outfit]["transforms"][layer_id])
        transform.update(
            spec.get("variant_transforms", {}).get(outfit, {}).get(expression, {}).get(layer_id, {})
        )
        transform.update(expression_data.get("layers", {}).get(layer_id, {}))
        role = layer["role"]
        visible = 1.0
        if role in {"eye_white", "iris", "eyeliner_open", "eye_aux"}:
            visible = 0.0 if blink else 1.0
        elif role == "eyelid_closed":
            visible = 1.0 if blink else 0.0
        elif role == "mouth_closed":
            visible = 1.0 - mouth
        elif role == "mouth_open":
            visible = mouth
        opacity = visible * float(transform.get("opacity", 1.0))
        if opacity <= 0.001:
            continue
        sprite_id = (
            spec.get("sprite_variants", {}).get(outfit, {}).get(expression, {}).get(layer_id, layer["sprite"])
        )
        image = Image.open(CHARACTER / spec["sprites"][sprite_id]).convert("RGBA")
        image = image.crop(image.getchannel("A").getbbox())
        sx, sy = float(transform.get("scale_x", 1.0)), float(transform.get("scale_y", 1.0))
        image = image.resize(
            (max(1, round(image.width * sx)), max(1, round(image.height * sy))),
            Image.Resampling.LANCZOS,
        )
        rotation = float(transform.get("rotation", 0.0))
        if rotation:
            image = image.rotate(-rotation, Image.Resampling.BICUBIC, expand=True)
        if opacity < 1.0:
            image.putalpha(image.getchannel("A").point(lambda value: round(value * opacity)))
        prepared.append(
            (
                float(layer.get("z", 0)) + float(transform.get("z", 0)),
                index,
                image,
                (round(float(transform.get("x", 0))), round(float(transform.get("y", 0)))),
            )
        )
    for _, _, image, position in sorted(prepared):
        base.alpha_composite(image, position)
    return base


def main() -> None:
    spec = json.loads((CHARACTER / "character.json").read_text(encoding="utf-8"))
    expressions = ("neutral", "happy", "unamused", "surprised")
    states = ((False, False, "idle"), (True, False, "talk"), (False, True, "blink"))
    card_width, card_height = 256, 404
    matrix = Image.new("RGB", (card_width * len(expressions), card_height * len(states) * 2), (28, 30, 39))
    draw = ImageDraw.Draw(matrix)
    for outfit_index, outfit in enumerate(("casual", "cos")):
        for state_index, (talk, blink, state_name) in enumerate(states):
            row = outfit_index * len(states) + state_index
            for column, expression in enumerate(expressions):
                frame = compose(spec, outfit, expression, talk=talk, blink=blink)
                frame.thumbnail((card_width - 12, card_height - 36), Image.Resampling.LANCZOS)
                x = column * card_width + (card_width - frame.width) // 2
                y = row * card_height + 28
                cell = Image.new("RGB", frame.size, (42, 45, 55))
                cell.paste(frame, mask=frame.getchannel("A"))
                matrix.paste(cell, (x, y))
                draw.text((column * card_width + 8, row * card_height + 7), f"{outfit} / {expression} / {state_name}", fill=(235, 237, 248))
    REPORTS.mkdir(exist_ok=True)
    destination = REPORTS / "modular_state_matrix.png"
    matrix.save(destination, optimize=True)
    print(destination)

    face_width, face_height = 280, 230
    faces = Image.new("RGB", (face_width * len(expressions), face_height * len(states) * 2), (28, 30, 39))
    face_draw = ImageDraw.Draw(faces)
    for outfit_index, outfit in enumerate(("casual", "cos")):
        for state_index, (talk, blink, state_name) in enumerate(states):
            row = outfit_index * len(states) + state_index
            for column, expression in enumerate(expressions):
                frame = compose(spec, outfit, expression, talk=talk, blink=blink)
                face = frame.crop((340, 35, 680, 315)).resize((face_width, face_height - 24), Image.Resampling.LANCZOS)
                cell = Image.new("RGB", face.size, (42, 45, 55))
                cell.paste(face, mask=face.getchannel("A"))
                faces.paste(cell, (column * face_width, row * face_height + 24))
                face_draw.text(
                    (column * face_width + 7, row * face_height + 6),
                    f"{outfit} / {expression} / {state_name}",
                    fill=(235, 237, 248),
                )
    face_destination = REPORTS / "modular_face_matrix.png"
    faces.save(face_destination, optimize=True)
    print(face_destination)


if __name__ == "__main__":
    main()
