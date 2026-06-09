"""Crawl the LiveATC archive using a headless browser (Playwright).

Playwright loads archive.php in real headless Chrome.  Cloudflare Turnstile
auto-solves silently for a real browser.  We fill the form, submit, wait for
the WaveSurfer player to appear, extract the audio URL, then download the MP3.

Each worker keeps its own browser page (already past the CF+Turnstile gate)
and processes (facility, date, time_slot) triples from a shared queue.

Usage (run on ser9 where Chrome is available)::

    /home/miro/.venvs/scrape/bin/python archive_playwright.py \
        --out /media/hdd4/liveatc/archive \
        --days 7 --workers 3

Upload directly to HF (no local save)::

    HF_TOKEN=hf_... HF_REPO=TigreGotico/liveatc-atc-audio \
    /home/miro/.venvs/scrape/bin/python archive_playwright.py --hf \
        --days 7 --workers 3

Scope to specific airports::

    ... --icao KJFK KLAX EHAM RJTT
"""
import argparse
import asyncio
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("liveatc-archive")

TIME_SLOTS = [f"{h:02d}{m:02d}Z" for h in range(24) for m in (0, 30)]

_AUDIO_RE = re.compile(
    r"""(?:url\s*:\s*['"]|src\s*=\s*['"])(https?://archive\.liveatc\.net/[^'"]+\.mp3)""",
    re.IGNORECASE,
)
_REGION_MAP = {
    "K": "usa", "C": "canada",
    "E": "europe", "L": "europe", "B": "europe", "D": "europe",
    "R": "japan_korea", "Y": "australia", "Z": "china",
    "V": "asia", "U": "russia", "F": "africa",
    "S": "south_america", "M": "central_america", "P": "pacific",
}
_ICAO_RE = re.compile(r"^([A-Z]{4})", re.I)


def _region(label: str) -> str:
    m = _ICAO_RE.match(label.strip())
    return _REGION_MAP.get(m.group(1)[0].upper(), "other") if m else "other"


def _date_range(days: int) -> list[str]:
    today = datetime.now(timezone.utc)
    return [(today - timedelta(days=i)).strftime("%Y%m%d") for i in range(1, days + 1)]


async def _open_archive_page(browser_ctx):
    """Open a fresh page, navigate to archive.php, wait past CF+Turnstile."""
    page = await browser_ctx.new_page()
    await page.goto("https://www.liveatc.net/archive.php", timeout=120_000)
    # CF challenge can take up to 90s; wait for facility select to appear
    await page.wait_for_selector("select[name='facility']", timeout=120_000)
    return page


async def _fetch_slot_url(page, facility: str, date: str, time_slot: str) -> str | None:
    """Fill form for one slot, submit, return MP3 URL or None."""
    try:
        await page.eval_on_selector("#archiveDate", f"el => el.value = '{date}'")
        await page.select_option("select[name='facility']", facility)
        await page.select_option("select[name='time']", time_slot)
        # Clear previous result
        await page.eval_on_selector("#archiveResults", "el => el.innerHTML = ''")
        await page.click("#archiveSubmit")
        await page.wait_for_function(
            "document.getElementById('archiveResults').innerHTML.trim().length > 50",
            timeout=25_000,
        )
        html = await page.inner_html("#archiveResults")
        m = _AUDIO_RE.search(html)
        return m.group(1) if m else None
    except Exception as exc:
        log.debug("slot %s/%s/%s: %s", facility, date, time_slot, exc)
        return None


async def _worker(worker_id: int, queue: asyncio.Queue, browser_ctx,
                  out_dir, hf_api, hf_repo: str, stats: dict):
    import httpx
    http = httpx.AsyncClient(timeout=60, follow_redirects=True)

    log.info("Worker %d: opening archive page …", worker_id)
    page = await _open_archive_page(browser_ctx)
    log.info("Worker %d: ready", worker_id)

    while True:
        try:
            facility_val, facility_label, date, time_slot = queue.get_nowait()
        except asyncio.QueueEmpty:
            break

        url = await _fetch_slot_url(page, facility_val, date, time_slot)
        if not url:
            queue.task_done()
            continue

        filename = url.split("/")[-1]
        region = _region(facility_label)
        log.info("[W%d] DL %s", worker_id, filename)

        try:
            if out_dir:
                dest = Path(out_dir) / region / facility_val / filename
                dest.parent.mkdir(parents=True, exist_ok=True)
                nbytes = await _download(url, dest, http)
            elif hf_api:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    tmp = Path(f.name)
                nbytes = await _download(url, tmp, http)
                path_in_repo = f"data/{region}/{facility_val}/{filename}"
                hf_api.upload_file(
                    path_or_fileobj=str(tmp),
                    path_in_repo=path_in_repo,
                    repo_id=hf_repo, repo_type="dataset",
                    commit_message=f"add {filename}",
                )
                tmp.unlink(missing_ok=True)
            else:
                queue.task_done()
                continue

            stats["files"] += 1
            stats["bytes"] += nbytes
            log.info("[W%d] OK %s  %d KB  total=%.0f MB",
                     worker_id, filename, nbytes // 1024, stats["bytes"] / 1e6)

        except Exception as exc:
            log.error("[W%d] ERR %s: %s", worker_id, filename, exc)

        queue.task_done()

    await http.aclose()
    await page.close()
    log.info("Worker %d done", worker_id)


async def _download(url: str, dest: Path, client) -> int:
    async with client.stream("GET", url) as r:
        r.raise_for_status()
        total = 0
        with open(dest, "wb") as fh:
            async for chunk in r.aiter_bytes(8192):
                fh.write(chunk)
                total += len(chunk)
    return total


async def _launch(pw):
    """Launch Chromium with anti-detection flags."""
    return await pw.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-dev-shm-usage",
        ],
    )


