let uLat=null,uLon=null,uMarker=null
let placeMarkers=[],routeCtrl=null
let curMode='nearby',selCat=''
let lastResults=[],favs=[]
let liveCats=new Set()

const map=L.map('map',{zoomControl:true}).setView([22.5,78.5],5)
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'© OpenStreetMap'}).addTo(map)

const CAT_COLORS={Heritage:'#FF6B2B',Museum:'#7C3AED',Temple:'#E8425A',
  Viewpoint:'#00B4A6',Beach:'#1A8FE3',Food:'#F59E0B',
  Cafe:'#9A3412',Shopping:'#8B5CF6',Nature:'#16A34A',Other:'#6B7280'}

function makeIcon(emoji,cat,isLandmark,isLive){
  const col = isLive ? '#00B4A6' : (CAT_COLORS[cat]||'#FF6B2B')
  const size = isLandmark ? 38 : 32
  const glow = isLandmark ? `box-shadow:0 0 0 3px ${col}44,0 3px 12px rgba(0,0,0,.3)` : '0 3px 10px rgba(0,0,0,.25)'
  return L.divIcon({
    html:`<div style="width:${size}px;height:${size}px;background:${col};border-radius:50% 50% 50% 0;
          transform:rotate(-45deg);display:flex;align-items:center;justify-content:center;
          ${glow};border:2.5px solid white;">
          <span style="transform:rotate(45deg);font-size:${isLandmark?16:13}px">${emoji}</span></div>`,
    iconSize:[size,size],iconAnchor:[size/2,size],popupAnchor:[0,-size-4],className:''
  })
}
const gpsIcon=L.divIcon({
  html:`<div style="width:20px;height:20px;background:#00B4A6;border-radius:50%;border:3px solid white;box-shadow:0 0 0 4px rgba(0,180,166,.3),0 2px 8px rgba(0,0,0,.3)"></div>`,
  iconSize:[20,20],iconAnchor:[10,10],className:''
})

// ── BOOT ────────────────────────────────────────────────────────
async function boot(){
  try{
    const[sRes,cRes,cityRes,favRes]=await Promise.all([
      fetch('/api/stats'),fetch('/api/categories'),
      fetch('/api/cities'),fetch('/api/favourites')
    ])
    const s=await sRes.json(), c=await cRes.json()
    const cities=await cityRes.json()
    favs=await favRes.json()
    liveCats=new Set(c.live_categories||[])

    document.getElementById('statsRow').innerHTML=
      `<div class="stat-chip"><strong>${s.total_places.toLocaleString()}</strong>Places</div>
       <div class="stat-chip"><strong>${s.total_cities}</strong>Cities</div>
       <div class="stat-chip"><strong>${s.total_landmarks||0}</strong>Icons</div>`

    const pillsEl=document.getElementById('catPills')
    c.categories.forEach(cat=>{
      const d=document.createElement('div')
      const isLive=liveCats.has(cat)
      d.className=`pill${isLive?' live-pill':''}`
      d.dataset.cat=cat
      d.innerHTML=`${c.icons[cat]||'📍'} ${cat}${isLive?' ⚡':''}`
      d.onclick=()=>pickCat(d)
      pillsEl.appendChild(d)
    })

    const cs=document.getElementById('citySelect')
    const ccs=document.getElementById('cityCatSelect')
    cities.forEach(city=>{cs.innerHTML+=`<option value="${city}">${city}</option>`})
    c.categories.forEach(cat=>{ccs.innerHTML+=`<option value="${cat}">${c.icons[cat]||''} ${cat}</option>`})
    renderFavList()
  }catch(e){console.warn('Boot error',e)}
}
boot()

