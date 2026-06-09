# CLI Reference

```
python -m pyliveatc <command> [args]
```

## Commands

### `search <ICAO>`

Search feeds for an airport or ARTCC code.

```bash
python -m pyliveatc search KJFK
python -m pyliveatc search EGLL
python -m pyliveatc search ZNY       # New York ARTCC
```

### `topfeeds`

Print the top-50 feeds by current listener count.

```bash
python -m pyliveatc topfeeds
```

### `feedindex [--type TYPE]`

List feeds by category. `TYPE` defaults to `all`.

```bash
python -m pyliveatc feedindex --type class-b
python -m pyliveatc feedindex --type international-eu
```

Available types: `all`, `class-b`, `class-d`, `us-artcc`, `international-eu`, `international-as`, `hf`, `canada`

### `archive <mount_id>`

List available archive files for a mount point.

```bash
python -m pyliveatc archive kjfk_app
```

### `download <mount_id> --date DATE [--hours H...] [--dest DIR]`

Download 30-minute archive segments.

```bash
python -m pyliveatc download kjfk_app --date 20260609 --hours 12 13 --dest ./audio
```

`--hours` accepts multiple UTC hours; each hour yields two 30-minute files (HH00Z + HH30Z).

### `dataset [--out DIR] [--types TYPE...]`

Export feeds to JSONL dataset files.

```bash
python -m pyliveatc dataset --out ./data --types class-b international-eu
python -m pyliveatc dataset --out ./data   # exports all feed types
```
