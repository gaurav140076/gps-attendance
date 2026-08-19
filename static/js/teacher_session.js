/*
 * Teacher session panel: the open/close switch, the rotating code, and
 * the live roster.
 */

const els = {
  status: document.getElementById('window-status'),
  countdownWrap: document.getElementById('countdown-wrap'),
  countdown: document.getElementById('countdown'),
  openBtn: document.getElementById('open-window'),
  closeBtn: document.getElementById('close-window'),
  seconds: document.getElementById('window-seconds'),
  message: document.getElementById('window-message'),
  qrCard: document.getElementById('qr-card'),
  qrImage: document.getElementById('qr-image'),
  displayCode: document.getElementById('display-code'),
  rosterSummary: document.getElementById('roster-summary'),
  roster: document.getElementById('roster'),
  failures: document.getElementById('failures'),
  useMyLocation: document.getElementById('use-my-location'),
  anchorStatus: document.getElementById('anchor-status'),
  checkLocation: document.getElementById('check-location'),
  anchorPanel: document.querySelector('.anchor-panel'),
};

let status = INITIAL_STATUS;
let remaining = 0;
let currentCode = null;
let tokenTimer = null;
let tickTimer = null;

function setStatus(next) {
  status = next;
  els.status.textContent = next;
  els.status.className = `pill pill-${next.toLowerCase()}`;

  const open = next === 'ACTIVE';
  els.openBtn.hidden = open;
  els.closeBtn.hidden = !open;
  els.qrCard.hidden = !open;
  els.countdownWrap.hidden = !open;
  els.seconds.disabled = open;
  // The anchor is fixed for the life of the window: moving the circle
  // mid-session would change the answer for students already marked.
  if (els.anchorPanel) els.anchorPanel.hidden = open;

  if (!open) {
    stopTokenLoop();
    els.displayCode.textContent = '------';
  }
}

function formatTime(total) {
  const m = String(Math.floor(total / 60)).padStart(2, '0');
  const s = String(total % 60).padStart(2, '0');
  return `${m}:${s}`;
}

/* ------------------------------------------------------------- anchor */

/* Read the teacher's position. Resolves to null rather than rejecting:
 * a missing fix must fall back to the saved coordinates, never block the
 * window from opening. */
function readPosition(timeout = 12000) {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (position) => resolve(position.coords),
      () => resolve(null),
      { enableHighAccuracy: true, timeout, maximumAge: 0 }
    );
  });
}

function describeAccuracy(coords) {
  if (!coords) {
    return {
      text:
        'Could not read your location. The saved classroom coordinates ' +
        'will be used instead.',
      className: 'alert alert-note',
    };
  }

  const accuracy = Math.round(coords.accuracy);

  if (accuracy > MAX_ANCHOR_ACCURACY) {
    return {
      text:
        `Accuracy is ±${accuracy} m — too vague to centre a ${RADIUS_METERS} m ` +
        `circle on, so the saved coordinates will be used. Move near a ` +
        `window and check again.`,
      className: 'alert alert-note',
    };
  }

  return {
    text:
      `Ready: ±${accuracy} m. The ${RADIUS_METERS} m circle will be centred ` +
      `here, and students are given credit for this margin as well as their own.`,
    className: 'alert alert-ok',
  };
}

els.checkLocation.addEventListener('click', async () => {
  els.checkLocation.disabled = true;
  els.anchorStatus.textContent = 'Reading your location…';
  els.anchorStatus.className = 'muted';

  const coords = await readPosition();
  const described = describeAccuracy(coords);
  els.anchorStatus.textContent = described.text;
  els.anchorStatus.className = described.className;
  els.checkLocation.disabled = false;
});

els.useMyLocation.addEventListener('change', () => {
  els.checkLocation.hidden = !els.useMyLocation.checked;
  if (!els.useMyLocation.checked) {
    els.anchorStatus.textContent =
      'Using the saved classroom coordinates.';
    els.anchorStatus.className = 'muted';
  }
});

/* ------------------------------------------------------- open / close */

