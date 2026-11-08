#!/usr/bin/env python3
"""Assemble the Sanjeevani Vann R07 five-minute architectural film.

The film uses Blender renders, verified site photographs and climate-analysis
boards. Motion is limited to slow optical zooms/pans; there is no shake or
vibration. Narration and music are mixed into the final MP4.
"""
from __future__ import annotations

import json
import math
import os
import shlex
import subprocess
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

OUT = Path(os.environ.get("SV_OUTPUT", "outputs")).resolve()
RENDERS = OUT / "renders"
SITE = OUT / "site_photos"
FILM = OUT / "film"
FILM.mkdir(parents=True, exist_ok=True)

FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H, FPS = 1920, 1080, 30
SCENE_DURATION = 12.0


def run(cmd: list[str]) -> None:
    print("+", " ".join(shlex.quote(x) for x in cmd), flush=True)
    subprocess.run(cmd, check=True)


def title_frame(path: Path, title: str, subtitle: str, kicker: str, closing: bool = False) -> None:
    image = Image.new("RGB", (W, H), "#071B15")
    draw = ImageDraw.Draw(image)
    gold = "#C8A85B"
    white = "#F4F0E4"
    muted = "#B9C8BF"
    draw.rectangle((0, 0, W, H), fill="#071B15")
    # Layered horizon motif.
    for i in range(7):
        y = 730 + i * 24
        draw.line((0, y, W, y - 180), fill=(24 + i*4, 63 + i*5, 48 + i*3), width=16)
    draw.text((110, 110), kicker.upper(), font=ImageFont.truetype(FONT_BOLD, 28), fill=gold)
    draw.text((105, 250), title, font=ImageFont.truetype(FONT_BOLD, 88 if not closing else 76), fill=white)
    draw.multiline_text((110, 390), subtitle, font=ImageFont.truetype(FONT_REG, 35), fill=muted, spacing=16)
    draw.line((110, 700, 740, 700), fill=gold, width=3)
    credit = "DESIGNED BY AERONOVA CONSULTANTS · ARCHITECT GAURAV VATSA"
    draw.text((110, 830), credit, font=ImageFont.truetype(FONT_BOLD, 22), fill=white)
    draw.text((110, 890), "LOD300-EQUIVALENT CONCEPT · SURVEY AND APPROVALS REQUIRED", font=ImageFont.truetype(FONT_REG, 18), fill=muted)
    image.save(path, quality=95)


def fit_caption(text: str) -> str:
    return text.replace("'", "’").replace(":", "\\:")


def scene_segment(image: Path, output: Path, caption: str, index: int, duration: float = SCENE_DURATION) -> None:
    frames = int(duration * FPS)
    # Alternate between slow push-in, pull-out and lateral drift.
    if index % 3 == 0:
        z = "min(zoom+0.00032,1.115)"
        x = "iw/2-(iw/zoom/2)+0.08*(iw-iw/zoom)*on/{frames}"
        y = "ih/2-(ih/zoom/2)"
    elif index % 3 == 1:
        z = "if(eq(on,0),1.11,max(zoom-0.00030,1.0))"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)-0.05*(ih-ih/zoom)*on/{frames}"
    else:
        z = "min(zoom+0.00027,1.10)"
        x = "iw/2-(iw/zoom/2)-0.08*(iw-iw/zoom)*on/{frames}"
        y = "ih/2-(ih/zoom/2)"
    x = x.format(frames=frames)
    y = y.format(frames=frames)
    caption = fit_caption(caption)
    vf = (
        "scale=3840:2160:force_original_aspect_ratio=increase,"
        "crop=3840:2160,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={W}x{H}:fps={FPS},"
        "format=yuv420p,"
        f"drawbox=x=0:y=h-164:w=w:h=164:color=0x061913@0.73:t=fill,"
        f"drawtext=fontfile={FONT_BOLD}:text='{caption}':x=72:y=h-108:fontsize=38:fontcolor=white:"
        "shadowx=2:shadowy=2:shadowcolor=black@0.45,"
        f"fade=t=in:st=0:d=0.65,fade=t=out:st={duration-0.7:.2f}:d=0.7"
    )
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(image),
        "-t", f"{duration:.3f}", "-vf", vf, "-an", "-c:v", "libx264", "-preset", "medium",
        "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS), str(output),
    ])


