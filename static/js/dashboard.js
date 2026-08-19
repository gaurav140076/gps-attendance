/* Student dashboard: poll for an open window, register the device. */

const sessionsEl = document.getElementById('sessions');
const registerBtn = document.getElementById('register-device');
const deviceMsg = document.getElementById('device-message');

async function loadSessions() {
  let data;
  try {
    const response = await fetch(SESSIONS_URL);
    data = await response.json();
  } catch (err) {
    sessionsEl.innerHTML =
      '<p class="alert alert-error">Could not reach the server.</p>';
    return;
  }

  const sessions = data.sessions || [];

  if (!sessions.length) {
    sessionsEl.innerHTML =
      '<p class="alert alert-note">Your teacher has not opened attendance ' +
      'yet. This page checks every few seconds.</p>';
    return;
  }

  sessionsEl.innerHTML = sessions
    .map((s) => {
      const meta =
        `<p class="muted">${s.teacher} &middot; ${s.location} &middot; ` +
        `${s.radius_meters} m radius</p>`;

      if (s.already_marked) {
        return `<div class="card">
            <h3>${s.subject}</h3>${meta}
            <p><span class="pill pill-present">Marked</span></p>
          </div>`;
      }

      return `<div class="card">
          <h3>${s.subject}</h3>${meta}
          <p class="muted">Window closes in ${s.seconds_remaining}s</p>
          <a class="btn btn-primary" href="${MARK_PAGE}">Scan code &amp; mark attendance</a>
        </div>`;
    })
    .join('');
}

if (registerBtn) {
  registerBtn.addEventListener('click', async () => {
    registerBtn.disabled = true;
    deviceMsg.textContent = 'Registering…';

    const response = await fetch(REGISTER_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fingerprint: navigator.userAgent }),
    });
    const data = await response.json();

    deviceMsg.textContent = data.message;
    deviceMsg.className = data.success ? 'alert alert-ok' : 'alert alert-error';
    if (data.success) setTimeout(() => window.location.reload(), 900);
    else registerBtn.disabled = false;
  });
}

loadSessions();
setInterval(loadSessions, 5000);
