# ocr/leitura_saldo.py
"""
Leitura do SALDO do casino via OCR.

O saldo aparece no canto superior do Aviator, em verde claro sobre
fundo escuro, formato "50,000 AOA" ou "46,243 AOA".

Funcoes principais:
  ler_saldo(area)                  -> float ou None
  ler_saldo_robusto(area, tentativas) -> float ou None
  aguardar_mudanca_saldo(...)      -> float (apos mudanca ou timeout)
"""
import sys
import re
import time
import cv2
import numpy as np
import pyautogui

if sys.platform == "win32":
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    import pytesseract


def _preprocessar_imagem(img_bgr) -> np.ndarray:
    """
    Pre-processa a imagem para melhorar OCR.
    Texto verde sobre fundo escuro -> binariza, inverte, upscale.
    """
    # Converter para gray
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # Binarizar (texto claro sobre fundo escuro -> texto branco)
    _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY)

    # Upscale 3x para Tesseract ler melhor
    binary = cv2.resize(binary, None, fx=3, fy=3,
                          interpolation=cv2.INTER_CUBIC)

    # Dilatar ligeiramente para "engrossar" os digitos
    kernel = np.ones((2, 2), np.uint8)
    binary = cv2.dilate(binary, kernel, iterations=1)

    return binary


def _extrair_numero(texto: str) -> float:
    """
    Extrai o numero do texto retornado pelo Tesseract.
    Exemplos:
      "50,000 AOA"     -> 50000.0
      "46,243"         -> 46243.0
      "1.234,56"       -> 1234.56 (formato PT)
      "1,234.56"       -> 1234.56 (formato US)
      "lixo"           -> None
    """
    if not texto:
        return None

    # Remover tudo excepto digitos, virgulas e pontos
    limpo = re.sub(r'[^\d,.]', '', texto)
    if not limpo:
        return None

    # Detectar separador decimal
    # Se houver virgula E ponto: o ultimo e' o decimal
    if ',' in limpo and '.' in limpo:
        ultimo_virgula = limpo.rfind(',')
        ultimo_ponto = limpo.rfind('.')
        if ultimo_virgula > ultimo_ponto:
            # Formato PT: 1.234,56
            limpo = limpo.replace('.', '').replace(',', '.')
        else:
            # Formato US: 1,234.56
            limpo = limpo.replace(',', '')
    elif ',' in limpo:
        # So virgula -> assumir separador de milhares (50,000)
        # A nao ser que sejam so 2 digitos apos (1,23)
        partes = limpo.split(',')
        if len(partes) == 2 and len(partes[1]) <= 2:
            limpo = limpo.replace(',', '.')
        else:
            limpo = limpo.replace(',', '')
    elif '.' in limpo:
        # So ponto - similar
        partes = limpo.split('.')
        if len(partes) == 2 and len(partes[1]) <= 2:
            pass  # decimal genuino
        else:
            limpo = limpo.replace('.', '')

    try:
        valor = float(limpo)
        # Sanity check: saldo razoavel
        if 0 < valor < 100_000_000:
            return valor
        return None
    except ValueError:
        return None


def ler_saldo(area: tuple = None, debug: bool = False) -> float:
    """
    Le o saldo na area definida (ou usa area do config se nao passar).

    Args:
        area: tupla (x, y, w, h). Se None, le do config.
        debug: se True, salva imagens de debug em /tmp/debug_saldo_*.png

    Returns:
        float com o saldo, ou None se nao conseguiu ler.
    """
    if area is None:
        from config.configuracoes import carregar_config
        cfg = carregar_config()
        area = cfg.get("area_saldo")
        if not area or len(area) != 4:
            print("⚠️ area_saldo não configurada. Corre calibrar_saldo.py primeiro.")
            return None

    x, y, w, h = area

    try:
        ss = pyautogui.screenshot(region=(x, y, w, h))
        img = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"⚠️ Erro a capturar screenshot: {e}")
        return None

    # Preprocessar
    binary = _preprocessar_imagem(img)

    if debug:
        ts = int(time.time())
        cv2.imwrite(f"/tmp/debug_saldo_{ts}_raw.png", img)
        cv2.imwrite(f"/tmp/debug_saldo_{ts}_proc.png", binary)

    # OCR
    config = '--psm 7 -c tessedit_char_whitelist=0123456789,.'
    try:
        texto = pytesseract.image_to_string(binary, config=config).strip()
    except Exception as e:
        print(f"⚠️ Erro Tesseract: {e}")
        return None

    valor = _extrair_numero(texto)

    if debug:
        print(f"   [debug] texto OCR: '{texto}' -> valor {valor}")

    return valor


def ler_saldo_robusto(area: tuple = None,
                        tentativas: int = 3,
                        intervalo: float = 0.25) -> float:
    """
    Tenta ler o saldo varias vezes e exige CONSENSO entre leituras.

    Em vez de aceitar a primeira leitura, faz 2-3 leituras e so' retorna
    se pelo menos duas concordarem (diferenca < 5%). Isto rejeita leituras
    corrompidas pontuais do OCR (ex: ler 439302 quando era 4393).
    """
    leituras = []
    for i in range(max(2, tentativas)):
        valor = ler_saldo(area)
        if valor is not None and valor > 0:
            leituras.append(valor)
        if i < tentativas - 1:
            time.sleep(intervalo)

    if not leituras:
        return None

    if len(leituras) == 1:
        return leituras[0]   # so uma leitura — devolve, sem garantia

    # Procura duas leituras que concordem (diferenca < 5%)
    for a in range(len(leituras)):
        for b in range(a + 1, len(leituras)):
            v1, v2 = leituras[a], leituras[b]
            if v1 > 0 and abs(v1 - v2) / max(v1, v2) < 0.05:
                # Consenso — retorna a media das duas
                return (v1 + v2) / 2

    # Sem consenso — leituras divergem muito. Retorna a MEDIANA
    # (mais robusta a outliers que a media)
    leituras.sort()
    return leituras[len(leituras) // 2]


def aguardar_mudanca_saldo(area: tuple,
                              valor_inicial: float,
                              timeout: float = 4.0,
                              tolerancia: float = 5.0,
                              intervalo: float = 0.3) -> float:
    """
    Aguarda ate o saldo mudar mais que `tolerancia` AOA do `valor_inicial`,
    ou ate dar timeout.

    Returns:
        Novo valor do saldo (mesmo que nao tenha mudado, retorna ultima leitura).
    """
    deadline = time.time() + timeout
    ultimo = valor_inicial

    while time.time() < deadline:
        valor = ler_saldo_robusto(area, tentativas=1)
        if valor is not None:
            ultimo = valor
            if abs(valor - valor_inicial) > tolerancia:
                return valor
        time.sleep(intervalo)

    return ultimo


# ====================================================================
# TESTE STANDALONE
# ====================================================================

if __name__ == "__main__":
    print("Teste de leitura_saldo.py")
    print()

    # Tenta carregar config
    try:
        from config.configuracoes import carregar_config
        cfg = carregar_config()
        area = cfg.get("area_saldo")
        if area:
            print(f"area_saldo no config: {area}")
        else:
            print("⚠️ area_saldo NAO configurada. Corre calibrar_saldo.py primeiro.")
            sys.exit(1)
    except Exception as e:
        print(f"Erro a carregar config: {e}")
        sys.exit(1)

    print()
    print("A ler saldo 5 vezes...")
    for i in range(5):
        valor = ler_saldo(area, debug=True)
        print(f"   {i+1}. Saldo: {valor}")
        time.sleep(0.5)
