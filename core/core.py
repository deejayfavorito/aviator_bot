# core/core.py
"""
Loop principal — agora com sistema de FASES para a leitura de padrões.

NOVA LÓGICA das 3 FASES (essencial para Follow Patterns):

  FASE 1: COLD START (ao arrancar)
    → Lê a lista visível no ecrã (8-13 valores recentes)
    → IGNORA o histórico de ficheiro (pode ser antigo)
    → Esta é a "fotografia do presente"

  FASE 2: WARM-UP (primeiros 3 rounds novos)
    → Acumula crashes novos na janela
    → Mistura com lista inicial
    → Janela cresce até ter 15-20 crashes

  FASE 3: OPERAÇÃO NORMAL (após 3 rounds)
    → Janela móvel: 20 últimos crashes vivos
    → Padrões totalmente confiáveis
    → Histórico de ficheiro só para relatórios/análise

Suporta 3 estratégias com prioridade:
  1. usar_estrategia_padroes  (Follow Patterns) — RECOMENDADO
  2. usar_estrategia_dados    (Minutos quentes — simples)
  3. estrategia.py (PDF tradicional) — fallback
"""
import time
import collections
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from ocr.leitura_lista import ler_lista_multiplicadores_atuais
from ocr.monitoramento_aposta import apostar_agora
from ocr.monitoramento_cashout import monitorar_cashout_preciso
from automation.escrever_valor import escrever_valor_aposta
from gestor.banca import deve_continuar, registrar_resultado_csv, registrar_resultado, carregar_estado as recarregar_banca_disco
from gestor.gestor_aposta import calcular_valor_aposta, registar_resultado_composta, info_estado
from gestor.inteligencia_adaptativa import (
    ajustar_alvo, deve_pausar, ajustar_valor,
    registar_aposta_real_hot_cold, registar_resultado_adaptive,
)
from data.data_writer import salvar_multiplicador
from config.configuracoes import carregar_config
from utils.logs import log
from utils.watchdog import verificar as watchdog_verificar, registar_nova_rodada
from utils.dashboard import imprimir_dashboard
from utils.log_sessao import iniciar_sessao, registar_aposta
from utils.humanizar import pausa_longa_ocasional, microactividade_idle, forcar_home
from utils.stop_graceful import iniciar_stop_graceful, paragem_pedida
from estrategia.estrategia import aplicar_estrategia, registar_resultado as registar_estrat

from estrategia.estrategia_padroes import (
    aplicar_estrategia_padroes,
    calcular_valor_aposta_padroes,
    registar_resultado_padrao,
    obter_ultima_decisao,
    recalcular_temperatura_dinamica,
    esta_activa as estrategia_padroes_activa,
)
from estrategia.estrategia_rosa import (
    decidir_aposta_rosa,
    registar_resultado_rosa,
    resetar_estado_rosa,
    esta_activa as estrategia_rosa_activa,
)
from estrategia.estrategia_dados import (
    aplicar_estrategia_dados,
    calcular_valor_aposta_dados,
    registar_resultado_dados,
    esta_activa as estrategia_dados_activa,
    info_minutos_quentes,
    CASHOUT_DEFAULT,
)


# ─── Configuração das fases ─────────────────────────────────────────────
ROUNDS_WARMUP = 3              # Quantos rounds novos para sair de WARM-UP
JANELA_OPERACIONAL = 20        # Tamanho da janela em FASE 3


def _carregar_historico_csv(caminho: str = "data/historico.csv", max_entradas: int = 200) -> list:
    """Carrega histórico de ficheiro (usado SÓ para relatórios — não para decisão)."""
    if not os.path.exists(caminho):
        return []
    mults = []
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            for linha in f:
                partes = linha.strip().split(",")
                if len(partes) >= 3 and partes[1] == "crash_registado":
                    try:
                        mults.append(float(partes[2].replace("x", "").strip()))
                    except ValueError:
                        pass
    except Exception as e:
        log(f"⚠️ Erro ao ler histórico: {e}", "warning")
    mults.reverse()
    return mults[:max_entradas]


def _round_novo(lista_atual: List[float], lista_anterior: List[float]) -> Optional[float]:
    if not lista_atual or not lista_anterior:
        return None
    novo = lista_atual[0]
    antigo_pos0 = lista_anterior[0]
    if novo == antigo_pos0:
        return None
    for i in range(1, min(5, len(lista_atual))):
        if lista_atual[i] == antigo_pos0:
            return novo
    valores_em_comum = set(lista_atual[:8]) & set(lista_anterior[:8])
    if len(valores_em_comum) >= 5:
        return novo
    if len(lista_atual) >= 10 and len(valores_em_comum) <= 2:
        log(f"🔄 Re-sincronização: lista divergiu (apenas {len(valores_em_comum)} em comum). Retomando com {novo:.2f}x")
        return novo
    return None


def _lista_e_valida(lista: List[float], min_elementos: int = 10) -> bool:
    return lista is not None and len(lista) >= min_elementos


def _ler_lucro_banca() -> float:
    try:
        path = Path("data/estado_banca.json")
        if path.exists():
            with open(path) as f:
                return json.load(f).get("lucro", 0.0)
    except Exception:
        pass
    return 0.0


