#!/usr/bin/env python3
"""Regional climate analysis for Sanjeevani Vann R07.

Uses the Nagpur-Wardha region as a transparent proxy until certified site
coordinates and on-site weather data are available. NASA POWER climatology is
requested first; conservative fallback values are used when the API is not
reachable. Outputs are presentation graphics and a concise PDF.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import requests
from matplotlib.backends.backend_pdf import PdfPages

OUT = Path(os.environ.get("SV_OUTPUT", "outputs"))
OUT.mkdir(parents=True, exist_ok=True)
LAT = float(os.environ.get("SV_LAT", "21.1458"))
LON = float(os.environ.get("SV_LON", "79.0882"))
LOCATION = "Nagpur-Wardha regional proxy"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
DAYS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31], dtype=float)

FALLBACK = {
    "T2M": [20.2, 23.4, 28.2, 32.5, 35.0, 31.7, 27.7, 26.6, 27.0, 26.4, 22.4, 19.4],
    "T2M_MAX": [29.2, 32.5, 37.3, 41.1, 43.3, 38.0, 31.6, 30.2, 31.7, 32.8, 30.7, 29.1],
    "T2M_MIN": [11.2, 14.3, 19.1, 23.9, 26.7, 25.5, 23.8, 23.0, 22.3, 20.0, 14.1, 10.8],
    "PRECTOTCORR": [0.42, 0.64, 0.65, 0.50, 0.81, 6.33, 10.00, 9.19, 5.83, 1.77, 0.50, 0.32],
    "RH2M": [50, 43, 35, 29, 34, 60, 78, 82, 74, 55, 48, 52],
    "WS10M": [2.1, 2.4, 2.8, 3.2, 3.4, 4.1, 4.3, 3.8, 3.0, 2.4, 2.0, 1.9],
    "ALLSKY_SFC_SW_DWN": [5.1, 5.8, 6.4, 6.5, 6.2, 4.8, 4.0, 4.1, 4.7, 5.4, 5.2, 4.8],
}


def nasa_power() -> tuple[Dict[str, List[float]], str]:
    params = "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,RH2M,WS10M,ALLSKY_SFC_SW_DWN"
    url = (
        "https://power.larc.nasa.gov/api/temporal/climatology/point"
        f"?parameters={params}&community=RE&longitude={LON}&latitude={LAT}&format=JSON"
    )
    try:
        response = requests.get(url, timeout=45)
        response.raise_for_status()
        payload = response.json()
        raw = payload["properties"]["parameter"]
        out: Dict[str, List[float]] = {}
        for key in FALLBACK:
            source = raw.get(key, {})
            values = []
            for month in MONTHS:
                value = source.get(month.upper())
                if value is None or value == -999:
                    raise ValueError(f"Missing {key} {month}")
                values.append(float(value))
            out[key] = values
        return out, "NASA POWER climatology API"
    except Exception as exc:  # noqa: BLE001
        print(f"NASA POWER unavailable; using documented regional proxy fallback: {exc}")
        return {k: list(v) for k, v in FALLBACK.items()}, "regional proxy fallback"


def solar_position(day_of_year: int, hour: float) -> tuple[float, float]:
    """Approximate solar altitude and azimuth (degrees, azimuth from north)."""
    lat = math.radians(LAT)
    decl = math.radians(23.45 * math.sin(math.radians(360 * (284 + day_of_year) / 365)))
    hour_angle = math.radians(15 * (hour - 12))
    sin_alt = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(hour_angle)
    alt = math.asin(max(-1.0, min(1.0, sin_alt)))
    if alt <= 0:
        return math.degrees(alt), 0.0
    cos_az = (math.sin(decl) - math.sin(alt) * math.sin(lat)) / (math.cos(alt) * math.cos(lat))
    az = math.degrees(math.acos(max(-1.0, min(1.0, cos_az))))
    if hour < 12:
        az = 180 - az
    else:
        az = 180 + az
    return math.degrees(alt), az


def base_figure(title: str, subtitle: str):
    fig = plt.figure(figsize=(16, 9), dpi=120, facecolor="#F2F0E8")
    fig.text(0.055, 0.925, "SANJEEVANI VANN · CLIMATE ANALYSIS R07", fontsize=12, weight="bold", color="#9B7B39")
    fig.text(0.055, 0.855, title, fontsize=30, weight="bold", color="#0D392D")
    fig.text(0.055, 0.805, subtitle, fontsize=13, color="#50645C")
    fig.text(0.055, 0.035, "Regional proxy only · exact site coordinates, contours and microclimate require verification", fontsize=9, color="#6C746F")
    return fig


def make_boards(data: Dict[str, List[float]], source: str) -> Dict[str, str]:
    x = np.arange(12)
    temp = np.array(data["T2M"])
    tmax = np.array(data["T2M_MAX"])
    tmin = np.array(data["T2M_MIN"])
    rain = np.array(data["PRECTOTCORR"]) * DAYS
    rh = np.array(data["RH2M"])
    wind = np.array(data["WS10M"])
    solar = np.array(data["ALLSKY_SFC_SW_DWN"])

    files: Dict[str, str] = {}

    fig = base_figure(
        "Hot summer. Strong monsoon. Mild dry winter.",
        f"{LOCATION} at {LAT:.2f}°N, {LON:.2f}°E · {source}",
    )
    ax = fig.add_axes([0.07, 0.13, 0.56, 0.59])
    ax.fill_between(x, tmin, tmax, color="#D8CBA8", alpha=0.55, label="Daily min-max band")
    ax.plot(x, tmax, color="#A75330", linewidth=2.6, marker="o", label="Mean daily maximum")
    ax.plot(x, temp, color="#0D5A49", linewidth=3.2, marker="o", label="Monthly mean")
    ax.plot(x, tmin, color="#4B7893", linewidth=2.2, marker="o", label="Mean daily minimum")
    ax.set_xticks(x, MONTHS)
    ax.set_ylabel("Temperature °C")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, loc="upper left", ncol=2)
    ax2 = ax.twinx()
    ax2.bar(x, rain, width=0.58, color="#5A9BA0", alpha=0.38, label="Rainfall")
    ax2.set_ylabel("Monthly rainfall mm")
    ax2.set_ylim(0, max(350, rain.max() * 1.15))
    ax2.legend(frameon=False, loc="upper right")
    ax3 = fig.add_axes([0.68, 0.13, 0.27, 0.59])
    ax3.axis("off")
    metrics = [
        (f"{tmax.max():.0f}°C", "Peak monthly mean maximum"),
        (f"{rain.sum():.0f} mm", "Approximate annual rainfall"),
        (f"{rh.max():.0f}%", "Peak monthly relative humidity"),
        ("Jun-Sep", "Primary monsoon design period"),
    ]
    for i, (value, label) in enumerate(metrics):
        y = 0.93 - i * 0.22
        ax3.text(0.0, y, value, fontsize=28, weight="bold", color="#0D392D", transform=ax3.transAxes)
        ax3.text(0.0, y - 0.075, label, fontsize=11, color="#5A6B64", transform=ax3.transAxes)
    path = OUT / "climate_01_temperature_rainfall.png"
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    files["temperature_rainfall"] = path.name

    fig = base_figure(
        "Shade first. Capture rain. Use air movement carefully.",
        "Solar resource, humidity and wind-speed implications for architecture and landscape",
    )
    ax = fig.add_axes([0.07, 0.16, 0.52, 0.55])
    ax.plot(x, solar, color="#C58A25", marker="o", linewidth=3.2, label="Solar resource")
    ax.set_xticks(x, MONTHS)
    ax.set_ylabel("Solar irradiation kWh/m²/day")
    ax.set_ylim(0, max(7.2, solar.max() + 0.5))
    ax.grid(axis="y", alpha=0.22)
    ax2 = ax.twinx()
    ax2.plot(x, wind, color="#3B7D78", marker="s", linewidth=2.4, label="10 m wind speed")
    ax2.plot(x, rh / 20, color="#6D7797", linestyle="--", linewidth=2.0, label="Relative humidity ÷ 20")
    ax2.set_ylabel("Wind m/s · RH scaled")
    handles = ax.get_lines() + ax2.get_lines()
    ax.legend(handles, [h.get_label() for h in handles], frameon=False, loc="upper right")

    polar = fig.add_axes([0.66, 0.16, 0.29, 0.55], projection="polar")
    polar.set_theta_zero_location("N")
    polar.set_theta_direction(-1)
    for doy, label, colour in [(172, "21 Jun", "#B66532"), (80, "Equinox", "#A8863D"), (355, "21 Dec", "#4D7692")]:
        azimuths, radii = [], []
        for hour in np.linspace(5.5, 18.5, 80):
            altitude, azimuth = solar_position(doy, float(hour))
            if altitude > 0:
                azimuths.append(math.radians(azimuth))
                radii.append(90 - altitude)
        polar.plot(azimuths, radii, linewidth=2.5, label=label, color=colour)
    polar.set_rlim(90, 0)
    polar.set_rticks([15, 30, 45, 60, 75])
    polar.set_yticklabels(["75°", "60°", "45°", "30°", "15°"])
    polar.set_title("Approximate sun path", pad=20, color="#0D392D", weight="bold")
    polar.legend(frameon=False, bbox_to_anchor=(1.17, -0.02), loc="lower right")
    path = OUT / "climate_02_solar_wind_sunpath.png"
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    files["solar_wind"] = path.name

    fig = base_figure(
        "Climate becomes architecture.",
        "Preliminary passive-design priorities for the forest campus",
    )
    ax = fig.add_axes([0.055, 0.12, 0.89, 0.62])
    ax.axis("off")
    responses = [
        ("01", "Deep shade", "2.4-3.0 m verandahs, broad roofs and shaded pedestrian loops reduce direct solar exposure."),
        ("02", "Control west heat", "Minimise unprotected west glazing; use stone cores, timber screens and planted buffers."),
        ("03", "Cross ventilation", "Use opposing openings, high-level exhaust and shaded courtyards during suitable seasons."),
        ("04", "Monsoon resilience", "Raised thresholds, oversized gutters, swales, permeable terraces and protected entrances."),
        ("05", "Cool landscape", "Retain teak canopy, add native understory, shade parking and reduce hard-surface heat storage."),
        ("06", "Water stewardship", "Capture roofs, protect the lake edge, reuse treated water and separate pools from natural water."),
        ("07", "Efficient comfort", "Ceiling fans, zoned conditioning and high-performance roofs before adding mechanical capacity."),
        ("08", "Dark habitat", "Warm low-level lighting, controlled operating hours and no floodlit waterfall spectacle."),
    ]
    for i, (num, title, body) in enumerate(responses):
        row, col = divmod(i, 2)
        x0 = 0.02 + col * 0.50
        y0 = 0.90 - row * 0.235
        ax.add_patch(plt.Rectangle((x0, y0 - 0.16), 0.46, 0.19, transform=ax.transAxes, facecolor="#FFFFFF", edgecolor="#D7D8CD", linewidth=1.0))
        ax.text(x0 + 0.025, y0 - 0.015, num, transform=ax.transAxes, color="#A2823D", fontsize=22, weight="bold")
        ax.text(x0 + 0.105, y0 - 0.005, title, transform=ax.transAxes, color="#0D392D", fontsize=14, weight="bold")
        ax.text(x0 + 0.105, y0 - 0.062, body, transform=ax.transAxes, color="#52625C", fontsize=10.5, wrap=True, va="top")
    path = OUT / "climate_03_design_responses.png"
    fig.savefig(path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    files["design_responses"] = path.name

    return files


def summary_payload(data: Dict[str, List[float]], source: str, files: Dict[str, str]) -> dict:
    rain = np.array(data["PRECTOTCORR"]) * DAYS
    return {
        "status": "regional_proxy_not_site_specific",
        "location_label": LOCATION,
        "latitude": LAT,
        "longitude": LON,
        "source": source,
        "months": MONTHS,
        "parameters": data,
        "derived": {
            "annual_rainfall_mm": round(float(rain.sum()), 1),
            "peak_mean_max_temperature_c": round(max(data["T2M_MAX"]), 1),
            "coolest_mean_min_temperature_c": round(min(data["T2M_MIN"]), 1),
            "peak_relative_humidity_pct": round(max(data["RH2M"]), 1),
            "mean_solar_resource_kwh_m2_day": round(float(np.mean(data["ALLSKY_SFC_SW_DWN"])), 2),
        },
        "outputs": files,
        "design_caveat": "Replace with surveyed site coordinates and measured microclimate before statutory or detailed design.",
    }


def make_pdf(files: Dict[str, str], summary: dict) -> None:
    pdf_path = OUT / "Sanjeevani_Vann_Regional_Climate_Analysis_R07.pdf"
    with PdfPages(pdf_path) as pdf:
        for key in ("temperature_rainfall", "solar_wind", "design_responses"):
            image = plt.imread(OUT / files[key])
            fig = plt.figure(figsize=(16, 9), dpi=100)
            ax = fig.add_axes([0, 0, 1, 1])
            ax.imshow(image)
            ax.axis("off")
            pdf.savefig(fig, bbox_inches="tight", pad_inches=0)
            plt.close(fig)
        fig = base_figure("Climate-analysis basis and limitations", "The design response is a feasibility input, not a site weather certificate.")
        ax = fig.add_axes([0.07, 0.14, 0.86, 0.58])
        ax.axis("off")
        text = (
            f"Proxy location: {summary['location_label']} ({LAT:.4f}°N, {LON:.4f}°E)\n\n"
            f"Data source used: {summary['source']}\n\n"
            "Required next steps:\n"
            "• confirm survey coordinates and true north\n"
            "• install a temporary site weather logger\n"
            "• obtain contour, vegetation and water-level surveys\n"
            "• run project-specific solar, shade, wind and daylight simulations\n"
            "• coordinate passive measures with structural, fire, MEP and landscape design\n\n"
            "The current findings support concept design and cost planning only."
        )
        ax.text(0, 0.95, text, va="top", fontsize=16, color="#243B33", linespacing=1.5)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close(fig)


def main() -> None:
    data, source = nasa_power()
    files = make_boards(data, source)
    summary = summary_payload(data, source, files)
    (OUT / "climate_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    make_pdf(files, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
