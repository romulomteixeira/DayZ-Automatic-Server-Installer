from mcrcon import MCRcon

HOST="127.0.0.1"
PORT=2305
PASSWORD="adminpass"

def send_command(cmd):

    with MCRcon(HOST, PASSWORD, PORT) as mcr:

        resp = mcr.command(cmd)

        return resp