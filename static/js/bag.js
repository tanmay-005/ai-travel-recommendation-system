// My Bag: list saved places grouped by destination, show them all on a map, allow removing.
const $ = id => document.getElementById(id)

const map = L.map('bagMap').setView([22.5, 78.5], 5)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: 19, attribution: '© OpenStreetMap contributors',
}).addTo(map)
const pinIcon = L.divIcon({className: '', html: '<div class="bag-pin"></div>', iconSize: [14, 14], iconAnchor: [7, 7]})
const markers = {}              // osm_id -> Leaflet marker
let places = []

async function loadBag() {
  try {
    const r = await fetch('/api/saved')
    if (r.status === 401) { location.href = '/login?next=/bag'; return }
    if (!r.ok) throw new Error(`Server error ${r.status}`)
    places = await r.json()
    render()
  } catch (e) {
    $('bagCount').textContent = "Couldn't load your bag. Refresh the page to try again."
  }
}

function render() {
  if (!places.length) {
    $('bagCount').innerHTML = 'Your bag is empty. <a href="/">Find a destination</a> and tap ♡ Save on any place.'
    $('groups').innerHTML = ''
    return
  }
  $('bagCount').textContent = `${places.length} saved ${places.length === 1 ? 'place' : 'places'}`

  // Group by the destination they were exploring: {"Hampi": [...], "Rishikesh": [...]}
  const groups = {}
  for (const p of places) (groups[p.destination || 'Other places'] ??= []).push(p)

  $('groups').innerHTML = Object.entries(groups).map(([dest, items]) => `
    <section class="group">
      <h2>${esc(dest)}</h2>
      <ul>${items.map(p => `
        <li class="item" data-id="${esc(p.osm_id)}">
          <div>
            <div class="item-name">${esc(p.place)}</div>
            <div class="item-meta">${esc(p.label || 'Place')}</div>
          </div>
          <div class="item-actions">
            <a href="https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lon}"
               target="_blank" rel="noopener">Directions</a>
            <button type="button" class="remove-btn">Remove</button>
          </div>
        </li>`).join('')}
      </ul>
    </section>`).join('')

  for (const id in markers) map.removeLayer(markers[id])
  for (const p of places) {
    markers[p.osm_id] = L.marker([p.lat, p.lon], {icon: pinIcon, title: p.place})
      .bindPopup(`<b>${esc(p.place)}</b><br>${esc(p.destination || '')}`).addTo(map)
  }
  map.fitBounds(places.map(p => [p.lat, p.lon]), {padding: [40, 40], maxZoom: 13})
}

$('groups').addEventListener('click', async e => {
  const btn = e.target.closest('.remove-btn')
  if (btn) {
    const id = btn.closest('.item').dataset.id
    btn.disabled = true
    const r = await fetch(`/api/saved/${encodeURIComponent(id)}`, {method: 'DELETE'}).catch(() => null)
    if (r && r.ok) {
      places = places.filter(p => p.osm_id !== id)
      render()
    } else {
      btn.disabled = false
    }
    return
  }
  const item = e.target.closest('.item')    // clicked a place: show it on the map
  if (item && !e.target.closest('a')) {
    const m = markers[item.dataset.id]
    map.setView(m.getLatLng(), 14)
    m.openPopup()
  }
})

function esc(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
}

loadBag()