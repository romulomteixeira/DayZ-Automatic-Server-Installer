# DayZ Automatic Server Installer - Docker Linux Refactor

## O que foi implementado

- Resolução automática de dependências de mods via Steam Web API.
- Geração automática do argumento `-mod=` com pastas instaladas.
- Instalador inteligente de mods (download + cópia + dependências).
- Endpoint dedicado para instalar o mapa **Chiemsee** automaticamente.
- Painel web estilo manager com cards de status, ações e saída em tempo real.
- Monitor de jogadores via RCON no backend (`players`).
- Arquitetura separada em **2 containers**:
  - `backend` (Python/Flask API + SteamCMD)
  - `web` (Nginx estático)

## Subir com Docker

```bash
docker compose up -d --build
```

- Painel web: `http://localhost:8080`
- API backend: `http://localhost:8000/api/health`

## Configuração

Arquivo principal: `config/manager.json`

- `steam_user` e `steam_password`: credenciais (opcional para mods públicos).
- `workshop_content_dir`: caminho de download do workshop.
- `server_mods_dir`: pasta onde os mods serão instalados no servidor.
- `rcon_host`, `rcon_port`, `rcon_password`: dados de acesso RCON.

## Endpoints

- `GET /api/status`
- `POST /api/mods/sync`
- `POST /api/maps/chiemsee/install`

Exemplo de sincronização com dependências:

```bash
curl -X POST http://localhost:8000/api/mods/sync \
  -H 'Content-Type: application/json' \
  -d '{"mods": ["1559212036", "1828439124"], "include_chiemsee": true}'
```

O backend resolve dependências recursivamente e retorna `mod_arg` pronto para uso.
