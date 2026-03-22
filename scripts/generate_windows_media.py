from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
ASSET_ROOT = ROOT / "notchi" / "notchi" / "Assets.xcassets"
OUTPUT_GIF = ROOT / "assets" / "windows-mascots.gif"

CANVAS_SIZE = (760, 300)
SPRITE_SCALE = 2.2
SCENE_FRAMES = 12
FRAME_DURATION_MS = 120

SCENES = [
    {
        "state": "working",
        "emotion": "happy",
        "title": "Happy",
        "subtitle": "Claude is actively working on a change",
        "accent": "#f59e0b",
    },
    {
        "state": "idle",
        "emotion": "sad",
        "title": "Sad",
        "subtitle": "A broken prompt leaves the mascot discouraged",
        "accent": "#60a5fa",
    },
    {
        "state": "waiting",
        "emotion": "neutral",
        "title": "Waiting",
        "subtitle": "The session pauses for permission or input",
        "accent": "#34d399",
    },
    {
        "state": "sleeping",
        "emotion": "neutral",
        "title": "Sleeping",
        "subtitle": "Long idle sessions slowly drift to sleep",
        "accent": "#c084fc",
    },
]


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        path = Path(candidate)
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _sprite_name_for(state: str, emotion: str) -> str:
    options = [f"{state}_{emotion}"]
    if emotion == "sob":
        options.append(f"{state}_sad")
    options.append(f"{state}_neutral")
    for name in options:
        if (ASSET_ROOT / f"{name}.imageset" / "sprite_sheet.png").exists():
            return name
    return f"{state}_neutral"


def _load_frame(state: str, emotion: str, frame_index: int) -> Image.Image:
    sprite_name = _sprite_name_for(state, emotion)
    path = ASSET_ROOT / f"{sprite_name}.imageset" / "sprite_sheet.png"
    sheet = Image.open(path).convert("RGBA")
    columns = 5 if state == "compacting" else 6
    frame_width = sheet.width // columns
    frame = sheet.crop((frame_index * frame_width, 0, (frame_index + 1) * frame_width, sheet.height))
    alpha_box = frame.getchannel("A").getbbox()
    if alpha_box is not None:
        left, top, right, bottom = alpha_box
        frame = frame.crop((max(0, left - 2), max(0, top - 2), min(frame.width, right + 2), min(frame.height, bottom + 2)))
    scaled_size = (max(48, int(frame.width * SPRITE_SCALE)), max(48, int(frame.height * SPRITE_SCALE)))
    return frame.resize(scaled_size, Image.Resampling.NEAREST)


def _background(accent: str) -> Image.Image:
    width, height = CANVAS_SIZE
    image = Image.new("RGBA", CANVAS_SIZE, "#08111f")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width, height), fill="#08111f")
    draw.ellipse((-140, -80, 240, 240), fill="#0e2640")
    draw.ellipse((width - 280, 20, width + 40, 250), fill="#132d2d")
    draw.rounded_rectangle((24, 22, width - 24, height - 22), radius=28, outline="#20304a", width=2, fill="#0b1526")
    draw.rounded_rectangle((40, 40, 210, 74), radius=17, fill=accent)
    draw.rounded_rectangle((220, 40, width - 40, 74), radius=17, fill="#101c31")
    return image


def _draw_grass_band(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    left = 176
    right = width - 176
    base_y = height - 62
    draw.ellipse((left + 26, base_y - 2, right - 26, base_y + 18), fill="#0b1020")
    draw.ellipse((left, base_y - 16, right, base_y + 10), fill="#5d7c67")
    draw.ellipse((left + 12, base_y - 18, right - 12, base_y - 4), fill="#86a390")


def _draw_scene_labels(draw: ImageDraw.ImageDraw, scene: dict[str, str]) -> None:
    title_font = _font(18, bold=True)
    subtitle_font = _font(16)
    label_font = _font(32, bold=True)
    small_font = _font(14)

    draw.text((58, 46), "Notchi for Windows", fill="#f8fafc", font=title_font)
    draw.text((236, 48), "Animated Claude Code companion for Windows", fill="#8fb2d8", font=subtitle_font)
    draw.text((58, 100), scene["title"], fill="#ffffff", font=label_font)
    draw.text((58, 146), scene["subtitle"], fill="#b9c8dc", font=subtitle_font)

    chips = ["happy", "sad", "waiting", "sleeping"]
    x = 58
    for chip in chips:
        active = chip == scene["title"].lower()
        fill = scene["accent"] if active else "#101c31"
        text_fill = "#0b1526" if active else "#94a3b8"
        chip_width = 96 if chip != "sleeping" else 108
        draw.rounded_rectangle((x, 196, x + chip_width, 226), radius=15, fill=fill)
        draw.text((x + 18, 202), chip.title(), fill=text_fill, font=small_font)
        x += chip_width + 10


def _compose_frame(scene: dict[str, str], frame_index: int) -> Image.Image:
    image = _background(scene["accent"])
    draw = ImageDraw.Draw(image)
    _draw_scene_labels(draw, scene)
    _draw_grass_band(draw, *CANVAS_SIZE)

    frame_count = 5 if scene["state"] == "compacting" else 6
    sprite = _load_frame(scene["state"], scene["emotion"], frame_index % frame_count)
    bob_amplitude = {
        "working": 7,
        "idle": 4,
        "waiting": 3,
        "sleeping": 1,
    }.get(scene["state"], 3)
    bob = ((frame_index % 6) - 2.5) * bob_amplitude / 6
    sprite_x = 560
    sprite_y = 184 + int(bob)
    image.alpha_composite(sprite, (int(sprite_x - sprite.width / 2), int(sprite_y - sprite.height / 2)))
    return image


def build_gif() -> None:
    frames: list[Image.Image] = []
    for scene in SCENES:
        for frame_index in range(SCENE_FRAMES):
            frames.append(_compose_frame(scene, frame_index).convert("P", palette=Image.Palette.ADAPTIVE))

    OUTPUT_GIF.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=frames[1:],
        duration=FRAME_DURATION_MS,
        loop=0,
        disposal=2,
    )


if __name__ == "__main__":
    build_gif()
