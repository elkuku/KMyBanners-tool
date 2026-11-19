# ingress-banners-tool

Build a mission banner page from Ingress mission medal screenshots and the Bannergress done list.
Work in progress: see [docs/spikes.md](docs/spikes.md).

```sh
python3 -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/ingress-banners-tool stitch shot1.png shot2.png … -o medals.png
.venv/bin/ingress-banners-tool build medals.png --done done.json -o out/
.venv/bin/ingress-banners-tool site --repo <agent repo> -o _site --url https://…/   # the whole page
.venv/bin/python -m pytest
```

## For agents' repos

Agents' page repos (named `ingress-banners`, made by the
[Android app](https://github.com/elkuku/ingress-banners-android)) are made from [ingress-banners-template](https://github.com/elkuku/ingress-banners-template).
Their workflow calls the shared build:

```yaml
jobs:
  page:
    uses: elkuku/ingress-banners-tool/.github/workflows/build-page.yml@v1
```

It stitches the newest screenshots in `inbox/` into `capture/medals.jpg` (and empties the inbox),
matches the medal rows with `done.json` and the agent's `corrections.json`, and deploys the page to
GitHub Pages. The page (`src/ingress_banners/site/`) comes from
[nikp3h-ingress-stats](https://github.com/elkuku/nikp3h-ingress-stats): Leaflet 1.9.4, TopoJSON 3.0.2,
flags from flag-icons (MIT), country outlines from Natural Earth via world-atlas.
