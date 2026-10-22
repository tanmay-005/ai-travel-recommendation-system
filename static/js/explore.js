// Explore page: one /api/discover call fills three tabs; the map shows the open tab.

// ── STATE ─────────────────────────────────────────────────────────
const params = new URLSearchParams(location.search)
const here = {
  lat:  parseFloat(params.get('lat')),
  lon:  parseFloat(params.get('lon')),
  name: params.get('name') || 'Selected place',
}
const RADII = [10, 25, 50]
let radius  = RADII.includes(+params.get('radius')) ? +params.get('radius') : 25
let results = {top_spots: [], hidden_gems: [], activities: []}
let tab     = 'top_spots'
let pins    = []            // map markers for the open tab, same order as the list
let savedIds  = new Set()   // osm_ids already in the user's bag (empty when logged out)

const TAB_NOTES = {
  top_spots:   'The best-known sights, ranked by fame, detail and distance.',
  hidden_gems: 'Well-mapped places without a Wikipedia page.',
  activities:  'Treks, camps, parks and adventure, closest first.',
}

const $ = id => document.getElementById(id)
const hasPlace = !isNaN(here.lat) && !isNaN(here.lon)

// ── MAP ───────────────────────────────────────────────────────────
const map = L.map('map', {zoomControl: true}).setView([22.5, 78.5], 5)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '© OpenStreetMap contributors',
}).addTo(map)
const pinLayer = L.layerGroup().addTo(map)
let ring = null

function drawHere() {                       // the destination dot, and a dashed ring showing the radius
  if (!ring) {
    L.marker([here.lat, here.lon], {
      icon: L.divIcon({className: '', html: '<div class="here"></div>', iconSize: [16, 16], iconAnchor: [8, 8]}),
      keyboard: false,
    }).addTo(map).bindTooltip(esc(here.name))
  } else {
    map.removeLayer(ring)
  }
  ring = L.circle([here.lat, here.lon], {
    radius: radius * 1000, color: '#00B4A6', weight: 1, dashArray: '4 6', fillOpacity: 0.03,
  }).addTo(map)
}

// ── LOADING DATA (one call, three lists) ──────────────────────────
async function load() {
  showLoading()
  try {
    const r = await fetch(`/api/discover?lat=${here.lat}&lon=${here.lon}&radius=${radius}`)
    const d = await r.json()
    if (!r.ok) throw new Error(d.error || `Server error ${r.status}`)
    results = {top_spots: d.top_spots, hidden_gems: d.hidden_gems, activities: d.activities}
    for (const key in results) $(`n-${key}`).textContent = results[key].length
    showTab(tab)
  } catch (e) {
    showError(e.message)
  }
}

// Switching tabs never asks the server again: it re-renders from `results`.
function showTab(key) {
  tab = key
  document.querySelectorAll('.tab').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === key))
  const i = Object.keys(results).indexOf(key)           // 0, 1 or 2
  $('tabLine').style.transform = `translateX(${i * 100}%)`
  $('tabs').dataset.tab = key                           // CSS picks the underline colour from this
  $('tabNote').textContent = TAB_NOTES[key]
  renderCards(results[key])
  plotMarkers(results[key])
}

// ── LIST ──────────────────────────────────────────────────────────
const SUBTYPE_NAMES = {
  hiking_route: 'Trek', place_of_worship: 'Place of worship', cave_entrance: 'Cave',
  camp_site: 'Campsite', archaeological_site: 'Archaeological site', canoe: 'Kayaking',
  scuba_diving: 'Scuba diving', theme_park: 'Theme park', water_park: 'Water park',
  nature_reserve: 'Nature reserve', national_park: 'National park', hot_spring: 'Hot spring',
}
function subtypeName(s) {
  if (!s) return ''
  return SUBTYPE_NAMES[s] || s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ')
}
function feeText(fee) {
  if (!fee) return ''
  if (fee === 'yes') return 'Entry fee'
  if (fee === 'no') return 'Free entry'
  return `Fee: ${fee}`
}

