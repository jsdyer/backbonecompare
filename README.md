# Backbone Compare

Compare the public evidence for two networks: observed BGP neighbours, listed Internet exchanges and listed facilities.

**Use it:** https://coolcode.ca/backbonecompare/ · **Source:** https://github.com/jsdyer/backbonecompare

<!-- coolcode:guide -->
Find providers by name, alias or ASN, including Eastlink (AS11260 / Bragg Communications), then compare RIPE RIS neighbours and PeeringDB exchange/facility listings. Filter IPv4 or IPv6 evidence, inspect shared and one-sided records, and see observation dates separately from fetch dates. Save named private pairs with notes, export JSON/CSV, or import earlier evidence. Uncertain RIS observations are excluded by default. Shared directory listings and AS-path adjacency do not prove physical route diversity, direct peering or a contractual transit relationship.
<!-- /coolcode:guide -->

## Use the evidence

1. Filter the starter directory locally and choose **Use as A/B**, or press **Search PeeringDB** for public name/alias matches. Search results are bounded to 25 per field; narrow a broad query. A brand may have multiple ASNs. Enter AS numbers with or without `AS`. Eight captured networks and a 13-network directory are starting points; arbitrary valid 32-bit ASNs can be looked up directly.
2. Compare shared records, records only in A's capture or records only in B's capture. Search and pagination work over the full evidence set, including large networks.
3. Choose IPv4 or IPv6. For BGP, this requires positive `v4_peers` / `v6_peers` observation counts. For exchange listings, it requires a listed address. Facilities are independent of this filter.
4. Save a private comparison name, notes and evidence in this browser, or export it. JSON captures retain each source's observation and check dates. CSV exports the current family and uncertainty filters; it includes both networks' source records so comparisons can be independently checked. Importing or restoring does not silently replace evidence with newer results.

## What the results mean

RIPE RIS is an observation point, not a complete map of the Internet. Its `left` / `right` labels describe positions in AS paths, not commercial relationships. Its `uncertain` label identifies observations that may arise from RIS's own peering; the comparison excludes them by default. Multiple observation rows for one ASN collapse into one neighbour with retained path-position labels.

PeeringDB records are participant-maintained. Multiple LAN memberships collapse by exchange ID. Facilities match by facility ID. Shared memberships do not establish direct peering, active connectivity, common fibres or independent outage domains. Empty records mean no captured evidence. A source error is not treated as zero overlap, and failed refreshes retain prior evidence with an explicit error and original dates.

**Useful next step:** ask providers about last-mile routes, common ducts, shared facilities, upstream design and failover testing. This tool supplies questions and dated evidence, not a diversity certification.

## Sources and privacy

- RIPEstat neighbours API: `https://stat.ripe.net/data/asn-neighbours/data.json?resource=AS852`
- Semantics: https://stat.ripe.net/docs/data-api/api-endpoints/asn-neighbours.html
- PeeringDB API: `https://www.peeringdb.com/api/net?asn=852&depth=2`
- API specifications: https://docs.peeringdb.com/api_specs/

`checked_at` records a successful fetch; RIPE's `query_starttime` is displayed separately as “Observed”. PeeringDB's network and membership `updated` dates describe directory edits. A newly checked source can still contain older observations. No source date is replaced with the build date.

Published defaults are fetched from this site. The Search PeeringDB button sends the entered name/alias query to PeeringDB (typing alone remains local). New ASN lookups and explicit refreshes send each ASN separately to RIPEstat and PeeringDB; those services receive normal request metadata including the visitor's IP address. Notes, pair labels and imports remain local. Save is explicit, using `coolcode:backbonecompare:pairs` in localStorage. The standard CoolCode aggregate visit counter also runs. No secret is sent to the visitor's browser.

## Optional key: exact location

In **this repository**, open **Settings → Secrets and variables → Actions → New repository secret**:

| Secret name | Value | Used by |
| --- | --- | --- |
| `PEERINGDB_API_KEY` | Your PeeringDB API key | Scheduled baseline collector only |

Direct link: https://github.com/jsdyer/backbonecompare/settings/secrets/actions

The key is optional: public GET requests work without it. It is sent as `Authorization: Api-Key ...` only to PeeringDB's official API host. The Actions workflow reads it only in the trusted main-branch source-refresh step. Never add the key to repository files, `web/`, variables exposed to the browser, generated JSON or this README. Visitor lookups use PeeringDB's public CORS-enabled API and need no login. An invalid key fails visibly; it is not silently ignored.

## Expand or customize

Edit `config/watchlist.json`:

- `asns`: baseline ASN integers (currently TELUS, Bell, Rogers, Shaw, Eastlink, Bell Aliant, TekSavvy and SaskTel). Add another valid ASN here; no frontend enumeration or hardcoded count must change. The collector validates each returned ASN. A valid ASN may have no observed neighbours or no directory listing.
- `directory_asns`: lightweight PeeringDB name/alias entries, independent of the larger evidence baseline. Add verified ASN integers here, up to 100; returned fields are validated and contact data is excluded. Arbitrary public name search remains available without editing this list.
- `default_pair`: two distinct ASNs present in the baseline.
- `max_saved_pairs`: local saved-pair limit (default 20, bounded to 50).
- `request_timeout_seconds`: source timeout (default 75; browser bounds 15–120).
- `request_interval_seconds`: collector interval between networks, minimum 3.1 seconds to respect guest rate limits.
- `peering_api_base`: browser public API base. The collector always uses the fixed official API endpoints and never sends credentials to a configured host.

Run `python3 scripts/refresh.py`, then the checks below. All sources must pass shape, ASN and record validation before the snapshot and its status probe are replaced. A malformed or unavailable source fails the workflow and preserves the last successful deployment. The collector strips contact records, private notes and unrelated metadata; only necessary public evidence is published. The API key is never part of output.

Commit configuration, `web/data/`, code and tests. Push to main or run **Browser tool · Check and publish** manually. PRs use the committed capture offline. Main builds refresh the sources, run all checks, commit captured data and publish GitHub Pages. Pages source must be GitHub Actions. No CNAME belongs in this repository.

## Schedule and watchdog

`.github/workflows/pages.yml` collects daily at **08:53 UTC**, on main pushes and manually. `.github/workflows/schedule-guard.yml` renews only that workflow and itself. Register both with the independent CoolCode watchdog; the guard does not demonstrate data freshness.

Small probe: `https://coolcode.ca/backbonecompare/data/status.json`, fields `checked_at`, `count` and `sha256` of the network JSON. Expected cadence 24 hours; alert after 72 hours, count below 1, failed workflow or bad HTTP response. Also probe `data/networks.json` and verify source observation dates independently of collection freshness.

## Development

```sh
node --test tests/*.test.mjs
python3 -m unittest discover -s tests -v
python3 scripts/build.py
python3 -m pip install -r tests/browser-requirements.txt
CHROMIUM_PATH=/usr/bin/google-chrome python3 tests/browser_smoke.py
```

The offline builder applies one deterministic content version to local scripts, module imports, CSS and the published capture fetch. A normal refresh therefore loads matching provider code and data instead of mixing a new page with cached modules. Captured JSON bytes and unversioned watchdog probe URLs remain unchanged.

CI uses Ubuntu 24.04's installed Google Chrome. Browser tests exercise arbitrary ASNs outside the presets, safe source text, IPv6 filtering, saved dated pairs, JSON download, partial-source failure preservation and mobile layout. Build output `dist/` is ignored. Follow `AGENTS.md` and the hub's tool lifecycle for catalogue, sitemap, Worker and watchdog integration.
