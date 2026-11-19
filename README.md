# ingress-banners

Build a mission banner page from Ingress mission medal screenshots and the Bannergress done list.
Work in progress: see [docs/spikes.md](docs/spikes.md).

```sh
python3 -m venv .venv && .venv/bin/pip install -e . pytest
.venv/bin/ingress-banners stitch shot1.png shot2.png … -o medals.png
.venv/bin/ingress-banners build medals.png --done done.json -o out/
.venv/bin/python -m pytest
```