function renderCards(places) {
  const list = $('list')
  list.className = tab
  if (!places.length) { showEmpty(); return }
  list.innerHTML = places.map((p, i) => {
    const chips = [
      p.opening_hours && `<span class="chip">${esc(p.opening_hours.split(';')[0])}</span>`,
      feeText(p.fee) && `<span class="chip">${esc(feeText(p.fee))}</span>`,
      p.source === 'live' && `<span class="chip" title="Fetched live from OpenStreetMap">live</span>`,
    ].filter(Boolean).join('')
    return `<li class="place" data-i="${i}" style="animation-delay:${i * 40}ms">
      <span class="num">${i + 1}</span>
      <div>
        <div class="p-name">${esc(p.place)}</div>
        <div class="p-meta">${esc(subtypeName(p.subtype))} · ${p.distance} km away</div>
        ${p.description ? `<div class="p-desc">${esc(p.description)}</div>` : ''}
        ${chips ? `<div class="p-chips">${chips}</div>` : ''}
        <div class="p-actions">
          <button type="button" class="dir-btn" data-i="${i}">Directions</button>
          ${saveButton(p, i)}
        </div>
      </div>
    </li>`
  }).join('')
}

// ── MAP PINS (numbered like the list) ─────────────────────────────
function plotMarkers(places) {
  pinLayer.clearLayers()
  pins = places.map((p, i) => {
    const icon = L.divIcon({
      className: '', iconSize: [28, 28], iconAnchor: [14, 28], popupAnchor: [0, -26],
      html: `<div class="pin ${tab}" style="animation-delay:${i * 40}ms"><b>${i + 1}</b></div>`,
    })
    const m = L.marker([p.lat, p.lon], {icon, title: p.place})
      .bindPopup(`<b>${esc(p.place)}</b><br>${esc(subtypeName(p.subtype))} · ${p.distance} km`)
      .on('click', () => focusCard(i))
    pinLayer.addLayer(m)
    return m
  })
  const pts = places.map(p => [p.lat, p.lon]).concat([[here.lat, here.lon]])
  if (pts.length > 1) map.fitBounds(pts, {padding: [40, 40], maxZoom: 14})
  else map.setView([here.lat, here.lon], 12)
}

// ── LINK LIST AND MAP ─────────────────────────────────────────────
function pinEl(i) { return pins[i] && pins[i].getElement() && pins[i].getElement().querySelector('.pin') }
function hot(i, on) {
  const el = pinEl(i)
  if (el) el.classList.toggle('hot', on)
}
function focusCard(i) {                     // clicked a pin: scroll to its card and flash it
  const card = document.querySelector(`.place[data-i="${i}"]`)
  if (!card) return
  card.scrollIntoView({behavior: 'smooth', block: 'center'})
  card.classList.add('flash')
  setTimeout(() => card.classList.remove('flash'), 1200)
}

// One listener on the list handles every card (event delegation).
$('list').addEventListener('mouseover', e => {
  const card = e.target.closest('.place')
  document.querySelectorAll('.pin.hot').forEach(p => p.classList.remove('hot'))
  if (card) hot(+card.dataset.i, true)
})
$('list').addEventListener('mouseleave', () => {
  document.querySelectorAll('.pin.hot').forEach(p => p.classList.remove('hot'))
})
$('list').addEventListener('click', e => {
  const save = e.target.closest('.save-btn')
  if (save) { toggleSave(+save.dataset.i, save); return }
  const dir = e.target.closest('.dir-btn')
  if (dir) { const p = results[tab][+dir.dataset.i]; showRoute(p.lat, p.lon, p.place); return }
  const card = e.target.closest('.place')
  if (card) {                               // clicked a card: centre its pin and open the popup
    const m = pins[+card.dataset.i]
    map.setView(m.getLatLng(), Math.max(map.getZoom(), 13))
    m.openPopup()
  }
})

