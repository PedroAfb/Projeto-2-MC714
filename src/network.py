"""API HTTP para envio/recebimento de RPCs usando FastAPI.

Fornece:
- endpoint POST /rpc que espera payload JSON: {"type", "from", "ts", "payload"}
- função send_rpc(url, message) que usa requests para enviar mensagens
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

import requests

from .lamport import LamportClock

from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI()
# clock pode ser injetado por node.py para compartilhar o mesmo LamportClock
clock: LamportClock = LamportClock()

# callback opcional que será chamado para processar mensagens RPC recebidas
# signature: handler(message_dict, local_ts)
_message_handler = None


def set_clock(c: LamportClock) -> None:
	"""Define o relógio Lamport a ser usado pelo módulo de rede.

	Isso permite ao `node` compartilhar a mesma instância de relógio entre
	componentes do nó e as rotas HTTP.
	"""
	global clock
	clock = c


def register_message_handler(fn) -> None:
	"""Registra uma função que será chamada quando uma mensagem RPC chegar.

	A função recebe (message_dict, local_ts).
	"""
	global _message_handler
	_message_handler = fn


class RPCMessage(BaseModel):
	type: str
	from_field: Optional[str] = Field(None, alias="from")
	ts: Optional[int] = None
	payload: Optional[Dict[str, Any]] = None

	class Config:
		allow_population_by_field_name = True


@app.post("/rpc")
async def rpc_endpoint(msg: RPCMessage):
	"""Recebe mensagens RPC genéricas.

	Atualiza o relógio de Lamport usando `ts` enviado (se presente) e
	responde com o timestamp atualizado.
	"""
	# Atualiza relógio com timestamp remoto se fornecido
	if msg.ts is not None:
		new_ts = clock.update(msg.ts)
		logger.info("Mensagem recebida de %s (ts=%s). clock=%s", msg.from_field, msg.ts, new_ts)
	else:
		# Se não houve ts, apenas considera evento de recepção
		new_ts = clock.tick()
		logger.info("Mensagem recebida sem ts de %s. clock=%s", msg.from_field, new_ts)

	# Invoca handler registrado (por exemplo, election) para processar a mensagem
	try:
		if _message_handler:
			# converte para dict com alias names (inclui 'from' key)
			# Compatível com Pydantic v1 e v2
			if hasattr(msg, 'model_dump'):
				msg_dict = msg.model_dump(by_alias=True)
			else:
				msg_dict = msg.dict(by_alias=True)
			# transforma payload vazio em {} para conveniência
			if msg_dict.get("payload") is None:
				msg_dict["payload"] = {}
			_message_handler(msg_dict, new_ts)
	except Exception:
		logger.exception("Erro ao processar handler de mensagem")

	return {"status": "ok", "ts": new_ts}


def send_rpc(target: str, message: Dict[str, Any], path: str = "/rpc", timeout: float = 5.0) -> requests.Response:
	"""Envia um RPC para `target` (URL base ou URL completo).

	Antes de enviar, incrementa o relógio (tick) e injeta `ts` no payload.

	target: url base (ex: http://host:port) ou url completo.
	message: dicionário serializável (não será modificado in-place).
	path: caminho do endpoint (padrão: /rpc).
	Retorna o objeto Response do requests.
	"""
	# garante cópia para não poluir o dicionário do chamador
	payload = dict(message)

	# gerar timestamp para envio
	ts = clock.tick()
	payload["ts"] = ts

	# montar URL final
	if target.endswith("/"):
		target = target[:-1]
	if path and not path.startswith("/"):
		path = "/" + path
	url = target + path

	logger.info("Enviando RPC para %s com ts=%s tipo=%s", url, ts, payload.get("type"))
	try:
		resp = requests.post(url, json=payload, timeout=timeout)
		resp.raise_for_status()
		return resp
	except requests.RequestException as exc:
		logger.exception("Falha ao enviar RPC para %s: %s", url, exc)
		raise


if __name__ == "__main__":
	# Execução direta para desenvolvimento
	import uvicorn

	logger.info("Iniciando FastAPI (desenvolvimento) com LamportClock")
	uvicorn.run("src.network:app", host="0.0.0.0", port=8000, log_level="info")

