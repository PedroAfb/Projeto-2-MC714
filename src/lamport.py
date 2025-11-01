"""Módulo simples para relógio lógico de Lamport.

Fornece a classe LamportClock com operações básicas:
- tick(): incrementa ao enviar/gerar evento local
- update(remote_ts): atualiza o relógio ao receber evento remoto
- get(): obtém timestamp atual
"""
from __future__ import annotations

from typing import Any


class LamportClock:
	"""Relógio lógico de Lamport simples.

	time: inteiro representando o timestamp lógico. Inicia em 0.
	"""

	def __init__(self, time: int = 0) -> None:
		self.time: int = int(time)

	def tick(self) -> int:
		"""Incrementa o relógio para um evento local (envio).

		Retorna o novo timestamp.
		"""
		self.time += 1
		return self.time

	def update(self, remote_ts: int | Any) -> int:
		"""Atualiza o relógio ao receber um timestamp remoto.

		Faz: time = max(time, remote_ts) + 1
		Retorna o novo timestamp.
		"""
		try:
			r = int(remote_ts)
		except Exception:
			# Se remote_ts não for conversível para int, ignora e apenas tick
			return self.tick()

		self.time = max(self.time, r) + 1
		return self.time

	def get(self) -> int:
		"""Retorna o timestamp atual."""
		return self.time


__all__ = ["LamportClock"]