async def _stealth_context(browser):
    ctx = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"
        ),
        java_script_enabled=True,
        extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
    )
    # Mask webdriver property
    await ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return ctx


def _flaresolverr_cookies(url: str = "https://www.liveatc.net/archive.php",
                           fs_url: str = "http://localhost:8191") -> tuple[list, str]:
    """Use FlareSolverr (must be running locally) to solve CF and return cookies + UA."""
    import requests as _req
    r = _req.post(f"{fs_url}/v1",
                  json={"cmd": "request.get", "url": url, "maxTimeout": 120_000},
                  timeout=150)
    sol = r.json().get("solution", {})
    return sol.get("cookies", []), sol.get("userAgent", "")


async def _get_facilities(pw) -> list[tuple[str, str]]:
    # Solve CF via FlareSolverr, then inject cookies into playwright context
    cookies, ua = _flaresolverr_cookies()
    browser = await _launch(pw)
    ctx = await _stealth_context(browser)
    # Inject CF cookies so playwright skips the CF challenge entirely
    await ctx.add_cookies([
        {"name": c["name"], "value": c["value"],
         "domain": c.get("domain", ".liveatc.net"), "path": c.get("path", "/")}
        for c in cookies
    ])
    page = await ctx.new_page()
    await page.goto("https://www.liveatc.net/archive.php", timeout=60_000)
    await page.wait_for_selector("select[name='facility']", timeout=30_000)
    opts = await page.eval_on_selector(
        "select[name='facility']",
        "s => Array.from(s.options).map(o => [o.value, o.text.trim()])"
    )
    await browser.close()
    return opts


async def main_async(args):
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        # Phase 1: discover facilities
        log.info("Fetching facility list …")
        facilities = await _get_facilities(pw)
        log.info("%d facilities", len(facilities))

        if args.icao:
            icaos = [i.upper() for i in args.icao]
            facilities = [(v, l) for v, l in facilities
                          if any(l.upper().startswith(i) for i in icaos)]
            log.info("Filtered to %d facilities for %s", len(facilities), icaos)

        dates = _date_range(min(args.days, 7))
        log.info("Dates: %s … %s", dates[-1], dates[0])

        # Build work queue
        queue: asyncio.Queue = asyncio.Queue()
        for fv, fl in facilities:
            for date in dates:
                for ts in TIME_SLOTS:
                    queue.put_nowait((fv, fl, date, ts))
        total_slots = queue.qsize()
        log.info("Total slots queued: %d", total_slots)

        # HF setup
        hf_api = None
        hf_repo = os.environ.get("HF_REPO", "TigreGotico/liveatc-atc-audio")
        if args.hf:
            from huggingface_hub import HfApi
            hf_api = HfApi(token=os.environ["HF_TOKEN"])
            hf_api.create_repo(repo_id=hf_repo, repo_type="dataset",
                               private=True, exist_ok=True)
            log.info("HF repo: %s", hf_repo)

        out_dir = args.out or (None if args.hf else "/tmp/liveatc_archive")

        # Phase 2: crawl with N browser workers sharing one browser context
        log.info("Solving CF via FlareSolverr …")
        cf_cookies, cf_ua = _flaresolverr_cookies()
        browser = await _launch(pw)
        ctx = await _stealth_context(browser)
        await ctx.add_cookies([
            {"name": c["name"], "value": c["value"],
             "domain": c.get("domain", ".liveatc.net"), "path": c.get("path", "/")}
            for c in cf_cookies
        ])

        stats = {"files": 0, "bytes": 0}
        workers = [
            _worker(i, queue, ctx, out_dir, hf_api, hf_repo, stats)
            for i in range(args.workers)
        ]
        await asyncio.gather(*workers)
        await browser.close()

    log.info("Done. %d files downloaded, %.1f MB", stats["files"], stats["bytes"] / 1e6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="", help="Local output directory")
    ap.add_argument("--hf", action="store_true", help="Upload to Hugging Face")
    ap.add_argument("--days", type=int, default=7, help="Days back (max 7)")
    ap.add_argument("--workers", type=int, default=2, help="Browser page workers")
    ap.add_argument("--icao", nargs="*", help="Limit to ICAO prefixes e.g. KJFK EHAM")
    args = ap.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
