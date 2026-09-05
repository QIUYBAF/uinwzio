"""Inspect independent deployment capabilities without importing optional modules."""
import importlib.util
import shutil


def module_status():
    def available(name):
        return importlib.util.find_spec(name) is not None

    ffmpeg, ffprobe = bool(shutil.which("ffmpeg")), bool(shutil.which("ffprobe"))
    editor = available("numpy") and available("PIL")
    return {"core": {"ready": True, "python_dependencies": []},
            "roughcut": {"ready": ffmpeg and ffprobe, "ffmpeg": ffmpeg, "ffprobe": ffprobe,
                         "python_dependencies": [], "requires_gpu": False},
            "editor": {"ready": editor, "install": "python -m pip install -e './AgentCut[render]'"},
            "api": {"ready": editor and available("fastapi") and available("uvicorn"),
                    "install": "python -m pip install -e './AgentCut[api]'"},
            "optional_analyzers": {"interface": "agentcut.roughcut.Detector",
                                   "external_events": "JSON absolute start/end/score/label",
                                   "bundled_models": False}}
