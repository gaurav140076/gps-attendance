/*
 * Student attendance check-in.
 *
 * The token lives about 15 seconds, so the page warms up the GPS fix in
 * the background from the moment it loads and submits the instant a code
 * is captured. Asking for location only after the scan would routinely
 * spend the token's whole lifetime waiting for a fix.
 */

const els = {
  banner: document.getElementById('session-banner'),
  radius: document.getElementById('radius-label'),
  startScan: document.getElementById('start-scan'),
  scannerWrap: document.getElementById('scanner-wrap'),
  scanner: document.getElementById('scanner'),
  manual: document.getElementById('manual-code'),
  tokenStatus: document.getElementById('token-status'),
  gpsStatus: document.getElementById('gps-status'),
  submit: document.getElementById('submit'),
  result: document.getElementById('result'),
  resultTitle: document.getElementById('result-title'),
  resultMessage: document.getElementById('result-message'),
  resultDetail: document.getElementById('result-detail'),
  scanCard: document.getElementById('scan-card'),
};

const state = {
  sessionId: null,
  token: null,
  position: null,
  submitting: false,
  finished: false,
  stream: null,
  watchId: null,
};

/* ---------------------------------------------------------------- session */

async function loadSession() {
  const response = await fetch(SESSIONS_URL);
  const data = await response.json();
  const open = (data.sessions || []).filter((s) => !s.already_marked);

  if (!open.length) {
    const marked = (data.sessions || []).length > 0;
    els.banner.textContent = marked
      ? 'You have already marked attendance for the open session.'
      : 'Your teacher has not opened attendance yet.';
    els.banner.className = 'alert alert-note';
    els.scanCard.hidden = true;
    return;
  }

  const session = open[0];
  state.sessionId = session.id;
  els.radius.textContent = session.radius_meters;
  els.banner.innerHTML =
    `<strong>${session.subject}</strong> &middot; ${session.teacher}` +
    `<br><span class="muted">${session.location} &middot; window closes in ` +
    `${session.seconds_remaining}s</span>`;
  els.banner.className = 'alert alert-ok';

  startGps();
}

/* -------------------------------------------------------------------- gps */

function startGps() {
  if (!navigator.geolocation) {
    els.gpsStatus.textContent = 'This device cannot report its location.';
    els.gpsStatus.className = 'alert alert-error';
    return;
  }

  els.gpsStatus.textContent = 'Getting your location…';

  state.watchId = navigator.geolocation.watchPosition(
    (position) => {
      state.position = position;
      const accuracy = Math.round(position.coords.accuracy);

      // Warn before the student spends a token on a reading the server
      // is going to refuse anyway.
      if (accuracy > MAX_ACCURACY) {
        els.gpsStatus.innerHTML =
          `Your location is only accurate to <strong>±${accuracy.toLocaleString()} m</strong>, ` +
          `but attendance needs ±${MAX_ACCURACY} m or better.<br>` +
          `Move near a window, or use a phone — laptops position themselves ` +
          `by Wi-Fi and are rarely precise enough.`;
        els.gpsStatus.className = 'alert alert-note';
      } else {
        els.gpsStatus.textContent = `Location ready (accuracy ±${accuracy} m).`;
        els.gpsStatus.className = 'muted';
      }
      refreshSubmit();
    },
    (error) => {
      const messages = {
        1: 'Location permission is required to mark attendance. Enable location access and reload.',
        2: 'Your location is unavailable. Move somewhere with a clearer view of the sky.',
        3: 'Getting your location took too long. Try again.',
      };
      els.gpsStatus.textContent = messages[error.code] || 'Could not get your location.';
      els.gpsStatus.className = 'alert alert-error';
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
  );
}

/* ------------------------------------------------------------------ token */

function captureToken(value, source) {
  if (state.finished || !value) return;

  state.token = value.trim();
  els.tokenStatus.textContent = `Code captured from ${source}.`;
  els.tokenStatus.className = 'muted';
  stopScanner();
  refreshSubmit();

  // Submit at once: the code expires in seconds.
  if (state.position) submit();
}

async function startScanner() {
  if (!('BarcodeDetector' in window)) {
    els.tokenStatus.textContent =
      'This browser cannot scan QR codes. Type the 6-character code instead.';
    els.tokenStatus.className = 'alert alert-note';
    els.manual.focus();
    return;
  }

  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment' },
    });
  } catch (err) {
    els.tokenStatus.textContent =
      'Camera unavailable. Type the 6-character code instead.';
    els.tokenStatus.className = 'alert alert-note';
    els.manual.focus();
    return;
  }

  els.scannerWrap.hidden = false;
  els.startScan.hidden = true;
  els.scanner.srcObject = state.stream;
  await els.scanner.play();

  const detector = new BarcodeDetector({ formats: ['qr_code'] });

  const tick = async () => {
    if (state.finished || !state.stream) return;
    try {
      const codes = await detector.detect(els.scanner);
      if (codes.length) {
        captureToken(codes[0].rawValue, 'the QR code');
        return;
      }
    } catch (err) {
      /* a dropped frame is not worth interrupting the scan for */
    }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function stopScanner() {
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
  }
  els.scannerWrap.hidden = true;
}

