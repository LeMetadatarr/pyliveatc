"""Download LiveATC archive audio using non-headless Chrome (Xvfb + UC).

Requires:
  - FlareSolverr v3.5.0 container on ser9 (192.168.1.116:8191)
    with undetected_chromedriver + Xvfb displays
  - Run *inside* the FlareSolverr container via docker exec

The archive form at liveatc.net is guarded by Cloudflare Turnstile. Non-headless
Chrome with Xvfb bypasses the Turnstile instantly. Each 30-min slot is fetched by
submitting the archive form and downloading the M4A via a same-origin <a download>
link (same-origin = www.liveatc.net/archive-cache/).

Usage — single worker (run inside container)::

    python3 /tmp/archive_scraper.py \\
        --out /tmp/atc_archive \\
        --days 1 --slice 0/4

    # --slice N/M = this process handles facility shard N of M total shards
    # Run M processes in parallel on different DISPLAY values for full speed

Upload to HuggingFace::

    HF_TOKEN=hf_... python3 /tmp/archive_scraper.py \\
        --hf --repo TigreGotico/liveatc-atc-audio-archive \\
        --days 1 --slice 0/4

See launch_archive_scraper.sh for the parallel launcher.

Notes:
  - Each M4A is ~200-2000 KB per 30-min slot (AAC-LC)
  - Signed URLs expire ~8 hours; download happens immediately after form submit
  - CF session auto-renews when Chrome's clearance expires (non-headless handles it)
  - Empty time slots return in ~3s; slots with data take ~30s total
"""
import argparse
import logging
import os
import re
import sys
import time
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from queue import Queue, Empty

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("liveatc-archive")

TIME_SLOTS = [f"{h:02d}{m:02d}Z" for h in range(24) for m in (0, 30)]

_REGION_MAP = {
    "K": "usa", "C": "canada",
    "E": "europe", "L": "europe", "B": "europe", "D": "europe",
    "R": "japan_korea", "Y": "australia", "Z": "china",
    "V": "asia", "U": "russia", "F": "africa",
    "S": "south_america", "M": "central_america", "P": "pacific",
}
_ICAO_RE = re.compile(r"^([A-Z]{4})", re.I)

FS_URL = "http://localhost:8191/v1"


def _region(label: str) -> str:
    m = _ICAO_RE.match(label.strip())
    return _REGION_MAP.get(m.group(1)[0].upper(), "other") if m else "other"


def _date_range(days: int) -> list[str]:
    today = datetime.now(timezone.utc)
    return [(today - timedelta(days=i)).strftime("%Y%m%d") for i in range(1, days + 1)]


def _get_cf_cookies() -> list[dict]:
    import requests
    log.info("Solving CF challenge via FlareSolverr...")
    r = requests.post(FS_URL, json={"cmd": "request.get", "url": "https://www.liveatc.net/",
                                     "maxTimeout": 120_000}, timeout=150)
    cookies = r.json().get("solution", {}).get("cookies", [])
    log.info("Got %d CF cookies", len(cookies))
    return cookies


def _make_driver(download_dir: str):
    sys.path.insert(0, "/app")
    import undetected_chromedriver as uc
    from utils import get_chrome_exe_path
    driver = uc.Chrome(
        browser_executable_path=get_chrome_exe_path(),
        driver_executable_path="/app/chromedriver",
        headless=False,
    )
    driver.set_script_timeout(30)
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow", "downloadPath": download_dir,
    })
    return driver


def _inject_cookies(driver, cookies_list: list[dict]) -> None:
    driver.get("about:blank")
    for c in cookies_list:
        if "liveatc" not in c.get("domain", ""):
            continue
        try:
            driver.execute_cdp_cmd("Network.setCookie", {
                "name": c["name"], "value": c["value"],
                "domain": c.get("domain", ".liveatc.net"),
                "path": c.get("path", "/"),
                "secure": c.get("secure", False),
                "httpOnly": c.get("httpOnly", False),
            })
        except Exception:
            pass


def _open_archive_page(driver) -> None:
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.common.by import By

    driver.get("https://www.liveatc.net/archive.php")
    WebDriverWait(driver, 90).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, "select[name='facility']")
    )
    # Non-headless Chrome fills Turnstile instantly
    for _ in range(15):
        el = driver.find_elements(By.CSS_SELECTOR, "input[name='cf-turnstile-response']")
        if el and el[0].get_attribute("value"):
            break
        time.sleep(1)


def _ensure_on_archive_page(driver) -> bool:
    """Navigate back to archive.php if we drifted (CF challenge etc)."""
    from selenium.webdriver.common.by import By
    if "archive.php" not in driver.current_url:
        log.info("Not on archive.php (%s), re-navigating...", driver.current_url)
        _open_archive_page(driver)
    if not driver.find_elements(By.CSS_SELECTOR, "select[name='facility']"):
        _open_archive_page(driver)
        return True
    return False


def _get_facilities(driver) -> list[tuple[str, str]]:
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import Select
    fac_el = driver.find_element(By.CSS_SELECTOR, "select[name='facility']")
    return [(o.get_attribute("value"), o.text.strip())
            for o in Select(fac_el).options if o.get_attribute("value")]


