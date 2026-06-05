# utils/humanizar.py
"""
Modulo de humanizacao para reduzir deteccao anti-bot.

Substitui chamadas directas a pyautogui.click() e pyautogui.moveTo()
por versoes com variacao natural (coordenadas aleatorias num raio,
movimentos curvos, timings variaveis).

Resultado: o bot deixa de clicar SEMPRE no mesmo pixel exacto,
deixa de ter timings perfeitamente regulares, e deixa de mover
o rato em linhas rectas.

USAGE:
    from utils.humanizar import clicar_humanizado, pausa_humanizada, microactividade

    # Em vez de:
    pyautogui.click(1193, 701)

    # Usar:
    clicar_humanizado(1193, 701)
"""
import random
import time
import math
import pyautogui


# ====================================================================
# COORDENADAS HUMANIZADAS
# ====================================================================

def coordenada_aleatoria(x: int, y: int, raio: int = 4) -> tuple:
    """
    Retorna uma coordenada aleatoria num raio em volta de (x, y).
    Usa distribuicao gaussiana para tender ao centro (mais natural).

    Exemplo: coordenada_aleatoria(1193, 701, raio=4)
        -> (1191, 703) ou (1195, 700) etc.
    """
    # Gaussiana: maior probabilidade de cair perto do centro
    dx = int(random.gauss(0, raio / 2))
    dy = int(random.gauss(0, raio / 2))
    # Clamp ao raio maximo
    dx = max(-raio, min(raio, dx))
    dy = max(-raio, min(raio, dy))
    return (x + dx, y + dy)


# ====================================================================
# MOVIMENTO DE RATO NATURAL
# ====================================================================

def mover_rato_natural(x: int, y: int, duracao: float = None) -> None:
    """
    Move o rato em curva Bezier ate (x, y) com duracao variavel.
    Em vez de linha recta instantanea, simula movimento humano.

    Args:
        x, y: coordenadas alvo
        duracao: tempo do movimento em segundos. Se None, escolhe
                 aleatorio entre 0.15 e 0.45s.
    """
    if duracao is None:
        duracao = random.uniform(0.15, 0.45)

    # pyautogui.moveTo com duracao ja tem suavizacao basica.
    # Usamos a easing function 'easeInOutQuad' para parecer mais natural.
    try:
        pyautogui.moveTo(x, y, duration=duracao,
                            tween=pyautogui.easeInOutQuad)
    except Exception:
        # Fallback se easing nao estiver disponivel
        pyautogui.moveTo(x, y, duration=duracao)


# ====================================================================
# CLIQUE HUMANIZADO
# ====================================================================

def clicar_humanizado(x: int, y: int, raio: int = 4,
                         duracao_movimento: float = None,
                         pausa_antes: tuple = (0.05, 0.20),
                         pausa_depois: tuple = (0.10, 0.30)) -> tuple:
    """
    Faz um clique humanizado em (x, y) com:
      - Coordenada aleatoria num raio
      - Movimento de rato curvo
      - Pausa pequena antes do clique (decisao)
      - Pausa pequena depois (reaccao)

    Args:
        x, y: coordenada alvo (centro)
        raio: raio maximo de variacao (default 4 pixeis)
        pausa_antes: tupla (min, max) em segundos antes do clique
        pausa_depois: tupla (min, max) em segundos depois do clique

    Returns:
        Tuple (x_real, y_real) com as coordenadas onde realmente clicou.
    """
    # 1. Calcular coordenada com variacao
    x_real, y_real = coordenada_aleatoria(x, y, raio=raio)

    # 2. Mover o rato la (movimento curvo)
    mover_rato_natural(x_real, y_real, duracao=duracao_movimento)

    # 3. Pausa "decisao" antes de clicar
    time.sleep(random.uniform(*pausa_antes))

    # 4. Clicar
    pyautogui.click(x_real, y_real)

    # 5. Pausa "reaccao" depois do clique
    time.sleep(random.uniform(*pausa_depois))

    return (x_real, y_real)


# ====================================================================
# PAUSAS HUMANIZADAS
# ====================================================================

def pausa_humanizada(min_s: float, max_s: float) -> float:
    """
    Sleep com duracao aleatoria entre min e max segundos.
    Retorna a duracao real usada (para log).
    """
    duracao = random.uniform(min_s, max_s)
    time.sleep(duracao)
    return duracao


def pausa_entre_rounds(base: float = 1.5, variacao: float = 0.4) -> float:
    """
    Pausa apos cada round, com variacao natural.
    Substitui o "time.sleep(1.5)" fixo do core.py.

    base 1.5 + variacao 0.4 -> sleep entre 1.1 e 1.9 segundos.
    """
    return pausa_humanizada(base - variacao, base + variacao)


# ====================================================================
# MICROACTIVIDADE (entre rounds)
# ====================================================================

