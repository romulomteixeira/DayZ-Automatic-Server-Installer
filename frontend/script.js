const api = window.API_BASE || 'http://localhost:8000';
let selectedServerId = null;
let cpuChart;
let ramChart;
let playersChart;

const q = (sel) => document.querySelector(sel);

function switchView(name) {
  document.querySelectorAll('.top-menu button').forEach(b => b.classList.toggle('active', b.dataset.view === name));
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === `view-${name}`));
}

document.querySelectorAll('.top-menu button').forEach(btn => btn.onclick = () => switchView(btn.dataset.view));

async function getJson(url, opts) {
  const res = await fetch(url, opts);
  return await res.json();
}

async function refreshSidebar() {
  const data = await getJson(`${api}/api/home`);
  q('#cpu').textContent = `${data.cpu}%`;
  q('#ram').textContent = `${data.ram}%`;
  q('#players-online').textContent = data.players_online;
  q('#players-list').innerHTML = data.players.map(p => `<li>${p}</li>`).join('') || '<li>Nenhum jogador</li>';
}

function buildChart(ctx, label, points, key, color) {
  return new Chart(ctx, {
    type: 'bar',
    data: {
      labels: points.map(p => new Date(p.ts).toLocaleDateString('pt-BR')),
      datasets: [{ label, data: points.map(p => p[key]), backgroundColor: color }],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });
}

async function refreshCharts() {
  const range = q('#range').value;
  const start = q('#start-date').value;
  const end = q('#end-date').value;
  let url = `${api}/api/metrics?range=${range}`;
  if (start) url += `&start=${encodeURIComponent(new Date(start).toISOString())}`;
  if (end) url += `&end=${encodeURIComponent(new Date(end).toISOString())}`;

  const data = await getJson(url);
  const points = data.points || [];

  cpuChart?.destroy();
  ramChart?.destroy();
  playersChart?.destroy();

  cpuChart = buildChart(q('#cpuChart'), 'CPU (%)', points, 'cpu', '#60a5fa');
  ramChart = buildChart(q('#ramChart'), 'RAM (%)', points, 'ram', '#34d399');
  playersChart = buildChart(q('#playersChart'), 'Jogadores', points, 'players', '#fbbf24');
}

async function refreshServers() {
  const data = await getJson(`${api}/api/servers`);
  q('#servers-list').innerHTML = data.servers.map(s => `
    <li>
      <strong>${s.name}</strong> (${s.port}) - ${s.status}
      <div>
        <button onclick="window.selectServer('${s.id}')">Selecionar</button>
        <button onclick="window.serverAction('${s.id}','start')">Iniciar</button>
        <button onclick="window.serverAction('${s.id}','stop')">Parar</button>
        <button class="danger" onclick="window.deleteServer('${s.id}')">Deletar</button>
      </div>
    </li>
  `).join('') || '<li>Nenhum servidor criado.</li>';
}

window.serverAction = async (id, action) => {
  await getJson(`${api}/api/servers/${id}/${action}`, { method: 'POST' });
  await refreshServers();
  await refreshSidebar();
};

window.deleteServer = async (id) => {
  await getJson(`${api}/api/servers/${id}`, { method: 'DELETE' });
  if (selectedServerId === id) selectedServerId = null;
  await refreshServers();
  await refreshMods();
};

window.selectServer = async (id) => {
  selectedServerId = id;
  const data = await getJson(`${api}/api/servers`);
  const server = data.servers.find(s => s.id === id);
  if (!server) return;

  q('#server-detail').innerHTML = `
    <h3>${server.name}</h3>
    <p>Porta: ${server.port}</p>
    <h4>Configuração</h4>
    <label>Mapa <input id="cfg-map" value="${server.config.map}" /></label>
    <label>Max jogadores <input id="cfg-max" type="number" value="${server.config.max_players}" /></label>
    <label>Velocidade jogo <input id="cfg-speed" type="number" step="0.1" value="${server.config.game_speed}" /></label>
    <label>Multiplicador tempo <input id="cfg-time" type="number" step="0.1" value="${server.config.time_multiplier}" /></label>
    <button id="save-config">Salvar config</button>

    <h4>Mods do servidor</h4>
    <ul>${server.mods.map(m => `<li>${m} <button onclick="window.uninstallServerMod('${server.id}','${m}')">Desinstalar</button></li>`).join('') || '<li>Sem mods</li>'}</ul>

    <h4>Buscar mod na Workshop</h4>
    <input id="workshop-query" placeholder="Nome do mod" />
    <button id="search-workshop">Buscar</button>
    <ul id="workshop-results"></ul>
  `;

  q('#save-config').onclick = async () => {
    await getJson(`${api}/api/servers/${server.id}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        map: q('#cfg-map').value,
        max_players: Number(q('#cfg-max').value),
        game_speed: Number(q('#cfg-speed').value),
        time_multiplier: Number(q('#cfg-time').value),
      }),
    });
    await refreshServers();
  };

  q('#search-workshop').onclick = async () => {
    const query = q('#workshop-query').value;
    const results = await getJson(`${api}/api/workshop/search?q=${encodeURIComponent(query)}`);
    q('#workshop-results').innerHTML = results.results.map(r => `<li>${r.title} (${r.id}) <button onclick="window.installServerMod('${server.id}','${r.id}')">Instalar</button></li>`).join('') || '<li>Nada encontrado</li>';
  };
};

window.installServerMod = async (serverId, modId) => {
  await getJson(`${api}/api/servers/${serverId}/mods/install`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mod_id: modId }),
  });
  await window.selectServer(serverId);
  await refreshMods();
};

window.uninstallServerMod = async (serverId, modId) => {
  await getJson(`${api}/api/servers/${serverId}/mods/uninstall`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mod_id: modId }),
  });
  await window.selectServer(serverId);
  await refreshMods();
};

q('#open-create-server').onclick = () => q('#server-modal').classList.remove('hidden');
q('#close-modal').onclick = () => q('#server-modal').classList.add('hidden');
q('#create-server').onclick = async () => {
  await getJson(`${api}/api/servers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: q('#server-name').value, port: Number(q('#server-port').value) }),
  });
  q('#server-modal').classList.add('hidden');
  q('#server-name').value = '';
  q('#server-port').value = '';
  await refreshServers();
};

async function refreshMods() {
  const filter = q('#mods-filter').value;
  const data = await getJson(`${api}/api/mods?filter=${filter}`);
  q('#mods-list').innerHTML = data.mods.map(m => `
    <li>${m.title} (${m.id}) - ${m.in_use ? 'Em uso' : 'Não usado'}
      <button class="danger" ${m.in_use ? 'disabled' : ''} onclick="window.removeMod('${m.id}')">Remover</button>
    </li>
  `).join('') || '<li>Nenhum mod.</li>';
}

window.removeMod = async (id) => {
  await getJson(`${api}/api/mods/${id}`, { method: 'DELETE' });
  await refreshMods();
};

q('#refresh-mods').onclick = refreshMods;
q('#mods-filter').onchange = refreshMods;
q('#apply-range').onclick = refreshCharts;

(async function init() {
  await refreshSidebar();
  await refreshCharts();
  await refreshServers();
  await refreshMods();
  setInterval(refreshSidebar, 10000);
})();
