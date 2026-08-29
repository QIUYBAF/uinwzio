from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
CHARACTER = ROOT / "assets" / "characters" / "zhou_wanqing"
REPORTS = ROOT / "reports"


def smootherstep(value: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    return value * value * value * (value * (value * 6.0 - 15.0) + 10.0)


def ramp(value: float, start: float, end: float) -> float:
    return smootherstep((value - start) / max(0.001, end - start))


def trim_sprite(image: Image.Image) -> Image.Image:
    alpha = np.asarray(image.getchannel("A"))
    ys, xs = np.nonzero(alpha >= 8)
    if not len(xs):
        return image.crop((0, 0, 1, 1))
    left, top = int(xs.min()), int(ys.min())
    right, bottom = int(xs.max()) + 1, int(ys.max()) + 1
    if image.width >= 768 and image.height >= 1152 and len(xs) >= 1000:
        q_left, q_right = np.quantile(xs, (0.001, 0.999))
        q_top, q_bottom = np.quantile(ys, (0.001, 0.999))
        left = max(0, int(q_left) - 2)
        top = max(0, int(q_top) - 2)
        right = min(image.width, int(q_right) + 3)
        bottom = min(image.height, int(q_bottom) + 3)
    return image.crop((left, top, right, bottom))


def merge_transform(spec: dict, outfit: str, expression: str, layer_id: str) -> dict[str, float]:
    result = {
        "x": 0.0,
        "y": 0.0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "rotation": 0.0,
        "opacity": 1.0,
        "z": 0.0,
    }
    result.update(spec["outfits"][outfit]["transforms"][layer_id])
    result.update(spec.get("variant_transforms", {}).get(outfit, {}).get(expression, {}).get(layer_id, {}))
    result.update(spec["expressions"][expression].get("layers", {}).get(layer_id, {}))
    return {key: float(value) for key, value in result.items()}


def apply_registration(transform: dict[str, float], registration: dict[str, float]) -> dict[str, float]:
    result = dict(transform)
    result["x"] += float(registration.get("x", 0.0))
    result["y"] += float(registration.get("y", 0.0))
    result["scale_x"] *= float(registration.get("scale_x", registration.get("scaleX", 1.0)))
    result["scale_y"] *= float(registration.get("scale_y", registration.get("scaleY", 1.0)))
    result["rotation"] += float(registration.get("rotation", 0.0))
    result["opacity"] *= float(registration.get("opacity", 1.0))
    result["z"] += float(registration.get("z", registration.get("z_order", 0.0)))
    return result


def apply_group(
    transform: dict[str, float],
    group: dict[str, float],
    pivot: tuple[float, float],
    sprite_size: tuple[int, int],
) -> dict[str, float]:
    width, height = sprite_size
    center_x = transform["x"] + width * transform["scale_x"] * 0.5
    center_y = transform["y"] + height * transform["scale_y"] * 0.5
    local_x = (center_x - pivot[0]) * float(group.get("scale_x", 1.0))
    local_y = (center_y - pivot[1]) * float(group.get("scale_y", 1.0))
    angle = math.radians(float(group.get("rotation", 0.0)))
    rotated_x = local_x * math.cos(angle) - local_y * math.sin(angle)
    rotated_y = local_x * math.sin(angle) + local_y * math.cos(angle)
    result = dict(transform)
    result["scale_x"] *= float(group.get("scale_x", 1.0))
    result["scale_y"] *= float(group.get("scale_y", 1.0))
    new_center_x = pivot[0] + float(group.get("x", 0.0)) + rotated_x
    new_center_y = pivot[1] + float(group.get("y", 0.0)) + rotated_y
    result["x"] = new_center_x - width * result["scale_x"] * 0.5
    result["y"] = new_center_y - height * result["scale_y"] * 0.5
    result["rotation"] += float(group.get("rotation", 0.0))
    result["opacity"] *= float(group.get("opacity", 1.0))
    result["z"] += float(group.get("z", 0.0))
    return result


def scale_about_center(
    transform: dict[str, float],
    sprite_size: tuple[int, int],
    scale_x_factor: float,
    scale_y_factor: float,
) -> dict[str, float]:
    width, height = sprite_size
    center_x = transform["x"] + width * transform["scale_x"] * 0.5
    center_y = transform["y"] + height * transform["scale_y"] * 0.5
    result = dict(transform)
    result["scale_x"] *= scale_x_factor
    result["scale_y"] *= scale_y_factor
    result["x"] = center_x - width * result["scale_x"] * 0.5
    result["y"] = center_y - height * result["scale_y"] * 0.5
    return result


def role_opacity(role: str, blink: float, mouth: float) -> float:
    if role in {"eye_white", "iris", "eyelid_upper", "eyelid_lower", "eye_aux"}:
        return 1.0 - ramp(blink, 0.34, 0.82)
    if role == "eyelid_closed":
        return ramp(blink, 0.16, 0.72)
    if role == "mouth_closed":
        return 1.0 - ramp(mouth, 0.26, 0.62)
    if role == "mouth_open":
        return ramp(mouth, 0.38, 0.74)
    return 1.0


def compose(
    spec: dict,
    outfit: str,
    expression: str,
    *,
    talk: bool | None = None,
    blink: bool | None = None,
    mouth_amount: float | None = None,
    blink_amount: float | None = None,
    gaze: tuple[float, float] = (0.0, 0.0),
) -> Image.Image:
    base = Image.open(CHARACTER / spec["outfits"][outfit]["base"]).convert("RGBA")
    expression_data = spec["expressions"][expression]
    if mouth_amount is None:
        mouth_amount = 1.0 if talk else 0.0
    if blink_amount is None:
        blink_amount = 1.0 if blink else 0.0
    mouth_value = max(max(0.0, min(1.0, mouth_amount)), float(expression_data.get("mouth_bias", 0.0)))
    blink_value = max(0.0, min(1.0, blink_amount))
    gaze_x, gaze_y = float(gaze[0]), float(gaze[1])
    gaze_length = math.hypot(gaze_x, gaze_y)
    if gaze_length > 1.0:
        gaze_x, gaze_y = gaze_x / gaze_length, gaze_y / gaze_length

    prepared: list[tuple[float, int, Image.Image, tuple[int, int]]] = []
    for index, layer in enumerate(spec["layers"]):
        layer_id = layer["id"]
        sprite_id = spec.get("sprite_variants", {}).get(outfit, {}).get(expression, {}).get(layer_id, layer["sprite"])
        image = trim_sprite(Image.open(CHARACTER / spec["sprites"][sprite_id]).convert("RGBA"))
        transform = merge_transform(spec, outfit, expression, layer_id)
        transform = apply_registration(transform, layer.get("registration", {}))
        group_id = layer.get("group")
        if group_id:
            group = dict(spec["outfits"][outfit].get("group_transforms", {}).get(group_id, {}))
            pivot_values = spec["groups"][group_id].get("pivots", {}).get(outfit, (0.0, 0.0))
            transform = apply_group(transform, group, (float(pivot_values[0]), float(pivot_values[1])), image.size)

        role = layer["role"]
        blink_curve = smootherstep(blink_value)
        mouth_curve = smootherstep(mouth_value)
        if role in {"eye_white", "iris"}:
            transform = scale_about_center(transform, image.size, 1.0, 1.0 - blink_curve * 0.78)
        elif role in {"eyelid_upper", "eyelid_lower"}:
            transform = scale_about_center(transform, image.size, 1.0, 1.0 - blink_curve * 0.52)
        elif role == "eyelid_closed":
            transform = scale_about_center(transform, image.size, 1.0, 0.72 + blink_curve * 0.28)
        elif role == "mouth_open":
            transform = scale_about_center(transform, image.size, 0.94 + mouth_curve * 0.06, 0.72 + mouth_curve * 0.28)
        elif role == "mouth_closed":
            transform = scale_about_center(transform, image.size, 1.0, 1.0 - mouth_curve * 0.08)

        if role == "iris":
            gaze_visibility = 1.0 - blink_curve
            transform["x"] += gaze_x * float(layer.get("eye_limit_x", 0.0)) * gaze_visibility
            transform["y"] += gaze_y * float(layer.get("eye_limit_y", 0.0)) * gaze_visibility

        opacity = role_opacity(role, blink_value, mouth_value) * transform["opacity"]
        if opacity <= 0.001:
            continue
        width = max(1, round(image.width * transform["scale_x"]))
        height = max(1, round(image.height * transform["scale_y"]))
        image = image.resize((width, height), Image.Resampling.LANCZOS)
        x, y = transform["x"], transform["y"]
        rotation = transform["rotation"]
        if rotation:
            old_size = image.size
            image = image.rotate(-rotation, Image.Resampling.BICUBIC, expand=True)
            x -= (image.width - old_size[0]) * 0.5
            y -= (image.height - old_size[1]) * 0.5
        if opacity < 1.0:
            image.putalpha(image.getchannel("A").point(lambda value: round(value * opacity)))
        prepared.append((float(layer.get("z", 0.0)) + transform["z"], index, image, (round(x), round(y))))

    for _, _, image, position in sorted(prepared):
        base.alpha_composite(image, position)
    return base


def main() -> None:
    spec = json.loads((CHARACTER / "character.json").read_text(encoding="utf-8"))
    expressions = ("neutral", "happy", "unamused", "surprised")
    states = ((0.0, 0.0, "idle"), (1.0, 0.0, "talk"), (0.0, 1.0, "blink"))
    card_width, card_height = 256, 404
    matrix = Image.new("RGB", (card_width * len(expressions), card_height * len(states) * 2), (28, 30, 39))
    draw = ImageDraw.Draw(matrix)
    for outfit_index, outfit in enumerate(("casual", "cos")):
        for state_index, (mouth, blink, state_name) in enumerate(states):
            row = outfit_index * len(states) + state_index
            for column, expression in enumerate(expressions):
                frame = compose(spec, outfit, expression, mouth_amount=mouth, blink_amount=blink)
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
        for state_index, (mouth, blink, state_name) in enumerate(states):
            row = outfit_index * len(states) + state_index
            for column, expression in enumerate(expressions):
                frame = compose(spec, outfit, expression, mouth_amount=mouth, blink_amount=blink)
                face = frame.crop((340, 35, 680, 315)).resize((face_width, face_height - 24), Image.Resampling.LANCZOS)
                cell = Image.new("RGB", face.size, (42, 45, 55))
                cell.paste(face, mask=face.getchannel("A"))
                faces.paste(cell, (column * face_width, row * face_height + 24))
                face_draw.text((column * face_width + 7, row * face_height + 6), f"{outfit} / {expression} / {state_name}", fill=(235, 237, 248))
    face_destination = REPORTS / "modular_face_matrix.png"
    faces.save(face_destination, optimize=True)
    print(face_destination)


if __name__ == "__main__":
    main()
