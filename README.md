# Magic City Pulse

A warm, two-sided Birmingham community-resource and food-dispatch prototype. Python standard library + vanilla HTML/CSS/JS. No install, npm build, or API key needed.

## Run

```sh
cd magic-city-pulse
python3 app.py
```

Python 3.9+ with IANA timezone data. The app serves http://127.0.0.1:8000 and opens the default browser automatically after binding. `PORT` changes the port. If an execution sandbox blocks sockets, run in your normal terminal. Stop with Ctrl-C.

The included JSON files are ready for a demo. Startup idempotently adds missing demo fixtures without duplicating requests or replacing edits. Leaflet/OpenStreetMap loads when connected; offline, a clickable neighborhood schematic replaces the map. Offline chat uses the same intake and eligibility rules.

## Five-minute walkthrough

1. In Neighbor View, choose **Food near Ensley tonight**. Maria's complete request is saved; Pip returns three food options with requirements and transit.
2. Choose **A safe place tonight**. Pip asks only for the missing first name; reply **Nora**. Matches enforce age, gender and positive bed counts.
3. Ask **Can I get a free bus pass?** to demonstrate the transit guardrail.
4. Open Food Provider Portal. The initial heatmap shows 9 pending requests in 35218, 5 in 35211, and 4 in 35212. Enter an organization and bags, select a host, and confirm.
5. Return to Neighbor View to see the new food-drop card and map marker. The provider view subtracts today's committed bags from unmet demand when recommending the next ZIP.

“Notify Neighbors” publishes to the local board; it does not send SMS, email, or reserve inventory. The neighbor board refreshes every ten seconds. A drop appears immediately after confirmation in the same page.

## Data and honesty

- `data/resources.json`: 10 original supplied local resources + 14 explicitly synthetic demo listings. Original shelter eligibility and bed counts are **demo overlays**, visibly labeled. Original names, addresses, coordinates, and hours are preserved.
- `data/requests.json`: 18 synthetic pending food requests plus local intake. Composite key is lowercased name + ZIP + normalized requested date/time. Upsert preserves original creation time.
- `data/deployments.json`: append-only provider demo commitments, with unique food cards for each confirmation.
- Proposed hosts, synthetic route/stop pairs, synthetic addresses, and ZIP centroid positions are demo information, not verified real-world services. Original transit details came from the supplied seed list. The app never promises free transit.
- Local JSON contains first names and intake facts. No authentication is implemented; the server binds only to loopback. This is a local demo, not a public production service.

Status is based on Chicago time and supplied schedules; it does not guarantee beds, meals, or future availability. Unknown federal hours remain `limited`; food/health search ranks open listings first but may include closed/limited alternatives, labeled in cards. Shelter search excludes closed entries, enforces explicit eligibility and requires positive beds. Provider drops expire to limited at local midnight. Volunteer reports also expire to limited at midnight. Demo listing availability is static so the offline demonstration stays usable. Requests stay pending until edited externally; dispatch commitments are tracked separately, not treated as fulfilled requests. Pending demand includes all requested dates, not just today.

Live ingestion remains available:

```sh
python3 scripts/build_dataset.py
```

It uses USDA ArcGIS pagination and streams the HRSA CSV, retaining existing downloads when a source fails. Exit 2 and `data/ingestion_report.json` indicate an incomplete fetch. Demo records, provider drops and volunteer edits survive ingestion. Fetch errors are never replaced with invented federal records. The included dataset's federal download counts remain zero because network resolution was unavailable during ingestion.

## Optional two-call LLM flow

The app loads a project-root `.env` automatically without dependencies; exported environment variables take precedence. Copy `.env.example` to `.env`, then add keys locally. Restart the server after changing credentials. `.env` and `.env.*` are ignored by Git (the blank `.env.example` is safe to track). Keys are never included in frontend assets or API responses.