def _ler_cofre() -> float:
    try:
        path = Path("data/estado_aposta_composta.json")
        if path.exists():
            with open(path) as f:
                return json.load(f).get("lucro_cofre", 0.0)
    except Exception:
        pass
    return 0.0


def _detectar_nome_estrategia(usar_padroes: bool, usar_dados: bool,
                              cashout_alvo: float, minuto: int) -> str:
    if usar_padroes:
        d = obter_ultima_decisao()
        if d:
            return d.nome_padrao
        return "padroes_unknown"
    if usar_dados:
        if cashout_alvo == CASHOUT_DEFAULT:
            return "dados_default"
        return f"dados_min{minuto:02d}_alvo{cashout_alvo:.1f}x"
    if cashout_alvo >= 20.0: return "P2.3_roxos"
    if cashout_alvo >= 10.0: return "P2.2_azuis"
    if cashout_alvo == 2.0:  return "P2.1_ou_rosa"
    return "default_1.20x"


def _aguardar_lista_valida_com_stop(max_segundos: float = 30.0) -> Optional[List[float]]:
    t0 = time.time()
    while time.time() - t0 < max_segundos:
        if paragem_pedida():
            return None
        lista = ler_lista_multiplicadores_atuais()
        if _lista_e_valida(lista):
            return lista
        time.sleep(0.3)
    return None


def _fase_actual(rounds_novos: int) -> str:
    """Devolve qual fase está activa para logging."""
    if rounds_novos == 0:
        return "FASE 1 (cold start — lista visível)"
    elif rounds_novos < ROUNDS_WARMUP:
        return f"FASE 2 (warm-up {rounds_novos}/{ROUNDS_WARMUP})"
    else:
        return "FASE 3 (operação normal)"


# ═══════════════════════════════════════════════════════════════════════════
# MODO OBSERVADOR (treinamento) — funcoes auxiliares
# ═══════════════════════════════════════════════════════════════════════════

CAMINHO_OBSERVACAO = "data/observacao_fases.csv"


