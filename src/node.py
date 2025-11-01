"""Orquestrador do nó: inicializa LamportClock, servidor HTTP e ciclo de heartbeat.

Uso (exemplo):
python -m src.node --id 1 --port 8001 --peers localhost:8002,localhost:8003

Observação: execute como módulo (`python -m src.node`) para que imports relativos
funcionem corretamente (pacote `src`).
"""
from __future__ import annotations

import argparse
import logging
import threading
import time
from typing import Dict

from .lamport import LamportClock
from . import network
from .election import BullyElection

import uvicorn

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")


def format_log(node_id: int, clock: LamportClock, message: str) -> str:
    return f"[{node_id}][{clock.get()}] {message}"


def parse_peers(peers_str: str, default_scheme: str = "http") -> Dict[int, str]:
    """Parse peers no formato id:host:port e retorna dict {id: url}.
    
    Exemplo: "1:localhost:8001,2:localhost:8002" -> {1: "http://localhost:8001", 2: "http://localhost:8002"}
    
    Também aceita formato antigo (host:port) para compatibilidade, mas sem id explícito.
    """
    if not peers_str:
        return {}
    
    parts = [p.strip() for p in peers_str.split(",") if p.strip()]
    peer_map = {}
    
    for p in parts:
        # tentar parsear formato id:host:port
        segments = p.split(":")
        if len(segments) >= 3:
            # formato: id:host:port ou id:host:port:extraport (IPv6 etc)
            try:
                peer_id = int(segments[0])
                host_port = ":".join(segments[1:])  # rejunta caso tenha : extra (IPv6)
                if host_port.startswith("http://") or host_port.startswith("https://"):
                    url = host_port
                else:
                    url = f"{default_scheme}://{host_port}"
                peer_map[peer_id] = url
            except ValueError:
                # se primeiro segmento não é int, trata como host:port normal (compatibilidade)
                if p.startswith("http://") or p.startswith("https://"):
                    peer_map[len(peer_map)] = p  # id fictício
                else:
                    peer_map[len(peer_map)] = f"{default_scheme}://{p}"
        else:
            # formato antigo host:port
            if p.startswith("http://") or p.startswith("https://"):
                peer_map[len(peer_map)] = p
            else:
                peer_map[len(peer_map)] = f"{default_scheme}://{p}"
    
    return peer_map


def start_uvicorn_in_thread(app, host: str, port: int) -> threading.Thread:
    def run():
        uvicorn.run(app, host=host, port=port, log_level="info")

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def heartbeat_loop(node_id: int, addr: str, peer_map: Dict[int, str], election: BullyElection, clock: LamportClock, interval: float = 3.0):
    """Loop de heartbeat que pinga peers periodicamente e detecta falhas"""
    while True:
        for peer_id, peer_url in peer_map.items():
            try:
                # enviar ping
                msg = {"type": "PING", "from": str(node_id), "payload": {"addr": addr}}
                network.send_rpc(peer_url, msg)
            except Exception:
                logger.info(format_log(node_id, clock, f"peer {peer_id} inacessível: {peer_url}"))
                # se o peer era o líder, iniciar eleição
                if election.leader_id is not None and peer_id == election.leader_id:
                    logger.info(format_log(node_id, clock, f"líder {peer_id} falhou — iniciando eleição"))
                    threading.Thread(target=election.start_election, daemon=True).start()
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--id", required=True, type=int, help="id inteiro do nó")
    parser.add_argument("--host", default="0.0.0.0", help="host para ouvir")
    parser.add_argument("--port", required=True, type=int, help="porta para o servidor HTTP")
    parser.add_argument("--peers", default="", help="lista comma-separated no formato id:host:port (ex: 1:localhost:8001,2:localhost:8002)")

    args = parser.parse_args()

    node_id = args.id
    host = args.host
    port = args.port
    peer_map = parse_peers(args.peers)

    # montar endereço deste nó
    addr = f"http://{host}:{port}"

    # inicializar relógio e injetar em network
    clock = LamportClock()
    network.set_clock(clock)

    # criar instância de eleição e registrar handler
    election = BullyElection(node_id=node_id, peer_map=peer_map, addr=addr, clock=clock)
    network.register_message_handler(election.handle_message)

    logger.info(format_log(node_id, clock, f"iniciando nó em {addr} com peers={list(peer_map.keys())}"))

    # iniciar servidor FastAPI (o app está em network.app)
    start_uvicorn_in_thread(network.app, host, port)

    # aguardar servidor estar pronto
    time.sleep(0.5)

    # iniciar eleição automaticamente no startup (para definir líder inicial)
    logger.info(format_log(node_id, clock, "iniciando eleição inicial"))
    threading.Thread(target=election.start_election, daemon=True).start()

    # iniciar heartbeat em thread separada
    hb_thread = threading.Thread(target=heartbeat_loop, args=(node_id, addr, peer_map, election, clock), daemon=True)
    hb_thread.start()

    # loop principal: aceita comandos locais via terminal (somente se stdin disponível)
    import sys
    if sys.stdin.isatty():
        # Modo interativo (terminal)
        try:
            while True:
                cmd = input("comando> ").strip()
                if not cmd:
                    continue
                if cmd.lower() in ("exit", "quit"):
                    logger.info(format_log(node_id, clock, "encerrando nó"))
                    break
                if cmd.lower() == "status":
                    logger.info(format_log(node_id, clock, f"líder={election.leader_id}, clock={clock.get()}"))
                    continue
                if cmd.lower() == "election":
                    threading.Thread(target=election.start_election, daemon=True).start()
                    continue
                # qualquer outro comando é tratado como evento local
                clock.tick()
                logger.info(format_log(node_id, clock, f"COMANDO LOCAL: {cmd}"))

        except (KeyboardInterrupt, EOFError):
            logger.info(format_log(node_id, clock, "interrompido pelo usuário"))
    else:
        # Modo background (sem stdin) — mantém servidor rodando
        logger.info(format_log(node_id, clock, "rodando em modo background (use Ctrl+C ou kill para parar)"))
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info(format_log(node_id, clock, "interrompido"))


if __name__ == "__main__":
    main()
