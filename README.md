# dagelijksekost-paprika

Imports today's [Dagelijkse Kost](https://dagelijksekost.vrt.be) recipe into [Paprika Recipe Manager](https://www.paprikaapp.com).

## Setup

**Prerequisites:** [uv](https://docs.astral.sh/uv/)

```bash
cp .env.example .env
```

Fill in your Paprika cloud sync credentials in `.env`:

```
PAPRIKA_EMAIL=you@example.com
PAPRIKA_PASSWORD=secret
```

> Your Paprika credentials are for the cloud sync account, found in the app under **Settings → Sync → Paprika Account**.

## Usage

```bash
uv run import_recipe.py
```

Preview the recipe without importing:

```bash
uv run import_recipe.py --dry-run
```
