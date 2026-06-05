# gui/interface.py
import tkinter as tk
import time
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from config.configuracoes import carregar_config

_root    = None
_labels  = {}
_grafico = {}
_historico_lucro: list = []
_inicio = time.time()


def iniciar_interface() -> tk.Tk:
    global _root
    _root = tk.Tk()
    _root.title("🤖 Robô Aviator — Painel de Controlo")
    _root.geometry("460x600")
    _root.resizable(False, False)

    # Status geral
    _labels["status"] = tk.Label(
        _root, text="🔄 Robô em execução...",
        bg="#e0e0e0", font=("Arial", 10, "bold"), relief="solid", bd=1
    )
    _labels["status"].pack(fill="x", pady=(5, 2), padx=5)

    frame = tk.Frame(_root)
    frame.pack(pady=5)

    campos = [
        ("mults",     "Últimos multiplicadores:"),
        ("prev",      "Previsão:"),
        ("conf",      "Confiança:"),
        ("acao",      "Acção:"),
        ("cashout",   "Cashout alvo:"),
    ]
    for chave, titulo in campos:
        tk.Label(frame, text=titulo, font=("Arial", 10, "bold")).pack()
        fonte = "Courier" if chave == "mults" else "Arial"
        _labels[chave] = tk.Label(frame, text="--", font=(fonte, 11))
        _labels[chave].pack()

    tk.Label(_root, text="─" * 52).pack()

    frame2 = tk.Frame(_root)
    frame2.pack(pady=5)

    estat = [
        ("resultado",  "✅ Ganhos: 0.00  ❌ Perdas: 0.00"),
        ("lucro",      "Lucro: 0.00"),
        ("banca",      "Banca actual: --"),
        ("restricao",  ""),
        ("crono",      "🕒 0min 0s"),
    ]
    for chave, texto in estat:
        bold = "bold" if chave in ("lucro",) else ("italic" if chave == "crono" else "normal")
        _labels[chave] = tk.Label(frame2, text=texto, font=("Arial", 10, bold))
        _labels[chave].pack()

    # Gráfico de lucro
    fig = plt.Figure(figsize=(4.4, 1.9), dpi=100)
    ax  = fig.add_subplot(111)
    ax.set_title("Histórico de Lucro", fontsize=9)
    ax.grid(True)
    _grafico["fig"]    = fig
    _grafico["canvas"] = FigureCanvasTkAgg(fig, master=_root)
    _grafico["canvas"].get_tk_widget().pack(pady=8)

    _atualizar_crono()
    return _root


def _atualizar_crono():
    if "crono" in _labels and _root:
        s = int(time.time() - _inicio)
        _labels["crono"].config(text=f"🕒 Em execução: {s // 60}min {s % 60}s")
        _root.after(1000, _atualizar_crono)


def atualizar_interface(
    ultimos_mults: list,
    confianca: float,
    vai_apostar: bool,
    lucro_real: float,
    ganhos: float,
    perdas: float,
    cashout_alvo: float = 0.0,
):
    """Actualiza todos os widgets com dados reais vindos do core."""
    config = carregar_config()
    meta   = float(config.get("meta_diaria", 500.0))
    limite = float(config.get("limite_perda", 500.0))
    banca  = float(config.get("saldo_inicial", 5000.0)) + lucro_real

    if _labels.get("mults"):
        _labels["mults"].config(text=", ".join(f"{m:.2f}x" for m in ultimos_mults[-5:]))
    if _labels.get("prev"):
        _labels["prev"].config(text="Alta" if vai_apostar else "Baixa",
                                fg="green" if vai_apostar else "red")
    if _labels.get("conf"):
        _labels["conf"].config(text=f"{confianca * 100:.1f}%")
    if _labels.get("acao"):
        _labels["acao"].config(text="Apostou" if vai_apostar else "Esperou",
                                fg="green" if vai_apostar else "gray")
    if _labels.get("cashout") and cashout_alvo:
        _labels["cashout"].config(text=f"{cashout_alvo:.2f}x")
    if _labels.get("lucro"):
        _labels["lucro"].config(text=f"Lucro: {lucro_real:.2f}",
                                  fg="green" if lucro_real >= 0 else "red")
    if _labels.get("resultado"):
        _labels["resultado"].config(text=f"✅ Ganhos: {ganhos:.2f}  ❌ Perdas: {perdas:.2f}")
    if _labels.get("banca"):
        _labels["banca"].config(text=f"Banca actual: {banca:.2f}")
    if _labels.get("restricao"):
        if lucro_real >= meta:
            _labels["restricao"].config(text="🏁 Meta diária atingida!", fg="green")
        elif perdas >= limite:
            _labels["restricao"].config(text="⛔ Limite de perdas!", fg="red")
        else:
            _labels["restricao"].config(text="", fg="black")

    # Gráfico com histórico real (por ordem de acontecimento)
    _historico_lucro.append(lucro_real)
    if _grafico.get("fig"):
        ax = _grafico["fig"].axes[0]
        ax.clear()
        ax.set_title("Histórico de Lucro", fontsize=9)
        ax.set_xlabel("Apostas")
        ax.set_ylabel("Lucro")
        ax.grid(True)
        cor = "green" if lucro_real >= 0 else "red"
        ax.plot(_historico_lucro, color=cor, linewidth=1.3)
        ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
        _grafico["canvas"].draw()


def iniciar_interface_em_thread():
    """
    Nota: Tkinter deve correr na thread principal.
    Use esta função apenas se o robô correr numa thread secundária.
    """
    janela = iniciar_interface()
    janela.mainloop()
