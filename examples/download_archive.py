"""Download two hours of archived ATC audio for KJFK Approach."""
from pyliveatc import download_range, fetch_archive_listing

# List available files first
print("Available archive files for kjfk_app:")
files = fetch_archive_listing("kjfk_app")
for af in files[:5]:
    print(f"  {af.filename}  {af.url}")

# Download hour 0 UTC from a specific date
paths = download_range(
    mount_id="kjfk_app",
    date="20260609",
    hours=[0],          # downloads 0000Z and 0030Z segments
    dest_dir="./atc_audio",
)

for path in paths:
    print(f"Saved: {path}  ({path.stat().st_size:,} bytes)")