// ── DIRECTIONS: up to 3 routes, busy stretches coloured ──────────
const ROUTE_COLOUR = '#FF6B2B', OTHER_COLOUR = '#8A8F98'
const JAM_COLOURS  = {minor: '#F5C518', moderate: '#FF8A00', major: '#E8425A', closed: '#7A0019', unknown: '#FF8A00'}
const routeLayer = L.layerGroup().addTo(map)
let routeData = null                        // the last /api/route answer
let travelMode = 'car'                      // 'car' (with traffic) or 'walk' (footpaths)
let chosen = 0                              // which of its routes is selected
let routeTo = null                          // {lat, lon, name} of the place we're going to
let routeFrom = 'centre'                    // start from 'centre' (the destination) or 'me' (GPS)
let myPos = null                            // your GPS position, once the browser has shared it
let watchId = null                          // the browser's live GPS watch, while it follows you
let meDot = null                            // the blue "You are here" dot on the map
let arrived = false                         // set once you reach the place, so the countdown stops
let lastReroute = 0                         // when we last fetched a new route because you left the old one
const ARRIVE_KM = 0.03, OFF_ROUTE_KM = 0.05, REROUTE_MS = 60 * 1000   // 30 m, 50 m, once a minute

function startPoint() {
  return routeFrom === 'me' ? myPos : {lat: here.lat, lon: here.lon}
}

function showRoute(lat, lon, name) {        // the Directions button on a card
  routeTo = {lat, lon, name}
  $('rpTitle').textContent = `Directions to ${name}`
  $('routePanel').hidden = false
  if (routeFrom === 'me') startFollowing()
  loadRoutes()
}

async function loadRoutes() {
  routeLayer.clearLayers()
  routeData = null
  const from = startPoint()
  showRouteMsg('Finding routes…')
  try {
    const r = await fetch(`/api/route?from=${from.lat},${from.lon}&to=${routeTo.lat},${routeTo.lon}&mode=${travelMode}`)
    const d = await r.json()
    if (!r.ok) throw new Error(d.error || `Server error ${r.status}`)
    routeData = d
    chosen = 0                              // routes arrive fastest first
    drawRoutes()
    renderRouteList()
    map.fitBounds(d.routes.flatMap(rt => rt.points), {padding: [40, 40]})
  } catch (e) {
    showRouteMsg(e.message === 'Failed to fetch' ? "Couldn't reach the server." : e.message, true)
  }
}

function drawRoutes() {
  routeLayer.clearLayers()
  const dash = routeData.mode === 'walk' ? '1 10' : null   // walking routes are drawn as dots
  // The other routes first (grey), so the chosen one is drawn on top of them.
  routeData.routes.forEach((rt, i) => {
    if (i === chosen) return
      L.polyline(rt.points, {color: OTHER_COLOUR, weight: 5, opacity: 0.7, dashArray: dash})
      .bindTooltip(`${rt.minutes} min · ${rt.distance_km} km`, {sticky: true})
      .on('click', () => selectRoute(i))
      .addTo(routeLayer)
  })
  const rt = routeData.routes[chosen]
  L.polyline(rt.points, {color: ROUTE_COLOUR, weight: 6, opacity: 0.9, dashArray: dash})
    .bindTooltip(`${rt.minutes} min · ${rt.distance_km} km`, {sticky: true})
    .addTo(routeLayer)
  // Busy stretches on top: points start..end of this route, coloured by how bad the delay is.
  rt.jams.forEach(j => {
    L.polyline(rt.points.slice(j.start, j.end + 1), {color: JAM_COLOURS[j.level] || JAM_COLOURS.unknown, weight: 8})
      .bindTooltip(`${j.kind.replace('_', ' ')} · ${j.level} · +${j.delay_min} min`, {sticky: true})
      .addTo(routeLayer)
  })
  meDot = null
  if (routeFrom === 'me') {                 // a blue dot where you are
    meDot = L.circleMarker([myPos.lat, myPos.lon], {radius: 7, color: '#fff', weight: 3, fillColor: '#2B6CFF', fillOpacity: 1})
      .bindTooltip('You are here').addTo(routeLayer)
  }
}

