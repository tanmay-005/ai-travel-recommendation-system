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
let routeCtrl = null

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
    return `<li class="place" data-i="${i}">
      <span class="num">${i + 1}</span>
      <div>
        <div class="p-name">${esc(p.place)}</div>
        <div class="p-meta">${esc(subtypeName(p.subtype))} · ${p.distance} km away</div>
        ${p.description ? `<div class="p-desc">${esc(p.description)}</div>` : ''}
        ${chips ? `<div class="p-chips">${chips}</div>` : ''}
        <div class="p-actions"><button type="button" class="dir-btn" data-i="${i}">Directions</button></div>
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
      html: `<div class="pin ${tab}"><b>${i + 1}</b></div>`,
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
  const dir = e.target.closest('.dir-btn')
  if (dir) { const p = results[tab][+dir.dataset.i]; showRoute(p.lat, p.lon); return }
  const card = e.target.closest('.place')
  if (card) {                               // clicked a card: centre its pin and open the popup
    const m = pins[+card.dataset.i]
    map.setView(m.getLatLng(), Math.max(map.getZoom(), 13))
    m.openPopup()
  }
})

// ── DIRECTIONS (from the destination centre to the place) ─────────
function showRoute(lat, lon) {
  clearRoute()
  routeCtrl = L.Routing.control({
    waypoints: [L.latLng(here.lat, here.lon), L.latLng(lat, lon)],
    router: L.Routing.osrmv1({serviceUrl: 'https://routing.openstreetmap.de/routed-car/route/v1'}),
    routeWhileDragging: false, addWaypoints: false, createMarker: () => null,
    lineOptions: {styles: [{color: '#FF6B2B', weight: 5, opacity: 0.85}]},
  }).addTo(map)
  $('clearRouteBtn').hidden = false
}
function clearRoute() {
  if (routeCtrl) { map.removeControl(routeCtrl); routeCtrl = null }
  $('clearRouteBtn').hidden = true
}
$('clearRouteBtn').addEventListener('click', clearRoute)

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
  document.title = `${here.name} · Yatra-Go`
  map.setView([here.lat, here.lon], 12)
  drawHere()
  load()
} else {
  showStart()
}