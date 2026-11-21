import json
from pathlib import Path

from skytripwire import openapi


def test_render_contains_api_paths() -> None:
    schema = json.loads(openapi.render())
    assert schema["info"]["title"] == "SkyTripwire"
    assert "/api/filters" in schema["paths"]
    assert "/api/channels/{channel_id}/test" in schema["paths"]


def test_main_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "openapi.json"
    openapi.main([str(target)])
    assert json.loads(target.read_text(encoding="utf-8"))["openapi"].startswith("3.")
