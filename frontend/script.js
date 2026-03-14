const apiBase = window.API_BASE || 'http://localhost:8000';

async function fetchStatus() {
  const res = await fetch(`${apiBase}/api/status`);
  const data = await res.json();
  document.getElementById('cpu').textContent = `${data.cpu}%`;
  document.getElementById('ram').textContent = `${data.ram}%`;
  document.getElementById('players-count').textContent = data.players.length;
  document.getElementById('players').innerHTML = data.players.map(p => `<li>${p}</li>`).join('') || '<li>Nenhum jogador</li>';
  document.getElementById('rcon-error').textContent = data.rcon_error ? `RCON indisponível: ${data.rcon_error}` : '';
}

async function postJson(url, payload = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  document.getElementById('output').textContent = JSON.stringify(data, null, 2);
}

document.getElementById('sync-mods').addEventListener('click', () => {
  postJson(`${apiBase}/api/mods/sync`, { include_chiemsee: false });
});

document.getElementById('install-chiemsee').addEventListener('click', () => {
  postJson(`${apiBase}/api/maps/chiemsee/install`);
});

fetchStatus();
setInterval(fetchStatus, 10000);