/* ----------------------------------------------------------------- submit */

function refreshSubmit() {
  els.submit.disabled = !(state.token && state.position) || state.submitting;
}

async function submit() {
  if (state.submitting || state.finished) return;
  if (!state.token || !state.position) return;

  state.submitting = true;
  refreshSubmit();
  els.submit.textContent = 'Checking…';

  const coords = state.position.coords;
  let data;

  try {
    const response = await fetch(MARK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        token: state.token,
        latitude: coords.latitude,
        longitude: coords.longitude,
        accuracy: coords.accuracy,
      }),
    });
    data = await response.json();
  } catch (err) {
    data = {
      success: false,
      message: 'Could not reach the server. Check your connection and try again.',
      retryable: true,
    };
  }

  state.submitting = false;
  els.submit.textContent = 'Mark attendance';
  showResult(data);
}

function showResult(data) {
  els.result.hidden = false;
  els.resultDetail.innerHTML = '';

  if (data.success) {
    state.finished = true;
    if (state.watchId !== null) navigator.geolocation.clearWatch(state.watchId);
    els.resultTitle.textContent = 'Attendance marked';
    els.resultTitle.className = '';
    els.resultMessage.textContent = data.message;

    const detail = [
      `Distance from classroom: ${data.distance_meters} m`,
      `Allowed radius: ${data.allowed_radius} m`,
      `Status: ${data.status}`,
    ];
    detail.forEach((text) => {
      const li = document.createElement('li');
      li.className = 'ok';
      li.textContent = text;
      els.resultDetail.appendChild(li);
    });
    els.submit.disabled = true;
    return;
  }

  els.resultTitle.textContent = 'Attendance not marked';
  els.resultMessage.textContent = data.message || 'Something went wrong.';
  els.resultMessage.className = 'alert alert-error';

  if (data.distance_meters !== undefined) {
    const li = document.createElement('li');
    li.className = 'bad';
    li.textContent =
      `You are about ${data.distance_meters} m away; the limit is ` +
      `${data.allowed_radius} m.`;
    els.resultDetail.appendChild(li);
  }

  // A retryable failure should not cost the student their attendance:
  // clear the dead code and let them scan the next rotation.
  if (data.retryable) {
    state.token = null;
    els.tokenStatus.textContent = 'Scan the code again.';
    els.tokenStatus.className = 'alert alert-note';
    els.manual.value = '';
    els.startScan.hidden = false;
    refreshSubmit();
  } else {
    state.finished = true;
  }
}

/* ------------------------------------------------------------------ wiring */

els.startScan.addEventListener('click', startScanner);
els.submit.addEventListener('click', submit);

els.manual.addEventListener('input', (event) => {
  const value = event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
  event.target.value = value;
  if (value.length === 6) captureToken(value, 'the typed code');
});

window.addEventListener('pagehide', stopScanner);

loadSession();