// ── ROUTE PANEL: compare the routes, pick one, choose where to start ──
function trafficText(rt) {
  if (routeData.mode === 'walk') return 'on foot'
  if (rt.delay_min === null) return 'no traffic data'
  if (rt.delay_min === 0) return 'clear'
  return `+${rt.delay_min} min traffic`
}

function renderRouteList() {
  $('rpList').innerHTML = routeData.routes.map((rt, i) => `
    <li><button type="button" class="rp-route${i === chosen ? ' on' : ''}" data-i="${i}" aria-pressed="${i === chosen}">
      <span class="rp-time">${rt.minutes} min</span>
      ${i === 0 ? '<span class="rp-tag">Fastest</span>' : '<span></span>'}
      <span class="rp-meta">${rt.distance_km} km · <span class="${rt.delay_min > 0 ? 'rp-busy' : 'rp-clear'}">${trafficText(rt)}</span></span>
    </button></li>`).join('')
    $('rpNote').textContent = routeData.mode === 'walk'
    ? 'Walking routes follow footpaths, and traffic doesn\'t matter on foot. Click a route to choose it.'
    : routeData.traffic
      ? 'Live traffic from TomTom. Click a route on the map or in this list to choose it.'
      : 'Live traffic is unavailable right now, so these routes ignore traffic.'
      showProgress()
}

function selectRoute(i) {
  chosen = i
  drawRoutes()
  renderRouteList()
}

function showRouteMsg(text, retry = false) {   // loading and error messages inside the panel
  $('rpList').innerHTML = `<li class="rp-msg">${esc(text)}
    ${retry ? '<button type="button" class="link-btn" data-action="route-retry">Retry</button>' : ''}</li>`
  $('rpNote').textContent = ''
  $('rpLive').hidden = true
}

// ── LIVE PROGRESS: follow your GPS and count down the distance left ──
function kmBetween(a, b) {                  // straight-line km between two [lat, lon] points (haversine)
  const rad = Math.PI / 180
  const dLat = (b[0] - a[0]) * rad, dLon = (b[1] - a[1]) * rad
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * rad) * Math.cos(b[0] * rad) * Math.sin(dLon / 2) ** 2
  return 2 * 6371 * Math.asin(Math.sqrt(h))
}

function routeKm(pts, from = 0) {           // length of the route from point number `from` to the end
  let km = 0
  for (let i = from; i < pts.length - 1; i++) km += kmBetween(pts[i], pts[i + 1])
  return km
}

function progress(pos, pts) {               // where you are on the route: {left: km to go, off: km away from it}
  let best = {off: Infinity, i: 0, at: pts[0]}
  for (let i = 0; i < pts.length - 1; i++) {
    const a = pts[i], b = pts[i + 1]
    // Closest point on the piece a→b. Over a few hundred metres the Earth is flat enough to
    // treat lat/lon as x/y, once longitude is shrunk by cos(latitude).
    const k = Math.cos(a[0] * Math.PI / 180)
    const dx = (b[1] - a[1]) * k, dy = b[0] - a[0]
    const px = (pos[1] - a[1]) * k, py = pos[0] - a[0]
    const len2 = dx * dx + dy * dy
    const t = len2 ? Math.min(1, Math.max(0, (px * dx + py * dy) / len2)) : 0
    const at = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
    const off = kmBetween(pos, at)
    if (off < best.off) best = {off, i, at}
  }
  const next = pts[best.i + 1] || best.at
  return {left: kmBetween(best.at, next) + routeKm(pts, best.i + 1), off: best.off}
}