def _registar_observacao_fase(crash_novo: float, janela: list) -> None:
    """
    Regista no CSV uma observacao de fase durante o modo observador.

    Cada linha: timestamp, crash, classificacao_actual, pct_rosas, q67, mediana

    Estes dados servem para depois analisar COMO as fases transitam
    (ex: apos uma fase quente, vem normal? fria? quanto tempo dura cada uma?).
    """
    try:
        import os
        from datetime import datetime as _dt

        # Calcula estatisticas da janela actual
        if len(janela) < 10:
            return  # amostra insuficiente

        amostra = janela[:80]
        n = len(amostra)
        rosas = sum(1 for c in amostra if c >= 10.0)
        pct_rosas = rosas / n * 100
        ordenados = sorted(amostra)
        mediana = ordenados[n // 2]
        q67 = ordenados[int(n * 0.67)]

        if pct_rosas < 6.0:
            cls = "fria"
        elif pct_rosas > 13.0:
            cls = "quente"
        else:
            cls = "normal"

        os.makedirs("data", exist_ok=True)
        existe = os.path.exists(CAMINHO_OBSERVACAO)
        with open(CAMINHO_OBSERVACAO, "a", newline="", encoding="utf-8") as f:
            if not existe:
                f.write("timestamp,crash,classificacao,pct_rosas,q67,mediana\n")
            ts = _dt.now().isoformat(timespec="seconds")
            f.write(f"{ts},{crash_novo:.2f},{cls},{pct_rosas:.1f},{q67:.2f},{mediana:.2f}\n")

        log(f"🔬 [obs] crash {crash_novo:.2f}x | fase {cls} | "
            f"{pct_rosas:.0f}% rosas | q67 {q67:.2f}")
    except Exception as _e:
        pass


def _fazer_aposta_anti_inatividade() -> None:
    """
    Faz uma aposta minima (65 AOA) com cashout baixissimo (1.10x) so'
    para o casino registar actividade e nao cancelar a sessao.

    Nao conta para a estrategia nem para a contabilidade principal —
    e' so' para "estar vivo" no jogo durante a observacao.
    """
    try:
        from ocr.monitoramento_aposta import apostar_agora
        from ocr.monitoramento_cashout import monitorar_cashout_preciso
        from automation.escrever_valor import escrever_valor_aposta

        log("   💉 Aposta anti-inatividade: 65 AOA @ 1.10x")
        escrever_valor_aposta(65)
        time.sleep(0.3)
        if apostar_agora(timeout=5.0):
            monitorar_cashout_preciso(timeout=30, ultimo=0, limiar=1.10)
            log("   💉 Aposta anti-inatividade concluída.")
        else:
            log("   💉 Não conseguiu apostar (anti-inatividade) — sem problema.")
    except Exception as _e:
        log(f"   💉 Erro na aposta anti-inatividade: {_e}")


def iniciar_robo_autonomo():
    log("🚀 Robô Aviator iniciado...")
    log("    💡 Carrega Ctrl+C UMA vez para parar com segurança após o round actual.")
    log("    💡 Carrega Ctrl+C DUAS vezes para forçar paragem imediata.")

    # ─── BUG 6 FIX: re-lê o estado da banca do disco ────────────────
    # O módulo banca.py guarda o estado num dict global carregado apenas
    # uma vez no import. Quando a meta diária é atingida, o lucro fica
    # acima da meta — e mesmo apagando o estado_banca.json pela GUI, o
    # dict em memória continua com o valor antigo. Resultado: deve_continuar()
    # retorna False ao iniciar nova sessão e o bot termina logo, obrigando
    # a fechar/reabrir a GUI.
    #
    # Solução: força nova leitura do disco no arranque. Se o ficheiro foi
    # apagado, o estado default {0,0,0} prevalece e o bot pode arrancar.
    recarregar_banca_disco()

    # Reset dos banners de missão (senão "OBJECTIVO ATINGIDO" não reaparece
    # numa nova sessão depois de ter sido mostrado na anterior)
    try:
        from gestor.banca import resetar_banners_missao
        resetar_banners_missao()
    except Exception:
        pass

    config = carregar_config()

    # ─── Detecta qual estratégia usar (prioridade: padroes > dados > PDF) ──
    usar_rosa = estrategia_rosa_activa(config)
    usar_padroes = (not usar_rosa) and estrategia_padroes_activa(config)
    usar_dados = (not usar_rosa) and (not usar_padroes) and estrategia_dados_activa(config)

    # Reset do estado da Estratégia Rosa no arranque
    if usar_rosa:
        try:
            resetar_estado_rosa()
        except Exception:
            pass

    if usar_rosa:
        _cashout_rosa = config.get("cashout_rosa", 1.90)
        log("🌹 ESTRATÉGIA ROSA ACTIVA")
        log("   📐 Aposta APENAS depois de um rosa (≥10x):")
        log("      🌹 Rosa (≥10x)  → aposta na próxima rodada")
        log("      🌹 Rosa de novo → continua a apostar")
        log("      🟣 Roxo (2-10x)  → alvo atingido, pausa até próximo rosa")
        log("      🔵 Azul (<2x)    → tenta + 1 vez (máx 2), depois pausa")
        log(f"   🎯 Cashout alvo: {_cashout_rosa:.2f}x")
        log("   📊 Resultados gravados em data/estrategia_rosa.csv para análise")

    if usar_padroes:
        # Ler cashouts actuais do JSON (em vez de hard-coded)
        try:
            from pathlib import Path
            import json as _json
            params_path = Path("config/parametros_padroes.json")
            if params_path.exists():
                with open(params_path, "r", encoding="utf-8") as _f:
                    _p = _json.load(_f)
                _p2 = _p.get("p2_seis_azuis", {}).get("cashout_alvo", 2.0)
                _p3n = _p.get("p3_combo_quente", {}).get("cashout_alvo_normal", 3.0)
                _p3j = _p.get("p3_combo_quente", {}).get("cashout_alvo_jackpot", 5.0)
                _p4 = _p.get("p4_hot_streak", {}).get("cashout_alvo", 1.5)
                _p5 = _p.get("p5_rosa_queimada", {}).get("cashout_alvo", 1.5)
                _p6 = _p.get("p6_default", {}).get("cashout_alvo", 1.5)
            else:
                _p2, _p3n, _p3j, _p4, _p5, _p6 = 2.0, 3.0, 5.0, 1.5, 1.5, 1.5
        except Exception:
            _p2, _p3n, _p3j, _p4, _p5, _p6 = 2.0, 3.0, 5.0, 1.5, 1.5, 1.5

        log("🎯 ESTRATÉGIA 'FOLLOW PATTERNS' ACTIVA")
        log("   📐 Padrões detectados em tempo real (cashouts do JSON):")
        log("      P1 Pós-mega       → não apostar")
        log(f"      P2 6+ azuis       → cashout {_p2:.2f}x (especulativo)")
        log(f"      P3 Combo quente   → cashout {_p3n:.1f}-{_p3j:.1f}x (jackpot)")
        log(f"      P4 Hot streak     → cashout {_p4:.2f}x")
        log(f"      P5 Rosa queimada  → cashout {_p5:.2f}x")
        log(f"      P6 Default        → cashout {_p6:.2f}x (cadeia)")
        log("   🎯 Sistema de 3 FASES:")
        log("      FASE 1: cold start — usa lista visível no ecrã")
        log(f"      FASE 2: warm-up — primeiros {ROUNDS_WARMUP} rounds novos")
        log(f"      FASE 3: operação normal — janela {JANELA_OPERACIONAL} crashes")
    elif usar_dados:
        log("📊 ESTRATÉGIA DE DADOS ACTIVA (minutos quentes — simples)")
        minutos_quentes = info_minutos_quentes()
        log(f"   🔥 {len(minutos_quentes)} minutos quentes configurados")
    else:
        log("📜 Estratégia PDF (base) activa.")

    modulos_on = []
    if config.get("adaptive_strategy"):  modulos_on.append("adaptive_strategy")
    if config.get("hot_cold_detection"): modulos_on.append("hot_cold_detection")
    if config.get("preservar_banca"):    modulos_on.append("preservar_banca")
    if modulos_on:
        log(f"🧠 Inteligência adaptativa ACTIVA: {', '.join(modulos_on)}")
    else:
        log(f"🧠 Inteligência adaptativa: tudo OFF (modo conservador)")

    iniciar_stop_graceful()

    # ─── HISTÓRICO DE FICHEIRO ──────────────────────────────────────
    # Apenas usado pelas estratégias PDF/dados. Para Follow Patterns
    # usamos a janela móvel baseada no contexto visível.
    historico_ficheiro = collections.deque(_carregar_historico_csv(), maxlen=200)
    log(f"📂 Histórico em ficheiro: {len(historico_ficheiro)} entradas (para PDF/dados)")
    log(f"💰 Estado aposta: {info_estado()}")

    iniciar_sessao()

    vitorias_sessao = 0
    derrotas_sessao = 0

    # ─── FASE 1: COLD START ─────────────────────────────────────────
    log("⏳ FASE 1: A captar lista visível (cold start)...")
    lista_anterior = _aguardar_lista_valida_com_stop(max_segundos=60.0)

    if lista_anterior is None:
        log("✋ Paragem pedida durante leitura inicial — a sair.")
        log("👋 Bot encerrado. Até à próxima!")
        return

    log(f"✅ Sync: {len(lista_anterior)} crashes visíveis (último = {lista_anterior[0]:.2f}x)")

    # ─── HISTORICO EXPANDIDO (se foi capturado pela GUI) ──────────────
    # Le data/historico_inicial.json se existir. Esse ficheiro tem ate 80
    # crashes do popup do casino, capturados antes de iniciar a sessao.
    # Sobrepoe com lista_anterior (que tem so 13 crashes mais recentes).
    crashes_iniciais = list(lista_anterior)   # default: so a lista pequena
    stats_temperatura = None
    cashout_adaptado_p6 = None

    # Reset cache da temperatura na estrategia (forca reler o JSON)
    try:
        from estrategia.estrategia_padroes import resetar_temperatura
        resetar_temperatura()
        # Apaga temperatura dinamica da sessao anterior
        from pathlib import Path as _P
        _temp_dyn = _P("data/temperatura_atual.json")
        if _temp_dyn.exists():
            _temp_dyn.unlink()
    except Exception:
        pass

    try:
        from pathlib import Path
        import json as _json
        path_hist = Path("data/historico_inicial.json")
        if path_hist.exists():
            with open(path_hist, "r", encoding="utf-8") as _f:
                hist_data = _json.load(_f)
            hist_crashes = hist_data.get("crashes", [])
            hist_stats   = hist_data.get("estatisticas", {})
            if hist_crashes and len(hist_crashes) >= 20:
                # Encontrar onde a lista_anterior encaixa no historico
                # (lista_anterior[0] e' o crash mais recente — procurar no historico)
                ultimo_lista = lista_anterior[0] if lista_anterior else None
                if ultimo_lista is not None:
                    # Procura ultimo_lista no historico
                    found_idx = -1
                    for i, c in enumerate(hist_crashes[:15]):
                        if abs(c - ultimo_lista) < 0.05:
                            found_idx = i
                            break
                    if found_idx >= 0:
                        # Encaixa: novos = lista_anterior[0:found_idx_da_lista],
                        # depois historico do found_idx em diante
                        crashes_iniciais = list(lista_anterior) + hist_crashes[found_idx + 1:]
                        log(f"📊 Histórico expandido: {len(hist_crashes)} crashes capturados + {found_idx} novos durante setup")
                    else:
                        # Nao encaixou — usa historico tal como esta (perdeu sync)
                        crashes_iniciais = hist_crashes
                        log(f"📊 Histórico expandido: {len(hist_crashes)} crashes capturados (sem sync com lista live — alguns rounds perdidos)")
                else:
                    crashes_iniciais = hist_crashes

                # Mostra estatisticas + classificacao
                stats_temperatura = hist_stats
                cls = hist_stats.get("classificacao", "normal")
                emoji_cls = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}.get(cls, "🟡")
                log(f"📈 Estatísticas: {hist_stats.get('pct_rosas', 0):.1f}% rosas | "
                    f"mediana {hist_stats.get('crash_mediano', 0):.2f}x | "
                    f"q67 {hist_stats.get('quantil_67', 0):.2f}x")
                log(f"🌡️ Classificação da sessão: {emoji_cls} {cls.upper()}")

                # Ajusta cashout do P6 baseado na temperatura
                try:
                    from ocr.leitura_historico import cashout_recomendado_da_temperatura
                    cashout_adaptado_p6, motivo_temp = cashout_recomendado_da_temperatura(
                        hist_stats, padrao_default=1.5)
                    log(f"🎯 Cashout adaptado: {motivo_temp}")
                except Exception:
                    pass
    except Exception as _e:
        log(f"⚠️ Erro a carregar historico_inicial.json: {_e}", "warning")

    # JANELA VIVA — esta é a fonte de verdade para Follow Patterns
    # Inicialmente é a lista expandida (historico + live) se disponivel,
    # senao a lista visivel pequena.
    JANELA_RICA = max(JANELA_OPERACIONAL, 80)   # ate 80 crashes se temos historico
    janela_viva = collections.deque(crashes_iniciais, maxlen=JANELA_RICA)
    rounds_novos_sessao = 0

    # ─── MODO OBSERVADOR (treinamento) — estado ──────────────────────
    _em_observacao = False
    _ts_inicio_observacao = 0.0
    _ts_ultima_aposta_anti = 0.0

    if usar_padroes:
        log(f"📊 Janela inicial Follow Patterns: {len(janela_viva)} crashes")
        log(f"   Recentes: {[f'{c:.2f}' for c in list(janela_viva)[:5]]}...")

    log("   A aguardar próximo round terminar...")

    while True:
        try:
            if paragem_pedida():
                log("✋ Paragem pedida — a sair do loop principal.")
                log(f"📊 Resumo final: {vitorias_sessao}W / {derrotas_sessao}L")
                break

            # ─── HUMANIZACAO: pausa longa ocasional ──────────────────
            # 4% de chance de fazer pausa de 6-15s (~1 em cada 25 rounds)
            # Simula humano a distrair-se / olhar para o ecra.
            #
            # EXCEPÇÃO: na Estratégia Rosa, NÃO fazemos pausas longas. A
            # estratégia precisa de reagir IMEDIATAMENTE quando sai um rosa
            # (apostar na janela seguinte). Uma pausa de 14s faria perder
            # o momento exacto e a janela de apostas pós-rosa.
            if not usar_rosa:
                dur_pausa = pausa_longa_ocasional(probabilidade=0.04,
                                                    min_s=6.0, max_s=15.0)
                if dur_pausa > 0:
                    log(f"☕ Pausa humanizada ({dur_pausa:.1f}s)")

            watchdog_verificar()

            # ─── META/STOP ATINGIDO → MODO OBSERVADOR (treinamento) ──────
            if not deve_continuar():
                modo_observador = config.get("modo_observador", True)
                if not modo_observador:
                    log("🛑 Limite de banca atingido.")
                    break

                # Entra/mantem-se em MODO OBSERVADOR:
                # nao aposta, mas continua a capturar a lista para aprender
                # como as fases transitam. A cada N min faz 1 aposta minima
                # anti-inatividade para o casino nao cancelar a sessao.
                if not _em_observacao:
                    _em_observacao = True
                    _ts_inicio_observacao = time.time()
                    _ts_ultima_aposta_anti = time.time()
                    log("")
                    log("🔬 ═══════════════════════════════════════════════")
                    log("🔬  MODO OBSERVADOR ACTIVADO (meta/stop atingido)")
                    log("🔬  O bot PAROU de apostar mas continua a OBSERVAR")
                    log("🔬  as fases para aprender as transições do jogo.")
                    log("🔬  A cada ~4 min faz 1 aposta mínima (anti-inatividade).")
                    log("🔬  Carrega PARAR quando quiseres terminar.")
                    log("🔬 ═══════════════════════════════════════════════")
                    log("")

                # Captura a lista e regista a transicao de fase
                lista_obs = ler_lista_multiplicadores_atuais()
                if lista_obs and _lista_e_valida(lista_obs):
                    novo_obs = _round_novo(lista_obs, lista_anterior)
                    if novo_obs is not None:
                        janela_viva.appendleft(novo_obs)
                        lista_anterior = lista_obs.copy()
                        _registar_observacao_fase(novo_obs, list(janela_viva))

                # Aposta minima anti-inatividade a cada ~4 min
                if time.time() - _ts_ultima_aposta_anti > 240:  # 240s = 4 min
                    log("⏱️ 4 min em observação — aposta mínima anti-inatividade...")
                    _fazer_aposta_anti_inatividade()
                    _ts_ultima_aposta_anti = time.time()

                if paragem_pedida():
                    tempo_obs = (time.time() - _ts_inicio_observacao) / 60
                    log(f"✋ Paragem pedida — fim da observação ({tempo_obs:.1f} min).")
                    log(f"📊 Resumo final: {vitorias_sessao}W / {derrotas_sessao}L")
                    break

                time.sleep(1.0)
                continue

            lista_actual = ler_lista_multiplicadores_atuais()
            if not lista_actual:
                if paragem_pedida():
                    log("✋ Paragem pedida durante OCR vazio — a sair.")
                    log(f"📊 Resumo final: {vitorias_sessao}W / {derrotas_sessao}L")
                    break
                time.sleep(0.3)
                continue

            novo = _round_novo(lista_actual, lista_anterior)
            if novo is None:
                if paragem_pedida():
                    log("✋ Paragem pedida — a sair.")
                    log(f"📊 Resumo final: {vitorias_sessao}W / {derrotas_sessao}L")
                    break
                time.sleep(0.3)
                continue

            t_round_acabou = time.time()
            salvar_multiplicador(novo)

            # ─── ACTUALIZAR JANELA VIVA ──────────────────────────────
            # appendleft = mais recente fica em [0]
            janela_viva.appendleft(novo)
            historico_ficheiro.appendleft(novo)
            rounds_novos_sessao += 1

            # ─── TEMPERATURA DINAMICA (IA Adaptativa v2) ─────────────
            # A cada 10 rounds novos, recalcula a temperatura a partir da
            # janela viva (crashes recentes da SESSAO, nao do historico inicial).
            # Isto faz a temperatura "respirar" — adapta-se se a sessao muda
            # de quente para fria a meio.
            if usar_padroes and rounds_novos_sessao % 10 == 0:
                stats_dyn = recalcular_temperatura_dinamica(list(janela_viva))
                if stats_dyn:
                    cls_dyn = stats_dyn.get("classificacao", "normal")
                    emoji_dyn = {"fria": "❄️", "normal": "🟡", "quente": "🔥"}.get(cls_dyn, "🟡")
                    log(f"🌡️ Temperatura recalculada (round {rounds_novos_sessao}): "
                        f"{emoji_dyn} {cls_dyn.upper()} | "
                        f"{stats_dyn['pct_rosas']:.1f}% rosas | q67 {stats_dyn['quantil_67']:.2f}x")

            # ─── ESTABILIZAR PAGINA (anti-scroll) ────────────────────
            # A cada 5 rounds, forca a pagina ao topo (Ctrl+Home) para
            # evitar que scroll acidental desalinhe a calibracao.
            # Usamos a versao SEM clique (garantir_topo_pagina) porque a
            # esta altura o foco ja esta no browser (ja apostamos antes),
            # e um clique extra poderia carregar acidentalmente num botao.
            if rounds_novos_sessao % 5 == 0:
                try:
                    from utils.humanizar import garantir_topo_pagina
                    garantir_topo_pagina()
                    log(f"🏠 Página estabilizada (Ctrl+Home, round {rounds_novos_sessao})")
                except Exception:
                    pass

            if _lista_e_valida(lista_actual):
                lista_anterior = lista_actual.copy()
            registar_nova_rodada()

            fase = _fase_actual(rounds_novos_sessao)
            log(f"📈 Round acabou: {novo:.2f}x — janela de aposta aberta! [{fase}]")

            if paragem_pedida():
                log("✋ Paragem pedida — não vou apostar neste round.")
                continue

            # ─── HOT/COLD DETECTION ──────────────────────────────────
            pausar_streak, motivo_streak = deve_pausar()
            if pausar_streak:
                log(motivo_streak)
                registrar_resultado_csv("pulado_streak")
                imprimir_dashboard(
                    multiplicador_round=novo, resultado="pulado",
                    vitorias_sessao=vitorias_sessao, derrotas_sessao=derrotas_sessao,
                )
                continue
            elif motivo_streak:
                log(motivo_streak)

            # ─── DECISÃO DA ESTRATÉGIA ───────────────────────────────
            minuto_actual = datetime.now().minute

            # IMPORTANTE: Follow Patterns usa JANELA VIVA (não histórico de ficheiro)
            # As outras estratégias usam o histórico tradicional
            if usar_rosa:
                contexto = list(janela_viva)
                deve_apostar, cashout_alvo, motivo_rosa = decidir_aposta_rosa(
                    contexto, config.get("cashout_rosa", 1.90))
                log(motivo_rosa)
            elif usar_padroes:
                contexto = list(janela_viva)
                deve_apostar, cashout_alvo = aplicar_estrategia_padroes(contexto, config)
            elif usar_dados:
                deve_apostar, cashout_alvo = aplicar_estrategia_dados(list(historico_ficheiro), config)
            else:
                deve_apostar, cashout_alvo = aplicar_estrategia(list(historico_ficheiro), config)

            if not deve_apostar:
                registrar_resultado_csv("pulado")
                registar_aposta(
                    multiplicador_round=novo, cashout_alvo=0.0,
                    valor_apostado=0.0, resultado="pulado",
                    cashout_obtido=0.0, lucro_aposta=0.0,
                    banca_acumulada=_ler_lucro_banca(),
                    cadeia_pos=0, cofre=_ler_cofre(),
                    estrategia=_detectar_nome_estrategia(usar_padroes, usar_dados,
                                                          0.0, minuto_actual),
                )
                imprimir_dashboard(
                    multiplicador_round=novo, resultado="pulado",
                    vitorias_sessao=vitorias_sessao, derrotas_sessao=derrotas_sessao,
                )
                continue

            # ─── AJUSTES INTELIGENTES DE ALVO ────────────────────────
            cashout_alvo_ajustado, motivo_alvo = ajustar_alvo(cashout_alvo)
            if cashout_alvo_ajustado != cashout_alvo:
                log(f"🧠 {motivo_alvo}")
                cashout_alvo = cashout_alvo_ajustado

            # ─── CÁLCULO DO VALOR DA APOSTA ──────────────────────────
            valor_cadeia, motivo_valor = calcular_valor_aposta(cashout_alvo)
            log(f"💼 {motivo_valor}")

            aposta_base = config.get("aposta_base", 100)

            if usar_padroes:
                valor_aposta, motivo_padrao = calcular_valor_aposta_padroes(
                    aposta_base, valor_cadeia
                )
                if motivo_padrao:
                    log(motivo_padrao)
            elif usar_dados:
                valor_aposta, motivo_dados = calcular_valor_aposta_dados(
                    cashout_alvo, aposta_base, valor_cadeia
                )
                if motivo_dados:
                    log(motivo_dados)
            else:
                valor_aposta = valor_cadeia

            lucro_actual = _ler_lucro_banca()
            valor_ajustado, motivo_preservar = ajustar_valor(valor_aposta, lucro_actual)
            if valor_ajustado != valor_aposta:
                log(f"🧠 {motivo_preservar}")
                valor_aposta = valor_ajustado

            tempo_decisao = time.time() - t_round_acabou
            log(f"🧠 Cashout alvo {cashout_alvo:.2f}x | Valor {valor_aposta:.0f} AOA | {tempo_decisao:.1f}s decisão")

            if not escrever_valor_aposta(valor_aposta):
                log("⚠️ Falhou a definir valor da aposta.", "warning")
                registrar_resultado_csv("falha_valor")
                continue

            # ─── OCR DO SALDO — antes da aposta (para detectar fantasmas) ───
            saldo_antes_aposta = None
            try:
                from ocr.leitura_saldo import ler_saldo_robusto
                from config.configuracoes import carregar_config as _cc
                _cfg = _cc()
                _area_saldo = _cfg.get("area_saldo")
                if _area_saldo:
                    saldo_antes_aposta = ler_saldo_robusto(_area_saldo, tentativas=1)
            except Exception:
                pass

            sucesso_aposta = apostar_agora(timeout=5.0)
            if not sucesso_aposta:
                log("⚠️ Falhou a apostar.", "warning")
                registrar_resultado_csv("falha_aposta")
                continue

            maior_mult, cashout_ok = monitorar_cashout_preciso(
                timeout=30, ultimo=novo, limiar=cashout_alvo
            )

            # ─── OCR DO SALDO — apos cashout (deteccao de fantasmas BLINDADA) ──
            # IMPORTANTE: o OCR do saldo as vezes le' lixo (ex: 439302 quando
            # era 4393, ou junta digitos). Se confiarmos cegamente, marcamos
            # vitorias REAIS como fantasmas e destruimos a contabilidade.
            #
            # Por isso aplicamos VARIOS sanity checks. So marcamos fantasma se
            # TODAS as condicoes de seguranca passarem. Na duvida, confiamos no
            # cashout original (detector de fase, que e' mais fiavel).
            if saldo_antes_aposta is not None and cashout_ok:
                try:
                    from ocr.leitura_saldo import ler_saldo_robusto
                    saldo_apos = ler_saldo_robusto(_area_saldo, tentativas=2)

                    # ── SANITY CHECK 1: leitura existe ──────────────────
                    if saldo_apos is None:
                        log("ℹ️ OCR saldo pós-cashout falhou — confio no cashout (fase).")
                        raise StopIteration  # sai do bloco, mantem cashout_ok=True

                    delta_real = saldo_apos - saldo_antes_aposta
                    delta_esperado = valor_aposta * (maior_mult - 1)

                    # ── SANITY CHECK 2: saldos plausiveis ───────────────
                    # Saldo nao pode ser absurdo (ex: 439302 quando banca ~50k)
                    # Limite: 100 milhoes. Acima disso, OCR leu lixo.
                    if (saldo_antes_aposta > 100_000_000 or
                            saldo_apos > 100_000_000 or
                            saldo_antes_aposta <= 0 or saldo_apos <= 0):
                        log(f"⚠️ OCR saldo implausível "
                            f"(antes={saldo_antes_aposta:.0f}, após={saldo_apos:.0f}) "
                            f"— ignoro verificação, confio no cashout.", "warning")
                        raise StopIteration

                    # ── SANITY CHECK 3: delta_real nao pode ser uma perda ─
                    # maior que a propria aposta. Se cashou OK, o pior caso e'
                    # delta=0 (nao mudou). Um delta MUITO negativo = OCR errado.
                    if delta_real < -valor_aposta * 1.5:
                        log(f"⚠️ OCR saldo deu delta impossível "
                            f"({delta_real:+.0f} para aposta {valor_aposta:.0f}) "
                            f"— OCR leu lixo, confio no cashout.", "warning")
                        raise StopIteration

                    # ── SANITY CHECK 4: delta absurdamente grande ───────
                    # Se o saldo "subiu" muito mais que o esperado (ex: 10x),
                    # tambem e' leitura suspeita.
                    if delta_real > abs(delta_esperado) * 5 + 1000:
                        log(f"⚠️ OCR saldo deu ganho suspeito "
                            f"({delta_real:+.0f} vs esperado {delta_esperado:+.0f}) "
                            f"— confio no cashout original.", "warning")
                        raise StopIteration

                    # ── Todos os checks passaram: verificacao FIAVEL ────
                    # Tolerancia generosa: 60% do esperado ou 100 AOA
                    tolerancia = max(abs(delta_esperado) * 0.6, 100)
                    if delta_real < delta_esperado - tolerancia:
                        # FANTASMA real: saldo claramente nao subiu o esperado
                        log(f"👻 FANTASMA DETECTADA: cashout dizia +{delta_esperado:.0f} "
                            f"mas saldo só mudou {delta_real:+.0f} AOA. "
                            f"A registar como PERDA.", "warning")
                        cashout_ok = False
                        maior_mult = 0.0
                    else:
                        log(f"✅ Cashout confirmado pelo saldo "
                            f"({delta_real:+.0f} real vs {delta_esperado:+.0f} esperado)")

                except StopIteration:
                    pass  # algum sanity check falhou — mantem cashout original
                except Exception:
                    pass  # qualquer outro erro — mantem cashout original

            estrategia_usada = _detectar_nome_estrategia(
                usar_padroes, usar_dados, cashout_alvo, minuto_actual
            )

            usa_cadeia_composta = True
            if usar_padroes:
                d = obter_ultima_decisao()
                if d and not d.usa_cadeia_composta:
                    usa_cadeia_composta = False

            if cashout_ok:
                registrar_resultado_csv("cashout_ok", maior_mult)
                registrar_resultado(sucesso=True, valor_apostado=valor_aposta,
                                       multiplicador_cashout=maior_mult)
                registar_estrat(True)

                if usa_cadeia_composta:
                    registar_resultado_composta(True, valor_aposta, maior_mult)

                registar_aposta_real_hot_cold(vitoria=True)
                registar_resultado_adaptive(cashout_alvo, ganhou=True)
                vitorias_sessao += 1
                lucro_aposta = valor_aposta * (maior_mult - 1)

                if usar_padroes:
                    registar_resultado_padrao(ganhou=True, lucro_aposta=lucro_aposta)
                elif usar_dados:
                    registar_resultado_dados(
                        minuto_da_aposta=minuto_actual,
                        cashout_alvo=cashout_alvo,
                        ganhou=True, lucro_aposta=lucro_aposta,
                    )

                if usar_rosa:
                    registar_resultado_rosa(novo, cashout_alvo, True, maior_mult)

                log(f"💰 GANHOU em {maior_mult:.2f}x | {info_estado()}")

                registar_aposta(
                    multiplicador_round=novo, cashout_alvo=cashout_alvo,
                    valor_apostado=valor_aposta, resultado="ganhou",
                    cashout_obtido=maior_mult, lucro_aposta=lucro_aposta,
                    banca_acumulada=_ler_lucro_banca(),
                    cadeia_pos=0, cofre=_ler_cofre(),
                    estrategia=estrategia_usada,
                )

                imprimir_dashboard(
                    multiplicador_round=novo, resultado="ganhou",
                    valor_apostado=valor_aposta, cashout_obtido=maior_mult,
                    vitorias_sessao=vitorias_sessao, derrotas_sessao=derrotas_sessao,
                )
            else:
                registrar_resultado_csv("crash_perdeu", maior_mult)
                registrar_resultado(sucesso=False, valor_apostado=valor_aposta)
                registar_estrat(False)

                if usa_cadeia_composta:
                    registar_resultado_composta(False, valor_aposta)

                registar_aposta_real_hot_cold(vitoria=False)
                registar_resultado_adaptive(cashout_alvo, ganhou=False)
                derrotas_sessao += 1

                if usar_padroes:
                    registar_resultado_padrao(ganhou=False, lucro_aposta=-valor_aposta)
                elif usar_dados:
                    registar_resultado_dados(
                        minuto_da_aposta=minuto_actual,
                        cashout_alvo=cashout_alvo,
                        ganhou=False, lucro_aposta=-valor_aposta,
                    )

                if usar_rosa:
                    registar_resultado_rosa(novo, cashout_alvo, False, maior_mult)

                log(f"💥 PERDEU em {maior_mult:.2f}x | {info_estado()}")

                registar_aposta(
                    multiplicador_round=novo, cashout_alvo=cashout_alvo,
                    valor_apostado=valor_aposta, resultado="perdeu",
                    cashout_obtido=maior_mult, lucro_aposta=-valor_aposta,
                    banca_acumulada=_ler_lucro_banca(),
                    cadeia_pos=0, cofre=_ler_cofre(),
                    estrategia=estrategia_usada,
                )

                imprimir_dashboard(
                    multiplicador_round=novo, resultado="perdeu",
                    valor_apostado=valor_aposta, cashout_obtido=maior_mult,
                    vitorias_sessao=vitorias_sessao, derrotas_sessao=derrotas_sessao,
                )

            if paragem_pedida():
                log("✋ Round terminado. Paragem confirmada — a sair.")
                log(f"📊 Resumo final: {vitorias_sessao}W / {derrotas_sessao}L")
                break

            nova_lista_apos_voo = ler_lista_multiplicadores_atuais()
            if _lista_e_valida(nova_lista_apos_voo):
                lista_anterior = nova_lista_apos_voo
            else:
                log("⚠️ Lista pós-voo inválida — a manter referência anterior")

        except KeyboardInterrupt:
            log("\n🛑 Robô forçado a parar (Ctrl+C duplo).")
            log(f"📊 Resumo final: {vitorias_sessao}W / {derrotas_sessao}L")
            break
        except Exception as e:
            log(f"❌ Erro: {e}", "error")
            if paragem_pedida():
                log("✋ Paragem pedida após erro — a sair.")
                break
            time.sleep(2)

    log("👋 Bot encerrado. Até à próxima!")