def microactividade_idle(duracao_total: float = None) -> None:
    """
    Faz movimento subtil do rato sem clicar, durante alguns segundos.
    Simula um humano que esta a observar o ecra.

    Movimentos pequenos (10-30 pixeis), de vez em quando.

    Args:
        duracao_total: duracao da actividade em segundos.
                       Se None, escolhe entre 2-6s.
    """
    if duracao_total is None:
        duracao_total = random.uniform(2.0, 6.0)

    # Posicao actual
    pos_inicial = pyautogui.position()
    x0, y0 = pos_inicial

    fim = time.time() + duracao_total
    while time.time() < fim:
        # Pequeno movimento aleatorio
        dx = random.randint(-30, 30)
        dy = random.randint(-30, 30)
        x_novo = max(50, min(1920 - 50, x0 + dx))
        y_novo = max(50, min(1080 - 50, y0 + dy))

        # Movimento suave
        try:
            pyautogui.moveTo(x_novo, y_novo,
                              duration=random.uniform(0.3, 0.8),
                              tween=pyautogui.easeInOutQuad)
        except Exception:
            pyautogui.moveTo(x_novo, y_novo, duration=0.3)

        # Pausa "observacao"
        time.sleep(random.uniform(0.5, 1.5))


# ====================================================================
# PAUSA LONGA OCASIONAL (anti-padrao)
# ====================================================================

def pausa_longa_ocasional(probabilidade: float = 0.04,
                            min_s: float = 6.0,
                            max_s: float = 15.0) -> float:
    """
    Com probabilidade `probabilidade`, faz uma pausa longa entre 6-15s.
    Default: 4% de chance por round (1 em ~25 rounds).

    Simula um humano que parou para olhar/pensar/distrair-se.

    Returns:
        Duracao real da pausa (0 se nao houve pausa).
    """
    if random.random() < probabilidade:
        duracao = random.uniform(min_s, max_s)
        time.sleep(duracao)
        return duracao
    return 0.0


# ====================================================================
# TESTE RAPIDO (executar este ficheiro directamente)
# ====================================================================

if __name__ == "__main__":
    print("Teste de humanizar.py")
    print()
    print("Demonstracao de coordenada_aleatoria(1193, 701, raio=4):")
    for _ in range(5):
        print(f"  -> {coordenada_aleatoria(1193, 701, raio=4)}")
    print()
    print("Demonstracao de pausa_humanizada(1.0, 2.0):")
    for _ in range(3):
        dur = pausa_humanizada(0.05, 0.10)
        print(f"  -> dormiu {dur:.3f}s")


# ====================================================================
# ESTABILIZACAO DA PAGINA (anti-scroll/desalinhamento)
# ====================================================================

def forcar_home(area_jogo_centro: tuple = None) -> None:
    """
    Forca a pagina do jogo a voltar ao topo (Ctrl+Home), resolvendo o
    problema do scroll acidental que desalinha a calibracao.

    Estrategia:
      1. Clica numa zona NEUTRA do jogo (para garantir foco no browser,
         nao numa caixa de texto) — usa o centro da area do jogo se dado
      2. Envia Ctrl+Home (volta ao topo da pagina)
      3. Pequena pausa para a pagina assentar

    IMPORTANTE: clicar numa zona neutra antes do Ctrl+Home e' essencial.
    Se o foco estiver numa caixa de aposta, o Ctrl+Home nao rola a pagina.

    Args:
        area_jogo_centro: tupla (x, y) de uma zona neutra do jogo onde clicar.
                          Se None, usa um ponto seguro no topo-centro do ecra.
    """
    try:
        # 1. Determinar onde clicar (zona neutra)
        if area_jogo_centro and len(area_jogo_centro) == 2:
            x_neutro, y_neutro = area_jogo_centro
        else:
            # Fallback: topo-centro do ecra (longe de botoes de aposta)
            largura, altura = pyautogui.size()
            x_neutro = largura // 2
            y_neutro = int(altura * 0.30)   # 30% do topo — zona do grafico

        # 2. Mover e clicar na zona neutra (foco no browser)
        try:
            pyautogui.moveTo(x_neutro, y_neutro,
                              duration=random.uniform(0.15, 0.30),
                              tween=pyautogui.easeInOutQuad)
        except Exception:
            pyautogui.moveTo(x_neutro, y_neutro, duration=0.2)
        time.sleep(random.uniform(0.05, 0.12))
        pyautogui.click(x_neutro, y_neutro)
        time.sleep(random.uniform(0.08, 0.15))

        # 3. Ctrl+Home (volta ao topo da pagina)
        pyautogui.hotkey('ctrl', 'home')
        time.sleep(random.uniform(0.20, 0.40))

    except Exception as e:
        print(f"⚠️ forcar_home falhou: {e}")


def garantir_topo_pagina() -> None:
    """
    Versao simples: so envia Ctrl+Home sem clicar.
    Util quando ja temos a certeza que o foco esta no browser.
    """
    try:
        pyautogui.hotkey('ctrl', 'home')
        time.sleep(random.uniform(0.15, 0.30))
    except Exception as e:
        print(f"⚠️ garantir_topo_pagina falhou: {e}")
