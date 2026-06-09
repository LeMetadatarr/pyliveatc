"""Explore LiveATC.net dataset: stats, plots, and archive capacity estimates.

Fetches live data via Wayback Machine (Cloudflare bypass) and produces:
  - Geographic distribution of feeds by ICAO region
  - Top-50 feeds by listener count with country breakdown
  - ATC function type breakdown (tower, approach, ground, ATIS, ...)
  - Archive capacity: feeds × segments × hours estimate
  - Listener distribution histogram

Usage::

    pip install matplotlib pandas
    python examples/explore_stats.py [--out ./plots]
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Data collection (live fetch via Wayback)
# ---------------------------------------------------------------------------

def fetch_facilities():
    """Fetch the full archive facility list (3,400+ feeds with archives)."""
    from unblock_requests import CloudflareSession
    s = CloudflareSession(mode="wayback")
    from bs4 import BeautifulSoup
    r = s.get("https://www.liveatc.net/archive.php", params={"m": "kjfk9_s"})
    soup = BeautifulSoup(r.text, "lxml")
    sel = soup.find_all("select")[0]
    return [(o.get("value", ""), o.get_text(strip=True)) for o in sel.find_all("option")]


def fetch_topfeeds():
    """Fetch top-50 feeds with listener counts and locations."""
    from unblock_requests import CloudflareSession
    from bs4 import BeautifulSoup
    s = CloudflareSession(mode="wayback")
    r = s.get("https://www.liveatc.net/topfeeds.php")
    soup = BeautifulSoup(r.text, "lxml")
    rows = []
    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 4:
            continue
        rank_text = tds[0].get_text(strip=True)
        if not rank_text.isdigit():
            continue
        rank = int(rank_text)
        listeners = int(re.sub(r"[^\d]", "", tds[1].get_text(strip=True)) or "0")
        title = tds[2].get_text(strip=True)
        city = tds[3].get_text(strip=True) if len(tds) > 3 else ""
        country = tds[5].get_text(strip=True) if len(tds) > 5 else ""
        onclick = tds[-1].find(attrs={"onclick": True}) or tds[-1].find("a", attrs={"onClick": True})
        mount_id = ""
        if onclick:
            m = re.search(r"myHTML5Popup\('([^']+)'", onclick.get("onclick") or onclick.get("onClick", ""))
            if m:
                mount_id = m.group(1)
        rows.append({"rank": rank, "listeners": listeners, "title": title,
                     "mount_id": mount_id, "city": city, "country": country})
    return rows


# ---------------------------------------------------------------------------
# Analysis helpers
# ---------------------------------------------------------------------------

_ICAO_RE = re.compile(r"^([A-Z]{4})\b", re.I)
_FUNC_RE = re.compile(
    r"\b(Approach|App|Departure|Dep|Tower|Twr|Ground|Gnd|ATIS|Delivery|Del|CTAF|Center|Ctr|Radar|FSS|Control)\b",
    re.I
)

_FUNC_CANONICAL = {
    "approach": "Approach", "app": "Approach",
    "departure": "Departure", "dep": "Departure",
    "tower": "Tower", "twr": "Tower",
    "ground": "Ground", "gnd": "Ground",
    "atis": "ATIS",
    "delivery": "Delivery", "del": "Delivery",
    "ctaf": "CTAF",
    "center": "Center", "ctr": "Center",
    "radar": "Radar",
    "fss": "FSS",
    "control": "Control",
}


def icao_region(icao: str) -> str:
    p = icao[0].upper()
    if p == "K":
        return "USA"
    if p == "C":
        return "Canada"
    if p in ("E", "L", "B", "D"):
        return "Europe"
    if p == "R":
        return "Japan / Korea"
    if p == "Y":
        return "Australia / NZ"
    if p == "Z":
        return "China"
    if p == "V":
        return "South / SE Asia"
    if p == "U":
        return "Russia / CIS"
    if p == "F":
        return "Africa"
    if p == "S":
        return "South America"
    if p in ("M", "T"):
        return "Cent. America / Carib"
    if p == "P":
        return "Pacific"
    return "Other"


def analyse_facilities(facilities):
    icaos, funcs = [], Counter()
    for _, text in facilities:
        m = _ICAO_RE.match(text.strip())
        if m:
            icaos.append(m.group(1).upper())
        for tok in _FUNC_RE.findall(text):
            canon = _FUNC_CANONICAL.get(tok.lower(), tok.title())
            funcs[canon] += 1
    regions = Counter(icao_region(i) for i in icaos)
    unique_airports = len(set(icaos))
    return regions, funcs, unique_airports


# ---------------------------------------------------------------------------
# Archive capacity math
# ---------------------------------------------------------------------------

SEGMENTS_PER_DAY = 48          # 30-min segments
SEGMENT_DURATION_MIN = 30
ARCHIVE_DAYS_ESTIMATE = 14     # LiveATC keeps ~2 weeks per feed
MP3_BITRATE_KBPS = 16
SEGMENT_SIZE_MB = (MP3_BITRATE_KBPS * 1000 / 8) * (SEGMENT_DURATION_MIN * 60) / 1_000_000


def archive_stats(n_feeds: int) -> dict:
    total_segments = n_feeds * SEGMENTS_PER_DAY * ARCHIVE_DAYS_ESTIMATE
    total_hours = total_segments * SEGMENT_DURATION_MIN / 60
    total_gb = total_segments * SEGMENT_SIZE_MB / 1024
    return {
        "feeds": n_feeds,
        "segments_per_feed_per_day": SEGMENTS_PER_DAY,
        "archive_days": ARCHIVE_DAYS_ESTIMATE,
        "total_segments": total_segments,
        "total_hours": total_hours,
        "total_tb": total_gb / 1024,
        "segment_size_mb": SEGMENT_SIZE_MB,
    }


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def make_plots(facilities, topfeeds, out_dir: Path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mtick

    regions, funcs, unique_airports = analyse_facilities(facilities)
    n_feeds = len(facilities)
    stats = archive_stats(n_feeds)

    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Figure 1: Geographic distribution ─────────────────────────────────
    fig, ax = plt.subplots(figsize=(10, 5))
    reg_labels = [k for k, _ in regions.most_common()]
    reg_counts = [v for _, v in regions.most_common()]
    colors = plt.cm.tab20.colors[:len(reg_labels)]
    bars = ax.barh(reg_labels[::-1], reg_counts[::-1], color=colors[::-1])
    for bar, count in zip(bars, reg_counts[::-1]):
        ax.text(bar.get_width() + 5, bar.get_y() + bar.get_height() / 2,
                str(count), va="center", fontsize=9)
    ax.set_xlabel("Number of archive feeds")
    ax.set_title(f"LiveATC.net — Feeds by Region\n({n_feeds} total archive feeds, {unique_airports} unique airports)")
    ax.margins(x=0.12)
    plt.tight_layout()
    out = out_dir / "01_feeds_by_region.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  saved {out}")

    # ── Figure 2: ATC function types ──────────────────────────────────────
    fig, ax = plt.subplots(figsize=(9, 5))
    func_top = funcs.most_common(12)
    flabels = [k for k, _ in func_top]
    fcounts = [v for _, v in func_top]
    ax.bar(flabels, fcounts, color=plt.cm.Set2.colors[:len(flabels)])
    ax.set_ylabel("Feed count")
    ax.set_title("ATC Function Type Breakdown\n(feeds can have multiple functions)")
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()
    out = out_dir / "02_function_types.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  saved {out}")

    # ── Figure 3: Top-50 listener counts ──────────────────────────────────
    if topfeeds:
        fig, ax = plt.subplots(figsize=(12, 8))
        labels = [f"#{r['rank']} {r['title'][:28]}" for r in topfeeds]
        listeners = [r["listeners"] for r in topfeeds]
        country_colors = {}
        palette = plt.cm.tab10.colors
        countries = list(dict.fromkeys(r["country"] for r in topfeeds))
        for i, c in enumerate(countries):
            country_colors[c] = palette[i % len(palette)]
        bar_colors = [country_colors[r["country"]] for r in topfeeds]
        ax.barh(labels[::-1], listeners[::-1], color=bar_colors[::-1])
        # Legend
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=country_colors[c], label=c) for c in countries]
        ax.legend(handles=legend_elements, loc="lower right", fontsize=8)
        ax.set_xlabel("Live listeners")
        ax.set_title(f"Top 50 Feeds by Listener Count")
        ax.tick_params(axis="y", labelsize=7)
        plt.tight_layout()
        out = out_dir / "03_top50_listeners.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"  saved {out}")

        # ── Figure 4: Listeners by country (top-50) ───────────────────────
        country_listeners = Counter()
        for r in topfeeds:
            country_listeners[r["country"]] += r["listeners"]
        fig, ax = plt.subplots(figsize=(8, 5))
        cl = country_listeners.most_common(10)
        ax.bar([k for k, _ in cl], [v for _, v in cl],
               color=plt.cm.Paired.colors[:len(cl)])
        ax.set_ylabel("Total listeners in top-50")
        ax.set_title("Listener Concentration by Country (Top 50 Feeds)")
        ax.tick_params(axis="x", rotation=25)
        plt.tight_layout()
        out = out_dir / "04_listeners_by_country.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(f"  saved {out}")

    # ── Figure 5: Archive capacity ─────────────────────────────────────────
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left: capacity breakdown
    ax = axes[0]
    labels = ["Daily segments\n(all feeds)", "Total segments\n(2-week archive)", "Total hours\n(×100)"]
    values = [n_feeds * SEGMENTS_PER_DAY,
              stats["total_segments"],
              stats["total_hours"] / 100]
    bars = ax.bar(labels, values, color=["#4e79a7", "#f28e2b", "#59a14f"])
    for bar, v, label in zip(bars, [n_feeds * SEGMENTS_PER_DAY, stats["total_segments"], stats["total_hours"]], labels):
        suffix = "" if "100" not in label else "k hrs"
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(values) * 0.01,
                f"{v:,.0f}{suffix}", ha="center", fontsize=9)
    ax.set_title("Archive Capacity\n(30-min segments, ~2-week retention)")
    ax.yaxis.set_major_formatter(mtick.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    ax.set_ylabel("Count")

    # Right: storage estimate
    ax2 = axes[1]
    storage_gb = stats["total_segments"] * SEGMENT_SIZE_MB / 1024
    # Bar chart of storage breakdown instead of pie
    storage_labels = ["Per day\n(all feeds)", "2-week total"]
    storage_values = [n_feeds * SEGMENTS_PER_DAY * SEGMENT_SIZE_MB / 1024,
                      storage_gb]
    bars2 = ax2.bar(storage_labels, storage_values, color=["#4e79a7", "#f28e2b"])
    for bar, v in zip(bars2, storage_values):
        ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.2,
                 f"{v:.0f} GB", ha="center", fontsize=10, fontweight="bold")
    ax2.set_ylabel("GB")
    ax2.set_title(f"Estimated Archive Storage\n({n_feeds} feeds × {SEGMENT_SIZE_MB:.1f} MB/segment)")
    plt.tight_layout()
    out = out_dir / "05_archive_capacity.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  saved {out}")

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="./plots", help="Output directory for plots")
    parser.add_argument("--cache", default="/tmp/liveatc_cache.json",
                        help="Cache file for fetched data (avoids re-fetching)")
    args = parser.parse_args()

    cache = Path(args.cache)
    if cache.exists():
        print(f"Loading cached data from {cache}")
        data = json.loads(cache.read_text())
        facilities = data["facilities"]
        topfeeds = data["topfeeds"]
    else:
        print("Fetching facilities from archive.php ...")
        facilities = fetch_facilities()
        print(f"  {len(facilities)} archive feeds found")
        time.sleep(2.0)
        print("Fetching top-50 feeds ...")
        topfeeds = fetch_topfeeds()
        print(f"  {len(topfeeds)} top feeds found")
        cache.write_text(json.dumps({"facilities": facilities, "topfeeds": topfeeds}))
        print(f"Cached to {cache}")

    # ── Print summary stats ──────────────────────────────────────────────
    regions, funcs, unique_airports = analyse_facilities(facilities)
    n_feeds = len(facilities)
    stats = archive_stats(n_feeds)

    print("\n" + "=" * 60)
    print("  LiveATC.net — Dataset Overview")
    print("=" * 60)
    print(f"  Total archive-enabled feeds : {n_feeds:,}")
    print(f"  Unique airports (by ICAO)   : {unique_airports:,}")
    print(f"  30-min segments per day     : {n_feeds * SEGMENTS_PER_DAY:,}")
    print(f"  Archive retention estimate  : {ARCHIVE_DAYS_ESTIMATE} days")
    print(f"  Total downloadable segments : {stats['total_segments']:,}")
    print(f"  Total audio hours           : {stats['total_hours']:,.0f} hours")
    print(f"  Total audio at 16 kbps      : ~{stats['total_tb']:.1f} TB")
    print()
    print("  Region breakdown:")
    for reg, cnt in regions.most_common():
        pct = cnt / n_feeds * 100
        print(f"    {reg:25s}  {cnt:5d} ({pct:.1f}%)")
    print()
    print("  Top function types:")
    for func, cnt in funcs.most_common(8):
        print(f"    {func:15s}  {cnt:4d}")
    if topfeeds:
        total_listeners = sum(r["listeners"] for r in topfeeds)
        print(f"\n  Top-50 total live listeners : {total_listeners}")
        top_country = Counter(r["country"] for r in topfeeds).most_common(1)[0]
        print(f"  Most represented country   : {top_country[0]} ({top_country[1]} feeds)")
    print("=" * 60)

    # ── Generate plots ───────────────────────────────────────────────────
    print(f"\nGenerating plots → {args.out}/")
    make_plots(facilities, topfeeds, Path(args.out))
    print("\nDone.")


if __name__ == "__main__":
    main()
