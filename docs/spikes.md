# Spikes (2026-11-19)

## 1. Matching medal rows with the Bannergress done list — works

Test data: nikp3h's stitched screenshot (418 medal rows), the done list from AgentTools (150 banners with
pictures) and the hand-made `mission-banners/data.js` of nikp3h-ingress-stats as the answer.

How: every medal is reduced to an 8 × 8 colour fingerprint of its inside (no ring, no background);
a row is 6 of them. A Bannergress banner picture has the same layout (6 medals per row, ~100 px each),
so each screen row is compared with every row of every done banner (mean colour difference, 0..1).

| | |
|---|---|
| Rows matched to the right banner, no tuning | 395 of 410 (distance median 0.015, p95 0.050) |
| Rows of banners that are not on the done list | distance ≥ 0.068 (median 0.180) |
| Chosen: accept ≤ 0.10, and only if the best other banner is > 0.005 further | 380 rows automatic, **0 wrong**, 38 to review |
| `ingress-banners build` vs data.js | **130 of 150 banners exactly right** (id and rows), 0 wrong, 1 partly (Grüner Krieger: 4 of 9 rows), 19 to review |

What goes to review (the app's review screen):
- Banners with identical pictures (Requiem Munich series in several cities, several Second Sunday banners):
  the picture can't decide. Hints for the review screen: the neighbouring banners' places, the done date.
- Mission Day banners and some others whose medals look different from the Bannergress picture
  (distance 0.13–0.23).
- Incomplete banners and single missions (rows with fewer than 6 medals).

To do: review groups of consecutive rows are merged (rows 370–373 are 4 different banners) — split them by
row for the review screen; try the done list order (`orderBy=listAdded`) and the places of the neighbouring
banners as tie-breakers; a Bannergress search near the neighbours for banners not on the done list.

## 2. Stitching screenshots — works, also with real phone screenshots

`stitch.py` aligns consecutive shots by searching where the top of the next shot's content band is in
the previous one (grey, every 4th pixel, then refined to the pixel).

What a real capture (Pixel 6a, 1080 × 2400, Ingress → profile → mission medal strip → arrow) showed:
- The view's **header stays in place** while the medals scroll (title, agent name, a line at y 390–392).
  So the first shot is used from below the status bar (y 140, with the header), the others only from
  y 410 (below the line and a slight fade under it).
- The medals **fade out towards the bottom** from about y 2040 (2400 − 360), above the close button
  (y 2080–2190) and the navigation bar. The band ends at 2400 − 370.
  → usable band per shot: 1620 px (about 10½ medal rows).
- A drag keeps scrolling a bit after the finger lifts: a 1200 px drag moved the list ~1430 px.
  Shots must overlap ≥ 250 px, so **scroll at most about 1350 px (≈ 9 rows, a bit over half the screen)
  per screenshot**. With 1000 px drags (~1200 px scroll) everything stitched.
- Medal pictures load lazily after scrolling: wait until they appear before taking the next screenshot
  (a shot with empty circles fails to align, with a clear message).

Results:
- 10 real screenshots → 80 medal rows; every row equals the same row of nikp3h's long screenshot
  (fingerprint difference median 0.005; only the last, cut-off row differs).
- `build` on that image: 36 banners exactly as in data.js, **0 wrong**, MD 2026 Schwerin partly
  (1 of 4 rows; MD medals look different from the Bannergress picture), the rest to review.
- Synthetic test (screens cut from the long screenshot, fixed header, changing clock, close button):
  identical to the original; too little overlap is refused.
- Fixed on the way: the header line is now found as the first thin bright line (a slice through bright
  medals, e.g. the Cygnus row, also looks like a line).

Open: other phone sizes (the bands are fixed in px at 1080 wide — check a 20:9 and a 16:9 phone, or find
the header line and the fade per shot instead of fixed numbers) and other app languages (only the title
text changes). For agents: the app should say "scroll about half a screen, wait for the pictures".

## 3. GitHub — works, with the `public_repo` scope only

Tested with `tests/spike_github.py` (stdlib only, the same calls the app will make) and an OAuth App
"Ingress Banners (spike)" (client id `Ov23lif5FOXCzfSGElyt`, device flow on, expiring user tokens on,
no client secret) against the test template `elkuku/ingress-banners-spike-template` (public, marked as
template; its workflow lists `inbox/` on a Pages site).

| Step | Call | Result |
|---|---|---|
| Sign-in | device flow: `POST github.com/login/device/code` (scope `public_repo`), user enters the code at github.com/login/device, poll `POST …/login/oauth/access_token` | token with `public_repo` only. GitHub asks the user for sudo confirmation (2FA/passkey) when authorizing |
| Repo from template | `POST /repos/elkuku/ingress-banners-spike-template/generate` {owner, name, private: false} | 201; the workflow file is copied — **no `workflow` scope needed** |
| Pages | `POST /repos/{o}/{r}/pages` {build_type: "workflow"} | 201, https://elkuku.github.io/ingress-banners-spike/ |
| Upload | Git Data API: 3 blobs (1.7–2.2 MB PNG, ~2.3 s each) → tree (`inbox/<time>/NN.png`) → commit → `PATCH refs/heads/main` | one commit |
| Build | the push starts the workflow (`paths: inbox/**`); poll `GET /actions/runs?head_sha=…` | success in under a minute; page lists the 3 files |

Notes for the app:
- With "Expire user access tokens" the token lasts 8 h and comes with a refresh token (6 months): the
  app has to refresh it (`grant_type=refresh_token`, no secret needed for device-flow apps).
- A full capture is ~25–40 screenshots of ~2 MB: upload them as JPEG or WebP (the stitcher works on grey,
  slightly lossy is fine — to check) or a few at a time, and delete `inbox/` after the build so the
  repo doesn't grow with every update.
- Generated repos don't get later template changes → the agent's workflow should call a reusable
  workflow `elkuku/ingress-banners/.github/workflows/build.yml@v1` (to test next).
- Clean-up after the spike: delete `elkuku/ingress-banners-spike` and `-spike-template`, and the OAuth
  App (or keep it for development).

## 4. Bannergress sign-in — decided: WebView for now

Same as AgentTools (`BannergressAuth.kt`): client `bannergress-website`, redirect `https://bannergress.com/`
caught in a WebView, PKCE. Done list: `GET https://api.bannergress.com/bnrs?listTypes=done&orderBy=listAdded&orderDirection=DESC&limit=100&offset=…`.
Later: an own Keycloak client and a Custom Tab (see OpenBanners).
