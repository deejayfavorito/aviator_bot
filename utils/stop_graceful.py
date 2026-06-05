# utils/stop_graceful.py
"""
Stop Graceful — termina o bot de forma segura.

Funciona em 2 modos:
  - Modo terminal: regista SIGINT (Ctrl+C)
  - Modo GUI: NÃO regista signal (GUI tem o seu próprio botão), apenas
    disponibiliza o flag _pedido_paragem que a GUI manipula directamente.

CORRECÇÃO: signal só pode ser registado na thread principal do Python.
Quando o bot corre em thread separada (GUI), tentar registar SIGINT
levanta "ValueError: signal only works in main thread of the main interpreter".
"""
import signal
import threading
from typing import Optional


class StopGracefulHandler:
    def __init__(self):
        self._pedido_paragem    = False
        self._segunda_tentativa = False
        self._handler_original  = None
        self._signal_registado  = False

    def activar(self):
        """Activa o handler de Ctrl+C, apenas se estivermos na thread principal."""
        if threading.current_thread() is threading.main_thread():
            try:
                self._handler_original = signal.signal(signal.SIGINT, self._on_ctrl_c)
                self._signal_registado = True
            except (ValueError, OSError):
                # Falha silenciosa — significa que estamos num contexto onde
                # signal não funciona (ex: GUI). A paragem fica pelo botão.
                self._signal_registado = False
        else:
            # Estamos em thread secundária (ex: dentro da GUI). NÃO registar signal.
            self._signal_registado = False

    def desactivar(self):
        if self._signal_registado and self._handler_original:
            try:
                signal.signal(signal.SIGINT, self._handler_original)
            except (ValueError, OSError):
                pass

    def _on_ctrl_c(self, signum, frame):
        if self._pedido_paragem:
            print("\n\n🛑🛑 SEGUNDO Ctrl+C — paragem FORÇADA imediata!")
            self._segunda_tentativa = True
            raise KeyboardInterrupt()
        else:
            self._pedido_paragem = True
            print("\n\n⏸️  Ctrl+C recebido — vou terminar o round actual e sair.")
            print("    (Carrega Ctrl+C novamente para forçar paragem imediata)\n")

    @property
    def paragem_pedida(self) -> bool:
        return self._pedido_paragem


_handler: Optional[StopGracefulHandler] = None


def iniciar_stop_graceful() -> StopGracefulHandler:
    global _handler
    _handler = StopGracefulHandler()
    _handler.activar()
    return _handler


def paragem_pedida() -> bool:
    return _handler is not None and _handler.paragem_pedida


def pedir_paragem():
    """Pede paragem programaticamente (para a GUI usar)."""
    global _handler
    if _handler:
        _handler._pedido_paragem = True