def ensure_images() -> list[tuple[Path, str]]:
    opening = FILM / "00_opening.png"
    closing = FILM / "99_closing.png"
    title_frame(opening, "SANJEEVANI VANN", "Forest wellness, active living and restorative architecture\nA five-minute R07 architectural vision", "Address 01")
    title_frame(closing, "WHERE NATURE BECOMES INFRASTRUCTURE", "A concept-stage development proposal for feasibility, coordination and investor discussion", "Sanjeevani Vann", closing=True)

    sequence = [
        (opening, "Sanjeevani Vann · R07 architectural vision"),
        (SITE / "actual_site_5.png", "The existing teak-forest setting and lower-field landscape"),
        (SITE / "actual_site_6.png", "A real site shaped by water, vegetation and seasonal light"),
        (RENDERS / "01_master_aerial_south.png", "Coordinated two-parcel masterplan and continuous serpentine road"),
        (RENDERS / "02_master_aerial_reverse.png", "Eighteen villas, long-stay living, wellness, sports and productive landscape"),
        (RENDERS / "14_plan_orthographic.png", "R07 plan view · roads, dual walkways, drainage, buildings and lake"),
        (RENDERS / "03_lower_field_arrival.png", "Lower-field entrance, gatehouse, shaded arrival and surface parking"),
        (RENDERS / "04_serpentine_road_walk.png", "Slow road, planted shoulders, swales and pedestrian walks on both sides"),
        (OUT / "climate_01_temperature_rainfall.png", "Regional climate proxy · hot summer, strong monsoon, mild dry winter"),
        (OUT / "climate_02_solar_wind_sunpath.png", "Solar exposure and seasonal air movement guide orientation and shade"),
        (OUT / "climate_03_design_responses.png", "Deep roofs, cross-ventilation, rain capture and a cool planted realm"),
        (RENDERS / "07_wellness_consultation.png", "Wellness consultation, nutrition, first aid and private therapy rooms"),
        (RENDERS / "08_physio_active_living.png", "Physio, gym, mobility, strength and outdoor active-living circuits"),
        (RENDERS / "09_van_nivas.png", "Van Nivas · twenty-four studios with shaded balconies and daylit circulation"),
        (RENDERS / "05_villa_cluster.png", "Forest pavilion villas step with the terrain and preserve mature tree cover"),
        (RENDERS / "06_villa_close.png", "Stone, timber, glass, deep verandahs and adaptable single-level living"),
        (SITE / "actual_site_7.png", "Architecture is developed around the real forest rather than imposed upon it"),
        (RENDERS / "10_clubhouse_arrival.png", "The lakeside clubhouse becomes the social heart of the campus"),
        (RENDERS / "11_waterfront_terraces.png", "Accessible terraces, restrained steps, shaded decks and small gravity cascades"),
        (RENDERS / "12_sports_farms.png", "Tennis, basketball, mini-golf, herb farms and active gardens"),
        (RENDERS / "13_herb_gardens.png", "Medicinal herbs, organic food, nursery and teaching landscape"),
        (SITE / "actual_site_8.png", "Waterfront interventions remain subject to hydrology and high-water verification"),
        (RENDERS / "15_golden_hour_aerial.png", "Golden-hour view of a low-density campus integrated with the forest"),
        (RENDERS / "16_clubhouse_night.png", "Warm low-level lighting protects the dark habitat and seasonal firefly experience"),
        (closing, "Designed by Aeronova Consultants · led by Architect Gaurav Vatsa"),
    ]
    missing = [str(p) for p, _ in sequence if not p.exists()]
    if missing:
        raise FileNotFoundError("Missing film sources:\n" + "\n".join(missing))
    return sequence


def main() -> None:
    sequence = ensure_images()
    segment_files = []
    for i, (image, caption) in enumerate(sequence):
        segment = FILM / f"segment_{i:02d}.mp4"
        scene_segment(image, segment, caption, i)
        segment_files.append(segment)

    concat_list = FILM / "concat.txt"
    concat_list.write_text("\n".join(f"file '{p.name}'" for p in segment_files) + "\n", encoding="utf-8")
    silent = FILM / "Sanjeevani_Vann_R07_5min_Silent.mp4"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", str(silent),
    ])

    narration = Path(os.environ["SV_NARRATION"])
    music = Path(os.environ["SV_MUSIC"])
    final = OUT / "Sanjeevani_Vann_R07_5min_Architectural_Film_1080p.mp4"
    audio_filter = (
        "[1:a]volume=1.0,apad=pad_dur=300[voice];"
        "[2:a]volume=0.12,afade=t=in:st=0:d=3,afade=t=out:st=294:d=6[music];"
        "[voice][music]amix=inputs=2:duration=longest:dropout_transition=4,"
        "alimiter=limit=0.95[aout]"
    )
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(silent),
        "-i", str(narration), "-stream_loop", "-1", "-i", str(music),
        "-filter_complex", audio_filter, "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", "300", "-movflags", "+faststart", str(final),
    ])

    web = OUT / "Sanjeevani_Vann_R07_5min_Architectural_Film_Web_720p.mp4"
    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(final),
        "-vf", "scale=-2:720", "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(web),
    ])

    probe = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate",
        "-show_entries", "stream=index,codec_type,codec_name,width,height,sample_rate,channels",
        "-of", "json", str(final),
    ], text=True)
    (OUT / "film_probe.json").write_text(probe, encoding="utf-8")
    print(probe)


if __name__ == "__main__":
    main()
