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
  $('tabNote').textContent = 'Places arrive in Step 7.2.'   // STEP 7.2 replaces this function
}

// Switching tabs never asks the server again: it re-renders from `results`.
function showTab(key) {
  tab = key
  document.querySelectorAll('.tab').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === key))
  $('tabNote').textContent = TAB_NOTES[key]
  renderCards(results[key])
  plotMarkers(results[key])
}

// ── LIST AND MAP PINS ─────────────────────────────────────────────
// STEP 7.2 replaces these two empty functions
function renderCards(places) {}
function plotMarkers(places) {}

// STEP 7.3: linking the list and the map, and directions, go here

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

// STEP 7.4: loading, empty and error states go here

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