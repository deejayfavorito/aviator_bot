# ocr/monitoramento_cashout.py
"""
Cashout — versão com DIAGNÓSTICO TEMPORAL.

Mudanças desta versão:
  1. Removido o time.sleep(0.08) que adiava a primeira leitura
  2. Adicionado timer: mostra quanto tempo passou desde detectar voo
     até cada leitura. Permite diagnosticar atrasos do OCR.
  3. Lê multiplicador IMEDIATAMENTE ao detectar fase laranja
"""
import time
from typing import Optional, Tuple

from config.configuracoes import carregar_config
from automation.cashout import acionar_cashout_na_area
from ocr.leitura_ao_vivo import capturar_multiplicador_voo, invalidar_cache
from ocr.detector_fase import detectar_fase, Fase


def monitorar_cashout_preciso(
    timeout: int = 30,
    ultimo: Optional[float] = None,
    limiar: Optional[float] = None
) -> Tuple[float, bool]:

    cfg = carregar_config()
    if limiar is None:
        limiar = float(cfg.get("limiar_cashout", 1.20))

    max_legit = float(cfg.get("max_multiplicador_valido", 10000.0))
    min_legit = float(cfg.get("min_multiplicador_valido", 1.00))

    offset_latencia = float(cfg.get("offset_latencia_cashout", 0.05))
    limiar_efectivo = max(1.01, limiar - offset_latencia)

    print(f"👁️ Cashout | alvo={limiar:.2f}× (gatilho={limiar_efectivo:.2f}×)")
    invalidar_cache()
    deadline = time.time() + timeout

    cashout_ok       = False
    maior            = 0.0
    voou             = False
    ts_voo_iniciado  = None

    print("🔁 A aguardar voo decolar (transição vermelho→laranja)...")

    while time.time() < deadline:
        fase, _ = detectar_fase()

        # ── Round acabou (botão voltou a verde) ──────────────────────────
        if fase == Fase.APOSTA_DISPONIVEL:
            if voou:
                print(f"💥 Voo terminou sem cashout (max visto: {maior:.2f}x)")
            else:
                print(f"⚠️  Saiu de fase sem voo decolar")
            break

        # ── Voo em curso (botão laranja) ─────────────────────────────────
        if fase == Fase.VOO_COM_APOSTA:
            if not voou:
                voou = True
                ts_voo_iniciado = time.time()
                print(f"🛫 Voo iniciado (botão laranja)")
                # SEM sleep — lê imediatamente

            # Lê multiplicador (cache invalidado para leitura fresca)
            invalidar_cache()
            v = capturar_multiplicador_voo()

            if v and min_legit <= v <= max_legit:
                dt = time.time() - ts_voo_iniciado
                maior = max(maior, v)

                if v >= limiar_efectivo:
                    print(f"⚡ Cashout @ {v:.2f}× após {dt:.2f}s (alvo {limiar:.2f}×)")
                    try:
                        acionar_cashout_na_area()
                        cashout_ok = True
                        print("💸 Cashout executado.")
                    except Exception as e:
                        print(f"❌ Erro no cashout: {e}")
                    break
                else:
                    print(f"✈️  {v:.2f}× ({dt:.2f}s)")

        # ── Aposta colocada, à espera do voo ─────────────────────────────
        elif fase == Fase.APOSTA_COLOCADA:
            pass

        # ── Voo sem aposta ────────────────────────────────────────────────
        elif fase == Fase.VOO_SEM_APOSTA:
            print(f"⚠️  Estado inesperado: voo sem aposta")
            break

        time.sleep(0.02)

    if not cashout_ok and maior > 0:
        print(f"📌 Maior visto: {maior:.2f}× (sem cashout)")

    print("⏸️  A aguardar limpeza do ecrã (1.5s)...")
    time.sleep(1.5)

    invalidar_cache()
    return maior, cashout_ok
