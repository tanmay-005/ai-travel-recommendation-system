# Yatra-Go: 3-minute demo script

## Before the demo (10 minutes earlier)

- [ ] `git checkout main`, `git pull`, venv active, `python run.py`, and the terminal stays open
- [ ] Browser: Chrome or Edge, **normal window** at about 1280px wide, zoom 100%, dark mode on or off (pick one)
- [ ] A demo account exists (e.g. `demo_traveller` / `demo@test.com` / `travel123`) and you are **logged out**
- [ ] My Bag already has 2 places from **Manali**, so the bag shows two trips at the end
- [ ] Open these tabs in this order:
  1. `http://127.0.0.1:5000/`
  2. Backup: `http://127.0.0.1:5000/explore?lat=15.335&lon=76.46&name=Hampi`
  3. Backup: `http://127.0.0.1:5000/explore?lat=32.2396&lon=77.1887&name=Manali`
- [ ] Run `python -m pytest -q` once; it should print `53 passed`
- [ ] `TOMTOM_API_KEY` is in `.env` (without it, directions still work but show no traffic)
- [ ] Phone hotspot ready in case the venue Wi-Fi is slow (the map tiles and place search need internet)

## The script

| Time | Do | Say |
|---|---|---|
| 0:00 | Tab 1: the landing page loads (route draws itself) | "Yatra-Go is for a solo traveller who has picked a destination but not a plan. You type one place and it shows you what's worth seeing around it." |
| 0:15 | Click the **Hampi** board | "The name goes to our server, which looks it up on OpenStreetMap and caches it. The location goes into the URL, so this page can be bookmarked or shared." |
| 0:30 | Explore loads: point at the three tabs | "One request to `/api/discover` returns three ranked lists. **Top Spots** are ranked 50% fame (does it have a Wikipedia link), 30% how well it's documented, and 20% distance." |
| 0:50 | Hover a card, then click a pin | "Card 3 and pin 3 are the same place. Hover one and the other lights up; click a pin and the list scrolls to it." |
| 1:05 | Click **Hidden Gems** | "Switching tabs doesn't call the server again; it re-draws from data already loaded. Hidden Gems are places with **no** Wikipedia page but lots of detail on the map: the ones guidebooks skip. Pushkarini, the Queen's Bath, is a good example." |
| 1:25 | Click **Things to Do** | "Activities, closest first. Hampi is a famous bouldering spot, and the data picked that up on its own." |
| 1:30 | Click **Directions** on a Top Spot, then the 2nd route in the panel | "Directions show up to three routes with live traffic from TomTom. Red and orange stretches are where it's slow, and you can switch routes here or on the map. If TomTom is down, it falls back to OSRM so it never just breaks. Switch to Walk and you get footpath routes instead." |
| 1:35 | Click **♡ Save** on a gem | "Browsing never needs an account. The moment you want to save something, it asks you to log in…" |
| 1:45 | Log in with the demo account | "…and brings you straight back to the same place, same tab. The `next` link is checked so it can only send you to pages on this site." |
| 2:00 | Click **♡ Save** again (it pops red), then **My Bag** | "Saved. My Bag groups places by trip, with a map of all of them and directions that open in Google Maps on your phone." |
| 2:20 | Point at the two groups (Hampi and Manali) | "The data is 6,624 places around 98 travel hubs, built from OpenStreetMap with a cleaning script. For small towns outside that, the server fills in live from OpenStreetMap, in parallel, and caches it." |
| 2:40 | Switch to the terminal: `python -m pytest -q` | "And it's tested: 53 tests for the distance maths, the ranking rules, the login flow, security checks and directions, each with its own empty database. They run in about 3 seconds." |
| 2:55 | `53 passed` appears | "Thank you." |

## If something goes wrong

| Problem | What to do |
|---|---|
| Place search fails (no internet, Nominatim down) | Use backup tab 2 (Hampi) or 3 (Manali): these URLs skip the search entirely |
| Map tiles stay grey | Switch to the phone hotspot. The lists and saving still work without tiles, so keep talking |
| A town shows few places or loads slowly | Stick to **Hampi**, **Manali**, **Jaipur**, **Darjeeling** or **Goa (Panaji)**: all three lists are full from the CSV alone, with no live call needed |
| The server crashed | `Ctrl+C`, then `python run.py` again (about 2 seconds) |
| Login fails | Sign up a new account on the spot (it logs you in straight away) |

## Cities and what to expect (25 km radius, from the CSV alone)

| Destination | Top Spots | Hidden Gems | Things to Do | Live top-up needed? |
|---|---|---|---|---|
| Hampi | 10 | 10 | 9 | No |
| Manali | 10 | 10 | 10 | No |
| Goa (Panaji) | 10 | 10 | 10 | No |
| Jaipur | 10 | 10 | 8 | No |
| Darjeeling | 10 | 9 | 7 | No |
| Rishikesh | 3 | 3 | 10 | Yes (tops up Top Spots and Gems) |
| Ziro | 0 | 0 | 0 | Yes (everything comes from the live lookup) |

**Ziro** is a good optional extra if someone asks "what about a town that isn't in your data?",
but only when the internet is reliable.

## Likely questions

- **Why not machine learning?** There are no ratings or user history to learn from, so a transparent
  weighted score that anyone can read and tune is more honest here. The weights are in `yatra/discover.py`.
- **Why OpenStreetMap?** It's free, has no API key, covers small Indian towns well, and its tags
  (`wikidata`, `opening_hours`, `fee`) give us the fame and detail signals.
- **Why an app factory?** `create_app()` lets every test build its own app with its own empty database.
- **How are passwords stored?** Hashed with Werkzeug's scrypt; the plain password is never saved.
- **What happens when Overpass is down?** The live top-up tries two servers with an 8-second limit each, then the page
  shows what the CSV has. Failed lookups aren't cached, so the next search tries again.
- **How does the traffic work?** The server asks TomTom for up to 3 routes with live traffic and reads
  which stretches are slow (`yatra/routing.py`). The key stays on the server. If TomTom fails, OSRM gives
  routes without traffic, and answers are cached for 5 minutes to save the free quota.
- **Does it follow you as you move?** Yes, when you start from *My location*: the browser's
  `watchPosition` moves the blue dot and the distance left is worked out in the browser from the route
  already loaded, so moving costs no API calls. More than 50 m off the route (with GPS accurate to 50 m)
  fetches a new route, at most once a minute; within 30 m it says "You've arrived".
