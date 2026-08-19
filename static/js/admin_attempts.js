/* Refused attempts: the trace a proxy attempt leaves behind. */

async function load() {
  const target = document.getElementById('attempts');
  const data = await (await fetch(ATTEMPTS_URL)).json();

  if (!data.attempts.length) {
    target.innerHTML = '<p class="muted">No refused attempts recorded.</p>';
    return;
  }

  target.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>When</th><th>Student</th><th>Session</th>
        <th>Reason</th><th>Distance</th><th>Source IP</th></tr></thead>
      <tbody>${data.attempts
        .map(
          (a) => `<tr>
            <td>${a.at}</td>
            <td>${a.roll_no || ''} ${a.student || '—'}</td>
            <td>${a.session_id ?? '—'}</td>
            <td><code>${a.reason || a.result}</code></td>
            <td>${a.distance_meters !== null ? a.distance_meters + ' m' : '—'}</td>
            <td><code>${a.source_ip || '—'}</code></td>
          </tr>`
        )
        .join('')}</tbody>
    </table></div>`;
}

load();
