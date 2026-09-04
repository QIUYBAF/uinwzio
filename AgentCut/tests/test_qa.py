from pathlib import Path
from PIL import Image
from agentcut import Editor


def test_qa_warns_aggressive_camera(tmp_path):
    img = tmp_path / "a.png"
    Image.new("RGB", (640, 360), (0, 0, 0)).save(img)
    e = Editor.create(tmp_path / "p", width=640, height=360, fps=24)
    e.add_asset(img, asset_id="img")
    e.add_scene("img", 1.5, scene_id="s")
    e.set_camera("s", motion="slow_push", amount=0.12)
    qa = e.qa()
    assert any(i["code"] == "AGGRESSIVE_CAMERA" for i in qa["issues"])
