# automation/clique.py
"""
Clique com seguranca + HUMANIZACAO COMPLETA.

Alteracoes (01/06/2026 — anti-deteccao):
  - Coordenada com variacao gaussiana num raio de 4 pixeis
    (em vez de clicar SEMPRE no mesmo pixel exacto)
  - Movimento de rato com easing Bezier (em vez de linha recta)
  - Pausas variaveis antes e depois do clique (decisao + reaccao)
  - Duracao do movimento mais natural (0.15-0.45s)

Interface PUBLICA inalterada: clicar_com_seguranca((x, y)) funciona
exactamente como antes. Os modulos que chamam esta funcao nao precisam
de mudar nada.
"""
import random
import time
import pyautogui
from typing import Tuple

pyautogui.FAILSAFE = True
pyautogui.PAUSE    = 0.0   # removemos a pausa global — controlamos nos


def _coordenada_aleatoria(x: int, y: int, raio: int = 4) -> Tuple[int, int]:
    """
    Calcula coordenada aleatoria num raio em volta de (x, y),
    com distribuicao gaussiana (mais provavel cair perto do centro).

    Isto faz com que o bot nao clique sempre no mesmo pixel exacto,
    o que e' uma das assinaturas mais detectaveis.
    """
    dx = int(random.gauss(0, raio / 2))
    dy = int(random.gauss(0, raio / 2))
    # Clamp ao raio maximo
    dx = max(-raio, min(raio, dx))
    dy = max(-raio, min(raio, dy))
    return (x + dx, y + dy)


def _mover_natural(x: int, y: int, duracao: float = None) -> None:
    """
    Move o rato com curva Bezier (easing) em vez de linha recta.
    Duracao variavel para parecer mais natural.
    """
    if duracao is None:
        duracao = random.uniform(0.15, 0.45)

    try:
        # easeInOutQuad: arranque suave, meio mais rapido, fim suave
        pyautogui.moveTo(x, y, duration=duracao,
                            tween=pyautogui.easeInOutQuad)
    except Exception:
        # Fallback se easing nao disponivel
        pyautogui.moveTo(x, y, duration=duracao)


def _garantir_foco(x: int, y: int):
    """Clica uma vez para garantir que o Chrome tem foco."""
    pyautogui.click(x, y)
    time.sleep(0.05)


def clicar_com_segurança(posicao: Tuple[int, int],
                            delay_min: float = 0.05,
                            delay_max: float = 0.10,
                            tentativas: int = 2,
                            raio_variacao: int = 4) -> bool:
    """
    Clique HUMANIZADO com verificacao de foco e re-tentativa.

    NOVO: o clique acontece num pixel aleatorio dentro de um raio
    de `raio_variacao` pixeis em volta da posicao alvo. O movimento
    e' curvo (Bezier) e tem pausas variaveis para parecer humano.

    Args:
        posicao: tupla (x, y) — centro do alvo
        delay_min/max: deprecated, mantido para compatibilidade
        tentativas: numero de re-tentativas em caso de erro
        raio_variacao: raio em pixeis para variacao da coordenada (default 4)

    Returns:
        True se o clique foi executado.
    """
    x, y = posicao

    largura, altura = pyautogui.size()
    if not (0 <= x <= largura and 0 <= y <= altura):
        print(f"⚠️ Coordenadas fora do ecrã: {posicao} — clique cancelado.")
        return False

    for tentativa in range(tentativas):
        try:
            # 1. Calcular coordenada com variacao aleatoria
            x_real, y_real = _coordenada_aleatoria(x, y, raio=raio_variacao)

            # 2. Mover o rato com movimento natural (curvo)
            _mover_natural(x_real, y_real)

            # 3. Pausa "decisao" antes do clique
            time.sleep(random.uniform(0.05, 0.18))

            # 4. Clicar
            pyautogui.click(x_real, y_real)

            # 5. Pausa "reaccao" depois do clique
            time.sleep(random.uniform(0.08, 0.25))

            print(f"🖱️ Clique em ({x_real}, {y_real}) [alvo ({x}, {y}), tentativa {tentativa + 1}]")
            return True

        except Exception as e:
            print(f"⚠️ Erro no clique (tentativa {tentativa + 1}): {e}")
            time.sleep(0.1)

    return False