els.openBtn.addEventListener('click', async () => {
  els.openBtn.disabled = true;

  const body = { window_seconds: Number(els.seconds.value) };

  if (els.useMyLocation.checked) {
    els.message.textContent = 'Reading your location…';
    els.message.className = 'muted';
    const coords = await readPosition();
    if (coords) {
      body.latitude = coords.latitude;
      body.longitude = coords.longitude;
      body.accuracy = coords.accuracy;
    }
  } else {
    body.anchor = false;
  }

  els.message.textContent = 'Opening…';

  const response = await fetch(OPEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();

  els.openBtn.disabled = false;

  if (!data.success) {
    els.message.textContent = data.message || 'Could not open the window.';
    els.message.className = 'alert alert-error';
    return;
  }

  const anchor = data.anchor || {};
  let text = `Attendance is open for ${data.window_seconds} seconds. `;

  if (anchor.source === 'TEACHER') {
    text +=
      `The ${anchor.radius_meters} m circle is centred on your position ` +
      `(${anchor.latitude}, ${anchor.longitude}, ±${anchor.accuracy} m).`;
    els.message.className = 'alert alert-ok';
  } else {
    text += anchor.note || 'Using the classroom\'s saved coordinates.';
    els.message.className = 'alert alert-note';
  }

  els.message.textContent = text;
  remaining = data.seconds_remaining;
  setStatus('ACTIVE');
  startTokenLoop();
});

els.closeBtn.addEventListener('click', async () => {
  els.closeBtn.disabled = true;
  const response = await fetch(CLOSE_URL, { method: 'POST' });
  const data = await response.json();
  els.closeBtn.disabled = false;

  if (data.success) {
    setStatus(data.status);
    els.message.textContent =
      'Attendance is closed. Outstanding codes are now dead.';
    els.message.className = 'muted';
  }
});

/* -------------------------------------------------------------- tokens */

async function refreshToken() {
  let data;
  try {
    const response = await fetch(TOKEN_URL);
    data = await response.json();
  } catch (err) {
    return;
  }

  if (!data.success) {
    // The window expired on its own while this panel was open.
    setStatus(data.status || 'CLOSED');
    return;
  }

  remaining = data.seconds_remaining;

  if (data.display_code !== currentCode) {
    currentCode = data.display_code;
    els.displayCode.textContent = currentCode;
    // Cache-bust so the browser fetches the new rotation's image.
    els.qrImage.src = `${QR_URL}?v=${encodeURIComponent(currentCode)}`;
  }
}

function startTokenLoop() {
  stopTokenLoop();
  refreshToken();
  tokenTimer = setInterval(refreshToken, 2000);
  tickTimer = setInterval(() => {
    if (status !== 'ACTIVE') return;
    remaining = Math.max(0, remaining - 1);
    els.countdown.textContent = formatTime(remaining);
    if (remaining === 0) refreshToken();
  }, 1000);
}

function stopTokenLoop() {
  if (tokenTimer) clearInterval(tokenTimer);
  if (tickTimer) clearInterval(tickTimer);
  tokenTimer = null;
  tickTimer = null;
}

/* -------------------------------------------------------------- roster */

async function refreshRoster() {
  let data;
  try {
    const response = await fetch(ROSTER_URL);
    data = await response.json();
  } catch (err) {
    return;
  }
  if (!data.success) return;

  if (data.status !== status) setStatus(data.status);

  els.rosterSummary.textContent =
    `${data.marked.length} of ${data.total_enrolled} marked` +
    ` · ${data.absent.length} not yet · ${data.failures.length} refused`;

  const markedRows = data.marked
    .map(
      (r) => `<tr>
        <td>${r.roll_no}</td>
        <td>${r.name}</td>
        <td>${r.time}</td>
        <td>${r.distance_meters !== null ? r.distance_meters + ' m' : '—'}</td>
        <td><span class="pill pill-${r.status.toLowerCase()}">${r.status}</span>
          ${r.override ? '<span class="pill">manual</span>' : ''}</td>
      </tr>`
    )
    .join('');

  const absentRows = data.absent
    .map(
      (s) => `<tr>
        <td>${s.roll_no}</td>
        <td>${s.name}</td>
        <td colspan="3">
          <button class="btn btn-small mark-present" data-id="${s.student_id}">
            Mark present
          </button>
        </td>
      </tr>`
    )
    .join('');

  els.roster.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Roll</th><th>Name</th><th>Time</th>
        <th>Distance</th><th>Status</th></tr></thead>
      <tbody>${markedRows}${absentRows}</tbody>
    </table></div>`;

  els.roster.querySelectorAll('.mark-present').forEach((button) => {
    button.addEventListener('click', () => overrideStudent(button.dataset.id));
  });

  els.failures.innerHTML = data.failures.length
    ? `<div class="table-wrap"><table>
        <thead><tr><th>Time</th><th>Student</th><th>Reason</th>
          <th>Distance</th></tr></thead>
        <tbody>${data.failures
          .map(
            (f) => `<tr>
              <td>${f.at}</td>
              <td>${f.roll_no} ${f.student}</td>
              <td><code>${f.reason}</code></td>
              <td>${f.distance_meters !== null ? f.distance_meters + ' m' : '—'}</td>
            </tr>`
          )
          .join('')}</tbody>
      </table></div>`
    : '<p class="muted">None.</p>';
}

async function overrideStudent(studentId) {
  const note = window.prompt(
    'Reason for marking this student present (recorded in the audit log):',
    'Present, could not mark in'
  );
  if (note === null) return;

  await fetch(OVERRIDE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ student_id: Number(studentId), present: true, note }),
  });
  refreshRoster();
}

/* ------------------------------------------------------------- startup */

setStatus(status);
if (status === 'ACTIVE') startTokenLoop();
refreshRoster();
setInterval(refreshRoster, 3000);
