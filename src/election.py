"""Algoritmo Bully simples para eleição de líder.

Usa mensagens RPC via `network.send_rpc` e integra um `LamportClock` para
incluir timestamps nas mensagens.

Protocolo (simplificado):
- ELECTION: enviado para nós com id maior
- OK: resposta de nó maior confirmando recepção
- COORDINATOR: anúncio do novo líder

Assunções simples:
- mensagens RPC contém 'from' (id do nó) e payload.addr com URL do nó
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Dict, List, Optional

from .network import send_rpc
from .lamport import LamportClock

logger = logging.getLogger(__name__)


class BullyElection:
    def __init__(self, node_id: int, peer_map: Dict[int, str], addr: str, clock: LamportClock, ok_timeout: float = 2.0):
        """Inicializa a eleição.

        node_id: inteiro único do nó (maior = mais prioridade)
        peer_map: dict {peer_id: url} mapeando ids para URLs dos peers
        addr: URL deste nó para ser incluído nas mensagens (payload.addr)
        clock: LamportClock compartilhado
        ok_timeout: tempo (segundos) a aguardar por respostas OK
        """
        self.id = int(node_id)
        self.peer_map = peer_map
        self.addr = addr
        self.clock = clock
        self.ok_timeout = ok_timeout

        self.leader_id: Optional[int] = None

        # sincronização para aguardar OK
        self._ok_event = threading.Event()
        self._election_lock = threading.Lock()

    def _send_message(self, target: str, m: Dict) -> None:
        try:
            send_rpc(target, m)
        except Exception:
            logger.debug("Falha ao enviar mensagem para %s", target)

    def start_election(self) -> None:
        """Inicia uma eleição usando Bully algorithm.

        Envia ELECTION para nós com id maior e aguarda OK.
        Se não receber OK em ok_timeout, anuncia COORDINATOR.
        """
        # evita concorrência de múltiplas eleições iniciadas simultaneamente
        if not self._election_lock.acquire(blocking=False):
            logger.warning("[%s][%s] ⚠️  Eleição já em andamento — ignorando", self.id, self.clock.get())
            return

        try:
            logger.warning("[%s][%s] 🗳️  INICIANDO ELEIÇÃO (líder anterior: %s)", self.id, self.clock.get(), self.leader_id)
            self._ok_event.clear()

            # enviar ELECTION apenas para peers com id maior
            higher_peers = {pid: url for pid, url in self.peer_map.items() if pid > self.id}
            
            if not higher_peers:
                # se não há peers com id maior, assume liderança imediatamente
                logger.warning("[%s][%s] 👑 Nenhum peer com id maior — ASSUMINDO LIDERANÇA", self.id, self.clock.get())
                self.leader_id = self.id
                coord_msg = {"type": "COORDINATOR", "from": str(self.id), "payload": {"leader": str(self.id), "addr": self.addr}}
                for peer_url in self.peer_map.values():
                    threading.Thread(target=self._send_message, args=(peer_url, coord_msg), daemon=True).start()
                return

            msg = {"type": "ELECTION", "from": str(self.id), "payload": {"addr": self.addr}}
            for peer_url in higher_peers.values():
                threading.Thread(target=self._send_message, args=(peer_url, msg), daemon=True).start()

            # aguarda OK
            got_ok = self._ok_event.wait(timeout=self.ok_timeout)
            if got_ok:
                logger.info("[%s][%s] ✅ Recebeu OK — aguardando anúncio de coordenador", self.id, self.clock.get())
                # outro nó com maior id irá anunciar coordenador; apenas aguardar
                return

            # não recebeu OK — torna-se líder
            logger.warning("[%s][%s] 👑 Nenhum OK recebido — ASSUMINDO LIDERANÇA", self.id, self.clock.get())
            self.leader_id = self.id
            coord_msg = {"type": "COORDINATOR", "from": str(self.id), "payload": {"leader": str(self.id), "addr": self.addr}}
            for peer_url in self.peer_map.values():
                threading.Thread(target=self._send_message, args=(peer_url, coord_msg), daemon=True).start()

        finally:
            self._election_lock.release()

    def handle_message(self, msg: Dict, local_ts: int) -> None:
        """Processa uma mensagem RPC recebida via network; é chamado pelo handler registrado."""
        mtype = msg.get("type")
        from_id = None
        try:
            from_id = int(msg.get("from", -1))
        except Exception:
            pass

        payload = msg.get("payload") or {}

        if mtype == "ELECTION":
            sender_addr = payload.get("addr")
            logger.info("[%s][%s] 📩 Recebeu ELECTION de nó %s", self.id, local_ts, from_id)
            
            if from_id is not None and from_id < self.id:
                ok_msg = {"type": "OK", "from": str(self.id), "payload": {"addr": self.addr}}
                if sender_addr:
                    logger.info("[%s][%s] 📤 Enviando OK para nó %s", self.id, local_ts, from_id)
                    threading.Thread(target=self._send_message, args=(sender_addr, ok_msg), daemon=True).start()
                
                logger.info("[%s][%s] 🗳️  Iniciando própria eleição (recebeu de nó menor)", self.id, local_ts)
                threading.Thread(target=self.start_election, daemon=True).start()

        elif mtype == "OK":
            logger.info("[%s][%s] ✅ Recebeu OK de nó %s", self.id, local_ts, from_id)
            self._ok_event.set()

        elif mtype == "COORDINATOR":
            leader = payload.get("leader")
            leader_id = None
            try:
                leader_id = int(leader)
            except Exception:
                pass

            self.leader_id = leader_id
            logger.warning("[%s][%s] 👑 NOVO LÍDER ANUNCIADO: %s", self.id, local_ts, leader)

        elif mtype == "PING":
            logger.debug("[%s][%s] 🏓 Ping recebido de %s", self.id, local_ts, from_id)


__all__ = ["BullyElection"]
