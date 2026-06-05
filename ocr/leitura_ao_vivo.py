# ocr/leitura_ao_vivo.py
"""
Leitura do multiplicador em voo — versão MAIS ROBUSTA.

PROBLEMAS RESOLVIDOS:
  1. Cache devolvia None entre leituras válidas, perdendo valores intermédios
  2. PSM 8 falhava com números pequenos no início do voo (1.00x, 1.05x)
  3. Sem escala, números pequenos eram difíceis de ler

NOVA ABORDAGEM:
  - Sem cache para `None` (só guarda em cache valores válidos)
  - Escala 2x da imagem (números pequenos ficam grandes)
  - 2 pipelines em paralelo: PSM 7 (linha) e PSM 8 (palavra)
"""
import os
import re
import sys
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
import pyautogui
import pytesseract
from config.configuracoes import carregar_config

if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    os.environ["TESSDATA_PREFIX"] = r"C:\Program Files\Tesseract-OCR\tessdata"

_cache_valor = None
_cache_ts    = None
_CACHE_S     = 0.10   # 100ms — curto


def invalidar_cache():
    global _cache_valor, _cache_ts
    _cache_valor = None
    _cache_ts    = None


def _ler_com_psm(img: np.ndarray, psm: int) -> Optional[float]:
    """Tenta ler o multiplicador com um PSM específico."""
    cfg = carregar_config()
    min_val = float(cfg.get("min_multiplicador_valido", 1.00))
    max_val = float(cfg.get("max_multiplicador_valido", 10000.0))

    try:
        texto = pytesseract.image_to_string(
            img,
            config=f"--oem 3 --psm {psm} -c tessedit_char_whitelist=0123456789."
        )
        m = re.search(r"\d+\.\d{2}", texto)
        if m:
            v = float(m.group())
            if min_val <= v <= max_val:
                return v
    except Exception:
        pass
    return None


def capturar_multiplicador_voo() -> Optional[float]:
    """Lê o multiplicador ao vivo com 2 pipelines em paralelo."""
    global _cache_valor, _cache_ts

    cfg = carregar_config()
    area = cfg.get("regiao_multiplicador_voo")
    if not area:
        return None

    # Usa cache apenas se ainda válido E tinha valor (None não é cacheado)
    if (_cache_valor is not None and _cache_ts is not None and
            (datetime.now() - _cache_ts).total_seconds() < _CACHE_S):
        return _cache_valor

    try:
        x, y, w, h = area
        ss   = pyautogui.screenshot(region=(x, y, w, h))
        img  = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)

        # Escala 2x — torna números pequenos mais legíveis
        img = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_CUBIC)

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

        # ── 2 pipelines em paralelo ──────────────────────────────────────
        v1 = _ler_com_psm(thresh, 7)   # PSM 7 = linha de texto
        if v1 is not None:
            _cache_valor = v1
            _cache_ts    = datetime.now()
            return v1

        v2 = _ler_com_psm(thresh, 8)   # PSM 8 = palavra única
        if v2 is not None:
            _cache_valor = v2
            _cache_ts    = datetime.now()
            return v2

    except Exception:
        pass

    return None


def numero_em_vermelho() -> bool:
    cfg  = carregar_config()
    area = cfg.get("regiao_multiplicador_voo")
    if not area: return False
    x, y, w, h = area
    ss   = pyautogui.screenshot(region=(x, y, w, h))
    img  = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)
    hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m1   = cv2.inRange(hsv, np.array([0,   70, 50]), np.array([10,  255, 255]))
    m2   = cv2.inRange(hsv, np.array([160, 70, 50]), np.array([180, 255, 255]))
    prop = cv2.countNonZero(cv2.bitwise_or(m1, m2)) / (w * h)
    return prop > 0.02


def capturar_area_voo_filtrada() -> Optional[np.ndarray]:
    cfg  = carregar_config()
    area = cfg.get("regiao_multiplicador_voo")
    if not area: return None
    x, y, w, h = area
    ss   = pyautogui.screenshot(region=(x, y, w, h))
    img  = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)
    hsv  = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([180, 30, 255]))
    return cv2.bitwise_and(img, img, mask=mask)


ler_multiplicador_preciso_com_cache = capturar_multiplicador_voo
