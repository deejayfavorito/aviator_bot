# gui/painel_controlo.py
"""
Painel de Controlo Gráfico do Aviator Bot — Parte 3 + Estratégia de Dados.

NOVO nesta versão:
  - Checkbox "usar_estrategia_dados" na aba Config
  - Indicador da estratégia activa no painel principal
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, simpledialog
import threading
import queue
import sys
import json
import csv
import subprocess
import os
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta


MAX_FILA           = 1000
MAX_BATCH          = 30
MAX_LINHAS_TEXTO   = 1500
LINHAS_PARA_CORTAR = 500


class RedireccionadorTexto:
    def __init__(self, fila, stream_original):
        self.fila = fila
        self.stream_original = stream_original

    def write(self, texto):
        if self.stream_original:
            try:
                self.stream_original.write(texto)
                self.stream_original.flush()
            except Exception:
                pass
        if texto.strip():
            try:
                self.fila.put_nowait(texto)
            except queue.Full:
                try:
                    self.fila.get_nowait()
                    self.fila.put_nowait(texto)
                except queue.Empty:
                    pass

    def flush(self):
        if self.stream_original:
            try:
                self.stream_original.flush()
            except Exception:
                pass


class PainelControlo:
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 Aviator Bot")
        self.root.geometry("580x620+10+10")
        self.root.minsize(450, 400)

        self.bot_thread = None
        self.bot_a_correr = False
        self.fila_logs = queue.Queue(maxsize=MAX_FILA)
        self.stdout_original = sys.stdout
        self.stderr_original = sys.stderr
        self.modo_compacto = False
        self.sempre_no_topo = False

        self.ultima_msg = None
        self.contador_repetidos = 0
        self.ultimo_index_repetido = None

        self.vars_config = {}

        self._construir_layout()
        self._aplicar_estilo()

        self.root.after(100, self._processar_fila_logs)
        self.root.after(1000, self._actualizar_estado)

        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

    def _construir_layout(self):
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill="x", padx=5, pady=5)

        self.btn_topo = tk.Button(toolbar, text="📌 Sempre no topo",
            command=self._toggle_sempre_topo,
            relief="raised", cursor="hand2", font=("Arial", 9))
        self.btn_topo.pack(side="left", padx=2)

        self.btn_compactar = tk.Button(toolbar, text="📐 Compactar",
            command=self._toggle_compactar,
            relief="raised", cursor="hand2", font=("Arial", 9))
        self.btn_compactar.pack(side="left", padx=2)

        ttk.Button(toolbar, text="🔻 Minimizar",
                   command=self.root.iconify).pack(side="left", padx=2)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        self.aba_controlo    = ttk.Frame(self.notebook)
        self.aba_calibracao  = ttk.Frame(self.notebook)
        self.aba_config      = ttk.Frame(self.notebook)
        self.aba_relatorios  = ttk.Frame(self.notebook)
        self.aba_historico   = ttk.Frame(self.notebook)

        self.notebook.add(self.aba_controlo,   text="🎮 Controlo")
        self.notebook.add(self.aba_calibracao, text="📐 Calibração")
        self.notebook.add(self.aba_config,     text="⚙ Config")
        self.notebook.add(self.aba_relatorios, text="📊 Relatórios")
        self.notebook.add(self.aba_historico,  text="📁 Histórico")

        self._construir_aba_controlo()
        self._construir_aba_calibracao()
        self._construir_aba_config()
        self._construir_aba_relatorios()
        self._construir_aba_historico()

    def _construir_aba_controlo(self):
        frame = self.aba_controlo

        # ═══ PAINEL DE MISSÃO ═══════════════════════════════════════
        self.painel_missao = tk.LabelFrame(frame, text="🎯 Missão", padx=8, pady=5,
                                             font=("Arial", 9, "bold"))
        self.painel_missao.pack(fill="x", padx=5, pady=(5, 3))

        # Linha 1: descrição (banca inicial → banca alvo)
        self.lbl_missao_desc = tk.Label(self.painel_missao,
                                          text="⏳ A carregar missão...",
                                          font=("Arial", 9, "bold"), anchor="w")
        self.lbl_missao_desc.pack(fill="x", padx=5)

        # Linha 2: barra de progresso
        self.progresso_missao = ttk.Progressbar(self.painel_missao, length=300,
                                                  mode="determinate", maximum=100)
        self.progresso_missao.pack(fill="x", padx=5, pady=(3, 3))

        # Linha 3: status (zona em rota, perigo, etc) + valor de progresso
        self.lbl_missao_status = tk.Label(self.painel_missao,
                                            text="--",
                                            font=("Arial", 8), anchor="w")
        self.lbl_missao_status.pack(fill="x", padx=5)

        # Linha 4: stop loss
        self.lbl_missao_stop = tk.Label(self.painel_missao,
                                          text="🛡️ Stop loss em --",
                                          font=("Arial", 8), foreground="gray",
                                          anchor="w")
        self.lbl_missao_stop.pack(fill="x", padx=5)

        # Linha 5: botão "Sincronizar saldo"
        f_sync = tk.Frame(self.painel_missao)
        f_sync.pack(fill="x", padx=5, pady=(3, 0))
        tk.Button(f_sync,
                    text="🔄 Sincronizar saldo (antes de iniciar sessão)",
                    command=self._sincronizar_saldo,
                    font=("Arial", 8), bg="#FFF3E0",
                    activebackground="#FFE0B2",
                    relief="flat", borderwidth=1,
                    cursor="hand2").pack(fill="x")

        # Botão de TESTE REAL do OCR do saldo (feedback imediato)
        tk.Button(f_sync,
                    text="🔍 Testar leitura do saldo agora",
                    command=self._testar_saldo,
                    font=("Arial", 8), bg="#E8F5E9",
                    activebackground="#C8E6C9",
                    relief="flat", borderwidth=1,
                    cursor="hand2").pack(fill="x", pady=(2, 0))

        # Linha 6: botão "Capturar Histórico"
        f_hist = tk.Frame(self.painel_missao)
        f_hist.pack(fill="x", padx=5, pady=(2, 0))
        tk.Button(f_hist,
                    text="📸 Capturar Histórico Expandido (antes de iniciar)",
                    command=self._capturar_historico,
                    font=("Arial", 8), bg="#E3F2FD",
                    activebackground="#BBDEFB",
                    relief="flat", borderwidth=1,
                    cursor="hand2").pack(fill="x")

        # Linha 7: indicador do histórico capturado
        self.lbl_historico_status = tk.Label(self.painel_missao,
                                                text="   Histórico: ainda não capturado",
                                                font=("Arial", 7, "italic"),
                                                foreground="gray", anchor="w")
        self.lbl_historico_status.pack(fill="x", padx=5)

        # ═══ PAINEL DE ESTADO (existente) ═══════════════════════════
        self.painel_estado = tk.LabelFrame(frame, text="📊 Estado", padx=8, pady=5, font=("Arial", 9, "bold"))
        self.painel_estado.pack(fill="x", padx=5, pady=(5, 3))

        self.lbl_banca       = tk.Label(self.painel_estado, text="💰 --", font=("Arial", 9), anchor="w")
        self.lbl_cofre       = tk.Label(self.painel_estado, text="🏦 --", font=("Arial", 9), anchor="w")
        self.lbl_sessao      = tk.Label(self.painel_estado, text="📈 --", font=("Arial", 9), anchor="w")
        self.lbl_roi         = tk.Label(self.painel_estado, text="📊 --", font=("Arial", 9), anchor="w")
        self.lbl_cadeia      = tk.Label(self.painel_estado, text="🔗 --", font=("Arial", 9), anchor="w")
        self.lbl_aposta      = tk.Label(self.painel_estado, text="💵 --", font=("Arial", 9), anchor="w")
        self.lbl_estado_bot  = tk.Label(self.painel_estado, text="🤖 PARADO", font=("Arial", 9, "bold"), foreground="red", anchor="w")
        self.lbl_estrategia  = tk.Label(self.painel_estado, text="📜 --", font=("Arial", 8), foreground="gray", anchor="w")
        self.lbl_ultima_act  = tk.Label(self.painel_estado, text="🕐 --", font=("Arial", 8), foreground="gray", anchor="w")

        self.lbl_banca.grid       (row=0, column=0, sticky="w", padx=5, pady=1)
        self.lbl_cofre.grid       (row=0, column=1, sticky="w", padx=5, pady=1)
        self.lbl_sessao.grid      (row=1, column=0, sticky="w", padx=5, pady=1)
        self.lbl_roi.grid         (row=1, column=1, sticky="w", padx=5, pady=1)
        self.lbl_cadeia.grid      (row=2, column=0, sticky="w", padx=5, pady=1)
        self.lbl_aposta.grid      (row=2, column=1, sticky="w", padx=5, pady=1)
        self.lbl_estado_bot.grid  (row=3, column=0, sticky="w", padx=5, pady=1)
        self.lbl_ultima_act.grid  (row=3, column=1, sticky="w", padx=5, pady=1)
        self.lbl_estrategia.grid  (row=4, column=0, columnspan=2, sticky="w", padx=5, pady=1)

        self.meio = ttk.Frame(frame)
        self.meio.pack(fill="x", padx=5, pady=3)

        self.frame_botoes = tk.LabelFrame(self.meio, text="🎮 Controlo", padx=10, pady=5)
        self.frame_botoes.pack(side="left", padx=(0, 5))

        self.btn_iniciar = tk.Button(self.frame_botoes, text="▶ INICIAR", width=12, height=1,
            font=("Arial", 10, "bold"), bg="#4CAF50", fg="white", activebackground="#45a049",
            command=self._iniciar_bot, cursor="hand2")
        self.btn_iniciar.pack(pady=1)

        self.btn_parar = tk.Button(self.frame_botoes, text="⏹ PARAR", width=12, height=1,
            font=("Arial", 10, "bold"), bg="#f44336", fg="white", activebackground="#da190b",
            command=self._parar_bot, cursor="hand2", state="disabled")
        self.btn_parar.pack(pady=1)

        # ═══ PAINEL TEMPERATURA DA SESSAO (IA Adaptativa v2) ═══════
        self.frame_flags = tk.LabelFrame(self.meio,
                                            text="🌡️ Temperatura (IA Adaptativa)",
                                            padx=10, pady=5,
                                            font=("Arial", 9, "bold"),
                                            fg="#1976D2")
        self.frame_flags.pack(side="left", fill="both", expand=True)

        # Linha 1: classificacao grande
        self.lbl_temp_classificacao = tk.Label(self.frame_flags,
                                                  text="❓ Sem dados",
                                                  font=("Arial", 11, "bold"),
                                                  anchor="w", fg="gray")
        self.lbl_temp_classificacao.pack(anchor="w")

        # Linha 2: detalhe estatistico
        self.lbl_temp_stats = tk.Label(self.frame_flags,
                                          text="Captura o histórico antes de iniciar",
                                          font=("Arial", 8), anchor="w", fg="gray")
        self.lbl_temp_stats.pack(anchor="w")

        # Linha 3: cashout adaptado
        self.lbl_temp_cashout = tk.Label(self.frame_flags,
                                            text="Cashout adaptado: —",
                                            font=("Arial", 8), anchor="w", fg="gray")
        self.lbl_temp_cashout.pack(anchor="w")

        # Linha 4: indicador de OCR Saldo
        self.lbl_ocr_saldo = tk.Label(self.frame_flags,
                                         text="💰 OCR Saldo: ⏳",
                                         font=("Arial", 8), anchor="w", fg="gray")
        self.lbl_ocr_saldo.pack(anchor="w")

        # Manter labels antigas escondidas (compatibilidade com _actualizar_estado)
        self.lbl_flag_hot_cold  = tk.Label(self.frame_flags)
        self.lbl_flag_adaptive  = tk.Label(self.frame_flags)
        self.lbl_flag_preservar = tk.Label(self.frame_flags)
        self.lbl_flag_kelly     = tk.Label(self.frame_flags)
        # NAO faz pack — fica escondido

        self.frame_log = tk.LabelFrame(frame, text="📜 Log", padx=5, pady=3, font=("Arial", 9, "bold"))
        self.frame_log.pack(fill="both", expand=True, padx=5, pady=(3, 5))

        self.txt_log = scrolledtext.ScrolledText(self.frame_log, font=("Consolas", 8),
            bg="#1e1e1e", fg="#d4d4d4", insertbackground="white", wrap=tk.WORD, height=10)
        self.txt_log.pack(fill="both", expand=True)
        self.txt_log.tag_configure("ganhou",    foreground="#4ec9b0")
        self.txt_log.tag_configure("perdeu",    foreground="#f48771")
        self.txt_log.tag_configure("info",      foreground="#569cd6")
        self.txt_log.tag_configure("warn",      foreground="#dcdcaa")
        self.txt_log.tag_configure("dashboard", foreground="#c586c0")
        self.txt_log.tag_configure("repetido",  foreground="#808080")

        self.frame_log_botoes = ttk.Frame(self.frame_log)
        self.frame_log_botoes.pack(fill="x", pady=(3, 0))
        ttk.Button(self.frame_log_botoes, text="🧹 Limpar", command=self._limpar_log).pack(side="right")
        self.lbl_linhas_log = tk.Label(self.frame_log_botoes, text="", font=("Arial", 7), foreground="gray")
        self.lbl_linhas_log.pack(side="left", padx=5)

    def _construir_aba_calibracao(self):
        frame = self.aba_calibracao

        aviso = tk.Label(frame,
            text="💡 Ao calibrar, a janela do bot vai minimizar automaticamente",
            font=("Arial", 9, "italic"), foreground="#1976D2")
        aviso.pack(pady=(10, 5))

        frame_areas = tk.LabelFrame(frame, text="📐 Áreas a Calibrar", padx=10, pady=8)
        frame_areas.pack(fill="x", padx=10, pady=5)

        calibracoes = [
            ("📋 Lista de multiplicadores", "calibrar.calibrar_area_lista"),
            ("🛫 Multiplicador do voo",     "calibrar.calibrar_area_voo"),
            ("🟢 Botão Apostar",            "calibrar.calibrar_area_apostar"),
            ("💸 Botão Cashout",            "calibrar.calibrar_area_cashout"),
            ("💥 Área vermelho final",      "calibrar.calibrar_area_vermelho"),
            ("💵 Valor da aposta",          "calibrar.calibrar_area_valor"),
            ("💰 Saldo do casino",          "calibrar.calibrar_saldo"),
            ("📐 Histórico expandido",      "calibrar.calibrar_historico"),
        ]

        for nome, modulo in calibracoes:
            linha = ttk.Frame(frame_areas)
            linha.pack(fill="x", pady=2)
            tk.Label(linha, text=nome, font=("Arial", 9), anchor="w", width=28).pack(side="left")
            tk.Button(linha, text="Calibrar", font=("Arial", 9),
                bg="#2196F3", fg="white", cursor="hand2", width=10,
                command=lambda m=modulo, n=nome: self._executar_calibracao(m, n)).pack(side="right")

        frame_ferr = tk.LabelFrame(frame, text="🔧 Ferramentas", padx=10, pady=8)
        frame_ferr.pack(fill="x", padx=10, pady=5)

        tk.Button(frame_ferr, text="👁 Ver áreas calibradas",
            font=("Arial", 9), bg="#FFC107", cursor="hand2",
            command=self._mostrar_areas_calibradas).pack(fill="x", pady=2)

        tk.Button(frame_ferr, text="🧹 Limpar dados (banca/cofre/cadeia)",
            font=("Arial", 9), bg="#FF9800", cursor="hand2",
            command=self._limpar_dados).pack(fill="x", pady=2)

        tk.Label(frame,
            text=("💡 Limpar dados apaga banca, cofre e cadeia da sessão.\n"
                  "    NÃO afecta calibrações, histórico nem CSVs de sessões."),
            font=("Arial", 8), foreground="gray", justify="left").pack(pady=10, padx=15, anchor="w")

    def _executar_calibracao(self, modulo, nome):
        if self.bot_a_correr:
            messagebox.showwarning("Bot a correr",
                "Para a bot antes de calibrar!\n\nVai à aba Controlo e clica em PARAR.")
            return

        resposta = messagebox.askyesno("Calibrar área",
            f"Vais calibrar: {nome}\n\n"
            "A janela do bot vai MINIMIZAR.\n"
            "Vai aparecer um cursor em cruz — clica e arrasta sobre a área.\n\n"
            "Pressiona ESC para cancelar.\n\nContinuar?")
        if not resposta:
            return

        self.root.iconify()
        self.root.update()

        thread = threading.Thread(target=self._executar_calibracao_thread,
            args=(modulo, nome), daemon=True)
        thread.start()

    def _executar_calibracao_thread(self, modulo, nome):
        sucesso = False
        erro_msg = None
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"

            kwargs = {
                "capture_output": True, "text": True, "timeout": 120,
                "cwd": os.getcwd(), "env": env,
                "encoding": "utf-8", "errors": "replace",
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = 0x08000000

            resultado = subprocess.run([sys.executable, "-m", modulo], **kwargs)
            if resultado.returncode == 0:
                sucesso = True
            else:
                erro_msg = f"Código de saída: {resultado.returncode}\n"
                if resultado.stderr:
                    erro_msg += f"\nErro:\n{resultado.stderr[:800]}"
        except subprocess.TimeoutExpired:
            erro_msg = "Calibração demorou mais que 2 minutos."
        except Exception as e:
            erro_msg = f"{type(e).__name__}: {e}"

        self.root.after(0, lambda: self._calibracao_terminou(nome, sucesso, erro_msg))

    def _calibracao_terminou(self, nome, sucesso, erro_msg):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        if sucesso:
            messagebox.showinfo("Calibração concluída",
                f"✅ {nome} calibrada com sucesso!")
        else:
            messagebox.showerror("Erro na calibração",
                f"❌ Não foi possível calibrar {nome}.\n\nErro: {erro_msg}")

    def _mostrar_areas_calibradas(self):
        cfg = self._ler_json("config/config.json")
        if not cfg:
            messagebox.showerror("Erro", "Config.json não encontrado.")
            return

        areas = {k: v for k, v in cfg.items() if "area" in k or "regiao" in k}
        if not areas:
            messagebox.showinfo("Áreas", "Nenhuma área calibrada ainda.")
            return

        texto = "📐 ÁREAS CALIBRADAS\n" + "═" * 40 + "\n\n"
        for chave, valor in areas.items():
            if isinstance(valor, list) and len(valor) == 4:
                x, y, w, h = valor
                texto += f"  {chave}\n     X={x}, Y={y}, W={w}, H={h}\n\n"
            else:
                texto += f"  {chave}: {valor}\n\n"

        win = tk.Toplevel(self.root)
        win.title("📐 Áreas Calibradas")
        win.geometry("400x350")
        txt = scrolledtext.ScrolledText(win, font=("Consolas", 9), wrap="word")
        txt.pack(fill="both", expand=True, padx=10, pady=10)
        txt.insert("1.0", texto)
        txt.config(state="disabled")

    def _limpar_dados(self):
        if self.bot_a_correr:
            messagebox.showwarning("Bot a correr", "Para a bot antes de limpar dados!")
            return

        resposta = messagebox.askyesno("Limpar dados",
            "Vais APAGAR:\n  • Banca actual\n  • Cadeia composta\n  • Cofre\n  • Estado de pausa\n\n"
            "NÃO vai apagar calibrações nem histórico.\n\nConfirmas?")
        if not resposta:
            return

        ficheiros = ["data/estado_estrategia.json", "data/estado_aposta_composta.json", "data/estado_banca.json"]
        apagados = 0
        for f in ficheiros:
            p = Path(f)
            if p.exists():
                try:
                    p.unlink()
                    apagados += 1
                except Exception as e:
                    print(f"⚠ Erro ao apagar {f}: {e}")

        messagebox.showinfo("Limpeza", f"✅ {apagados} ficheiros apagados.")

    def _construir_aba_config(self):
        """Aba Config reescrita — design limpo, apenas o essencial."""
        frame = self.aba_config

        # ─── SCROLLABLE CANVAS ────────────────────────────────────────
        canvas    = tk.Canvas(frame, highlightthickness=0, bg="#FAFAFA")
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True, padx=(5, 0))
        scrollbar.pack(side="right", fill="y")

        # Cores tema
        COR_PRIMARIA   = "#1976D2"   # azul
        COR_SUCESSO    = "#2E7D32"   # verde
        COR_AVISO      = "#D32F2F"   # vermelho
        COR_NEUTRO     = "#616161"   # cinza
        COR_DESTAQUE   = "#F57C00"   # laranja

        # ════════════════════════════════════════════════════════════════
        # SECCAO 0 — ESTRATÉGIA ACTIVA (selector único — só UMA actua)
        # ════════════════════════════════════════════════════════════════
        f_estrat = tk.LabelFrame(scrollable, text="  🎯  Estratégia a Usar  ",
                                   padx=12, pady=10,
                                   font=("Arial", 10, "bold"),
                                   fg=COR_PRIMARIA)
        f_estrat.pack(fill="x", padx=8, pady=(8, 6))

        tk.Label(f_estrat,
            text="Escolhe UMA. Só uma estratégia actua de cada vez — "
                 "seleccionar uma desliga automaticamente as outras.",
            font=("Arial", 8), foreground=COR_AVISO,
            wraplength=540, justify="left").pack(anchor="w", pady=(0, 6))

        self.var_estrategia_activa = tk.StringVar(value="rosa")
        _estrategias_radio = [
            ("rosa",    "🌹 Estratégia Rosa — aposta só depois de rosa (≥10x)"),
            ("padroes", "🎯 Follow Patterns — padrões P1-P6 em tempo real"),
            ("dados",   "📊 Dados Simples — estatística do histórico"),
            ("pdf",     "📜 PDF tradicional — estratégia base"),
        ]
        for _valor, _texto in _estrategias_radio:
            tk.Radiobutton(f_estrat, text=_texto,
                             variable=self.var_estrategia_activa, value=_valor,
                             font=("Arial", 9), anchor="w",
                             justify="left").pack(anchor="w", pady=1)

        # ════════════════════════════════════════════════════════════════
        # SECCAO 1 — MISSAO (objectivo da sessao)
        # ════════════════════════════════════════════════════════════════
        f_missao = tk.LabelFrame(scrollable, text="  🎯  Missão  ",
                                   padx=12, pady=10,
                                   font=("Arial", 10, "bold"),
                                   fg=COR_PRIMARIA)
        f_missao.pack(fill="x", padx=8, pady=(8, 6))

        tk.Label(f_missao,
            text="A banca inicial é o SALDO REAL no casino antes de iniciar.",
            font=("Arial", 8), foreground=COR_AVISO,
            justify="left").pack(anchor="w", pady=(0, 6))

        self._criar_campo(f_missao, "banca_inicial",  "Banca inicial",      "10000", "AOA")
        self._criar_campo(f_missao, "objectivo_pct",  "Objectivo de lucro", "100",   "%")
        self._criar_campo(f_missao, "stop_loss_pct",  "Stop loss máximo",   "30",    "%")

        tk.Label(f_missao,
            text="💡 Tens 50000 + obj 100% + stop 30% → pára em +50000 ou −15000.",
            font=("Arial", 8, "italic"), foreground=COR_NEUTRO,
            justify="left").pack(anchor="w", pady=(4, 0))

        # ════════════════════════════════════════════════════════════════
        # SECCAO 2 — APOSTAS (valor base, cadeia composta)
        # ════════════════════════════════════════════════════════════════
        f_apostas = tk.LabelFrame(scrollable, text="  💰  Apostas  ",
                                    padx=12, pady=10,
                                    font=("Arial", 10, "bold"),
                                    fg=COR_PRIMARIA)
        f_apostas.pack(fill="x", padx=8, pady=6)

        self._criar_campo(f_apostas, "aposta_base",         "Aposta base",       "1000", "AOA")
        self._criar_campo(f_apostas, "reset_apos_vitorias", "Reset após",        "3",    "vitórias seguidas")

        tk.Label(f_apostas,
            text="💡 Aposta base ≈ 2% da banca. Cadeia: ganha N seguidas → guarda no cofre.",
            font=("Arial", 8, "italic"), foreground=COR_NEUTRO,
            justify="left").pack(anchor="w", pady=(4, 0))

        # ════════════════════════════════════════════════════════════════
        # SECCAO 2.4 — DEFINIÇÕES DA ESTRATÉGIA ROSA
        # ════════════════════════════════════════════════════════════════
        f_rosa = tk.LabelFrame(scrollable, text="  🌹  Definições da Estratégia Rosa  ",
                                 padx=12, pady=10,
                                 font=("Arial", 10, "bold"),
                                 fg="#C2185B")
        f_rosa.pack(fill="x", padx=8, pady=6)

        tk.Label(f_rosa,
            text="(Para ACTIVAR, escolhe '🌹 Estratégia Rosa' no selector lá em cima.)",
            font=("Arial", 8, "italic"), foreground=COR_NEUTRO,
            justify="left").pack(anchor="w", pady=(0, 4))

        # Campo cashout_rosa
        linha_cr = tk.Frame(f_rosa)
        linha_cr.pack(fill="x", pady=(2, 0))
        tk.Label(linha_cr, text="Cashout alvo", font=("Arial", 9),
                   width=24, anchor="w").pack(side="left")
        self.var_cashout_rosa = tk.StringVar(value="1.90")
        self.vars_config["cashout_rosa"] = self.var_cashout_rosa
        tk.Entry(linha_cr, textvariable=self.var_cashout_rosa,
                   font=("Arial", 9), width=8, justify="center").pack(side="left", padx=5)
        tk.Label(linha_cr, text="x (recomendado 1.80-2.00)",
                   font=("Arial", 8), fg=COR_NEUTRO).pack(side="left")

        tk.Label(f_rosa,
            text="Aposta APENAS depois de um rosa (≥10x). Se vier azul (<2x), "
                 "tenta + 1 vez. Se vier roxo (2-10x), pausa. Se vier rosa de novo, "
                 "continua. Resultados em data/estrategia_rosa.csv.",
            font=("Arial", 8), foreground=COR_NEUTRO,
            wraplength=540, justify="left").pack(anchor="w", pady=(6, 0))

        # ════════════════════════════════════════════════════════════════
        # SECCAO 2.5 — MODO OBSERVADOR (treinamento)
        # ════════════════════════════════════════════════════════════════
        f_obs = tk.LabelFrame(scrollable, text="  🔬  Modo Observador (treinamento)  ",
                                padx=12, pady=10,
                                font=("Arial", 10, "bold"),
                                fg="#7B1FA2")
        f_obs.pack(fill="x", padx=8, pady=6)

        # Checkbox modo_observador
        self.var_modo_observador = tk.BooleanVar(value=True)
        self.vars_config["modo_observador"] = self.var_modo_observador
        tk.Checkbutton(f_obs,
                         text="Activar Modo Observador",
                         variable=self.var_modo_observador,
                         font=("Arial", 9, "bold"),
                         fg="#7B1FA2").pack(anchor="w")

        tk.Label(f_obs,
            text="Quando atinge meta/stop, o bot NÃO fecha — continua a observar "
                 "as fases (quente↔normal↔fria) para aprender as transições do "
                 "jogo. A cada ~4 min faz 1 aposta mínima (65 AOA) para não dar "
                 "inatividade. Os dados vão para data/observacao_fases.csv.",
            font=("Arial", 8), foreground=COR_NEUTRO,
            wraplength=540, justify="left").pack(anchor="w", pady=(4, 0))

        # ════════════════════════════════════════════════════════════════
        # SECCAO 3 — PADRÕES (Follow Patterns — a NOVA gestao)
        # ════════════════════════════════════════════════════════════════
        f_padroes = tk.LabelFrame(scrollable, text="  📐  Padrões (Follow Patterns)  ",
                                     padx=12, pady=10,
                                     font=("Arial", 10, "bold"),
                                     fg=COR_SUCESSO)
        f_padroes.pack(fill="x", padx=8, pady=6)

        tk.Label(f_padroes,
            text="O bot detecta padrões na janela e ajusta o cashout. Desactiva um padrão se não confias nele.",
            font=("Arial", 8), foreground=COR_NEUTRO,
            wraplength=540, justify="left").pack(anchor="w", pady=(0, 8))

        # Inicializar vars dos padroes
        self.vars_padroes = {}

        # Helper para criar linha de padrão
        def _padrao_row(parent, key, titulo, descricao, cor_titulo, campos):
            """
            Cria uma linha colapsável para um padrão.
            campos = [(json_key, label, default, unidade), ...]
            """
            wrap = tk.Frame(parent, bg="white",
                              highlightbackground="#E0E0E0",
                              highlightthickness=1)
            wrap.pack(fill="x", pady=3)

            # Header com checkbox + título
            hdr = tk.Frame(wrap, bg="white")
            hdr.pack(fill="x", padx=8, pady=(6, 2))

            var_activo = tk.BooleanVar(value=True)
            self.vars_padroes[f"{key}_ativo"] = var_activo
            tk.Checkbutton(hdr, variable=var_activo, bg="white",
                              activebackground="white").pack(side="left")

            tk.Label(hdr, text=titulo, font=("Arial", 9, "bold"),
                       fg=cor_titulo, bg="white").pack(side="left", padx=(2, 0))

            # Descricao curta
            tk.Label(wrap, text=descricao, font=("Arial", 8),
                       fg=COR_NEUTRO, bg="white", wraplength=520,
                       justify="left").pack(anchor="w", padx=28, pady=(0, 4))

            # Campos
            for json_key, label, default, unidade in campos:
                linha = tk.Frame(wrap, bg="white")
                linha.pack(fill="x", padx=28, pady=1)
                tk.Label(linha, text=label, font=("Arial", 8),
                           bg="white", width=24, anchor="w").pack(side="left")
                var = tk.StringVar(value=str(default))
                self.vars_padroes[f"{key}_{json_key}"] = var
                tk.Entry(linha, textvariable=var, font=("Arial", 8),
                           width=8, justify="center").pack(side="left", padx=5)
                tk.Label(linha, text=unidade, font=("Arial", 8),
                           fg=COR_NEUTRO, bg="white").pack(side="left")

            tk.Frame(wrap, bg="white", height=4).pack()

        # P1 Pos-mega
        _padrao_row(f_padroes, "p1_pos_mega",
            "❄️ P1 — Pós-mega",
            "Após um mega-crash (≥ limiar x), salta os próximos rounds. Sangria evitada.",
            COR_PRIMARIA,
            [("limiar_mega", "Limiar do mega",  "100", "x"),
             ("rounds_skip", "Rounds a saltar", "3",   "rounds")])

        # P2 6+ azuis
        _padrao_row(f_padroes, "p2_seis_azuis",
            "🔵 P2 — Sequência azul",
            "Após N+ crashes baixos seguidos, aposta para apanhar a regressão.",
            COR_PRIMARIA,
            [("min_azuis_seguidos", "Min. azuis seguidos",  "6",   ""),
             ("cashout_alvo",       "Cashout alvo",         "2.0", "x"),
             ("fraccao_banca",      "Fracção da banca",     "0.5", "(0-1)")])

        # P3 Combo quente
        _padrao_row(f_padroes, "p3_combo_quente",
            "🔥 P3 — Combo quente",
            "Minuto quente + janela quente. Modo jackpot em minutos especiais.",
            COR_DESTAQUE,
            [("min_azuis_recentes",       "Min. azuis recentes",     "5",   ""),
             ("cashout_alvo_normal",      "Cashout normal",          "3.0", "x"),
             ("cashout_alvo_jackpot",     "Cashout jackpot",         "5.0", "x"),
             ("minuto_jackpot",           "Minuto jackpot",          "49",  ""),
             ("fraccao_banca_normal",     "Fracção normal",          "0.3", "(0-1)"),
             ("fraccao_banca_jackpot",    "Fracção jackpot",         "0.2", "(0-1)")])

        # P4 Hot streak
        _padrao_row(f_padroes, "p4_hot_streak",
            "🌶️ P4 — Hot streak",
            "Janela com 2+ rosas em 10 recentes — segue o momentum.",
            COR_DESTAQUE,
            [("min_rosas_em_10", "Min. rosas em 10", "2",   ""),
             ("cashout_alvo",    "Cashout alvo",     "1.5", "x")])

        # P5 Rosa queimada
        _padrao_row(f_padroes, "p5_rosa_queimada",
            "💨 P5 — Rosa queimada",
            "Último crash foi alto (≥ limiar) — cauteloso no seguinte.",
            COR_PRIMARIA,
            [("limiar_rosa_queimada", "Limiar rosa queimada", "5.0", "x"),
             ("cashout_alvo",         "Cashout alvo",         "1.5", "x")])

        # P6 Default
        _padrao_row(f_padroes, "p6_default",
            "✅ P6 — Default",
            "Nenhum padrão especial — comportamento normal (a maioria dos rounds).",
            COR_SUCESSO,
            [("cashout_alvo", "Cashout alvo", "1.5", "x")])

        # Aviso matemático
        tk.Label(f_padroes,
            text="⚠️ Cashout 1.50x precisa de ≥67% WR para break-even. 1.30x precisa de 77%. 1.20x precisa de 83%.",
            font=("Arial", 8, "italic"), foreground=COR_AVISO,
            wraplength=540, justify="left").pack(anchor="w", pady=(8, 0))

        # ════════════════════════════════════════════════════════════════
        # BOTOES
        # ════════════════════════════════════════════════════════════════
        f_botoes = tk.Frame(scrollable)
        f_botoes.pack(fill="x", padx=8, pady=12)

        tk.Button(f_botoes, text="💾  Guardar tudo",
                    font=("Arial", 10, "bold"),
                    bg=COR_SUCESSO, fg="white",
                    activebackground="#1B5E20",
                    cursor="hand2", width=18, height=2,
                    relief="flat", borderwidth=0,
                    command=self._guardar_config_completo).pack(side="left", padx=5)

        tk.Button(f_botoes, text="↺  Recarregar",
                    font=("Arial", 10),
                    bg=COR_NEUTRO, fg="white",
                    activebackground="#424242",
                    cursor="hand2", width=14, height=2,
                    relief="flat", borderwidth=0,
                    command=self._recarregar_tudo).pack(side="left", padx=5)

        # Inicializar com valores do disco
        self._recarregar_tudo()

    def _criar_campo(self, parent, chave, label, default, unidade):
        linha = ttk.Frame(parent)
        linha.pack(fill="x", pady=2)
        tk.Label(linha, text=label, font=("Arial", 9), anchor="w", width=22).pack(side="left")
        var = tk.StringVar(value=default)
        self.vars_config[chave] = var
        tk.Entry(linha, textvariable=var, font=("Arial", 9), width=10).pack(side="left", padx=(5, 5))
        if unidade:
            tk.Label(linha, text=unidade, font=("Arial", 8), foreground="gray").pack(side="left")

    def _criar_checkbox(self, parent, chave, label):
        var = tk.BooleanVar(value=False)
        self.vars_config[chave] = var
        tk.Checkbutton(parent, text=label, variable=var, font=("Arial", 9), anchor="w").pack(anchor="w", pady=1)

    def _recarregar_tudo(self):
        """Recarrega config.json + parametros_padroes.json para os campos da GUI."""
        self._recarregar_config()
        self._recarregar_padroes()

    def _recarregar_padroes(self):
        """Carrega parametros_padroes.json para self.vars_padroes."""
        path = Path("config/parametros_padroes.json")
        if not path.exists():
            return  # usa defaults dos vars
        try:
            with open(path, "r", encoding="utf-8") as f:
                params = json.load(f)
        except Exception as e:
            print(f"⚠️ Erro a carregar parametros_padroes.json: {e}")
            return

        # Para cada padrão, popula os vars
        for padrao_key, padrao_data in params.items():
            if not isinstance(padrao_data, dict):
                continue
            for campo_key, valor in padrao_data.items():
                if campo_key == "descricao":
                    continue
                var_key = f"{padrao_key}_{campo_key}"
                if campo_key == "ativo":
                    var_key = f"{padrao_key}_ativo"
                    if var_key in self.vars_padroes:
                        self.vars_padroes[var_key].set(bool(valor))
                else:
                    if var_key in self.vars_padroes:
                        self.vars_padroes[var_key].set(str(valor))

    def _guardar_config_completo(self):
        """Guarda config.json + parametros_padroes.json em conjunto."""
        ok_cfg     = self._guardar_config_silent()
        ok_padroes = self._guardar_padroes_silent()

        if ok_cfg and ok_padroes:
            messagebox.showinfo(
                "✅ Tudo guardado",
                "Config + parâmetros dos padrões guardados com sucesso.\n\n"
                "As alterações entram em vigor na próxima sessão (INICIAR)."
            )
        elif ok_cfg:
            messagebox.showwarning(
                "⚠️ Guardado parcial",
                "config.json guardado.\n"
                "parametros_padroes.json FALHOU — vê a consola."
            )
        elif ok_padroes:
            messagebox.showwarning(
                "⚠️ Guardado parcial",
                "parametros_padroes.json guardado.\n"
                "config.json FALHOU — vê a consola."
            )
        else:
            messagebox.showerror("❌ Erro", "Nada foi guardado. Vê a consola.")

    def _guardar_config_silent(self) -> bool:
        """Guarda config.json sem dialog. Retorna True/False."""
        path = Path("config/config.json")
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            # ── SELECTOR DE ESTRATÉGIA ÚNICA → 3 booleanos ──────────────
            # Garante exclusividade: escolher uma desliga as outras.
            if hasattr(self, "var_estrategia_activa"):
                escolha = self.var_estrategia_activa.get()
                cfg["usar_estrategia_rosa"]    = (escolha == "rosa")
                cfg["usar_estrategia_padroes"] = (escolha == "padroes")
                cfg["usar_estrategia_dados"]   = (escolha == "dados")

            for chave, var in self.vars_config.items():
                if isinstance(var, tk.BooleanVar):
                    cfg[chave] = var.get()
                else:
                    valor_str = var.get().strip()
                    if not valor_str:
                        continue
                    try:
                        cfg[chave] = float(valor_str) if "." in valor_str else int(valor_str)
                    except ValueError:
                        cfg[chave] = valor_str
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"⚠️ Erro a guardar config.json: {e}")
            return False

    def _guardar_padroes_silent(self) -> bool:
        """Guarda parametros_padroes.json a partir de self.vars_padroes. Retorna True/False."""
        path = Path("config/parametros_padroes.json")
        # Estrutura base com descrições preservadas
        defaults = {
            "p1_pos_mega":      {"descricao": "Após mega-crash, salta os próximos rounds."},
            "p2_seis_azuis":    {"descricao": "Após N+ azuis seguidos, aposta 2x cauteloso."},
            "p3_combo_quente":  {"descricao": "Minuto quente + janela quente. Jackpot em min especiais."},
            "p4_hot_streak":    {"descricao": "2+ rosas em 10 recentes = janela quente, segue."},
            "p5_rosa_queimada": {"descricao": "Último crash alto, cauteloso a seguir."},
            "p6_default":       {"descricao": "Sem padrão especial — comportamento default."},
        }

        try:
            # Se ficheiro existe, carrega para preservar descrições
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    params = json.load(f)
            else:
                params = defaults.copy()

            # Popula a partir das vars
            for var_key, var in self.vars_padroes.items():
                # var_key formato: "p1_pos_mega_ativo" ou "p1_pos_mega_limiar_mega"
                # Encontrar o padrão (prefixo conhecido)
                padrao_key = None
                campo_key = None
                for pk in defaults:
                    if var_key.startswith(pk + "_"):
                        padrao_key = pk
                        campo_key = var_key[len(pk) + 1:]
                        break
                if padrao_key is None:
                    continue

                if padrao_key not in params:
                    params[padrao_key] = defaults[padrao_key].copy()

                if isinstance(var, tk.BooleanVar):
                    params[padrao_key][campo_key] = var.get()
                else:
                    valor_str = var.get().strip()
                    if not valor_str:
                        continue
                    try:
                        params[padrao_key][campo_key] = float(valor_str) if "." in valor_str else int(valor_str)
                    except ValueError:
                        params[padrao_key][campo_key] = valor_str

            os.makedirs(path.parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(params, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"⚠️ Erro a guardar parametros_padroes.json: {e}")
            return False

    def _recarregar_config(self):
        cfg = self._ler_json("config/config.json")
        if not cfg:
            return
        for chave, var in self.vars_config.items():
            if chave in cfg:
                valor = cfg[chave]
                if isinstance(var, tk.BooleanVar):
                    var.set(bool(valor))
                else:
                    var.set(str(valor))

        # Selector de estratégia: determina o activo pela prioridade
        # (Rosa > Patterns > Dados > PDF) a partir dos booleanos do config
        if hasattr(self, "var_estrategia_activa"):
            if cfg.get("usar_estrategia_rosa", False):
                self.var_estrategia_activa.set("rosa")
            elif cfg.get("usar_estrategia_padroes", False):
                self.var_estrategia_activa.set("padroes")
            elif cfg.get("usar_estrategia_dados", False):
                self.var_estrategia_activa.set("dados")
            else:
                self.var_estrategia_activa.set("pdf")

    def _guardar_config(self):
        path = Path("config/config.json")
        if not path.exists():
            messagebox.showerror("Erro", "config.json não encontrado.")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f)

            for chave, var in self.vars_config.items():
                if isinstance(var, tk.BooleanVar):
                    cfg[chave] = var.get()
                elif isinstance(var, tk.StringVar):
                    valor_str = var.get().strip()
                    if chave == "kelly_modo":
                        cfg[chave] = valor_str
                    else:
                        try:
                            if "." in valor_str:
                                cfg[chave] = float(valor_str)
                            else:
                                cfg[chave] = int(valor_str)
                        except ValueError:
                            cfg[chave] = valor_str

            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=4, ensure_ascii=False)

            messagebox.showinfo("Guardado", "✅ Configuração guardada!\nCalibrações preservadas.")
        except Exception as e:
            messagebox.showerror("Erro", f"Falhou a guardar:\n{e}")

    def _construir_aba_relatorios(self):
        frame = self.aba_relatorios

        # Scrollable area (igual à aba Config)
        canvas = tk.Canvas(frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable = ttk.Frame(canvas)

        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True, padx=(5, 0))
        scrollbar.pack(side="right", fill="y")

        # Permite scroll com a roda do rato
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        cabec = tk.Label(scrollable, text="📊 Ferramentas de Análise",
            font=("Arial", 11, "bold"))
        cabec.pack(pady=(15, 5))

        desc = tk.Label(scrollable,
            text="Corre análises sobre os dados acumulados.",
            font=("Arial", 9, "italic"), foreground="gray", justify="center")
        desc.pack(pady=(0, 15))

        botoes_frame = ttk.Frame(scrollable)
        botoes_frame.pack(padx=20, pady=10, fill="x")

        analises = [
            ("🌹 Relatório da Estratégia Rosa (apostas reais)",
             "Desempenho das tuas apostas pós-rosa: win rate, lucro, e se\n"
             "'depois de rosa vem ≥2x' se confirma vs a base rate (~62%).",
             "relatorio_estrategia_rosa.py"),
            ("🌹 Testar Padrão Rosa (dados históricos)",
             "Testa o teu padrão nos 1857 crashes já gravados, com margem de erro.\n"
             "Diz se há sinal real ou se é a base rate a disfarçar-se.",
             "testar_padrao_rosa.py"),
            ("🔬 Analisar Transições de Fase (Modo Observador)",
             "Analisa os dados recolhidos em observação: após uma fase quente,\n"
             "o que vem? Há ciclos previsíveis? Precisa de correr o Modo Observador antes.",
             "analise_transicoes.py"),
            ("🔬 Análise RETROACTIVA de Padrões (sessões antigas)",
             "Simula 'Follow Patterns' sobre as tuas 33 sessões anteriores.\n"
             "Mostra quanto terias ganhado/perdido a mais com cada padrão.",
             "aplicar_padroes_retroactivo.py"),
            ("🎯 Análise de Padrões (Follow Patterns)",
             "Desempenho de cada padrão P1-P6 das sessões com a estratégia activa.\n"
             "Inclui recomendações automáticas de ajuste.",
             "analise_padroes.py"),
            ("🎲 Backtesting",
             "Simula a estratégia sobre o histórico de crashes.",
             "backtesting.py"),
            ("⏰ Análise Temporal",
             "Identifica padrões temporais: minutos quentes, frios.",
             "analise_temporal.py"),
        ]

        for nome, descricao, script in analises:
            f = tk.LabelFrame(botoes_frame, text="", padx=10, pady=5)
            f.pack(fill="x", pady=5)
            tk.Label(f, text=nome, font=("Arial", 10, "bold"), anchor="w").pack(anchor="w")
            tk.Label(f, text=descricao, font=("Arial", 8), foreground="gray",
                     anchor="w", justify="left").pack(anchor="w", pady=(0, 5))
            tk.Button(f, text="▶ Correr análise",
                font=("Arial", 9), bg="#673AB7", fg="white", cursor="hand2",
                command=lambda s=script, n=nome: self._correr_analise(s, n)).pack(anchor="e")

    def _correr_analise(self, script, nome):
        if self.bot_a_correr:
            messagebox.showwarning("Bot a correr", "Para a bot antes de correr análises!")
            return

        if not Path(script).exists():
            messagebox.showerror("Erro", f"Script não encontrado:\n{script}")
            return

        win = tk.Toplevel(self.root)
        win.title(f"📊 {nome}")
        win.geometry("800x600")
        win.transient(self.root)

        header = tk.Frame(win, bg="#1976D2")
        header.pack(fill="x")
        tk.Label(header, text=f"  {nome}",
            font=("Arial", 11, "bold"), bg="#1976D2", fg="white").pack(side="left", padx=10, pady=8)
        lbl_status = tk.Label(header, text="A correr...", font=("Arial", 9), bg="#1976D2", fg="#FFE082")
        lbl_status.pack(side="right", padx=10)

        txt = scrolledtext.ScrolledText(win, font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4", wrap="word")
        txt.pack(fill="both", expand=True, padx=5, pady=5)

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", pady=5)
        tk.Button(btn_frame, text="📋 Copiar tudo",
            command=lambda: self._copiar_para_clipboard(txt.get("1.0", tk.END))).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✖ Fechar", command=win.destroy).pack(side="right", padx=5)

        thread = threading.Thread(
            target=self._correr_analise_thread,
            args=(script, txt, lbl_status, win),
            daemon=True)
        thread.start()

    def _correr_analise_thread(self, script, txt_widget, lbl_status, win):
        try:
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"

            kwargs = {
                "capture_output": True, "text": True, "timeout": 300,
                "cwd": os.getcwd(), "env": env,
                "encoding": "utf-8", "errors": "replace",
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = 0x08000000

            resultado = subprocess.run([sys.executable, script], **kwargs)
            output = resultado.stdout or ""
            if resultado.stderr:
                output += "\n\n--- ERROS ---\n" + resultado.stderr

            self.root.after(0, lambda: self._mostrar_resultado_analise(
                txt_widget, lbl_status, output, resultado.returncode == 0))
        except Exception as e:
            self.root.after(0, lambda: self._mostrar_resultado_analise(
                txt_widget, lbl_status, f"Erro: {e}", False))

    def _mostrar_resultado_analise(self, txt_widget, lbl_status, output, sucesso):
        try:
            txt_widget.insert("1.0", output)
            if sucesso:
                lbl_status.config(text="✅ Concluído", fg="#4ec9b0")
            else:
                lbl_status.config(text="❌ Erro", fg="#f48771")
        except Exception:
            pass

    def _copiar_para_clipboard(self, texto):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(texto)
            self.root.update()
            messagebox.showinfo("Copiado", "✅ Conteúdo copiado para o clipboard.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível copiar:\n{e}")

    def _construir_aba_historico(self):
        frame = self.aba_historico

        topo = ttk.Frame(frame)
        topo.pack(fill="x", padx=5, pady=5)

        tk.Label(topo, text="Filtro:", font=("Arial", 9, "bold")).pack(side="left", padx=(0, 5))

        self.var_filtro_historico = tk.StringVar(value="todas")
        filtros = [("Hoje", "hoje"), ("Semana", "semana"), ("Mês", "mes"), ("Todas", "todas")]
        for nome, valor in filtros:
            tk.Radiobutton(topo, text=nome, variable=self.var_filtro_historico,
                          value=valor, font=("Arial", 9),
                          command=self._actualizar_lista_sessoes).pack(side="left", padx=2)

        tk.Button(topo, text="🔄", font=("Arial", 9), cursor="hand2",
            command=self._actualizar_lista_sessoes).pack(side="right", padx=5)

        lista_frame = tk.LabelFrame(frame, text="Sessões", padx=5, pady=5)
        lista_frame.pack(fill="both", expand=True, padx=5, pady=5)

        cols = ("data", "w", "l", "wr", "lucro", "ficheiro")
        self.tree_sessoes = ttk.Treeview(lista_frame, columns=cols, show="headings", height=10)

        self.tree_sessoes.heading("data",     text="Data / Hora")
        self.tree_sessoes.heading("w",        text="W")
        self.tree_sessoes.heading("l",        text="L")
        self.tree_sessoes.heading("wr",       text="WR %")
        self.tree_sessoes.heading("lucro",    text="Lucro AOA")
        self.tree_sessoes.heading("ficheiro", text="")

        self.tree_sessoes.column("data",     width=130, anchor="w")
        self.tree_sessoes.column("w",        width=40,  anchor="center")
        self.tree_sessoes.column("l",        width=40,  anchor="center")
        self.tree_sessoes.column("wr",       width=55,  anchor="center")
        self.tree_sessoes.column("lucro",    width=80,  anchor="e")
        self.tree_sessoes.column("ficheiro", width=0,   stretch=False)

        scrollbar_tree = ttk.Scrollbar(lista_frame, orient="vertical", command=self.tree_sessoes.yview)
        self.tree_sessoes.configure(yscrollcommand=scrollbar_tree.set)
        self.tree_sessoes.pack(side="left", fill="both", expand=True)
        scrollbar_tree.pack(side="right", fill="y")

        self.tree_sessoes.bind("<Double-Button-1>", self._abrir_detalhe_sessao)

        self.lbl_resumo_historico = tk.Label(frame, text="", font=("Arial", 9, "italic"),
                                              foreground="gray")
        self.lbl_resumo_historico.pack(pady=5)

        tk.Button(frame, text="🔍 Ver detalhe da sessão seleccionada",
            font=("Arial", 9), bg="#03A9F4", fg="white", cursor="hand2",
            command=lambda: self._abrir_detalhe_sessao(None)).pack(pady=5)

        self._actualizar_lista_sessoes()

    def _actualizar_lista_sessoes(self):
        for item in self.tree_sessoes.get_children():
            self.tree_sessoes.delete(item)

        pasta = Path("data")
        if not pasta.exists():
            self.lbl_resumo_historico.config(text="Pasta 'data' não existe.")
            return

        ficheiros = sorted(pasta.glob("sessao_*.csv"), reverse=True)
        if not ficheiros:
            self.lbl_resumo_historico.config(text="Nenhuma sessão encontrada.")
            return

        agora = datetime.now()
        filtro = self.var_filtro_historico.get()
        if filtro == "hoje":
            cutoff = agora.replace(hour=0, minute=0, second=0, microsecond=0)
        elif filtro == "semana":
            cutoff = agora - timedelta(days=7)
        elif filtro == "mes":
            cutoff = agora - timedelta(days=30)
        else:
            cutoff = None

        total_w = total_l = 0
        total_lucro = 0.0
        n_sessoes = 0

        for ficheiro in ficheiros:
            nome = ficheiro.stem
            partes = nome.split("_")
            if len(partes) < 3:
                continue

            try:
                data_sessao = datetime.strptime(f"{partes[1]} {partes[2]}", "%Y-%m-%d %H-%M")
            except ValueError:
                continue

            if cutoff and data_sessao < cutoff:
                continue

            w, l, lucro = self._calcular_estatisticas_csv(ficheiro)
            wr = (w / (w + l) * 100) if (w + l) > 0 else 0

            data_display = data_sessao.strftime("%Y-%m-%d %H:%M")
            cor_tag = "ganhou" if lucro > 0 else ("perdeu" if lucro < 0 else "neutro")
            sinal = "+" if lucro >= 0 else ""

            self.tree_sessoes.insert("", "end", values=(
                data_display, w, l, f"{wr:.0f}%",
                f"{sinal}{lucro:.0f}", str(ficheiro)
            ), tags=(cor_tag,))

            total_w += w
            total_l += l
            total_lucro += lucro
            n_sessoes += 1

        self.tree_sessoes.tag_configure("ganhou", foreground="#2E7D32")
        self.tree_sessoes.tag_configure("perdeu", foreground="#C62828")
        self.tree_sessoes.tag_configure("neutro", foreground="gray")

        if n_sessoes > 0:
            wr_total = (total_w / (total_w + total_l) * 100) if (total_w + total_l) > 0 else 0
            sinal = "+" if total_lucro >= 0 else ""
            self.lbl_resumo_historico.config(
                text=f"{n_sessoes} sessões | {total_w}W / {total_l}L "
                     f"({wr_total:.0f}%) | Lucro total: {sinal}{total_lucro:.0f} AOA"
            )
        else:
            self.lbl_resumo_historico.config(text="Nenhuma sessão no período seleccionado.")

    def _calcular_estatisticas_csv(self, caminho):
        w = l = 0
        lucro = 0.0
        try:
            with open(caminho, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for linha in reader:
                    resultado = linha.get("resultado", "")
                    try:
                        l_aposta = float(linha.get("lucro_aposta", "0") or 0)
                    except ValueError:
                        l_aposta = 0
                    if resultado == "ganhou":
                        w += 1
                        lucro += l_aposta
                    elif resultado == "perdeu":
                        l += 1
                        lucro += l_aposta
        except Exception:
            pass
        return w, l, lucro

    def _abrir_detalhe_sessao(self, event):
        seleccao = self.tree_sessoes.selection()
        if not seleccao:
            messagebox.showinfo("Detalhe", "Selecciona uma sessão na lista primeiro.")
            return

        valores = self.tree_sessoes.item(seleccao[0], "values")
        data, w, l, wr, lucro, ficheiro = valores

        try:
            with open(ficheiro, "r", encoding="utf-8") as f:
                conteudo = f.read()
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível ler:\n{e}")
            return

        win = tk.Toplevel(self.root)
        win.title(f"📁 Sessão {data}")
        win.geometry("750x550")

        header = tk.Frame(win, bg="#1976D2")
        header.pack(fill="x")
        tk.Label(header, text=f"  Sessão {data}",
            font=("Arial", 11, "bold"), bg="#1976D2", fg="white").pack(side="left", padx=10, pady=8)
        tk.Label(header, text=f"{w}W / {l}L ({wr}) | Lucro: {lucro}",
            font=("Arial", 9), bg="#1976D2", fg="white").pack(side="right", padx=10)

        try:
            linhas = list(csv.DictReader(conteudo.splitlines()))
            if linhas:
                colunas = list(linhas[0].keys())
                tree_frame = ttk.Frame(win)
                tree_frame.pack(fill="both", expand=True, padx=5, pady=5)

                tree = ttk.Treeview(tree_frame, columns=colunas, show="headings", height=15)
                for col in colunas:
                    tree.heading(col, text=col)
                    tree.column(col, width=80, anchor="center")

                scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
                scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
                tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

                tree.grid(row=0, column=0, sticky="nsew")
                scrollbar_y.grid(row=0, column=1, sticky="ns")
                scrollbar_x.grid(row=1, column=0, sticky="ew")
                tree_frame.grid_rowconfigure(0, weight=1)
                tree_frame.grid_columnconfigure(0, weight=1)

                for linha in linhas:
                    resultado = linha.get("resultado", "")
                    cor_tag = "ganhou" if resultado == "ganhou" else ("perdeu" if resultado == "perdeu" else "")
                    tree.insert("", "end", values=[linha.get(c, "") for c in colunas], tags=(cor_tag,))

                tree.tag_configure("ganhou", foreground="#2E7D32")
                tree.tag_configure("perdeu", foreground="#C62828")
        except Exception:
            txt = scrolledtext.ScrolledText(win, font=("Consolas", 8), wrap="none")
            txt.pack(fill="both", expand=True, padx=5, pady=5)
            txt.insert("1.0", conteudo)
            txt.config(state="disabled")

        btn_frame = tk.Frame(win)
        btn_frame.pack(fill="x", pady=5)
        tk.Button(btn_frame, text="📋 Copiar CSV completo",
            command=lambda: self._copiar_para_clipboard(conteudo)).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✖ Fechar", command=win.destroy).pack(side="right", padx=5)

    def _aplicar_estilo(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TNotebook.Tab", padding=[8, 3], font=("Arial", 9))

    def _toggle_sempre_topo(self):
        self.sempre_no_topo = not self.sempre_no_topo
        self.root.attributes("-topmost", self.sempre_no_topo)
        if self.sempre_no_topo:
            self.btn_topo.config(text="📌 No topo ✓", bg="#FFE082")
        else:
            self.btn_topo.config(text="📌 Sempre no topo", bg="SystemButtonFace")

    def _toggle_compactar(self):
        self.modo_compacto = not self.modo_compacto
        if self.modo_compacto:
            self.frame_log.pack_forget()
            self.frame_flags.pack_forget()
            self.btn_compactar.config(text="📐 Expandir", bg="#FFE082")
            self.root.geometry("400x250")
        else:
            self.frame_flags.pack(side="left", fill="both", expand=True)
            self.frame_log.pack(fill="both", expand=True, padx=5, pady=(3, 5))
            self.btn_compactar.config(text="📐 Compactar", bg="SystemButtonFace")
            self.root.geometry("580x620")

    def _iniciar_bot(self):
        if self.bot_a_correr:
            return

        # ─── AVISO de lucro residual da sessão anterior ──────────────
        try:
            banca_data = self._ler_json("data/estado_banca.json") or {}
            lucro_residual = float(banca_data.get("lucro", 0))
            if abs(lucro_residual) > 50:  # mais de 50 AOA é significativo
                resposta = messagebox.askyesnocancel(
                    "⚠️ Lucro residual detectado",
                    f"O bot vai começar com {lucro_residual:+.0f} AOA de lucro "
                    f"residual da sessão anterior.\n\n"
                    f"Isto vai DESCOLAR a contabilidade do saldo real.\n\n"
                    f"Recomendado:\n"
                    f"   • Carrega 🔄 Sincronizar saldo PRIMEIRO\n"
                    f"   • Insere o saldo actual do casino\n"
                    f"   • Depois inicia\n\n"
                    f"Continuar mesmo assim?"
                )
                if resposta is None or resposta is False:
                    return
        except Exception:
            pass  # se falhar, continua normal

        sys.stdout = RedireccionadorTexto(self.fila_logs, self.stdout_original)
        sys.stderr = RedireccionadorTexto(self.fila_logs, self.stderr_original)
        self.bot_a_correr = True
        self.btn_iniciar.config(state="disabled")
        self.btn_parar.config(state="normal")
        self.lbl_estado_bot.config(text="🤖 A CORRER", foreground="#4CAF50")
        self.bot_thread = threading.Thread(target=self._executar_bot, daemon=True)
        self.bot_thread.start()
        self._adicionar_log_directo("\n" + "═" * 50 + "\n", "info")
        self._adicionar_log_directo(f"▶ Bot iniciado às {datetime.now():%H:%M:%S}\n", "info")
        self._adicionar_log_directo("═" * 50 + "\n\n", "info")

    def _executar_bot(self):
        try:
            from core.core import iniciar_robo_autonomo
            iniciar_robo_autonomo()
        except Exception as e:
            try:
                self.fila_logs.put_nowait(f"\n❌ Erro fatal: {e}\n")
            except queue.Full:
                pass
        finally:
            self.bot_a_correr = False
            self.root.after(0, self._ao_terminar_bot)

    def _parar_bot(self):
        if not self.bot_a_correr:
            return
        try:
            from utils.stop_graceful import pedir_paragem
            pedir_paragem()
            self._adicionar_log_directo("\n⏸ Paragem pedida — bot vai parar após este round.\n", "warn")
        except Exception as e:
            self._adicionar_log_directo(f"\n⚠ Erro ao parar: {e}\n", "warn")

    def _ao_terminar_bot(self):
        self.bot_a_correr = False
        self.btn_iniciar.config(state="normal")
        self.btn_parar.config(state="disabled")
        self.lbl_estado_bot.config(text="🤖 PARADO", foreground="red")
        self._adicionar_log_directo("\n" + "═" * 50 + "\n", "info")
        self._adicionar_log_directo("⏹ Bot terminado.\n", "info")
        self._adicionar_log_directo("═" * 50 + "\n\n", "info")
        sys.stdout = self.stdout_original
        sys.stderr = self.stderr_original
        try:
            self._actualizar_lista_sessoes()
        except Exception:
            pass

    def _limpar_log(self):
        self.txt_log.delete("1.0", tk.END)
        self.ultima_msg = None
        self.contador_repetidos = 0

    def _processar_fila_logs(self):
        processadas = 0
        try:
            while processadas < MAX_BATCH:
                msg = self.fila_logs.get_nowait()
                tag = self._classificar_msg(msg)
                self._adicionar_log_com_agrupamento(msg, tag)
                processadas += 1
        except queue.Empty:
            pass

        self._cortar_texto_se_grande()
        self.root.after(100, self._processar_fila_logs)

    def _cortar_texto_se_grande(self):
        try:
            total = int(self.txt_log.index("end-1c").split(".")[0])
            if total > MAX_LINHAS_TEXTO:
                self.txt_log.delete("1.0", f"{LINHAS_PARA_CORTAR}.0")
                self.txt_log.insert("1.0", f"[... {LINHAS_PARA_CORTAR} linhas antigas removidas ...]\n", "repetido")
                self.ultima_msg = None
                self.contador_repetidos = 0
                self.ultimo_index_repetido = None
                total = int(self.txt_log.index("end-1c").split(".")[0])
            self.lbl_linhas_log.config(text=f"{total} linhas")
        except Exception:
            pass

    def _adicionar_log_com_agrupamento(self, texto, tag):
        texto_limpo = texto.strip()

        if texto_limpo and texto_limpo == self.ultima_msg and self.ultimo_index_repetido is not None:
            self.contador_repetidos += 1
            try:
                inicio_linha = f"{self.ultimo_index_repetido}.0"
                fim_linha = f"{self.ultimo_index_repetido}.end"
                self.txt_log.delete(inicio_linha, fim_linha)
                self.txt_log.insert(inicio_linha, f"{texto_limpo} (×{self.contador_repetidos})", tag)
                self.txt_log.see(tk.END)
            except Exception:
                self.ultima_msg = None
                self.contador_repetidos = 0
                self._adicionar_log_directo(texto, tag)
        else:
            self.contador_repetidos = 1
            self.ultima_msg = texto_limpo if texto_limpo else None
            self._adicionar_log_directo(texto, tag)
            try:
                idx = self.txt_log.index("end-1c").split(".")[0]
                self.ultimo_index_repetido = int(idx) - 1
            except Exception:
                self.ultimo_index_repetido = None

    def _adicionar_log_directo(self, texto, tag="info"):
        try:
            self.txt_log.insert(tk.END, texto, tag)
            self.txt_log.see(tk.END)
        except Exception:
            pass

    def _classificar_msg(self, msg):
        m = msg.lower()
        if "ganhou" in m or "vitória" in m or "💰" in msg or "cofre" in m:
            return "ganhou"
        if "perdeu" in m or "💥" in msg or "❌" in msg:
            return "perdeu"
        if "⚠" in msg or "warning" in m:
            return "warn"
        if "═══" in msg or "round " in m:
            return "dashboard"
        return "info"

    def _capturar_historico(self):
        """
        Captura o histórico expandido via OCR.
        O utilizador deve abrir o popup do histórico ANTES de clicar.
        """
        if self.bot_a_correr:
            messagebox.showwarning(
                "Bot a correr",
                "Pára o bot antes de capturar o histórico!"
            )
            return

        # Verifica se area_historico está calibrada
        cfg = self._ler_json("config/config.json") or {}
        if not cfg.get("area_historico"):
            messagebox.showerror(
                "Área não calibrada",
                "A área do histórico ainda não está calibrada.\n\n"
                "Vai à aba Calibração e calibra '📐 Histórico expandido' primeiro."
            )
            return

        # Confirma com o user que o popup está aberto
        resposta = messagebox.askokcancel(
            "📸 Capturar histórico",
            "Antes de continuar, abre o popup de Histórico no Aviator\n"
            "(ícone com os multiplicadores recentes — 5-6 linhas).\n\n"
            "Quando o popup estiver visível, clica OK para capturar.\n"
            "Depois fecha o popup e clica INICIAR."
        )
        if not resposta:
            return

        # Faz a captura via OCR
        try:
            from ocr.leitura_historico import ler_historico, estatisticas_historico
            crashes = ler_historico(cfg["area_historico"], debug=False)
        except Exception as e:
            messagebox.showerror("Erro OCR",
                                   f"Falhou a ler histórico:\n{e}")
            return

        if not crashes:
            messagebox.showerror(
                "❌ Nada detectado",
                "OCR não detectou nenhum crash.\n\n"
                "Verifica:\n"
                "  • O popup do histórico está aberto?\n"
                "  • A calibração da área está correcta?\n"
                "  • Recalibra se necessário."
            )
            return

        # Calcula estatísticas
        stats = estatisticas_historico(crashes)

        # Guarda em disco para o core.py usar
        try:
            import json
            from pathlib import Path
            path = Path("data/historico_inicial.json")
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "crashes":      crashes,
                    "estatisticas": stats,
                    "capturado_em": datetime.now().isoformat(timespec="seconds"),
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Erro a guardar", str(e))
            return

        # Actualiza indicador
        cls = stats["classificacao"]
        emoji_cls = {"fria": "❄️", "normal": "🟡", "quente": "🔥",
                       "sem_dados": "❓"}.get(cls, "🟡")
        self.lbl_historico_status.config(
            text=f"   Histórico: ✅ {len(crashes)} crashes capturados — {emoji_cls} {cls.upper()}",
            foreground="#2E7D32"
        )

        # Resumo no popup
        messagebox.showinfo(
            "✅ Histórico capturado",
            f"📊 {len(crashes)} crashes detectados\n\n"
            f"   Azuis (<2x):    {stats['azuis']:>3} ({stats['pct_azuis']:.1f}%)\n"
            f"   Rosas (≥10x):   {stats['rosas']:>3} ({stats['pct_rosas']:.1f}%)\n"
            f"   Megas (≥100x):  {stats['megas']:>3} ({stats['pct_megas']:.1f}%)\n"
            f"   Mediana:        {stats['crash_mediano']:.2f}x\n"
            f"   Quantil 67%:    {stats['quantil_67']:.2f}x\n"
            f"   Max visto:      {stats['max_visto']:.1f}x\n\n"
            f"Classificação: {emoji_cls} {cls.upper()}\n\n"
            f"Já podes fechar o popup do histórico e clicar INICIAR."
        )

    def _sincronizar_saldo(self):
        """
        Pede ao utilizador o saldo REAL actual do casino e:
          1. Actualiza 'banca_inicial' no config para esse valor
          2. Reseta lucro/ganhos/perdas em memória e disco
          3. (Não toca no cofre — esse é lucro já protegido de sessões anteriores)
        """
        # Não pode sincronizar com bot a correr
        if self.bot_a_correr:
            messagebox.showwarning(
                "Bot a correr",
                "Pára o bot antes de sincronizar o saldo!\n\n"
                "Sincronizar reseta o lucro acumulado para zero, "
                "o que ia partir os cálculos a meio."
            )
            return

        # Lê valor actual para mostrar no dialog
        cfg = self._ler_json("config/config.json") or {}
        banca_data = self._ler_json("data/estado_banca.json") or {}
        banca_actual_cfg = float(cfg.get("banca_inicial",
                                           cfg.get("saldo_inicial", 10000)))
        lucro_actual = float(banca_data.get("lucro", 0))

        # Pede o novo valor (com sugestão = banca_inicial + lucro acumulado)
        sugestao = banca_actual_cfg + lucro_actual
        novo_saldo = simpledialog.askfloat(
            "Sincronizar saldo",
            f"Banca inicial actual no config: {banca_actual_cfg:.0f} AOA\n"
            f"Lucro acumulado registado:      {lucro_actual:+.0f} AOA\n"
            f"Soma teórica:                   {sugestao:.0f} AOA\n"
            "\n"
            "Qual é o saldo REAL no casino agora?\n"
            "(Olha no canto superior do Aviator, ex: 46243)",
            initialvalue=sugestao,
            minvalue=0.0,
            parent=self.root,
        )

        if novo_saldo is None:
            return  # cancelou

        if novo_saldo <= 0:
            messagebox.showerror("Valor inválido",
                                   "O saldo tem de ser maior que zero.")
            return

        # Confirma — vamos resetar o lucro
        confirma = messagebox.askyesno(
            "Confirmar sincronização",
            f"Vou actualizar:\n\n"
            f"   • Banca inicial:  {banca_actual_cfg:.0f}  →  {novo_saldo:.0f} AOA\n"
            f"   • Lucro/ganhos/perdas: serão RESETADOS para zero\n"
            f"   • Cofre: NÃO mexe (lucro já protegido)\n"
            f"\n"
            f"A partir daqui, a missão calcula com base em {novo_saldo:.0f} AOA "
            f"de banca inicial.\n\n"
            f"Continuar?"
        )

        if not confirma:
            return

        # 1) Actualiza config.json
        try:
            from pathlib import Path
            path = Path("config/config.json")
            with open(path, "r", encoding="utf-8") as f:
                cfg_full = json.load(f)
            cfg_full["banca_inicial"] = float(novo_saldo)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg_full, f, indent=4, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Erro",
                                   f"Falhou a actualizar config.json:\n{e}")
            return

        # 2) Reseta o estado da banca em memória e disco
        try:
            # Apaga o ficheiro — banca.py vai recarregar com defaults na próxima sessão
            from pathlib import Path
            estado_path = Path("data/estado_banca.json")
            if estado_path.exists():
                estado_path.unlink()
        except Exception as e:
            messagebox.showerror("Erro",
                                   f"Falhou a resetar estado da banca:\n{e}")
            return

        # 3) Actualiza o campo na GUI (aba Config) se estiver visível
        if "banca_inicial" in self.vars_config:
            self.vars_config["banca_inicial"].set(str(novo_saldo))

        # 4) Refresca o painel da Missão imediatamente
        self._actualizar_missao()

        messagebox.showinfo(
            "✅ Saldo sincronizado",
            f"Banca inicial: {novo_saldo:.0f} AOA\n"
            f"Lucro: 0 AOA\n"
            f"\n"
            f"Já podes iniciar a sessão!"
        )

    def _actualizar_missao(self):
        """Actualiza o painel da Missão (banca inicial, objectivo, stop loss)."""
        try:
            cfg = self._ler_json("config/config.json") or {}
            banca_data = self._ler_json("data/estado_banca.json") or {}

            banca_inicial = float(cfg.get("banca_inicial",
                                            cfg.get("saldo_inicial", 10000)))
            objectivo_pct = float(cfg.get("objectivo_pct", 100))
            stop_loss_pct = float(cfg.get("stop_loss_pct", 30))

            lucro_actual = float(banca_data.get("lucro", 0))
            lucro_alvo   = banca_inicial * (objectivo_pct / 100)
            perda_max    = banca_inicial * (stop_loss_pct / 100)

            banca_actual = banca_inicial + lucro_actual
            banca_alvo   = banca_inicial + lucro_alvo
            banca_stop   = banca_inicial - perda_max

            if lucro_alvo > 0:
                progresso = min(100, max(0, (lucro_actual / lucro_alvo) * 100))
            else:
                progresso = 0

            dist_stop = perda_max + lucro_actual

            # Determina estado/cor
            if lucro_actual >= lucro_alvo:
                cor_barra, cor_status = "#4CAF50", "#4CAF50"
                emoji = "🏆"
                status_txt = f"OBJECTIVO ATINGIDO! {progresso:.0f}%"
            elif lucro_actual <= -perda_max:
                cor_barra, cor_status = "#f44336", "#f44336"
                emoji = "🛡️"
                status_txt = f"STOP LOSS atingido"
            elif dist_stop < perda_max * 0.25:
                cor_barra, cor_status = "#FF9800", "#FF9800"
                emoji = "⚠️"
                status_txt = f"Zona de perigo — perto do stop"
            elif lucro_actual >= 0:
                cor_barra, cor_status = "#4CAF50", "#4CAF50"
                emoji = "🟢"
                status_txt = f"Em rota — progresso {progresso:.0f}%"
            else:
                cor_barra, cor_status = "#FFA726", "#666"
                emoji = "🟡"
                status_txt = f"A recuperar — lucro {lucro_actual:.0f} AOA"

            # Descrição: banca inicial → banca alvo
            self.lbl_missao_desc.config(
                text=f"{emoji} {banca_inicial:.0f} → {banca_alvo:.0f} AOA "
                     f"(meta +{objectivo_pct:.0f}%)",
                foreground=cor_status,
            )

            # Barra de progresso (estilo customizado para cor)
            try:
                style = ttk.Style()
                style.configure("Missao.Horizontal.TProgressbar",
                                  background=cor_barra)
                self.progresso_missao.config(style="Missao.Horizontal.TProgressbar")
            except Exception:
                pass
            self.progresso_missao["value"] = progresso

            # Status linha
            sinal_lucro = "+" if lucro_actual >= 0 else ""
            self.lbl_missao_status.config(
                text=f"   {status_txt}  |  Banca actual: {banca_actual:.0f} "
                     f"({sinal_lucro}{lucro_actual:.0f} AOA)",
                foreground=cor_status,
            )

            # Stop loss linha
            cor_stop = "#f44336" if dist_stop < perda_max * 0.25 else "gray"
            self.lbl_missao_stop.config(
                text=f"   🛡️ Stop em {banca_stop:.0f} AOA "
                     f"(-{stop_loss_pct:.0f}%) — distância: {dist_stop:.0f} AOA",
                foreground=cor_stop,
            )

        except Exception as e:
            self.lbl_missao_desc.config(text=f"⚠️ Missão: erro a calcular ({e})",
                                          foreground="gray")

    def _actualizar_temperatura(self):
        """Actualiza o painel da Temperatura da Sessao (IA Adaptativa v2)."""
        try:
            from pathlib import Path
            import json

            # 1. Prioridade: temperatura DINAMICA (recalculada durante a sessao)
            #    Fallback: temperatura do historico inicial (estatica)
            stats = None
            fonte_dinamica = False
            atualizado_em = None

            path_dyn = Path("data/temperatura_atual.json")
            path_hist = Path("data/historico_inicial.json")

            if path_dyn.exists():
                try:
                    with open(path_dyn, encoding="utf-8") as f:
                        dyn_data = json.load(f)
                    stats = dyn_data.get("estatisticas")
                    atualizado_em = dyn_data.get("atualizado_em", "")
                    fonte_dinamica = True
                except Exception:
                    stats = None

            if stats is None and path_hist.exists():
                with open(path_hist, encoding="utf-8") as f:
                    hist_data = json.load(f)
                stats = hist_data.get("estatisticas", {})

            if stats:
                cls = stats.get("classificacao", "sem_dados")
                pct_rosas = stats.get("pct_rosas", 0)
                q67 = stats.get("quantil_67", 0)
                mediana = stats.get("crash_mediano", 0)
                total = stats.get("total", 0)

                emoji_cls = {"fria": "❄️", "normal": "🟡", "quente": "🔥",
                              "sem_dados": "❓"}.get(cls, "❓")
                cor_cls = {"fria": "#1976D2", "normal": "#FF9800",
                            "quente": "#D32F2F", "sem_dados": "gray"}.get(cls, "gray")

                # Indicador de fonte: 🔄 dinamica vs 📸 inicial
                tag_fonte = "🔄 ao vivo" if fonte_dinamica else "📸 inicial"

                self.lbl_temp_classificacao.config(
                    text=f"{emoji_cls} Sessão {cls.upper()}  ({tag_fonte})",
                    foreground=cor_cls)
                self.lbl_temp_stats.config(
                    text=f"{total} crashes | {pct_rosas:.1f}% rosas | mediana {mediana:.2f}x | q67 {q67:.2f}x",
                    foreground="black")

                try:
                    from ocr.leitura_historico import cashout_recomendado_da_temperatura
                    cashout_adapt, motivo = cashout_recomendado_da_temperatura(stats, 1.5)
                    self.lbl_temp_cashout.config(
                        text=f"🎯 Cashout P6 adaptado: {cashout_adapt:.2f}x",
                        foreground=cor_cls)
                except Exception:
                    self.lbl_temp_cashout.config(text="Cashout adaptado: —",
                                                   foreground="gray")
            else:
                self.lbl_temp_classificacao.config(text="❓ Sem dados",
                                                     foreground="gray")
                self.lbl_temp_stats.config(
                    text="Clica '📸 Capturar Histórico' antes de iniciar",
                    foreground="gray")
                self.lbl_temp_cashout.config(text="Cashout adaptado: —",
                                                foreground="gray")

            # 2. Indicador de OCR Saldo (honesto: área definida ≠ OCR a funcionar)
            cfg = self._ler_json("config/config.json") or {}
            if cfg.get("area_saldo"):
                self.lbl_ocr_saldo.config(
                    text="💰 OCR Saldo: 📐 área definida (usa 🔍 Testar p/ confirmar)",
                    foreground="#F57C00")
            else:
                self.lbl_ocr_saldo.config(text="💰 OCR Saldo: ⚠️ não calibrado",
                                            foreground="#D32F2F")
        except Exception:
            pass

    def _actualizar_estado(self):
        try:
            # ═══ MISSAO ═══════════════════════════════════════════════
            self._actualizar_missao()

            # ═══ TEMPERATURA (IA Adaptativa v2) ═══════════════════════
            self._actualizar_temperatura()

            banca = self._ler_json("data/estado_banca.json")
            if banca:
                lucro = banca.get("lucro", 0)
                cor = "#4CAF50" if lucro >= 0 else "#f44336"
                sinal = "+" if lucro >= 0 else ""
                self.lbl_banca.config(text=f"💰 {sinal}{lucro:.0f}", foreground=cor)
            else:
                self.lbl_banca.config(text="💰 0 AOA", foreground="black")

            cofre_data = self._ler_json("data/estado_aposta_composta.json")
            if cofre_data:
                cofre = cofre_data.get("lucro_cofre", 0)
                # Aceita "valor_atual" (chave real do gestor) e "valor_actual" (legado)
                aposta = cofre_data.get("valor_atual",
                                         cofre_data.get("valor_actual", 0))
                vit_seg = cofre_data.get("vitorias_seguidas", 0)
                reset_apos = cofre_data.get("reset_apos_vitorias", 3)
                self.lbl_cofre.config(text=f"🏦 {cofre:.0f}", foreground="#9C27B0")
                self.lbl_aposta.config(text=f"💵 {aposta:.0f}")
                preenchidos = "▮" * vit_seg
                vazios = "▯" * (reset_apos - vit_seg)
                self.lbl_cadeia.config(text=f"🔗 [{preenchidos}{vazios}] {vit_seg}/{reset_apos}")
            else:
                self.lbl_cofre.config(text="🏦 0")
                self.lbl_aposta.config(text="💵 100")
                self.lbl_cadeia.config(text="🔗 [▯▯▯] 0/3")

            sessao_info = self._calcular_sessao_actual()
            if sessao_info:
                w, l, pct = sessao_info
                self.lbl_sessao.config(text=f"📈 {w}W/{l}L ({pct:.0f}%)")
            else:
                self.lbl_sessao.config(text="📈 0W/0L")

            if banca:
                lucro = banca.get("lucro", 0)
                ganhos = banca.get("ganhos", 0) + banca.get("perdas", 0)
                if ganhos > 0:
                    roi = (lucro / ganhos) * 100
                    sinal = "+" if roi >= 0 else ""
                    self.lbl_roi.config(text=f"📊 {sinal}{roi:.1f}%")
                else:
                    self.lbl_roi.config(text="📊 --")

            self._actualizar_flags()
            self.lbl_ultima_act.config(text=f"🕐 {datetime.now():%H:%M:%S}")
        except Exception:
            pass
        self.root.after(1000, self._actualizar_estado)

    def _testar_saldo(self):
        """Lê o saldo do casino AGORA e mostra o resultado (feedback real do OCR)."""
        cfg = self._ler_json("config/config.json")
        area = cfg.get("area_saldo") if cfg else None
        if not area or len(area) != 4:
            messagebox.showwarning(
                "Saldo não calibrado",
                "A área do saldo não está definida.\n\n"
                "Vai à aba Calibração → '💰 Saldo do casino' e calibra primeiro.")
            return
        try:
            from ocr.leitura_saldo import ler_saldo_robusto
            valor = ler_saldo_robusto(tuple(area), tentativas=3)
        except Exception as e:
            messagebox.showerror("Erro no teste",
                f"Não consegui correr o OCR do saldo:\n\n{e}")
            return

        if valor is not None:
            messagebox.showinfo(
                "🔍 Teste do saldo",
                f"✅ O OCR leu: {valor:.0f} AOA\n\n"
                f"Bate com o saldo REAL no casino?\n"
                f"  • Sim → está calibrado, podes usar.\n"
                f"  • Não → recalibra com o rectângulo mais justo\n"
                f"    sobre o número (sem 'AOA', sem espaços a mais).")
        else:
            messagebox.showerror(
                "🔍 Teste do saldo",
                "❌ O OCR NÃO conseguiu ler o saldo.\n\n"
                "Prováveis causas:\n"
                "  • A área apanha 'AOA' ou espaço a mais\n"
                "  • O rectângulo está torto ou grande demais\n\n"
                "Vai à aba Calibração → '💰 Saldo do casino' e recalibra\n"
                "marcando SÓ o número, bem justo.")

    def _ler_json(self, caminho):
        try:
            p = Path(caminho)
            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _calcular_sessao_actual(self):
        try:
            pasta = Path("data")
            if not pasta.exists():
                return None
            ficheiros = sorted(pasta.glob("sessao_*.csv"), reverse=True)
            if not ficheiros:
                return None
            mais_recente = ficheiros[0]
            w, l = 0, 0
            with open(mais_recente, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for linha in reader:
                    if linha.get("resultado") == "ganhou":
                        w += 1
                    elif linha.get("resultado") == "perdeu":
                        l += 1
            if w + l == 0:
                return (0, 0, 0)
            return (w, l, w / (w + l) * 100)
        except Exception:
            return None

    def _actualizar_flags(self):
        cfg = self._ler_json("config/config.json")
        if not cfg:
            return

        def marcar(label, chave, nome):
            on = cfg.get(chave, False)
            if on:
                label.config(text=f"✅ {nome}", foreground="#4CAF50")
            else:
                label.config(text=f"⬜ {nome}", foreground="gray")

        marcar(self.lbl_flag_hot_cold,  "hot_cold_detection", "hot_cold_detection")
        marcar(self.lbl_flag_adaptive,  "adaptive_strategy",  "adaptive_strategy")
        marcar(self.lbl_flag_preservar, "preservar_banca",    "preservar_banca")

        kelly_modo = cfg.get("kelly_modo", "off")
        if kelly_modo != "off":
            self.lbl_flag_kelly.config(text=f"✅ kelly ({kelly_modo})", foreground="#4CAF50")
        else:
            self.lbl_flag_kelly.config(text="⬜ kelly_criterion", foreground="gray")

        # Indicador de estratégia activa.
        # Prioridade REAL (igual à do core): Rosa > Patterns > Dados > PDF
        if cfg.get("usar_estrategia_rosa", False):
            cashout_r = cfg.get("cashout_rosa", 1.90)
            self.lbl_estrategia.config(
                text=f"🌹 Estratégia: ROSA (aposta pós-rosa, alvo {cashout_r:.2f}x)",
                foreground="#C2185B")
        elif cfg.get("usar_estrategia_padroes", False):
            self.lbl_estrategia.config(text="🎯 Estratégia: FOLLOW PATTERNS", foreground="#2E7D32")
        elif cfg.get("usar_estrategia_dados", False):
            self.lbl_estrategia.config(text="📊 Estratégia: Dados Simples", foreground="#1976D2")
        else:
            self.lbl_estrategia.config(text="📜 Estratégia: PDF tradicional", foreground="gray")

    def _ao_fechar(self):
        if self.bot_a_correr:
            resposta = messagebox.askyesno("Bot a correr",
                "O bot está activo. Queres realmente fechar?")
            if not resposta:
                return
            try:
                from utils.stop_graceful import pedir_paragem
                pedir_paragem()
            except Exception:
                pass
        sys.stdout = self.stdout_original
        sys.stderr = self.stderr_original
        self.root.destroy()


def main():
    root = tk.Tk()
    app = PainelControlo(root)
    root.mainloop()


if __name__ == "__main__":
    main()
