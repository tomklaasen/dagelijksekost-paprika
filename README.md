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

## Optional: HTTP trigger for mobile use

`server.py` is a small HTTP server that lets you trigger the import remotely — for example from an iPhone Shortcut on the same local network.

### Server setup

```bash
cp dagelijksekost-paprika.service.example dagelijksekost-paprika.service
```

Edit `dagelijksekost-paprika.service` and fill in your username and paths, then:

```bash
sudo ln -s "$(pwd)/dagelijksekost-paprika.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dagelijksekost-paprika
```

The server listens on port 5050. Verify it works:

```bash
curl -X POST http://localhost:5050/run
```

### iOS Shortcut

Create a Shortcut with these actions:

1. **Get Contents of URL** — `http://<server-ip>:5050/run`, method **POST**
2. **Get Dictionary Value** — key `stdout`, from the result of step 1
3. **Show Result**

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/run` | Run the import script, returns JSON with `ok`, `exit_code`, `stdout`, `stderr` |
| `GET` | `/health` | Health check |