Set either `GROQ_API_KEY` (llama-3.3-70b-versatile) or `GEMINI_API_KEY` (gemini-2.5-flash). Groq takes precedence. Both use the OpenAI-compatible endpoints requested for this prototype. The parser receives the message and intake state; the response generator receives only up to three deterministically filtered records. Missing-field checks and eligibility stay in Python. Provider errors fall back to deterministic replies. Configuring a key sends the intake to that provider; without keys all processing stays local.

Optional `GOOGLE_MAPS_API_KEY` enables server-side geocoding of street addresses, neighborhoods, or ZIPs before matching. Only the extracted location is sent to Google, not the full chat or neighbor name. Successful local results supply the search coordinates; a street address can also supply a missing supported ZIP. The original ZIP/neighborhood center remains the fallback for missing keys, timeouts, rejected requests, malformed responses, or results outside the Birmingham area. Neighborhood/ZIP results describe areas and are not necessarily rooftop coordinates. No map key is exposed to the browser; Leaflet continues to work independently. Geocoding requests follow [Google's Geocoding API documentation](https://developers.google.com/maps/documentation/geocoding/requests-geocoding).

## API

| Route | Behavior |
|---|---|
| `GET /` | Neighbor/provider single-page interface |
| `GET /api/status` | Safe provider configuration and last-call outcome; no keys or raw provider errors |
| `GET /api/resources` | Optional `category`, `neighborhood`, `status` filters |
| `POST /api/chat` | `{message, state?}`; returns missing fields or saved request + matches + reply + next state |
| `GET /api/provider/demand` | ZIP counts, proposed hosts, committed bags, uncovered demand, deployments |
| `POST /api/provider/confirm` | `{provider_name, base_zip, bags_count, target_zip, drop_location}`; publishes a food card |
| `POST /api/ask` | Original stateless resource search |
| `POST /api/volunteer-update` | `{resource_id, text}`; persists status, hours and timestamp |

Supported demo ZIPs: 35203, 35204, 35205, 35208, 35211, 35212, 35218. Neighborhood names map to these ZIP centers (Ensley → 35218). Relative times use America/Chicago; “tonight” defaults to 6 PM and “morning” to 9 AM. Explicit times override those defaults. Plain “today” uses the current hour. Names are first names; the request key excludes category as specified, so a same-name/ZIP/time request replaces the previous category.

## Verification

```sh
python3 -m unittest discover -s tests -v
node --check static/main.js  # optional developer syntax check; Node is not required to run
```

Tests exercise WSGI routes directly with temporary JSON stores, including static assets, parser follow-ups, upserts, strict shelter eligibility, provider persistence, immediate resource publication, input validation and record-only LLM context. Federal parsing tests use fixtures; tests do not imply live download success. The development server serializes requests; JSON writes are atomic per file. Resource and deployment files are separate writes, not a cross-file transaction.

Pip’s chat now shows whether the server has a configured provider and whether each turn used successful LLM calls or a fallback. `/api/chat` includes per-turn `llm.calls` with safe reason codes. A key exported in one terminal is not inherited by a separate terminal opened by the graphical launcher. Use `.env` for persistent configuration or restart directly in the terminal containing your exported key.

`GROQ_MODEL` overrides the originally requested Llama model. Groq deprecated free/developer access to Llama 3.3 70B in August 2026; use `GROQ_MODEL=openai/gpt-oss-120b` in `.env` for its recommended replacement. See https://console.groq.com/docs/deprecations.

The neighbor experience uses a full-width conversation followed by a map and expandable resource cards. Replies are short plain prose; overly long or Markdown-table model outputs are replaced with a friendly fallback. Matched places appear as clickable suggestions in the conversation, linked to numbered map pins and details. Food intake defaults to free-food services (pantries/meals/drops); explicit SNAP/grocery requests search retailers instead. That preference persists during missing-field follow-up. Simple greetings do not create a request or guess a name.

## Optional location and walking routes

After a completed intake, Pip offers **Yes, use my location** and **Keep using my ZIP**. Browser permission is requested only after the location button is clicked. Current position is held in page memory, can be cleared, and is sent by POST to the local backend. It is not added to requests or deployments and is never sent to the LLM. On location sharing, nearby search returns original local listings rather than synthetic destinations, with existing category, free-food and shelter eligibility filters. Closed/limited hours remain labeled and must be confirmed for the requested time.

The map now fills the available width. The app attempts locally cached Leaflet first, then pinned CDN alternatives. One failed tile no longer destroys the street map. `python3 scripts/cache_map_assets.py` optionally caches the pinned JS and CSS without dependencies. Street tiles are supplied by OpenStreetMap and require an internet connection. When unavailable, the location overview is explicitly labeled offline and is not a navigation map.

`POST /api/resources/nearby` accepts `{location:{lat,lon},state:{category,food_preference?,age?,gender?}}`. `POST /api/route` accepts `{location:{lat,lon},resource_id}`. Route destinations are selected from the saved dataset; synthetic destinations are rejected for navigation. Origin coordinates must be numeric, finite and within the Birmingham demo bounds.

Walking routes use the **pedestrian instance** at `routing.openstreetmap.de/routed-foot`, not the driving instance. Real route GeoJSON, distance and estimated duration come from OSRM/FOSSGIS. The public service needs no API key for this small noncommercial prototype; it has no availability guarantee. The app enforces at most one upstream request/second and caches at most 128 routes in memory for up to five minutes (cleared on restart). Do not deploy this public demo endpoint as a production routing dependency. [Service policy](https://github.com/Project-OSRM/osrm-backend/wiki/Demo-server).

A successful walking route is drawn on the map. If map or routing loading fails, the UI offers a Google Maps directions link. The MAX tab displays the supplied route/stop and opens current transit planning in Google Maps; no bus itinerary, fare exemption or free ride is invented. Those Maps URLs need no API key. [Maps URL documentation](https://developers.google.com/maps/documentation/urls/get-started).

Location is a one-time current-position lookup, not continuous background tracking. Browser/device position can be approximate, and network routing requires sharing origin and destination coordinates with FOSSGIS. The inline prompt explains this before requesting permission. Users can keep ZIP-based search or clear location at any time. Route estimates do not confirm food availability, opening hours, accessibility or service eligibility beyond the supplied listing.

## Conversation continuity

The current page keeps the last ten chat messages (up to 700 characters each) and sends them to the intake parser with the current state. No chat history or precise device location is written into the demand log; refreshing starts a fresh conversation. Reset clears recent history and state. The response generator still receives only the selected database records.

New explicit needs override prior categories, including natural phrases such as “a place to stay” and “somewhere to sleep.” Name/location remain known, and missing shelter age/gender are requested before matching. Category switches clear the prior map results and route while intake is incomplete. Quick reply buttons support eligibility answers, listing requirements, directions, and finding the next service. Questions about the first/second/third result read the corresponding saved listing and do not create a new demand request.

The chat includes three-dot loading feedback during network requests, soft message and card entrances, an animated Pip, and a short visual text reveal after a complete response arrives. This is a presentation effect, not streamed LLM tokens; no extra fake network delay is added. “Show all” skips the reveal. A Motion toggle and the system reduced-motion preference disable animations and reveal; replies are announced once for screen readers. Scrolling up pauses automatic chat scrolling, with a “Back to our chat” button to resume. Reply prompts and offline copy use short, everyday language.

The page also remembers the displayed food and shelter IDs separately, including explicitly selected cards. A question such as “are that food place and shelter close?” compares those actual listings instead of starting another food search. The comparison labels straight-line distance, checks supplied schedules at the requested Chicago time, displays both pins, and offers a real walking route between the two. Unknown hours and demo bed counts remain unconfirmed. Comparison and listing follow-ups do not create new requests.

To clone this prototype, run `git clone https://github.com/s-hacks/-magic-city-pulse.git magic-city-pulse`, then `cd magic-city-pulse` and `python3 app.py`. Add keys only to a local `.env` file. The repository contains demo intake fixtures, not the owner’s live intake log.
