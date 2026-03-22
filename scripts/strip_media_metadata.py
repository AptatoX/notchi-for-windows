from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageSequence
from PIL.PngImagePlugin import PngInfo


ROOT = Path(__file__).resolve().parent.parent
EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}


def iter_media_files() -> list[Path]:
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in EXTENSIONS
    )


def strip_png_like(path: Path) -> None:
    with Image.open(path) as image:
        converted = image.convert("RGBA")
        clean = Image.new("RGBA", converted.size)
        clean.paste(converted)
        suffix = path.suffix.lower()
        if suffix == ".png":
            clean.save(path, pnginfo=PngInfo(), icc_profile=None)
        elif suffix == ".ico":
            clean.save(path)
        else:
            clean.save(path)


def strip_gif(path: Path) -> None:
    with Image.open(path) as image:
        frames = []
        durations: list[int] = []
        for frame in ImageSequence.Iterator(image):
            durations.append(frame.info.get("duration", 100))
            frames.append(frame.convert("RGBA"))

        if not frames:
            return

        palette_frames = [frame.convert("P", palette=Image.Palette.ADAPTIVE) for frame in frames]
        palette_frames[0].save(
            path,
            save_all=True,
            append_images=palette_frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
        )


def main() -> None:
    for path in iter_media_files():
        suffix = path.suffix.lower()
        if suffix == ".gif":
            strip_gif(path)
        else:
            strip_png_like(path)
        print(path)


if __name__ == "__main__":
    main()
