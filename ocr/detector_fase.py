# ocr/detector_fase.py
"""
Detector de FASE — corrigido.

Mudança chave: a fase CRASH é apenas TRANSITÓRIA. Imediatamente após
o crash, o jogo entra em janela de aposta — o botão fica verde "Aposta"
mas o ecrã do voo ainda mostra "VOOU PARA LONGE" durante 1-2 segundos.

Então: se botão é VERDE → é APOSTA_DISPONIVEL, independentemente da
área do voo (a área do voo pode mostrar resíduo do round anterior).
"""
import sys
import cv2
import numpy as np
import pyautogui
from enum import Enum
from typing import Tuple
from config.configuracoes import carregar_config

if sys.platform == "win32":
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


class Fase(Enum):
    APOSTA_DISPONIVEL = "aposta_disponivel"
    APOSTA_COLOCADA   = "aposta_colocada"
    VOO_COM_APOSTA    = "voo_com_aposta"
    VOO_SEM_APOSTA    = "voo_sem_aposta"
    SEM_INTERNET      = "sem_internet"
    INDEFINIDA        = "indefinida"


def _capturar_botao() -> np.ndarray:
    cfg = carregar_config()
    area = cfg.get("area_apostar") or cfg.get("area_aposta")
    if not area:
        raise RuntimeError("area_apostar não configurada")
    x, y, w, h = area
    ss = pyautogui.screenshot(region=(x, y, w, h))
    return cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)


def _pct_cor(img: np.ndarray, hsv_lo, hsv_hi) -> float:
    hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array(hsv_lo), np.array(hsv_hi))
    return cv2.countNonZero(mask) / mask.size


def _pct_verde(img):    return _pct_cor(img, [50, 100, 100], [80, 255, 255])
def _pct_laranja(img):  return _pct_cor(img, [10, 150, 150], [25, 255, 255])
def _pct_vermelho(img):
    return _pct_cor(img, [0,   120, 120], [10,  255, 255]) + \
           _pct_cor(img, [170, 120, 120], [180, 255, 255])


def detectar_fase() -> Tuple[Fase, dict]:
    """
    Detecta a fase atual baseando-se SÓ no botão.
    Cada fase tem cor distinta — esta é a verdade autoritativa.
    """
    try:
        img_botao = _capturar_botao()
    except Exception as e:
        return Fase.INDEFINIDA, {"erro": str(e)}

    verde    = _pct_verde(img_botao)
    laranja  = _pct_laranja(img_botao)
    vermelho = _pct_vermelho(img_botao)

    info = {
        "verde":    f"{verde*100:.0f}%",
        "laranja":  f"{laranja*100:.0f}%",
        "vermelho": f"{vermelho*100:.0f}%",
    }

    # PRIORIDADE: cor mais dominante
    # ── Laranja → Cashout disponível (voo com a nossa aposta) ───────────
    if laranja > 0.20:
        return Fase.VOO_COM_APOSTA, info

    # ── Vermelho → Aposta colocada, a aguardar voo ──────────────────────
    if vermelho > 0.20:
        return Fase.APOSTA_COLOCADA, info

    # ── Verde → APOSTA DISPONÍVEL ───────────────────────────────────────
    # Não importa o que o resto do ecrã mostra (resíduo de crash anterior)
    # Verde = podemos apostar, ponto.
    if verde > 0.20:
        return Fase.APOSTA_DISPONIVEL, info

    return Fase.INDEFINIDA, info


def descricao_fase(fase: Fase) -> str:
    mapa = {
        Fase.APOSTA_DISPONIVEL: "🟢 APOSTA DISPONÍVEL",
        Fase.APOSTA_COLOCADA:   "🔴 APOSTA COLOCADA — aguardar voo",
        Fase.VOO_COM_APOSTA:    "🟠 VOO EM CURSO — pode cashout",
        Fase.VOO_SEM_APOSTA:    "⚪ VOO SEM APOSTA",
        Fase.SEM_INTERNET:      "📡 SEM INTERNET",
        Fase.INDEFINIDA:        "❓ INDEFINIDA",
    }
    return mapa.get(fase, "?")
