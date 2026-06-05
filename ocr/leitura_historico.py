# ocr/leitura_historico.py
"""
Leitura do HISTORICO EXPANDIDO do Aviator via OCR.

O historico aparece como popup com 5-6 linhas de multiplicadores.
Total: 60-80 crashes (representam 4-5 horas de jogo).

Funcao principal:
  ler_historico(area) -> List[float]
    Retorna lista de crashes na ORDEM DO POPUP:
    - posicao 0 = MAIS RECENTE (canto superior esquerdo)
    - ordem natural de leitura: esquerda-direita, cima-baixo
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


def _preprocessar(img_bgr) -> np.ndarray:
    """Pre-processa imagem para Tesseract ler texto colorido sobre fundo escuro."""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 80, 255, cv2.THRESH_BINARY)
    # Upscale 2x (nao 3x — area grande, manter dimensao gerivel)
    binary = cv2.resize(binary, None, fx=2, fy=2,
                          interpolation=cv2.INTER_CUBIC)
    return binary


def _extrair_crashes_do_texto(texto: str) -> list:
    """
    Extrai TODOS os numeros tipo '1.23x' ou '1.23' do texto.
    Aceita variacoes (espacos, virgulas, OCR ruidoso).
    """
    if not texto:
        return []

    # Padroes:
    #   1.23x   1.23   1,23x   1,23
    # Acompanhar 'x' opcional, ponto OU virgula como decimal
    pattern = r'(\d+[.,]\d+)\s*[xX×]?'
    matches = re.findall(pattern, texto)

    crashes = []
    for m in matches:
        try:
            valor = float(m.replace(',', '.'))
            # Sanity check: Aviator crashes entre 1.0 e ~10000
            if 1.0 <= valor <= 10000.0:
                crashes.append(valor)
        except ValueError:
            continue

    return crashes


def ler_historico(area: tuple = None, debug: bool = False) -> list:
    """
    Le o historico expandido na area definida.

    Args:
        area: tupla (x, y, w, h). Se None, le do config.
        debug: se True, salva imagens de debug e imprime texto OCR.

    Returns:
        Lista de crashes, mais recente primeiro.
    """
    if area is None:
        from config.configuracoes import carregar_config
        cfg = carregar_config()
        area = cfg.get("area_historico")
        if not area or len(area) != 4:
            print("⚠️ area_historico não configurada. Corre calibrar_historico primeiro.")
            return []

    x, y, w, h = area

    try:
        ss = pyautogui.screenshot(region=(x, y, w, h))
        img = cv2.cvtColor(np.array(ss), cv2.COLOR_RGB2BGR)
    except Exception as e:
        print(f"⚠️ Erro a capturar screenshot: {e}")
        return []

    binary = _preprocessar(img)

    if debug:
        ts = int(time.time())
        cv2.imwrite(f"/tmp/debug_hist_{ts}_raw.png", img)
        cv2.imwrite(f"/tmp/debug_hist_{ts}_proc.png", binary)

    # OCR — psm 6 (block of text) ou 11 (sparse)
    config = '--psm 6 -c tessedit_char_whitelist=0123456789.,xX× '
    try:
        texto = pytesseract.image_to_string(binary, config=config)
    except Exception as e:
        print(f"⚠️ Erro Tesseract: {e}")
        return []

    if debug:
        print(f"   [debug] texto bruto:\n{texto}")

    crashes = _extrair_crashes_do_texto(texto)

    if debug:
        print(f"   [debug] crashes extraidos: {len(crashes)}")
        print(f"   [debug] primeiros 10: {crashes[:10]}")

    return crashes


def estatisticas_historico(crashes: list) -> dict:
    """
    Calcula estatisticas uteis sobre uma lista de crashes.

    Returns:
        dict com:
          - total
          - pct_azuis (< 2.0)
          - pct_rosas (>= 10.0)
          - pct_megas (>= 100.0)
          - crash_mediano
          - crash_medio
          - quantil_50, quantil_67, quantil_75
          - max_visto
          - classificacao: "fria" | "normal" | "quente"
    """
    if not crashes:
        return {"total": 0, "classificacao": "sem_dados"}

    n = len(crashes)
    azuis = sum(1 for c in crashes if c < 2.0)
    rosas = sum(1 for c in crashes if c >= 10.0)
    megas = sum(1 for c in crashes if c >= 100.0)

    pct_rosas = rosas / n * 100

    ordenados = sorted(crashes)
    mediana    = ordenados[n // 2]
    media      = sum(crashes) / n
    q50        = ordenados[int(n * 0.50)]
    q67        = ordenados[int(n * 0.67)]
    q75        = ordenados[int(n * 0.75)]

    # Classificacao baseada em pct_rosas (media esperada do jogo ≈ 10%)
    if pct_rosas < 6.0:
        classificacao = "fria"
    elif pct_rosas > 13.0:
        classificacao = "quente"
    else:
        classificacao = "normal"

    return {
        "total":           n,
        "azuis":           azuis,
        "rosas":           rosas,
        "megas":           megas,
        "pct_azuis":       azuis / n * 100,
        "pct_rosas":       pct_rosas,
        "pct_megas":       megas / n * 100,
        "crash_mediano":   mediana,
        "crash_medio":     media,
        "quantil_50":      q50,
        "quantil_67":      q67,
        "quantil_75":      q75,
        "max_visto":       max(crashes),
        "classificacao":   classificacao,
    }


def cashout_recomendado_da_temperatura(stats: dict, padrao_default: float = 1.5) -> tuple:
    """
    Sugere cashout-alvo baseado nas estatisticas observadas.

    Returns:
        (cashout, motivo)
    """
    cls = stats.get("classificacao", "normal")
    q67 = stats.get("quantil_67", padrao_default)

    if cls == "fria":
        # Sessao fria — usa cashout mais baixo, defensivo
        cashout = min(padrao_default, 1.30)
        return cashout, f"❄️ Sessão FRIA ({stats['pct_rosas']:.1f}% rosas) — defensivo {cashout:.2f}x"

    if cls == "quente":
        # Sessao quente — pode subir
        cashout = max(padrao_default, min(q67, 2.0))
        return cashout, f"🔥 Sessão QUENTE ({stats['pct_rosas']:.1f}% rosas) — agressivo {cashout:.2f}x"

    # Normal — usa o quantil_67 observado se for razoavel
    cashout = max(1.30, min(q67, 1.70))
    return cashout, f"🟡 Sessão NORMAL ({stats['pct_rosas']:.1f}% rosas) — q67={q67:.2f}x → cashout {cashout:.2f}x"


if __name__ == "__main__":
    print("Teste de leitura_historico.py")
    from config.configuracoes import carregar_config
    cfg = carregar_config()
    area = cfg.get("area_historico")
    if not area:
        print("area_historico nao configurada.")
        sys.exit(1)
    crashes = ler_historico(area, debug=True)
    print(f"\nTotal: {len(crashes)} crashes")
    if crashes:
        stats = estatisticas_historico(crashes)
        print(f"Estatisticas: {stats}")
        cash, motivo = cashout_recomendado_da_temperatura(stats)
        print(f"Recomendacao: {motivo}")
