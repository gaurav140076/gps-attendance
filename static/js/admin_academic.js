/* Departments, classes and subjects. */

async function post(url, body, note) {
  note.textContent = 'Saving…';
  note.className = 'muted';

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await response.json();

  if (data.success) {
    note.textContent = 'Added.';
    note.className = 'alert alert-ok';
  } else {
    note.textContent = data.message || 'Could not save that.';
    note.className = 'alert alert-error';
  }
  return data.success;
}

async function remove(url, label) {
  const response = await fetch(url, { method: 'DELETE' });
  const data = await response.json();
  if (!data.success) {
    // Deletion is refused while anything still references the row, so a
    // class with students in it cannot vanish from under them.
    window.alert(data.message || `Could not delete that ${label}.`);
    return false;
  }
  return true;
}

function table(rows, headers) {
  if (!rows.length) return '<p class="muted">None yet.</p>';
  return `<div class="table-wrap"><table>
      <thead><tr>${headers.map((h) => `<th>${h}</th>`).join('')}<th></th></tr></thead>
      <tbody>${rows.join('')}</tbody>
    </table></div>`;
}

async function load() {
  const data = await (await fetch(CATALOG_URL)).json();

  document.getElementById('departments').innerHTML = table(
    data.departments.map(
      (d) => `<tr><td>${d.name}</td>
        <td><button class="btn btn-small del" data-url="/api/admin/departments/${d.id}"
              data-label="department">Delete</button></td></tr>`
    ),
    ['Name']
  );

  document.getElementById('classes').innerHTML = table(
    data.classes.map(
      (c) => `<tr><td>${c.name}</td>
        <td><button class="btn btn-small del" data-url="/api/admin/classes/${c.id}"
              data-label="class">Delete</button></td></tr>`
    ),
    ['Name']
  );

  document.getElementById('subjects').innerHTML = table(
    data.subjects.map(
      (s) => `<tr><td>${s.name}</td><td>${s.code || '—'}</td>
        <td>${s.department || '—'}</td>
        <td><button class="btn btn-small del" data-url="/api/admin/subjects/${s.id}"
              data-label="subject">Delete</button></td></tr>`
    ),
    ['Name', 'Code', 'Department']
  );

  document.querySelectorAll('.del').forEach((b) =>
    b.addEventListener('click', async () => {
      if (!window.confirm(`Delete this ${b.dataset.label}?`)) return;
      if (await remove(b.dataset.url, b.dataset.label)) load();
    })
  );
}

function wire(formId, url, noteId) {
  const form = document.getElementById(formId);
  const note = document.getElementById(noteId);
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const body = Object.fromEntries(new FormData(form).entries());
    if (await post(url, body, note)) {
      form.reset();
      load();
    }
  });
}

wire('dept-form', '/api/admin/departments', 'dept-message');
wire('class-form', '/api/admin/classes', 'class-message');
wire('subject-form', '/api/admin/subjects', 'subject-message');

load();
