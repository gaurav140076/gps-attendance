/* Admin overview: counts, plus the misconfigurations only an admin can fix. */

const TILES = [
  ['students', 'Students'],
  ['teachers', 'Teachers'],
  ['classes', 'Classes'],
  ['subjects', 'Subjects'],
  ['locations', 'Classrooms'],
  ['sessions', 'Sessions held'],
  ['devices_bound', 'Devices bound'],
  ['pending_device_requests', 'Device requests'],
  ['refused_attempts', 'Refused attempts'],
  ['flagged_records', 'Flagged records'],
];

async function load() {
  const stats = document.getElementById('stats');
  const alerts = document.getElementById('alerts');

  let data;
  try {
    data = await (await fetch(STATS_URL)).json();
  } catch (err) {
    stats.innerHTML = '<p class="alert alert-error">Could not load stats.</p>';
    return;
  }

  stats.innerHTML = TILES.map(
    ([key, label]) => `<div class="stat-tile">
        <span class="stat-value">${data[key]}</span>
        <span class="stat-label">${label}</span>
      </div>`
  ).join('');

  const notes = [];

  // A classroom with no network registered cannot pass the network layer,
  // so attendance there fails for everyone until it is fixed. This is the
  // single most useful thing this page can tell an administrator.
  if (data.locations_without_network.length) {
    notes.push(
      `<p class="alert alert-error">
        <strong>${data.locations_without_network.length} classroom(s) have no
        network registered:</strong> ${data.locations_without_network.join(', ')}.
        Attendance will fail there for every student until you add one.
        <a href="${LOCATIONS_PAGE}">Fix now &rarr;</a>
      </p>`
    );
  }

  if (data.students_without_device > 0) {
    notes.push(
      `<p class="alert alert-note">
        ${data.students_without_device} active student(s) have not registered a
        device yet. They cannot mark attendance until they do.
      </p>`
    );
  }

  if (data.pending_device_requests > 0) {
    notes.push(
      `<p class="alert alert-note">
        ${data.pending_device_requests} device change request(s) are waiting for
        a teacher or administrator to approve.
      </p>`
    );
  }

  if (data.flagged_records > 0) {
    notes.push(
      `<p class="alert alert-note">
        ${data.flagged_records} attendance record(s) are flagged for review.
        <a href="${ATTEMPTS_PAGE}">Review &rarr;</a>
      </p>`
    );
  }

  alerts.innerHTML = notes.join('');
}

load();