// ── MODES ────────────────────────────────────────────────────────
function setMode(mode,el){
  curMode=mode
  document.querySelectorAll('.mtab').forEach(t=>t.classList.remove('on'))
  el.classList.add('on')
  document.querySelectorAll('.mpanel').forEach(p=>p.classList.remove('on'))
  document.getElementById('p-'+mode).classList.add('on')
  clearResults()
}
function pickCat(el){
  document.querySelectorAll('#catPills .pill').forEach(p=>p.classList.remove('on'))
  el.classList.add('on'); selCat=el.dataset.cat
}

// ── LOCATION ──────────────────────────────────────────────────────
async function locateCity(){
  const q=document.getElementById('citySearch').value.trim()
  if(!q){toast('Enter a city name');return}
  showLoader()
  try{
    const r=await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encodeURIComponent(q)}&countrycodes=in&limit=1`)
    const d=await r.json()
    if(!d.length){toast('City not found');hideLoader();return}
    setLocation(parseFloat(d[0].lat),parseFloat(d[0].lon),d[0].display_name.split(',')[0])
  }catch(e){toast('Search failed');hideLoader()}
}
function useGPS(){
  if(!navigator.geolocation){toast('GPS not supported');return}
  toast('Detecting GPS…')
  navigator.geolocation.getCurrentPosition(
    p=>setLocation(p.coords.latitude,p.coords.longitude,'Your Location'),
    ()=>toast('Location access denied')
  )
}
function setLocation(lat,lon,label){
  uLat=lat;uLon=lon
  map.setView([lat,lon],14)
  if(uMarker)map.removeLayer(uMarker)
  uMarker=L.marker([lat,lon],{icon:gpsIcon}).addTo(map)
    .bindPopup(`<b style="color:#00B4A6">📍 ${label}</b>`).openPopup()
  document.getElementById('locText').innerText=`${label} (${lat.toFixed(3)}, ${lon.toFixed(3)})`
  document.getElementById('locBadge').classList.add('show')
  hideLoader()
}

// ── NEARBY ────────────────────────────────────────────────────────
async function doNearby(){
  if(!uLat){toast('Set a location first');return}
  const isLiveSearch=!selCat||(selCat&&liveCats.has(selCat))
  showLoader(isLiveSearch)
  const radius=document.getElementById('radiusSlider').value
  const topN=document.getElementById('topNSlider').value
  try{
    const r=await fetch(`/api/nearby?lat=${uLat}&lon=${uLon}&category=${encodeURIComponent(selCat)}&radius=${radius}&top_n=${topN}`)
    const d=await r.json()
    if(d.error){toast(d.error);hideLoader();return}
    lastResults=d
    renderCards(d,'nearby')
    plotMarkers(d)
  }catch(e){toast('Request failed');hideLoader()}
}

async function doCity(){
  const city=document.getElementById('citySelect').value
  const cat=document.getElementById('cityCatSelect').value
  if(!city){toast('Select a city');return}
  showLoader()
  try{
    const r=await fetch(`/api/city_places?city=${encodeURIComponent(city)}&category=${encodeURIComponent(cat)}&top_n=15`)
    const d=await r.json()
    if(d.error){toast(d.error);hideLoader();return}
    lastResults=d
    renderCards(d,'city',`Top places in ${city}`)
    plotMarkers(d)
    if(d.length)map.setView([d[0].lat,d[0].lon],12)
  }catch(e){toast('Request failed');hideLoader()}
}

// ── SEARCH ────────────────────────────────────────────────────────
let srchTimer=null
document.getElementById('globalSearch').addEventListener('input',function(){
  clearTimeout(srchTimer);const q=this.value.trim()
  const drop=document.getElementById('searchDrop')
  if(q.length<2){drop.style.display='none';return}
  srchTimer=setTimeout(async()=>{
    try{
      const r=await fetch(`/api/search?q=${encodeURIComponent(q)}`)
      const d=await r.json()
      if(!d.length){drop.style.display='none';return}
      drop.innerHTML=d.map(p=>`
        <div class="sdrop-item" onclick="jumpTo(${p.lat},${p.lon},'${esc(p.place)}')">
          <span>${p.icon||'📍'}</span><span>${esc(p.place)}</span>
          <span class="sdrop-city">${esc(p.city)}</span>
          ${p.important?'<span style="font-size:.65rem;background:#F5C518;color:#5a3e00;padding:1px 5px;border-radius:8px;font-weight:700">⭐</span>':''}
        </div>`).join('')
      drop.style.display='block'
    }catch(e){}
  },280)
})
function doGlobalSearch(){
  const first=document.querySelector('.sdrop-item');if(first)first.click()
}
document.addEventListener('click',e=>{
  if(!e.target.closest('#searchWrap'))document.getElementById('searchDrop').style.display='none'
})
function jumpTo(lat,lon,name){
  map.setView([lat,lon],16);document.getElementById('searchDrop').style.display='none'
  L.popup().setLatLng([lat,lon]).setContent(`<b>📍 ${name}</b>`).openOn(map)
}

// ── RENDER CARDS ──────────────────────────────────────────────────
function renderCards(places,mode,subtitle=''){
  const el=document.getElementById('results')
  const liveBanner=document.getElementById('liveBanner')
  liveBanner.classList.remove('show')
  document.getElementById('resLabel').innerText=subtitle||`${places.length} Results`

  if(!places.length){
    el.innerHTML=`<div class="empty"><div class="empty-ico">🔍</div>
      <div class="empty-txt">No places found nearby.<br>
      For Cafe/Food, results come live from OpenStreetMap — try reducing radius or check internet connection.</div></div>`
    return
  }

  const liveCount=places.filter(p=>p.source==='live').length
  const csvCount=places.length-liveCount
  let summary=''
  if(liveCount>0&&csvCount>0) summary=`<div style="font-size:.72rem;color:var(--muted);margin-bottom:8px">
    <span class="src-badge src-live" style="font-size:.65rem">⚡ ${liveCount} live</span> &nbsp;
    <span class="src-badge src-csv" style="font-size:.65rem">📦 ${csvCount} from dataset</span></div>`
  else if(liveCount>0) summary=`<div style="font-size:.72rem;color:var(--muted);margin-bottom:8px">
    <span class="src-badge src-live" style="font-size:.65rem">⚡ ${liveCount} live from OpenStreetMap</span></div>`

  el.innerHTML=summary+places.map((p,i)=>{
    const isFav=favs.some(f=>f.place===p.place)
    const isLandmark=p.important===1
    const isLive=p.source==='live'
    const catCls=`cat-${(p.category||'Other').replace(/\s/g,'')}`
    const scoreBadge=mode==='nearby'?`<span class="score-badge">${((p.score||0)*100).toFixed(0)}%</span>`:''
    const distChip=p.distance!=null?`<span class="meta-chip">📏 ${p.distance} km</span>`:''
    const srcTag=`<span class="card-src ${isLive?'live':'csv'}">${isLive?'⚡ Live':'📦 DB'}</span>`
    // Extra info for live results
    let extraChips=''
    if(isLive){
      if(p.opening_hours) extraChips+=`<span class="info-chip">🕐 ${esc(p.opening_hours.split(';')[0])}</span>`
      if(p.cuisine) extraChips+=`<span class="info-chip">🍴 ${esc(p.cuisine)}</span>`
      if(p.phone) extraChips+=`<span class="info-chip">📞 ${esc(p.phone)}</span>`
    }
    return`<div class="card ${isLandmark?'landmark':''} ${isLive&&!isLandmark?'live-card':''}" style="animation-delay:${i*.04}s"
      onclick="showRoute(${p.lat},${p.lon},'${esc(p.place)}')">
      ${isLandmark?'<div class="landmark-badge">⭐ Iconic Landmark</div>':''}
      <div class="card-top">
        <div class="card-name">${p.icon||'📍'} ${esc(p.place)} ${srcTag}</div>
        <button class="card-fav ${isFav?'on':''}"
          onclick="toggleFav(event,${JSON.stringify(p).replace(/"/g,'&quot;')})">${isFav?'♥':'♡'}</button>
      </div>
      <div class="cat-badge ${catCls}">${esc(p.category||'Other')}</div>
      <div class="card-meta">
        <span class="meta-chip">🏙 ${esc(p.city||'—')}</span>
        ${distChip}
        ${scoreBadge}
      </div>
      ${extraChips?`<div class="card-meta" style="margin-top:4px">${extraChips}</div>`:''}
    </div>`
  }).join('')
}

// ── MAP MARKERS ───────────────────────────────────────────────────
function plotMarkers(places){
  clearMarkersArr();const bounds=[]
  if(uLat)bounds.push([uLat,uLon])
  places.forEach(p=>{
    const lat=parseFloat(p.lat),lon=parseFloat(p.lon)
    const icon=makeIcon(p.icon||'📍',p.category||'Other',p.important===1,p.source==='live')
    const srcLabel=p.source==='live'?'<span style="color:#00B4A6;font-size:.65rem">⚡ Live</span>':'<span style="color:#7C3AED;font-size:.65rem">📦 DB</span>'
    const extras=[]
    if(p.opening_hours) extras.push(`🕐 ${p.opening_hours.split(';')[0]}`)
    if(p.cuisine) extras.push(`🍴 ${p.cuisine}`)
    if(p.phone) extras.push(`📞 ${p.phone}`)
    const extraHtml=extras.length?`<div style="margin-top:4px;font-size:.7rem;color:#6B5E50">${extras.join(' · ')}</div>`:''
    const m=L.marker([lat,lon],{icon}).addTo(map)
      .bindPopup(`<div style="font-family:'Nunito',sans-serif;min-width:170px">
        ${p.important?'<div style="font-size:.62rem;background:#F5C518;color:#5a3e00;padding:1px 6px;border-radius:8px;font-weight:700;margin-bottom:4px;display:inline-block">⭐ Iconic</div>':''}
        <b style="font-size:.88rem">${p.place}</b> ${srcLabel}<br>
        <span style="font-size:.72rem;color:#6B5E50">${p.city||'—'} · ${p.category}</span><br>
        ${extraHtml}</div>`)
    m.on('click',()=>showRoute(lat,lon,p.place))
    placeMarkers.push(m);bounds.push([lat,lon])
  })
  if(bounds.length>1)map.fitBounds(bounds,{padding:[50,50]})
  else if(bounds.length===1)map.setView(bounds[0],15)
}

// ── ROUTING ───────────────────────────────────────────────────────
function showRoute(lat,lon,name){
  if(!uLat){toast('Set location first');return}
  clearRoute()
  routeCtrl=L.Routing.control({
    waypoints:[L.latLng(uLat,uLon),L.latLng(lat,lon)],
    routeWhileDragging:false,
    router:L.Routing.osrmv1({serviceUrl:'https://routing.openstreetmap.de/routed-car/route/v1'}),
    show:true,createMarker:()=>null,
    lineOptions:{styles:[{color:'#FF6B2B',weight:4,opacity:.85}]}
  }).addTo(map)
  toast(`Route to ${name}`)
}
function clearRoute(){if(routeCtrl){map.removeControl(routeCtrl);routeCtrl=null}}
function fitMarkers(){
  const pts=[]
  if(uLat)pts.push([uLat,uLon])
  placeMarkers.forEach(m=>pts.push([m.getLatLng().lat,m.getLatLng().lng]))
  if(pts.length>1)map.fitBounds(pts,{padding:[50,50]})
  else if(uLat)map.setView([uLat,uLon],14)
}

// ── FAVOURITES ────────────────────────────────────────────────────
async function toggleFav(evt,place){
  evt.stopPropagation()
  const already=favs.some(f=>f.place===place.place)
  const res=await fetch('/api/favourites',{method:already?'DELETE':'POST',
    headers:{'Content-Type':'application/json'},body:JSON.stringify(place)})
  favs=await res.json();renderFavList()
  document.querySelectorAll('.card-fav').forEach(btn=>{
    const nm=btn.closest('.card').querySelector('.card-name').innerText.replace(/^.\s/,'').replace(/⚡.*$|📦.*$/,'').trim()
    const on=favs.some(f=>f.place===nm)
    btn.classList.toggle('on',on);btn.innerText=on?'♥':'♡'
  })
  toast(already?'Removed':'Saved! ♥')
}
async function removeFav(evt,name){
  evt.stopPropagation()
  const res=await fetch('/api/favourites',{method:'DELETE',
    headers:{'Content-Type':'application/json'},body:JSON.stringify({place:name})})
  favs=await res.json();renderFavList()
}
function renderFavList(){
  const el=document.getElementById('favList')
  if(!favs.length){
    el.innerHTML=`<div class="empty" style="padding:24px"><div class="empty-ico" style="font-size:1.8rem">♡</div><div class="empty-txt">No saved places yet</div></div>`
    return
  }
  el.innerHTML=favs.map(f=>`
    <div class="fav-item" onclick="map.setView([${f.lat},${f.lon}],16)">
      <div><div class="fav-name">${f.icon||'📍'} ${esc(f.place)}</div>
      <div class="fav-city">${esc(f.city||'—')} · ${esc(f.category||'')}</div></div>
      <button class="fav-rm" onclick="removeFav(event,'${esc(f.place)}')">✕</button>
    </div>`).join('')
}
function toggleFavPanel(){document.getElementById('favPanel').classList.toggle('open')}

// ── EXPORT ────────────────────────────────────────────────────────
function exportCSV(){if(!lastResults.length){toast('No results');return}dlCSV(toCSV(lastResults),'yatra_results.csv');toast('Exported!')}
function exportFavCSV(){if(!favs.length){toast('No saved places');return}dlCSV(toCSV(favs),'yatra_saved.csv');toast('Exported!')}
function toCSV(arr){if(!arr.length)return'';const k=Object.keys(arr[0]);return[k.join(','),...arr.map(r=>k.map(key=>JSON.stringify(r[key]??'')).join(','))].join('\n')}
function dlCSV(csv,name){const a=document.createElement('a');a.href='data:text/csv;charset=utf-8,'+encodeURIComponent(csv);a.download=name;a.click()}

// ── UTILS ─────────────────────────────────────────────────────────
function clearMarkersArr(){placeMarkers.forEach(m=>map.removeLayer(m));placeMarkers=[]}
function clearResults(){
  lastResults=[]
  document.getElementById('results').innerHTML=`<div class="empty"><div class="empty-ico">🗺️</div><div class="empty-txt">Set a location and search<br>to discover places</div></div>`
  document.getElementById('resLabel').innerText='Results'
  document.getElementById('liveBanner').classList.remove('show')
  clearMarkersArr()
}
function showLoader(isLive=false){
  const banner=document.getElementById('liveBanner')
  if(isLive){banner.classList.add('show');document.getElementById('liveBannerText').innerText='Fetching live local spots from OpenStreetMap…'}
  else banner.classList.remove('show')
  document.getElementById('results').innerHTML=`<div class="loader"><div class="spinner"></div><div class="loader-txt">${isLive?'Querying live data…':'Finding best places…'}</div></div>`
}
function hideLoader(){document.getElementById('liveBanner').classList.remove('show')}

let _tt=null
function toast(msg,d=2700){const e=document.getElementById('toast');e.innerText=msg;e.classList.add('show');clearTimeout(_tt);_tt=setTimeout(()=>e.classList.remove('show'),d)}
function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}

document.getElementById('citySearch').addEventListener('keydown',e=>e.key==='Enter'&&locateCity())
document.getElementById('globalSearch').addEventListener('keydown',e=>e.key==='Enter'&&doGlobalSearch())