function showProgress() {                   // "2.3 km · 7 min left" at the top of the panel
  if (arrived) return
  $('rpLive').classList.remove('done')
  if (!routeData || routeFrom !== 'me' || !myPos) { $('rpLive').hidden = true; return }
  const rt = routeData.routes[chosen]
  const share = progress([myPos.lat, myPos.lon], rt.points).left / (routeKm(rt.points) || 1)   // 1 at the start, 0 at the end
  const km = rt.distance_km * share, mins = Math.max(1, Math.round(rt.minutes * share))
  const dist = km < 1 ? `${Math.round(km * 100) * 10} m` : `${km.toFixed(1)} km`
  $('rpLive').textContent = `${dist} · ${mins} min left`
  $('rpLive').hidden = false
}

function startFollowing() {                 // keep the blue dot and the countdown up to date
  if (watchId !== null || !navigator.geolocation) return
  watchId = navigator.geolocation.watchPosition(pos => {
    myPos = {lat: +pos.coords.latitude.toFixed(5), lon: +pos.coords.longitude.toFixed(5)}
    if (meDot) meDot.setLatLng([myPos.lat, myPos.lon])
    showProgress()
    checkRoute(pos.coords.accuracy)
  }, err => {
    if (err.code === err.PERMISSION_DENIED) {
      stopFollowing()
      $('rpNote').textContent = 'Location is blocked. Allow it in your browser, or start from the destination centre.'
      return
    }
    $('rpLive').textContent = 'Waiting for GPS signal…'   // in a tunnel, indoors: try again on the next update
    $('rpLive').hidden = false
  }, {enableHighAccuracy: true, maximumAge: 5000})
  arrived = false
}

function checkRoute(accuracy) {             // have you arrived? have you left the route?
  if (!routeData || !routeTo) return        // still loading
  const me = [myPos.lat, myPos.lon], rt = routeData.routes[chosen]
  const end = rt.points[rt.points.length - 1]
  // The route ends on the nearest road, which can be some way from the pin of a big place (a park),
  // so reaching either the end of the route or the pin counts as arriving.
  if (kmBetween(me, end) < ARRIVE_KM || kmBetween(me, [routeTo.lat, routeTo.lon]) < ARRIVE_KM) {
    stopFollowing()
    arrived = true
    $('rpLive').textContent = `You've arrived at ${routeTo.name}`
    $('rpLive').classList.add('done')
    $('rpLive').hidden = false
    return
  }
  // Off the route? Only trust it when GPS is accurate to 50 m, and fetch at most once a minute.
  const {off} = progress(me, rt.points)
  if (off > OFF_ROUTE_KM && accuracy <= 50 && Date.now() - lastReroute > REROUTE_MS) {
    lastReroute = Date.now()
    loadRoutes()                             // new routes from where you are now
  }
}

function stopFollowing() {                  // save battery: stop GPS when it isn't needed
  if (watchId !== null) navigator.geolocation.clearWatch(watchId)
  watchId = null
  $('rpLive').hidden = true
}

function setFrom(which) {
  if (which === 'me' && !myPos) {           // ask the browser for GPS once, then remember it
    if (!navigator.geolocation) { $('rpNote').textContent = "This browser can't share your location."; return }
    $('rpNote').textContent = 'Finding where you are…'
    navigator.geolocation.getCurrentPosition(
      pos => { myPos = {lat: +pos.coords.latitude.toFixed(5), lon: +pos.coords.longitude.toFixed(5)}; setFrom('me') },
      () => { $('rpNote').textContent = 'Location is blocked. Allow it in your browser, or start from the destination centre.' },
      {timeout: 10000},
    )
    return
  }
  routeFrom = which
  which === 'me' ? startFollowing() : stopFollowing()
  document.querySelectorAll('.rp-from-btn').forEach(b => {
    b.classList.toggle('on', b.dataset.from === which)
    b.setAttribute('aria-pressed', b.dataset.from === which)
  })
  if (routeTo) loadRoutes()
}

