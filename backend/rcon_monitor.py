from __future__ import annotations

from typing import List

from mcrcon import MCRcon


class RconPlayerMonitor:
    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password

    def get_players(self) -> List[str]:
        with MCRcon(self.host, self.password, self.port) as client:
            output = client.command("players")

        players: List[str] = []
        for line in output.splitlines():
            line = line.strip()
            if not line or line.lower().startswith("players"):
                continue
            players.append(line)
        return players
