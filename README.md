# DayZ Automatic Server Installer - Docker Linux

Painel com **Home / Servidores / Mods**, histórico de métricas (CPU/RAM/Jogadores), gestão de servidores e gestão de mods com integração Workshop.

## Recursos

- Dependências de mods resolvidas automaticamente.
- Geração automática de `-mod=`.
- Instalador inteligente de mods com dependências.
- Instalação automática do mapa Chiemsee.
- Monitor de jogadores via RCON.
- Home com sidebar (CPU/RAM/Jogadores) + 3 gráficos de barras (CPU, RAM, players).
- Seleção de período: 1d, 7d, 15d, 1m, 3m, 6m, 1y e intervalo manual por data.
- Menu **Servidores**:
  - Lista de servidores ativos/criados.
  - Criar servidor via modal (nome + porta).
  - Iniciar, parar e deletar servidor.
  - Editar configuração (mapa, max players, velocidade do jogo, multiplicador de tempo).
  - Buscar mods por nome na Workshop Steam e instalar/desinstalar no servidor.
- Menu **Mods**:
  - Lista de mods instalados.
  - Filtro: todos / em uso / não usados.
  - Remoção de mods não usados.

## Docker

```bash
docker compose up -d --build
```

- Frontend: `http://localhost:8080`
- Backend: `http://localhost:8000`

## Persistência

Dados ficam em `data/manager`:
- `servers.json`
- `installed_mods.json`
- `metrics.json`

## Credenciais SteamCMD

- Para instalação de servidor/mods com conta Steam, crie `config/steam.json` com base em `config/steam_example.json`.
- O backend agora prioriza as credenciais desse arquivo (`steam_username` / `steam_password`) e faz fallback para `config/manager.json`.

## Endpoints principais

- `GET /api/home`
- `GET /api/metrics?range=7d`
- `GET /api/servers`
- `POST /api/servers`
- `DELETE /api/servers/<id>`
- `POST /api/servers/<id>/start`
- `POST /api/servers/<id>/stop`
- `PUT /api/servers/<id>/config`
- `GET /api/workshop/search?q=cf`
- `POST /api/servers/<id>/mods/install`
- `POST /api/servers/<id>/mods/uninstall`
- `GET /api/mods?filter=all|used|unused`
- `DELETE /api/mods/<id>`
