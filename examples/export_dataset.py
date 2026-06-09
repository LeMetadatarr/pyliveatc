"""Export all Class-B and European feeds to JSONL dataset files."""
from pyliveatc.dataset import export_all

counts = export_all(
    out_dir="./liveatc_data",
    feed_types=["class-b", "international-eu"],
    include_topfeeds=True,
)

for fname, n in counts.items():
    print(f"  {fname:45s}  {n:>6} rows")
