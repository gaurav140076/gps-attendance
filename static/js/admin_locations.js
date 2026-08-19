/* Classroom setup. */

const form = document.getElementById('location-form');
const note = document.getElementById('location-message');

document.getElementById('use-my-location').addEventListener('click', () => {
  if (!navigator.geolocation) {
    note.textContent = 'This device cannot report its location.';
    note.className = 'alert alert-error';
    return;
  }

  note.textContent = 'Reading your position…';
  note.className = 'muted';

  navigator.geolocation.getCurrentPosition(
    (position) => {
      document.getElementById('latitude').value =
        position.coords.latitude.toFixed(6);
      document.getElementById('longitude').value =
        position.coords.longitude.toFixed(6);

      const accuracy = Math.round(position.coords.accuracy);
      // Say so plainly: a fix this vague will place the circle in the
      // wrong part of the building.
      note.textContent =
        accuracy > 15
          ? `Captured, but accuracy is ±${accuracy} m — too vague for a 10 m ` +
            `radius. Take several readings inside the room and average them.`
          : `Captured with ±${accuracy} m accuracy.`;
      note.className = accuracy > 15 ? 'alert alert-note' : 'alert alert-ok';
    },
    () => {
      note.textContent = 'Could not read your position.';
      note.className = 'alert alert-error';
    },
    { enableHighAccuracy: true, timeout: 20000, maximumAge: 0 }
  );
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  note.textContent = 'Saving…';
  note.className = 'muted';

  const body = Object.fromEntries(new FormData(form).entries());
  const response = await fetch(LOCATIONS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();

  if (data.success) {
    window.location.reload();
    return;
  }

  note.textContent = data.fields
    ? Object.entries(data.fields).map(([k, v]) => `${k}: ${v}`).join('; ')
    : 'Could not save the classroom.';
  note.className = 'alert alert-error';
});