function setMode(which) {
  travelMode = which
  document.querySelectorAll('.rp-mode-btn').forEach(b => {
    b.classList.toggle('on', b.dataset.mode === which)
    b.setAttribute('aria-pressed', b.dataset.mode === which)
  })
  if (routeTo) loadRoutes()
}

function clearRoute() {
  stopFollowing()
  routeLayer.clearLayers()
  routeData = null
  routeTo = null
  $('routePanel').hidden = true
}

$('rpClose').addEventListener('click', clearRoute)
document.querySelectorAll('.rp-from-btn').forEach(b => b.addEventListener('click', () => setFrom(b.dataset.from)))
document.querySelectorAll('.rp-mode-btn').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)))
$('rpList').addEventListener('click', e => { 
  if (e.target.closest('[data-action="route-retry"]')) { loadRoutes(); return }
  const b = e.target.closest('.rp-route')
  if (b) selectRoute(+b.dataset.i)
})

// ── SAVE TO MY BAG ────────────────────────────────────────────────
function saveButton(p, i) {
  const on = savedIds.has(p.osm_id)
  return `<button type="button" class="save-btn" data-i="${i}" aria-pressed="${on}">${on ? '♥ Saved' : '♡ Save'}</button>`
}

async function loadSaved() {                // which places are already in the bag?
  try {
    const r = await fetch('/api/saved')
    if (r.ok) savedIds = new Set((await r.json()).map(s => s.osm_id))
  } catch (e) { /* logged out or offline: every heart starts empty */ }
}

async function toggleSave(i, btn) {
  const p = results[tab][i]
  const on = savedIds.has(p.osm_id)
  btn.disabled = true
  try {
    const r = on
      ? await fetch(`/api/saved/${encodeURIComponent(p.osm_id)}`, {method: 'DELETE'})
      : await fetch('/api/saved', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({osm_id: p.osm_id, place: p.place, destination: here.name,
                                label: subtypeName(p.subtype), lat: p.lat, lon: p.lon}),
        })
    if (r.status === 401) {                 // not logged in: log in, then come straight back here
      location.href = `/login?next=${encodeURIComponent(location.pathname + location.search)}`
      return
    }
    if (r.ok) {
      on ? savedIds.delete(p.osm_id) : savedIds.add(p.osm_id)
      btn.outerHTML = saveButton(p, i)
      const fresh = document.querySelector(`.place[data-i="${i}"] .save-btn`)
      if (!on) fresh.classList.add('anim-pop')         // the heart pops when it's saved
      return
    }
  } catch (e) { /* offline: leave the button as it was */ }
  btn.disabled = false
}

// ── START, LOADING, EMPTY AND ERROR STATES ─────────────────────────
function showStart() {                      // opened /explore with no place in the URL
  $('tabNote').textContent = ''
  $('list').innerHTML = `<li class="state">
    <p class="state-title">Where are you headed?</p>
    <p>Type a destination above, or use your location.</p>
  </li>`
  $('cancelChange').hidden = true           // nothing to cancel back to
  openChange()
}

let slowTimer = null
function showLoading() {
  clearTimeout(slowTimer)
  pinLayer.clearLayers()
  for (const key in results) $(`n-${key}`).textContent = ''
  $('list').className = tab
  $('list').innerHTML = Array(4).fill('<li class="skeleton"><span></span><div><i></i><i></i><i></i></div></li>').join('')
  $('tabNote').textContent = `Looking within ${radius} km of ${here.name}…`
  // Small towns trigger a live OpenStreetMap lookup, which takes a few seconds.
  slowTimer = setTimeout(() => {
    if ($('list').querySelector('.skeleton')) $('tabNote').textContent = 'Still looking. Small places take a few seconds to check live.'
  }, 2500)
}

