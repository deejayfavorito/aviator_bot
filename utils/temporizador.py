# utils/temporizador.py
import time


class Temporizador:
    def __init__(self, segundos: float):
        self.segundos = segundos
        self.reiniciar()

    def reiniciar(self):
        self._inicio = time.time()

    def expirou(self) -> bool:
        return (time.time() - self._inicio) > self.segundos

    def reset(self):
        self.reiniciar()