def _submit_form(driver, facility_val: str, date: str, time_slot: str) -> tuple[str | None, str | None]:
    from selenium.webdriver.support.ui import WebDriverWait, Select
    from selenium.webdriver.common.by import By
    try:
        driver.execute_script(f"document.getElementById('archiveDate').value = '{date}'")
        fac_el = driver.find_element(By.CSS_SELECTOR, "select[name='facility']")
        Select(fac_el).select_by_value(facility_val)
        Select(driver.find_element(By.CSS_SELECTOR, "select[name='time']")).select_by_value(time_slot)
        driver.execute_script("document.getElementById('archiveResults').innerHTML = ''")
        driver.find_element(By.ID, "archiveSubmit").click()
        WebDriverWait(driver, 20).until(
            lambda d: len(d.find_element(By.ID, "archiveResults").get_attribute("innerHTML").strip()) > 10
        )
        html = driver.find_element(By.ID, "archiveResults").get_attribute("innerHTML")
        m4a_match = re.search(r'AUDIO_URL\s*=\s*"((?:\\/|/)archive-cache[^"]+\.m4a[^"]*)"', html)
        mp3_match = re.search(r'href="(https?://archive\.liveatc\.net/[^"]+\.mp3[^"]*)"', html)
        m4a_path = m4a_match.group(1).replace("\\/", "/") if m4a_match else None
        mp3_url = mp3_match.group(1).replace("&amp;", "&") if mp3_match else None
        return m4a_path, mp3_url
    except Exception as exc:
        log.debug("form %s/%s/%s: %s", facility_val, date, time_slot, type(exc).__name__)
        return None, None


def _download_m4a(driver, m4a_path: str, download_dir: str) -> Path | None:
    filename = m4a_path.split("?")[0].split("/")[-1]
    dest = Path(download_dir) / filename
    if dest.exists():
        return dest  # already downloaded (resume)

    escaped = m4a_path.replace("'", "\\'")
    driver.execute_script(f"""
        var a = document.createElement('a');
        a.href = '{escaped}';
        a.download = '{filename}';
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    """)

    crdownload = Path(download_dir) / (filename + ".crdownload")
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if dest.exists() and not crdownload.exists():
            return dest
        time.sleep(1)

    log.warning("Download timeout: %s", filename)
    return None


def run(args) -> None:
    download_dir = Path(args.out)
    download_dir.mkdir(parents=True, exist_ok=True)

    cf_cookies = _get_cf_cookies()
    driver = _make_driver(str(download_dir))

    hf_api = None
    if args.hf:
        from huggingface_hub import HfApi
        hf_api = HfApi(token=os.environ["HF_TOKEN"])
        hf_api.create_repo(repo_id=args.repo, repo_type="dataset",
                           private=True, exist_ok=True)
        log.info("HF repo: %s", args.repo)

    stats = {"files": 0, "bytes": 0, "skipped": 0}

    try:
        _inject_cookies(driver, cf_cookies)
        _open_archive_page(driver)
        facilities = _get_facilities(driver)
        log.info("%d total facilities", len(facilities))

        if args.icao:
            icaos = [i.upper() for i in args.icao]
            facilities = [(v, l) for v, l in facilities
                          if any(l.upper().startswith(i) or v.upper().startswith(i) for i in icaos)]
            log.info("Filtered to %d facilities", len(facilities))

        # Facility sharding: --slice N/M
        if args.slice:
            n, m = map(int, args.slice.split("/"))
            total = len(facilities)
            lo = n * total // m
            hi = (n + 1) * total // m
            facilities = facilities[lo:hi]
            log.info("Shard %d/%d: facilities %d-%d (%d total)", n, m, lo, hi-1, len(facilities))

        dates = _date_range(min(args.days, 7))
        log.info("Dates: %s … %s  (%d days)", dates[-1], dates[0], len(dates))

        total_slots = len(facilities) * len(dates) * len(TIME_SLOTS)
        log.info("Total slots to check: %d", total_slots)

        n_processed = 0
        for fv, fl in facilities:
            for date in dates:
                _ensure_on_archive_page(driver)
                for ts in TIME_SLOTS:
                    n_processed += 1
                    m4a_path, mp3_url = _submit_form(driver, fv, date, ts)
                    if not m4a_path:
                        stats["skipped"] += 1
                        continue

                    filename = m4a_path.split("?")[0].split("/")[-1]
                    region = _region(fl)
                    log.info("[%d/%d] DL %s  %s/%s", n_processed, total_slots, filename, date, ts)

                    local_path = _download_m4a(driver, m4a_path, str(download_dir))
                    if not local_path:
                        continue

                    nbytes = local_path.stat().st_size

                    if hf_api:
                        path_in_repo = f"data/{region}/{fv}/{filename}"
                        try:
                            hf_api.upload_file(
                                path_or_fileobj=str(local_path),
                                path_in_repo=path_in_repo,
                                repo_id=args.repo, repo_type="dataset",
                                commit_message=f"add {filename}",
                            )
                            local_path.unlink(missing_ok=True)
                        except Exception as exc:
                            log.error("HF upload %s: %s", filename, exc)

                    stats["files"] += 1
                    stats["bytes"] += nbytes

                    if n_processed % 100 == 0:
                        pct = 100 * n_processed / total_slots
                        log.info("Progress: %d/%d (%.1f%%)  %d files  %.1f MB",
                                 n_processed, total_slots, pct,
                                 stats["files"], stats["bytes"] / 1e6)

    finally:
        driver.quit()
        log.info("Done. %d files  %.1f MB  %d empty slots",
                 stats["files"], stats["bytes"] / 1e6, stats["skipped"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="/tmp/atc_archive")
    ap.add_argument("--hf", action="store_true")
    ap.add_argument("--repo", default="TigreGotico/liveatc-atc-audio-archive")
    ap.add_argument("--days", type=int, default=1)
    ap.add_argument("--slice", default="0/1", help="N/M facility shard e.g. 0/4 1/4 2/4 3/4")
    ap.add_argument("--icao", nargs="*")
    args = ap.parse_args()

    if args.hf and not os.environ.get("HF_TOKEN"):
        raise SystemExit("Set HF_TOKEN env var")

    run(args)


if __name__ == "__main__":
    main()
