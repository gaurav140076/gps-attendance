/* Teacher dashboard: create sessions, handle device change requests. */

document.getElementById('create-session').addEventListener('submit', async (event) => {
  event.preventDefault();
  const note = document.getElementById('create-message');
  note.textContent = 'Creating…';

  const body = Object.fromEntries(new FormData(event.target).entries());
  const response = await fetch(CREATE_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();

  if (data.success) {
    window.location = `/teacher/sessions/${data.session_id}`;
  } else {
    note.textContent = data.message || 'Could not create the session.';
    note.className = 'alert alert-error';
  }
});

async function loadRequests() {
  const target = document.getElementById('device-requests');
  let data;
  try {
    const response = await fetch(REQUESTS_URL);
    data = await response.json();
  } catch (err) {
    return;
  }

  if (!data.requests.length) {
    target.innerHTML = '<p class="muted">No pending requests.</p>';
    return;
  }

  target.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Student</th><th>Reason</th><th>Requested</th><th></th></tr></thead>
      <tbody>${data.requests
        .map(
          (r) => `<tr>
            <td>${r.roll_no} ${r.student}</td>
            <td>${r.reason || '—'}</td>
            <td>${r.requested_at}</td>
            <td>
              <button class="btn btn-small approve" data-id="${r.id}">Approve</button>
              <button class="btn btn-small reject" data-id="${r.id}">Reject</button>
            </td>
          </tr>`
        )
        .join('')}</tbody>
    </table></div>`;

  target.querySelectorAll('.approve').forEach((b) =>
    b.addEventListener('click', () => decide(b.dataset.id, 'approve'))
  );
  target.querySelectorAll('.reject').forEach((b) =>
    b.addEventListener('click', () => decide(b.dataset.id, 'reject'))
  );
}

async function decide(id, action) {
  await fetch(`/api/teacher/device-requests/${id}/${action}`, { method: 'POST' });
  loadRequests();
}

loadRequests();
