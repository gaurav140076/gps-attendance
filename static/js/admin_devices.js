/* Device bindings. */

async function load() {
  const target = document.getElementById('devices');
  const data = await (await fetch(DEVICES_URL)).json();

  if (!data.devices.length) {
    target.innerHTML =
      '<p class="muted">No devices registered yet. Students register on ' +
      'their first login.</p>';
    return;
  }

  target.innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Student</th><th>Registered</th><th>Status</th><th></th></tr></thead>
      <tbody>${data.devices
        .map(
          (d) => `<tr>
            <td>${d.roll_no} ${d.student}</td>
            <td>${d.registered_at}</td>
            <td><span class="pill pill-${
              d.status === 'ACTIVE' ? 'present' : 'rejected'
            }">${d.status}</span></td>
            <td>${
              d.status === 'ACTIVE'
                ? `<button class="btn btn-small revoke" data-id="${d.id}"
                     data-name="${d.student}">Revoke</button>`
                : ''
            }</td>
          </tr>`
        )
        .join('')}</tbody>
    </table></div>`;

  target.querySelectorAll('.revoke').forEach((button) =>
    button.addEventListener('click', async () => {
      if (!window.confirm(
        `Revoke ${button.dataset.name}'s device? They will be able to ` +
        `register a new phone on their next login.`
      )) return;
      await fetch(`/api/admin/devices/${button.dataset.id}/revoke`, {
        method: 'POST',
      });
      load();
    })
  );
}

load();
