// Login and sign-up: send the form as JSON, show the server's errors next to the right field.
const form   = document.getElementById('authForm')
const submit = form.querySelector('.btn-submit')
const formError = document.getElementById('formError')

// Where to go afterwards. Only same-site paths are allowed (see safe_next in pages.py).
function nextUrl() {
  const next = new URLSearchParams(location.search).get('next')
  if (next && next.startsWith('/') && !next.startsWith('//') && !next.includes('\\')) return next
  return '/'
}

function clearErrors() {
  formError.textContent = ''
  form.querySelectorAll('.field-error').forEach(p => p.textContent = '')
  form.querySelectorAll('input').forEach(i => i.removeAttribute('aria-invalid'))
}

function shake() {                          // replay the shake, even if it ran a moment ago
  form.classList.remove('anim-shake')
  void form.offsetWidth                     // makes the browser notice the class was removed
  form.classList.add('anim-shake')
}

function showErrors(data) {
  const fields = data.errors || {}
  let shown = false
  for (const [name, message] of Object.entries(fields)) {
    const slot = document.getElementById(`err-${name}`)
    const input = form.elements[name]
    if (slot && input) {
      slot.textContent = message
      input.setAttribute('aria-invalid', 'true')
      if (!shown) input.focus()               // put the cursor in the first field to fix
      shown = true
    }
  }
  if (!shown) formError.textContent = data.error || 'Something went wrong. Please try again.'
}

form.addEventListener('submit', async e => {
  e.preventDefault()
  clearErrors()
  const body = Object.fromEntries(new FormData(form))   // {email: "...", password: "..."}
  const label = submit.textContent
  submit.disabled = true
  submit.textContent = submit.dataset.busy
  submit.classList.add('busy')               // shows the spinner ring        

  try {
    const r = await fetch(form.dataset.endpoint, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    })
    const data = await r.json()
    if (r.ok) { location.href = nextUrl(); return }
    showErrors(data)                       // typed values stay in the inputs
    shake()                                                                
  } catch (err) {
    formError.textContent = "Couldn't reach the server. Check your connection and try again."
  }
  submit.disabled = false
  submit.textContent = label
  submit.classList.remove('busy')                                            
})

// Show / hide password
document.querySelectorAll('.pw-toggle').forEach(btn => {
  btn.addEventListener('click', () => {
    const input = document.getElementById(btn.getAttribute('aria-controls'))
    const show = input.type === 'password'
    input.type = show ? 'text' : 'password'
    btn.textContent = show ? 'Hide' : 'Show'
    btn.setAttribute('aria-pressed', show)
  })
})