# automation/cashout.py
"""
Cashout com HUMANIZACAO COMPLETA.

Alteracoes (01/06/2026 — anti-deteccao):
  - Coordenada com variacao gaussiana num raio de 4 pixeis
  - Movimento de rato com easing Bezier
  - Pausas variaveis antes/depois do clique

Nota: cashout e' tempo-critico. Mantemos pausas MENORES que no clique
de aposta — o tempo de reaccao humano para um botao critico
e' mais rapido que para uma decisao.
"""
import random
import time
import pyautogui
from typing import Tuple
from config.configuracoes import carregar_config


def _coordenada_aleatoria(x: int, y: int, raio: int = 3) -> Tuple[int, int]:
    """Coordenada aleatoria gaussiana num raio. Raio menor que o clique
    de aposta porque o botao de cashout costuma ser mais pequeno."""
    dx = int(random.gauss(0, raio / 2))
    dy = int(random.gauss(0, raio / 2))
    dx = max(-raio, min(raio, dx))
    dy = max(-raio, min(raio, dy))
    return (x + dx, y + dy)


def _mover_natural(x: int, y: int, duracao: float = None) -> None:
    """Movimento de rato com easing. Duracao mais curta que clique
    de aposta (cashout precisa de ser rapido)."""
    if duracao is None:
        # 0.08-0.22s — mais rapido que clicar_com_seguranca
        # porque cashout e' tempo-critico
        duracao = random.uniform(0.08, 0.22)

    try:
        pyautogui.moveTo(x, y, duration=duracao,
                            tween=pyautogui.easeInOutQuad)
    except Exception:
        pyautogui.moveTo(x, y, duration=duracao)


def acionar_cashout_na_area() -> bool:
    """
    Clica na area calibrada do botao CASHOUT, de forma humanizada.

    A decisao de quando clicar e' feita pelo monitoramento_cashout.py
    — esta funcao apenas executa o clique no momento em que e' chamada.

    Returns:
        True se o clique foi executado com sucesso.
    """
    config = carregar_config()
    area   = config.get("area_cashout")

    if not area or len(area) != 4:
        print("❌ Área do botão CASHOUT não configurada no config.json.")
        return False

    x, y, w, h = area
    centro_x   = x + w // 2
    centro_y   = y + h // 2

    # 1. Coordenada com variacao (raio 3 px — menor que clique de aposta)
    x_real, y_real = _coordenada_aleatoria(centro_x, centro_y, raio=3)

    # 2. Movimento natural (mais rapido que clique de aposta)
    _mover_natural(x_real, y_real)

    # 3. Pausa minima antes do clique (cashout e' tempo-critico,
    #    nao podemos atrasar muito)
    time.sleep(random.uniform(0.02, 0.08))

    # 4. Clicar
    pyautogui.click(x_real, y_real)

    # 5. Pausa pequena depois
    time.sleep(random.uniform(0.04, 0.12))

    print(f"💸 Cashout executado em ({x_real}, {y_real})")
    return True
