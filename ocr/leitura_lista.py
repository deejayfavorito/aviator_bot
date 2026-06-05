# ocr/leitura_lista.py
"""
Leitura ROBUSTA com suporte para números grandes (>100x).

Mudança chave: pre-processamento separado para números coloridos.
A lista do Aviator tem:
  - Azul (<2x): claro
  - Roxo (2-10x): escuro
  - Rosa (>10x): muito vivo
Cada cor tem contraste diferente — precisam de pipelines distintos.
"""
import re
import sys
import cv2
import numpy as np
import pyautogui
import pytesseract
from typing import List
from config.configuracoes import carregar_config

if sys.platform == "win32":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def _preproc_geral(img: np.ndarray) -> np.ndarray:
    """Pipeline geral: bom para azul/roxo médios."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(4, 4))
    gray = clahe.apply(gray)
    inverted = cv2.bitwise_not(gray)
    thresh = cv2.adaptiveThreshold(
        inverted, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 15, 4
    )
    return thresh


def _preproc_rosa(img: np.ndarray) -> np.ndarray:
    """Pipeline focado em ROSA/MAGENTA (números grandes >10x)."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Isola tons de rosa/magenta/roxo claro
    mask_rosa = cv2.inRange(hsv, np.array([140, 50, 100]), np.array([170, 255, 255]))
    # Threshold simples no canal isolado
    return mask_rosa


def _preproc_alto_contraste(img: np.ndarray) -> np.ndarray:
    """Otsu com escala forte — útil para números muito brilhantes."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Equalização forte
    gray = cv2.equalizeHist(gray)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return thresh


def _extrair_mults(texto: str, max_val: float) -> List[float]:
    """Extrai multiplicadores com formato N.NN do texto OCR."""
    cfg = carregar_config()
    min_val = float(cfg.get("min_multiplicador_valido", 1.00))
    mults = []

    # Divide por 'x' primeiro (separador natural)
    for seg in re.split(r"[xX]", texto):
        seg = seg.strip()
        # Aceita 1-5 dígitos antes do ponto (suporta até 99999.99)
        m = re.search(r"(?<!\d)(\d{1,5}\.\d{2})(?!\d)", seg)
        if m:
            try:
                v = float(m.group(1))
                if min_val <= v <= max_val:
                    mults.append(v)
            except ValueError:
                pass

    return mults


def _ocr_passagem(img: np.ndarray, preproc, psm: int, max_val: float) -> List[float]:
    try:
        thresh = preproc(img)
        cfg_tess = f"--oem 3 --psm {psm} -c tessedit_char_whitelist=0123456789.x"
        texto = pytesseract.image_to_string(thresh, config=cfg_tess)
        return _extrair_mults(texto, max_val)
    except Exception:
        return []


def ler_lista_multiplicadores_atuais() -> List[float]:
    cfg  = carregar_config()
    area = cfg.get("regiao_lista_multiplicadores")
    if not area:
        print("❌ Região da lista não configurada.")
        return []

    max_val = float(cfg.get("max_multiplicador_valido", 10000.0))

    try:
        x, y, w, h = area
        ss  = pyautogui.screenshot(region=(x, y, w, h))
        img = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)

        # Escala 3x para melhor OCR de números pequenos
        img = cv2.resize(img, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)

        # ── 4 pipelines em paralelo ──────────────────────────────────────
        resultados = [
            _ocr_passagem(img, _preproc_geral,        7, max_val),
            _ocr_passagem(img, _preproc_geral,        6, max_val),
            _ocr_passagem(img, _preproc_alto_contraste, 7, max_val),
            _ocr_passagem(img, _preproc_rosa,         7, max_val),
        ]

        # Combina TODOS — escolhe o mais completo, mantém ordem
        # Pega o resultado com MAIS números válidos
        mults = max(resultados, key=len)

        if mults:
            print(f"🎯 Lista ({len(mults)}): {mults}")
        else:
            print("⚠️ OCR: lista vazia")

        return mults
    except Exception as e:
        print(f"❌ Erro na leitura: {e}")
        return []
