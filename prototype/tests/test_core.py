"""Minimal no-GPU tests. Run pytest -q from prototype."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from api import save_images

def test_tiff_zip_and_manifest():
    with TemporaryDirectory() as temp:
        folder = Path(temp)
        first = Image.new("RGBA", (32, 24), (255, 0, 0, 200))
        second = Image.new("RGBA", (32, 24), (0, 0, 255, 90))
        result = save_images(folder, [first, second], 300)
        assert result["dpi"] == 300
        assert len(result["layers"]) == 2
        assert (folder / "artwork.zip").exists()
        with Image.open(folder / "print_rgba.tif") as im:
            assert im.size == (32, 24)
        assert len(json.loads((folder / "manifest.json").read_text())["layers"]) == 2
