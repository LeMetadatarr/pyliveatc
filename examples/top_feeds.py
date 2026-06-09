"""Show the top 50 feeds by live listener count."""
from pyliveatc import fetch_topfeeds

feeds = fetch_topfeeds()
print(f"{'Rank':>4}  {'Listeners':>9}  {'Status':6}  Feed")
print("-" * 70)
for tf in feeds:
    status = "UP" if tf.up else "DOWN"
    print(f"{tf.rank:>4}  {tf.listener_count:>9}  {status:6}  {tf.title}")
    print(f"             mount: {tf.mount_id}  stream: {tf.stream_url}")
