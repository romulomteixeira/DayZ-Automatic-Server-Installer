import valve.source.a2s

address = ("127.0.0.1",2303)

def get_players():

    with valve.source.a2s.ServerQuerier(address) as server:

        players = server.players()

        return [p["name"] for p in players]