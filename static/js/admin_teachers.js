/* Teacher management. */

const form = document.getElementById('teacher-form');
const note = document.getElementById('teacher-message');

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  note.textContent = 'Saving…';
  note.className = 'muted';

  const body = Object.fromEntries(new FormData(form).entries());
  const response = await fetch(TEACHERS_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();

  if (data.success) {
    form.reset();
    note.textContent = data.teacher_id
      ? `Teacher added with ID ${data.teacher_id}.`
      : 'Teacher added.';
    note.className = 'alert alert-ok';
    load();
    return;
  }

  note.textContent = data.message || 'Could not add the teacher.';
  note.className = 'alert alert-error';
});

async function load() {
  const target = document.getElementById('teachers');
  const data = await (await fetch(TEACHERS_URL)).json();

  if (!data.teachers.length) {
    target.innerHTML = '<p class="muted">No teachers yet.</p>';
    return;
  }

  target.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Teacher ID</th><th>Name</th><th>Email</th><th></th></tr></thead>
      <tbody>${data.teachers
        .map(
          (t) => `<tr>
            <td>${
              t.teacher_id
                ? `<code>${t.teacher_id}</code>`
                : '<span class="muted">—</span>'
            }</td>
            <td>${t.name}</td>
            <td class="muted">${t.email}</td>
            <td>
              <button class="btn btn-small edit-id" data-id="${t.id}"
                data-current="${t.teacher_id || ''}">Set ID</button>
              <button class="btn btn-small remove" data-id="${t.id}"
                data-name="${t.name}">Delete</button>
            </td>
          </tr>`
        )
        .join('')}</tbody>
    </table></div>`;

  target.querySelectorAll('.edit-id').forEach((b) =>
    b.addEventListener('click', async () => {
      const next = window.prompt(
        'Teacher ID (leave blank to clear):', b.dataset.current);
      if (next === null) return;

      const response = await fetch(`${TEACHERS_URL}/${b.dataset.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ teacher_id: next }),
      });
      const data = await response.json();
      if (!data.success) {
        window.alert(data.message || 'Could not set that ID.');
        return;
      }
      load();
    })
  );

  target.querySelectorAll('.remove').forEach((b) =>
    b.addEventListener('click', async () => {
      if (!window.confirm(`Delete ${b.dataset.name}?`)) return;

      const response = await fetch(`${TEACHERS_URL}/${b.dataset.id}`, {
        method: 'DELETE',
      });
      const data = await response.json();

      if (!data.success) {
        // Deleting a teacher who owns sessions would orphan the audit
        // trail behind every attendance record in them.
        window.alert(data.message || 'Could not delete that teacher.');
        return;
      }
      load();
    })
  );
}

load();
