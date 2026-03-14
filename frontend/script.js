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

  const cfgEntries = Object.entries(server.config || {});
  q('#server-detail').innerHTML = `
    <h3>${server.name}</h3>
    <p>Porta: ${server.port}</p>
    <h4>Configuração</h4>
    <div id="cfg-list">
      ${cfgEntries.map(([key, value]) => `
        <label style="display:flex; gap:8px; align-items:center; margin-bottom:6px;">
          <input class="cfg-key" value="${key}" style="max-width:240px;" />
          <input class="cfg-value" value="${String(value).replace(/"/g, '&quot;')}" style="flex:1;" />
          <button type="button" class="danger cfg-remove">Remover</button>
        </label>
      `).join('') || '<p>Nenhum parâmetro no arquivo serverDZ.cfg.</p>'}
    </div>
    <div style="display:flex; gap:8px; margin:8px 0;">
      <input id="new-cfg-key" placeholder="Novo parâmetro" />
      <input id="new-cfg-value" placeholder="Valor" />
      <button type="button" id="add-cfg">Adicionar</button>
    </div>
    <button id="save-config">Salvar config</button>

    <h4>Mods do servidor</h4>
    <ul>${server.mods.map(m => `<li>${m} <button onclick="window.uninstallServerMod('${server.id}','${m}')">Desinstalar</button></li>`).join('') || '<li>Sem mods</li>'}</ul>

    <h4>Buscar mod na Workshop</h4>
    <input id="workshop-query" placeholder="Nome do mod" />
    <button id="search-workshop">Buscar</button>
    <ul id="workshop-results"></ul>
  `;

  q('#add-cfg').onclick = () => {
    const key = q('#new-cfg-key').value.trim();
    const value = q('#new-cfg-value').value;
    if (!key) return;
    const container = q('#cfg-list');
    container.insertAdjacentHTML('beforeend', `
      <label style="display:flex; gap:8px; align-items:center; margin-bottom:6px;">
        <input class="cfg-key" value="${key}" style="max-width:240px;" />
        <input class="cfg-value" value="${String(value).replace(/"/g, '&quot;')}" style="flex:1;" />
        <button type="button" class="danger cfg-remove">Remover</button>
      </label>
    `);
    q('#new-cfg-key').value = '';
    q('#new-cfg-value').value = '';
    bindConfigRemoveButtons();
  };

  function bindConfigRemoveButtons() {
    document.querySelectorAll('.cfg-remove').forEach((btn) => {
      btn.onclick = () => btn.closest('label')?.remove();
    });
  }

  bindConfigRemoveButtons();

  q('#save-config').onclick = async () => {
    const set = {};
    document.querySelectorAll('#cfg-list label').forEach((row) => {
      const key = row.querySelector('.cfg-key')?.value.trim();
      const value = row.querySelector('.cfg-value')?.value ?? '';
      if (key) set[key] = value;
    });

    await getJson(`${api}/api/servers/${server.id}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ set }),
    });
    await window.selectServer(server.id);
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
q('#close-modal').onclick = () => {
  if (q('#create-server').disabled) return;
  q('#server-modal').classList.add('hidden');
};
q('#create-server').onclick = async () => {
  const name = q('#server-name').value.trim();
  const port = Number(q('#server-port').value);
  if (!name || !port) return;

  const createBtn = q('#create-server');
  const closeBtn = q('#close-modal');
  const progressWrap = q('#create-server-progress');
  const progressBar = q('#create-server-progress-bar');
  const status = q('#create-server-status');

  createBtn.disabled = true;
  closeBtn.disabled = true;
  progressWrap.classList.remove('hidden');
  status.classList.remove('hidden');
  progressBar.style.width = '8%';
  status.textContent = 'Preparando criação do servidor...';

  let value = 8;
  const ticker = setInterval(() => {
    if (value < 90) {
      value += value < 45 ? 8 : 3;
      progressBar.style.width = `${Math.min(value, 90)}%`;
    }
  }, 700);

  try {
    status.textContent = 'Instalando/replicando arquivos do DayZ Server...';
    const created = await getJson(`${api}/api/servers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, port }),
    });

    progressBar.style.width = '100%';
    if (created.default_backup_created) {
      status.textContent = 'Servidor criado. Backup padrão foi gerado para acelerar próximas criações.';
    } else {
      status.textContent = 'Servidor criado com sucesso usando cópia do backup padrão.';
    }

    await refreshServers();
    setTimeout(() => {
      q('#server-modal').classList.add('hidden');
      q('#server-name').value = '';
      q('#server-port').value = '';
      progressWrap.classList.add('hidden');
      status.classList.add('hidden');
      status.textContent = '';
      progressBar.style.width = '0%';
    }, 900);
  } catch (err) {
    status.textContent = `Falha ao criar servidor: ${err?.message || 'erro desconhecido'}`;
    progressBar.style.width = '0%';
  } finally {
    clearInterval(ticker);
    createBtn.disabled = false;
    closeBtn.disabled = false;
  }
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