function showEmpty() {
  clearTimeout(slowTimer)
  const next = RADII.find(km => km > radius)
  $('list').innerHTML = `<li class="state">
    <p class="state-title">Nothing here within ${radius} km.</p>
    ${next
      ? `<p>Places may be a little further out.</p>
         <button type="button" class="btn-go" data-action="widen" data-km="${next}">Search within ${next} km</button>`
      : `<p>Try another tab, or a different destination.</p>
         <button type="button" class="btn-go" data-action="change">Change destination</button>`}
  </li>`
}

function showError(message) {
  clearTimeout(slowTimer)
  $('tabNote').textContent = ''
  $('list').innerHTML = `<li class="state">
    <p class="state-title">Couldn't load places.</p>
    <p>${esc(message)}. Check your connection, then try again.</p>
    <button type="button" class="btn-go" data-action="retry">Retry</button>
  </li>`
}

$('list').addEventListener('click', e => {  // buttons inside the empty and error messages
  const btn = e.target.closest('[data-action]')
  if (!btn) return
  if (btn.dataset.action === 'retry')  load()
  if (btn.dataset.action === 'widen')  setRadius(+btn.dataset.km)
  if (btn.dataset.action === 'change') openChange()
})

// ── TOP BAR: radius and change destination ────────────────────────
function setRadius(km) {
  radius = km
  document.querySelectorAll('.r-btn').forEach(b => b.classList.toggle('on', +b.dataset.km === km))
  params.set('radius', km)
  history.replaceState(null, '', `?${params}`)   // keep the URL shareable without a reload
  if (hasPlace) { drawHere(); load() }
}
document.querySelectorAll('.r-btn').forEach(b => b.addEventListener('click', () => setRadius(+b.dataset.km)))
document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)))

function goTo(lat, lon, name) {
  const p = new URLSearchParams({lat, lon, name, radius})
  location.href = `/explore?${p}`
}
function openChange() {
  $('where').hidden = true
  $('changeForm').hidden = false
  $('changeInput').focus()
}
function closeChange() {
  if (!hasPlace) return                     // nothing to go back to
  $('changeForm').hidden = true
  $('where').hidden = false
}
$('changeBtn').addEventListener('click', openChange)
$('cancelChange').addEventListener('click', closeChange)
$('changeForm').addEventListener('submit', async e => {
  e.preventDefault()
  const q = $('changeInput').value.trim()
  try {
    const r = await fetch(`/api/geocode?q=${encodeURIComponent(q)}`)
    const d = await r.json()
    if (!r.ok) { $('changeInput').setCustomValidity(d.error); $('changeInput').reportValidity(); return }
    goTo(d.lat, d.lon, d.name)
  } catch (err) {
    $('changeInput').setCustomValidity("Couldn't reach the server."); $('changeInput').reportValidity()
  }
})
$('changeInput').addEventListener('input', () => $('changeInput').setCustomValidity(''))
$('nearMeBtn').addEventListener('click', () => {
  navigator.geolocation?.getCurrentPosition(
    pos => goTo(pos.coords.latitude.toFixed(5), pos.coords.longitude.toFixed(5), 'Near you'),
    () => { $('changeInput').setCustomValidity('Location is blocked. Type a place instead.'); $('changeInput').reportValidity() },
    {timeout: 10000},
  )
})

// ── HELPERS ───────────────────────────────────────────────────────
function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

// ── START ─────────────────────────────────────────────────────────
document.querySelectorAll('.r-btn').forEach(b => b.classList.toggle('on', +b.dataset.km === radius))
if (hasPlace) {
  $('placeName').textContent = here.name
  $('fromCentre').textContent = `${here.name} centre`
  document.title = `${here.name} · Yatra-Go`
  map.setView([here.lat, here.lon], 12)
  drawHere()
  loadSaved().then(load) 
} else {
  showStart()
}