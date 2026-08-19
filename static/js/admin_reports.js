/* Daily and per-student reports. */

async function loadDaily() {
  const target = document.getElementById('daily');
  const data = await (await fetch(DAILY_URL)).json();

  if (!data.count) {
    target.innerHTML = '<p class="muted">No attendance recorded today.</p>';
    return;
  }

  target.innerHTML = `<p class="muted">${data.count} record(s) today.</p>
    <div class="table-wrap"><table>
      <thead><tr><th>Roll</th><th>Student</th><th>Subject</th>
        <th>Time</th><th>Status</th></tr></thead>
      <tbody>${data.records
        .map(
          (r) => `<tr>
            <td>${r.roll_no}</td><td>${r.student}</td><td>${r.subject}</td>
            <td>${r.time}</td>
            <td><span class="pill pill-${r.status.toLowerCase()}">${r.status}</span></td>
          </tr>`
        )
        .join('')}</tbody>
    </table></div>`;
}

document.getElementById('student').addEventListener('change', async (event) => {
  const id = event.target.value;
  const target = document.getElementById('student-report');
  const exportLink = document.getElementById('export');

  if (!id) {
    target.innerHTML = '';
    exportLink.hidden = true;
    return;
  }

  exportLink.href = `/api/admin/reports/student/${id}/export.csv`;
  exportLink.hidden = false;

  const data = await (await fetch(`/api/admin/reports/student/${id}`)).json();

  if (!data.by_subject.length) {
    target.innerHTML =
      '<p class="muted">No sessions have been held for this student\'s ' +
      'class this month.</p>';
    return;
  }

  target.innerHTML = `
    <p class="big-stat">${data.overall_percentage}%<span class="muted"> this month</span></p>
    <div class="table-wrap"><table>
      <thead><tr><th>Subject</th><th>Present</th><th>Held</th><th>%</th></tr></thead>
      <tbody>${data.by_subject
        .map(
          (r) => `<tr><td>${r.subject}</td><td>${r.present}</td>
            <td>${r.total}</td><td>${r.percentage}%</td></tr>`
        )
        .join('')}</tbody>
    </table></div>`;
});

loadDaily();
