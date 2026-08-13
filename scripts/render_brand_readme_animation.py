"""Render the README-safe BIMChange-Agent logo evolution animation.

The renderer is deterministic and derives every frame from the checked-in brand
asset. It never calls a model or reads project data.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    ROOT
    / "src"
    / "bimchange_agent"
    / "resources"
    / "branding"
    / "bimchange-app-icon.png"
)
DEFAULT_OUTPUT = ROOT / "docs" / "assets" / "brand" / "bimchange-logo-evolution.gif"


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def smoothstep(value: float) -> float:
    value = clamp(value)
    return value * value * (3.0 - 2.0 * value)


def ease_out_cubic(value: float) -> float:
    value = clamp(value)
    return 1.0 - (1.0 - value) ** 3


def ease_out_back(value: float) -> float:
    value = clamp(value)
    overshoot = 1.70158
    shifted = value - 1.0
    return 1.0 + (overshoot + 1.0) * shifted**3 + overshoot * shifted**2


def scaled_polygon(points: list[tuple[int, int]], size: tuple[int, int]) -> list[tuple[int, int]]:
    sx = size[0] / 1024.0
    sy = size[1] / 1024.0
    return [(round(x * sx), round(y * sy)) for x, y in points]


def geometric_masks(size: tuple[int, int]) -> tuple[Image.Image, Image.Image, Image.Image]:
    """Return anti-aliased masks for the lower model, callout, and connectors."""

    scale = 4
    hi_size = (size[0] * scale, size[1] * scale)

    lower = Image.new("L", hi_size, 0)
    lower_draw = ImageDraw.Draw(lower)
    lower_points = [
        (225, 570),
        (355, 490),
        (620, 510),
        (790, 610),
        (785, 735),
        (615, 870),
        (345, 810),
        (235, 715),
    ]
    lower_draw.polygon(
        scaled_polygon(lower_points, hi_size),
        fill=255,
    )

    callout = Image.new("L", hi_size, 0)
    callout_draw = ImageDraw.Draw(callout)
    sx = hi_size[0] / 1024.0
    sy = hi_size[1] / 1024.0
    callout_draw.ellipse(
        (round(631 * sx), round(94 * sy), round(820 * sx), round(292 * sy)),
        fill=255,
    )
    callout_draw.polygon(
        scaled_polygon([(678, 246), (757, 249), (703, 326), (657, 346)], hi_size),
        fill=255,
    )
    callout_draw.ellipse(
        (round(660 * sx), round(298 * sy), round(708 * sx), round(346 * sy)),
        fill=255,
    )

    connectors = Image.new("L", hi_size, 0)
    connector_draw = ImageDraw.Draw(connectors)
    connector_draw.rounded_rectangle(
        (round(334 * sx), round(454 * sy), round(386 * sx), round(674 * sy)),
        radius=round(18 * sx),
        fill=255,
    )
    connector_draw.rounded_rectangle(
        (round(620 * sx), round(449 * sy), round(672 * sx), round(690 * sy)),
        radius=round(18 * sx),
        fill=255,
    )

    return tuple(
        mask.resize(size, Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(0.45))
        for mask in (lower, callout, connectors)
    )


def extract_layers(source: Image.Image) -> dict[str, Image.Image]:
    alpha = source.getchannel("A")
    lower_shape, callout_shape, connector_shape = geometric_masks(source.size)

    lower_mask = ImageChops.multiply(alpha, lower_shape)
    callout_mask = ImageChops.multiply(alpha, callout_shape)

    bright = Image.new("L", source.size, 0)
    src_px = source.load()
    bright_px = bright.load()
    for y in range(source.height):
        for x in range(source.width):
            r, g, b, a = src_px[x, y]
            if a > 0 and r > 205 and g > 205 and b > 205:
                bright_px[x, y] = a
    connector_mask = ImageChops.multiply(bright, connector_shape)

    excluded = ImageChops.lighter(lower_mask, callout_mask)
    excluded = ImageChops.lighter(excluded, connector_mask)
    top_mask = ImageChops.subtract(alpha, excluded)

    def with_mask(mask: Image.Image) -> Image.Image:
        layer = source.copy()
        layer.putalpha(mask)
        return layer

    return {
        "top": with_mask(top_mask),
        "lower": with_mask(lower_mask),
        "callout": with_mask(callout_mask),
        "connectors": with_mask(connector_mask),
    }


def neutralize_orange(image: Image.Image) -> Image.Image:
    result = image.copy()
    pixels = result.load()
    for y in range(result.height):
        for x in range(result.width):
            r, g, b, a = pixels[x, y]
            if a == 0:
                continue
            warm_delta = r - max(g, b)
            orange_weight = clamp((warm_delta - 5) / 48.0)
            orange_weight *= clamp((r - 62) / 105.0)
            if r > 92 and r > g * 1.12 and r > b * 1.08:
                orange_weight = max(orange_weight, 0.94)
            if orange_weight <= 0:
                continue
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            target = (
                int(clamp(luminance * 0.82 + 76, 0, 246)),
                int(clamp(luminance * 0.82 + 74, 0, 244)),
                int(clamp(luminance * 0.80 + 72, 0, 240)),
            )
            pixels[x, y] = tuple(
                round(channel * (1.0 - orange_weight) + neutral * orange_weight)
                for channel, neutral in zip((r, g, b), target)
            ) + (a,)
    return result


def set_opacity(image: Image.Image, opacity: float) -> Image.Image:
    opacity = clamp(opacity)
    result = image.copy()
    result.putalpha(result.getchannel("A").point(lambda value: round(value * opacity)))
    return result


def scale_about_anchor(
    image: Image.Image,
    scale: float,
    anchor: tuple[int, int],
) -> tuple[Image.Image, tuple[int, int]]:
    scale = max(0.01, scale)
    width = max(1, round(image.width * scale))
    height = max(1, round(image.height * scale))
    resized = image.resize((width, height), Image.Resampling.LANCZOS)
    x = round(anchor[0] - anchor[0] * scale)
    y = round(anchor[1] - anchor[1] * scale)
    return resized, (x, y)


def make_background(size: tuple[int, int]) -> Image.Image:
    top = (239, 239, 235)
    bottom = (218, 221, 219)
    background = Image.new("RGB", size)
    draw = ImageDraw.Draw(background)
    for y in range(size[1]):
        t = y / max(1, size[1] - 1)
        color = tuple(round(a * (1.0 - t) + b * t) for a, b in zip(top, bottom))
        draw.line((0, y, size[0], y), fill=color)

    vignette = Image.new("L", size, 0)
    vignette_draw = ImageDraw.Draw(vignette)
    margin_x = round(size[0] * 0.08)
    margin_y = round(size[1] * 0.04)
    vignette_draw.ellipse(
        (margin_x, margin_y, size[0] - margin_x, size[1] * 1.22),
        fill=52,
    )
    vignette = vignette.filter(ImageFilter.GaussianBlur(round(size[1] * 0.12)))
    soft_white = Image.new("RGB", size, (255, 255, 252))
    return Image.composite(soft_white, background, vignette)


def load_brand_font(font_path: Path | None, size: int) -> ImageFont.FreeTypeFont:
    candidates = [
        font_path,
        Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path("DejaVuSans-Bold.ttf"),
    ]
    for candidate in candidates:
        if candidate is None:
            continue
        try:
            return ImageFont.truetype(str(candidate), size)
        except OSError:
            continue
    raise RuntimeError("No suitable bold TrueType font was found.")


def build_wordmark_mask(
    canvas_size: tuple[int, int],
    text: str,
    left: int,
    font_path: Path | None,
) -> tuple[Image.Image, int, int, int, int]:
    max_width = canvas_size[0] - left - round(canvas_size[0] * 0.035)
    font_size = round(canvas_size[1] * 0.20)
    while font_size >= 34:
        font = load_brand_font(font_path, font_size)
        probe = ImageDraw.Draw(Image.new("L", (1, 1)))
        bbox = probe.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            break
        font_size -= 2
    else:
        raise RuntimeError("The wordmark does not fit the requested canvas.")

    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    text_y = round((canvas_size[1] - text_height) / 2 - bbox[1])
    mask = Image.new("L", canvas_size, 0)
    ImageDraw.Draw(mask).text((left, text_y), text, font=font, fill=255)
    return mask, left, text_y + bbox[1], text_width, text_height


def horizontal_reveal_mask(
    size: tuple[int, int],
    left: int,
    width: int,
    progress: float,
) -> Image.Image:
    progress = clamp(progress)
    cutoff = left + width * progress
    feather = max(3, round(size[1] * 0.018))
    mask = Image.new("L", size, 0)
    pixels = mask.load()
    solid_end = cutoff - feather
    for x in range(max(0, left), min(size[0], math.ceil(cutoff + 1))):
        if x <= solid_end:
            value = 255
        else:
            value = round(255 * clamp((cutoff - x) / feather))
        for y in range(size[1]):
            pixels[x, y] = value
    return mask


def render_frames(
    source: Image.Image,
    canvas_size: tuple[int, int],
    wordmark: str,
    font_path: Path | None,
) -> list[Image.Image]:
    if canvas_size[0] < 900:
        raise ValueError("Composite logo animation width must be at least 900 pixels.")

    layers = extract_layers(source)
    top_neutral = neutralize_orange(layers["top"])
    lower_neutral = neutralize_orange(layers["lower"])

    logo_stage_width = round(canvas_size[0] * 0.43)
    logo_extent = min(round(canvas_size[1] * 0.92), round(logo_stage_width * 0.82))
    render_size = (logo_extent, logo_extent)
    resized = {
        name: image.resize(render_size, Image.Resampling.LANCZOS)
        for name, image in {
            **layers,
            "top_neutral": top_neutral,
            "lower_neutral": lower_neutral,
            "source": source,
        }.items()
    }

    base_x = (logo_stage_width - logo_extent) // 2
    base_y = (canvas_size[1] - logo_extent) // 2 - round(canvas_size[1] * 0.01)
    # In the opening pose both revision layers must read as one complete,
    # two-level building: the dark lower model stays visible as its base.
    # A modest overlap closes the final gap without hiding the lower level.
    collapse = round(logo_extent * 0.082)
    anchor = (round(logo_extent * 0.67), round(logo_extent * 0.32))
    background = make_background(canvas_size)
    wordmark_left = logo_stage_width + round(canvas_size[0] * 0.025)
    wordmark_mask, text_x, text_y, text_width, text_height = build_wordmark_mask(
        canvas_size,
        wordmark,
        wordmark_left,
        font_path,
    )
    frames: list[Image.Image] = []

    for index in range(96):
        canvas = background.convert("RGBA")

        if index < 8:
            intro = smoothstep(index / 7.0)
        else:
            intro = 1.0

        split = ease_out_cubic((index - 18) / 24.0)
        color_change = smoothstep((index - 42) / 16.0)
        bubble_t = clamp((index - 58) / 14.0)

        if index >= 89:
            outro = 1.0 - smoothstep((index - 89) / 6.0)
        else:
            outro = 1.0

        overall_opacity = intro * outro
        top_y = round(base_y + collapse * (1.0 - split))
        lower_y = round(base_y - collapse * (1.0 - split))

        shadow = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow)
        shadow_width = round(logo_extent * (0.34 + 0.08 * split))
        shadow_height = round(logo_extent * 0.055)
        shadow_cx = logo_stage_width // 2
        shadow_cy = round(base_y + logo_extent * (0.72 + 0.10 * split))
        shadow_draw.ellipse(
            (
                shadow_cx - shadow_width,
                shadow_cy - shadow_height,
                shadow_cx + shadow_width,
                shadow_cy + shadow_height,
            ),
            fill=(38, 43, 42, round(32 * overall_opacity)),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(round(logo_extent * 0.035)))
        canvas.alpha_composite(shadow)

        # Never fade the lower model in. It is already part of the opening
        # building and moves downward while the upper model moves upward.
        lower_opacity = overall_opacity
        if lower_opacity > 0:
            canvas.alpha_composite(
                set_opacity(resized["lower_neutral"], lower_opacity),
                (base_x, lower_y),
            )

        top_neutral_opacity = overall_opacity * (1.0 - color_change)
        top_color_opacity = overall_opacity * color_change
        if top_neutral_opacity > 0:
            canvas.alpha_composite(
                set_opacity(resized["top_neutral"], top_neutral_opacity),
                (base_x, top_y),
            )
        if top_color_opacity > 0:
            canvas.alpha_composite(
                set_opacity(resized["top"], top_color_opacity),
                (base_x, top_y),
            )

        connector_opacity = overall_opacity * smoothstep((split - 0.32) / 0.68)
        if connector_opacity > 0:
            canvas.alpha_composite(
                set_opacity(resized["connectors"], connector_opacity),
                (base_x, base_y),
            )

        if bubble_t > 0:
            bubble_scale = 0.18 + 0.82 * ease_out_back(bubble_t)
            bubble_scale = min(bubble_scale, 1.08)
            bubble_layer, offset = scale_about_anchor(resized["callout"], bubble_scale, anchor)
            bubble_opacity = overall_opacity * smoothstep(bubble_t * 1.6)
            canvas.alpha_composite(
                set_opacity(bubble_layer, bubble_opacity),
                (base_x + offset[0], base_y + offset[1]),
            )

        exact_final = smoothstep((index - 69) / 8.0) * overall_opacity
        if exact_final > 0:
            canvas.alpha_composite(
                set_opacity(resized["source"], exact_final),
                (base_x, base_y),
            )

        # The wordmark follows the same narrative rhythm as the logo. It starts
        # after separation begins, finishes as the evidence marker settles, and
        # then changes from construction orange to the final neutral black.
        word_reveal = smoothstep((index - 25) / 43.0)
        word_complete = smoothstep((index - 68) / 10.0)
        reveal_mask = horizontal_reveal_mask(
            canvas_size,
            text_x,
            text_width,
            word_reveal,
        )
        visible_text_mask = ImageChops.multiply(wordmark_mask, reveal_mask)
        visible_text_mask = visible_text_mask.point(
            lambda value: round(value * overall_opacity)
        )

        if 0.0 < word_reveal < 1.0:
            lead_x = round(text_x + text_width * word_reveal)
            glow = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            glow_draw.rounded_rectangle(
                (
                    lead_x - round(canvas_size[1] * 0.012),
                    text_y - round(canvas_size[1] * 0.045),
                    lead_x + round(canvas_size[1] * 0.012),
                    text_y + text_height + round(canvas_size[1] * 0.045),
                ),
                radius=round(canvas_size[1] * 0.012),
                fill=(221, 82, 42, round(58 * overall_opacity)),
            )
            canvas.alpha_composite(
                glow.filter(ImageFilter.GaussianBlur(round(canvas_size[1] * 0.024)))
            )

        orange_layer = Image.new("RGBA", canvas_size, (220, 78, 39, 0))
        orange_layer.putalpha(
            visible_text_mask.point(lambda value: round(value * (1.0 - word_complete)))
        )
        black_layer = Image.new("RGBA", canvas_size, (31, 33, 32, 0))
        black_layer.putalpha(
            visible_text_mask.point(lambda value: round(value * word_complete))
        )
        canvas.alpha_composite(orange_layer)
        canvas.alpha_composite(black_layer)

        frames.append(canvas.convert("RGB"))

    return frames


def global_palette(frames: list[Image.Image]) -> Image.Image:
    sample_indices = [0, 12, 24, 36, 48, 60, 70, 80]
    thumb_size = (160, 105)
    sheet = Image.new("RGB", (thumb_size[0] * 4, thumb_size[1] * 2))
    for slot, frame_index in enumerate(sample_indices):
        thumb = frames[frame_index].resize(thumb_size, Image.Resampling.LANCZOS)
        sheet.paste(thumb, ((slot % 4) * thumb_size[0], (slot // 4) * thumb_size[1]))
    return sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)


def save_contact_sheet(frames: list[Image.Image], path: Path) -> None:
    indices = [10, 20, 32, 44, 54, 64, 72, 82]
    thumb_width = 320
    thumb_height = round(thumb_width * frames[0].height / frames[0].width)
    sheet = Image.new("RGB", (thumb_width * 4, thumb_height * 2), (232, 233, 230))
    for slot, frame_index in enumerate(indices):
        thumb = frames[frame_index].resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        sheet.paste(thumb, ((slot % 4) * thumb_width, (slot // 4) * thumb_height))
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, optimize=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--poster", type=Path)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--width", type=int, default=1120)
    parser.add_argument("--height", type=int, default=360)
    parser.add_argument("--wordmark", default="BIMChange-Agent")
    parser.add_argument("--font", type=Path)
    args = parser.parse_args()

    source = Image.open(args.source).convert("RGBA")
    frames = render_frames(
        source,
        (args.width, args.height),
        args.wordmark,
        args.font,
    )
    palette = global_palette(frames)
    gif_frames = [
        frame.quantize(palette=palette, dither=Image.Dither.FLOYDSTEINBERG)
        for frame in frames
    ]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    gif_frames[0].save(
        args.output,
        save_all=True,
        append_images=gif_frames[1:],
        # A list lets Pillow fold visually identical hold frames while adding
        # their time to the retained frame instead of shortening the loop.
        duration=[50] * len(gif_frames),
        loop=0,
        optimize=False,
        disposal=2,
    )
    if args.poster:
        args.poster.parent.mkdir(parents=True, exist_ok=True)
        frames[80].save(args.poster, optimize=True)
    if args.contact_sheet:
        save_contact_sheet(frames, args.contact_sheet)

    print(f"animation={args.output}")
    if args.poster:
        print(f"poster={args.poster}")
    if args.contact_sheet:
        print(f"contact_sheet={args.contact_sheet}")
    print(f"frames={len(frames)} duration_ms={len(frames) * 50}")


if __name__ == "__main__":
    main()
