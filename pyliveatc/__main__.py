"""CLI: python -m pyliveatc <command> [args]

Commands:
  search <ICAO>                             Search feeds for an airport/ARTCC
  topfeeds                                  Show top-50 feeds by listener count
  feedindex [--type TYPE]                   List feeds by category
  archive <mount_id>                        List available archive files
  download <mount_id> --date DATE [--hours H [H...]] [--dest DIR]
  dataset [--out DIR] [--types TYPE [TYPE...]]
"""
import argparse
import sys

from . import (
    FEED_TYPES, download_range, export_all, fetch_archive_listing,
    fetch_feedindex, fetch_topfeeds, search,
)


def cmd_search(args):
    feeds = search(args.icao)
    if not feeds:
        print(f"No feeds found for {args.icao}")
        return
    for feed in feeds:
        status = "UP" if feed.up else "DOWN"
        freqs = ", ".join(f"{f.title} {f.frequency}" for f in feed.frequencies)
        print(f"[{status}] {feed.title}")
        print(f"       mount: {feed.mount_id}  stream: {feed.stream_url}")
        if freqs:
            print(f"       freqs: {freqs}")
        print()


def cmd_topfeeds(args):
    feeds = fetch_topfeeds()
    for tf in feeds:
        status = "UP" if tf.up else "DOWN"
        print(f"#{tf.rank:>3} [{status}] {tf.title}  ({tf.listener_count} listeners)")
        print(f"       mount: {tf.mount_id}  stream: {tf.stream_url}")
    print(f"\n{len(feeds)} feeds")


def cmd_feedindex(args):
    feeds = fetch_feedindex(args.type)
    for feed in feeds:
        status = "UP" if feed.up else "DOWN"
        print(f"[{status}] {feed.title}  mount={feed.mount_id}")
    print(f"\n{len(feeds)} feeds")


def cmd_archive(args):
    files = fetch_archive_listing(args.mount_id)
    if not files:
        print(f"No archive files found for {args.mount_id}")
        return
    for af in files:
        print(f"  {af.filename}  {af.url}")
    print(f"\n{len(files)} files")


def cmd_download(args):
    hours = args.hours or [0]
    paths = download_range(
        mount_id=args.mount_id,
        date=args.date,
        hours=hours,
        dest_dir=args.dest,
    )
    if paths:
        for p in paths:
            print(f"  saved: {p}")
    else:
        print("No files downloaded (check mount_id/date/hours)")


def cmd_dataset(args):
    types = args.types or None
    counts = export_all(out_dir=args.out, feed_types=types)
    for fname, n in counts.items():
        print(f"  {fname}: {n} rows")
    print(f"\nOutput: {args.out}")


def main():
    parser = argparse.ArgumentParser(prog="pyliveatc",
                                     description="LiveATC.net client")
    sub = parser.add_subparsers(dest="cmd")

    p_search = sub.add_parser("search", help="Search by ICAO/ARTCC code")
    p_search.add_argument("icao")

    sub.add_parser("topfeeds", help="Top-50 feeds by listener count")

    p_fi = sub.add_parser("feedindex", help="List feeds by category")
    p_fi.add_argument("--type", default="all", choices=FEED_TYPES)

    p_arch = sub.add_parser("archive", help="List archive files for a mount")
    p_arch.add_argument("mount_id")

    p_dl = sub.add_parser("download", help="Download archive MP3 files")
    p_dl.add_argument("mount_id")
    p_dl.add_argument("--date", required=True, help="YYYYMMDD")
    p_dl.add_argument("--hours", nargs="+", type=int, default=[0],
                      help="UTC hours to download (default: 0)")
    p_dl.add_argument("--dest", default="./atc_audio",
                      help="Destination directory")

    p_ds = sub.add_parser("dataset", help="Export feeds to JSONL dataset")
    p_ds.add_argument("--out", default="./liveatc_data")
    p_ds.add_argument("--types", nargs="+", choices=FEED_TYPES)

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        sys.exit(1)

    dispatch = {
        "search": cmd_search,
        "topfeeds": cmd_topfeeds,
        "feedindex": cmd_feedindex,
        "archive": cmd_archive,
        "download": cmd_download,
        "dataset": cmd_dataset,
    }
    dispatch[args.cmd](args)


if __name__ == "__main__":
    main()
