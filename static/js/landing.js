// Landing page: turn what the traveler typed (or their GPS position) into an Explore URL.
const form   = document.getElementById('heroSearch')
const input  = document.getElementById('heroInput')
const msg    = document.getElementById('heroMsg')
const nearMe = document.getElementById('nearMe')

function say(text, busy = false) {
  msg.textContent = text
  msg.classList.toggle('busy', busy)
}

// /explore?lat=15.33&lon=76.46&name=Hampi  (bookmarkable, shareable, back button works)
function openExplore(lat, lon, name) {
  const params = new URLSearchParams({ lat, lon, name })
  window.location.href = `/explore?${params}`
}

async function searchPlace(query) {
  say(`Looking up ${query}…`, true)
  try {
    const r = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`)
    const d = await r.json()
    if (!r.ok) { say(d.error || "Couldn't find that place."); return }
    openExplore(d.lat, d.lon, d.name)
  } catch (e) {
    say("Couldn't reach the server. Check your connection and try again.")
  }
}

form.addEventListener('submit', e => {
  e.preventDefault()                      // stop the browser's normal page reload
  searchPlace(input.value.trim())
})

document.querySelectorAll('.board').forEach(board => {
  board.addEventListener('click', () => {
    input.value = board.textContent
    searchPlace(board.dataset.place)
  })
})

nearMe.addEventListener('click', () => {
  if (!navigator.geolocation) { say("This browser can't share your location. Type a place instead."); return }
  say('Finding where you are…', true)
  nearMe.disabled = true
  navigator.geolocation.getCurrentPosition(
    pos => openExplore(pos.coords.latitude.toFixed(5), pos.coords.longitude.toFixed(5), 'Near you'),
    err => {
      nearMe.disabled = false
      say(err.code === err.PERMISSION_DENIED
        ? 'Location is blocked for this site. Allow it in your browser settings, or type a place instead.'
        : "Couldn't get your location. Type a place instead.")
    },
    { timeout: 10000 }
  )
})