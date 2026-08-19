/* Student management. */

const form = document.getElementById('student-form');
const note = document.getElementById('student-message');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  note.textContent = 'Saving…';
  note.className = 'muted';

  const body = Object.fromEntries(new FormData(form).entries());
  const response = await fetch(STUDENTS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();

  if (data.success) {
    form.reset();
    note.textContent = 'Student added.';
    note.className = 'alert alert-ok';
    load();
    return;
  }

  note.textContent =
    data.message ||
    { EMAIL_TAKEN: 'That email is already registered.',
      MISSING_FIELDS: 'Name, roll number, email and password are required.' }[data.error] ||
    'Could not add the student.';
  note.className = 'alert alert-error';
});

async function load() {
  const target = document.getElementById('students');
  const data = await (await fetch(STUDENTS_URL)).json();

  if (!data.students.length) {
    target.innerHTML = '<p class="muted">No students yet.</p>';
    return;
  }

  target.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Roll</th><th>Name</th><th>Email</th><th>Class</th>
        <th>Device</th><th>Status</th><th></th></tr></thead>
      <tbody>${data.students
        .map(
          (s) => `<tr>
            <td>${s.roll_no}</td>
            <td>${s.name}</td>
            <td class="muted">${s.email}</td>
            <td>${s.class || '<span class="pill pill-rejected">no class</span>'}</td>
            <td>${
              s.device_registered
                ? '<span class="pill pill-present">bound</span>'
                : '<span class="pill pill-flagged">none</span>'
            }</td>
            <td>${s.active ? 'active' : '<span class="muted">inactive</span>'}</td>
            <td>${
              s.active
                ? `<button class="btn btn-small deactivate" data-id="${s.id}"
                     data-name="${s.name}">Deactivate</button>`
                : `<button class="btn btn-small reactivate" data-id="${s.id}">Reactivate</button>`
            }</td>
          </tr>`
        )
        .join('')}</tbody>
    </table></div>`;

  target.querySelectorAll('.deactivate').forEach((b) =>
    b.addEventListener('click', async () => {
      if (!window.confirm(
        `Deactivate ${b.dataset.name}? Their attendance history is kept — ` +
        `deactivating only stops them logging in.`
      )) return;
      await fetch(`${STUDENTS_URL}/${b.dataset.id}`, { method: 'DELETE' });
      load();
    })
  );

  target.querySelectorAll('.reactivate').forEach((b) =>
    b.addEventListener('click', async () => {
      await fetch(`${STUDENTS_URL}/${b.dataset.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: true }),
      });
      load();
    })
  );
}

load();
