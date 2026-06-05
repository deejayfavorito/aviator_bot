# utils/imagem.py
import time
import pyautogui
from typing import Optional, Tuple, List


def encontrar_imagem_em_area(
    imagem_path: str,
    regiao: List[int],
    confianca: float = 0.7,
    timeout: float = 3.0,
    intervalo: float = 0.1
) -> Optional[Tuple[int, int]]:
    """
    Procura uma imagem dentro de uma região do ecrã durante o tempo definido.
    Retorna a posição central se encontrada, None caso contrário.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        resultado = pyautogui.locateCenterOnScreen(
            imagem_path, region=tuple(regiao), confidence=confianca
        )
        if resultado:
            return resultado
        time.sleep(intervalo)
    return None
