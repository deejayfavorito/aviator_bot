"""
Aba GUI para o Agente Autónomo — integração leve no painel de controlo.

Funcionalidades:
  1. Carrega últimas N sessões (CSVs)
  2. Simula cada uma com 4 configurações (Conservador, Adaptativo, Rosa, Moderado)
  3. Mostra qual configuração cumpre a missão (+10%) mais vezes
  4. Recomenda a melhor estratégia
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
from pathlib import Path
from datetime import datetime
import json

from gestor.agente_autonomo import (
    AgenteGestao, Configuracao, MissaoGestao
)


class AbaAgenteAutonomo:
    """Integração do Agente Autónomo como aba na GUI."""
    
    def __init__(self, parent_notebook):
        """
        parent_notebook: ttk.Notebook onde adicionar a aba.
        """
        self.frame = ttk.Frame(parent_notebook)
        parent_notebook.add(self.frame, text="🤖 Agente Autónomo")
        
        self.teste_a_correr = False
        self.thread_teste = None
        
        self._construir_layout()
    
    def _construir_layout(self):
        """Constrói a interface da aba."""
        
        # ─── Header ───────────────────────────────────────────────────
        header = tk.LabelFrame(self.frame, text="📊 Simulador de Configurações",
                               padx=10, pady=8, font=("Arial", 10, "bold"))
        header.pack(fill="x", padx=5, pady=5)
        
        tk.Label(header,
                text="Carrega as últimas sessões (CSVs) e testa qual configuração\n"
                     "cumpre a missão (+10%) mais vezes.",
                font=("Arial", 9), foreground="gray", justify="left").pack(anchor="w")
        
        # ─── Controlos ─────────────────────────────────────────────────
        ctrl_frame = tk.Frame(header)
        ctrl_frame.pack(fill="x", pady=(8, 0))
        
        tk.Label(ctrl_frame, text="Banca inicial:", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        self.var_banca = tk.StringVar(value="2000")
        tk.Entry(ctrl_frame, textvariable=self.var_banca, width=10,
                font=("Arial", 9)).pack(side="left", padx=(0, 20))
        
        tk.Label(ctrl_frame, text="Meta (+%):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        self.var_meta = tk.StringVar(value="10")
        tk.Entry(ctrl_frame, textvariable=self.var_meta, width=5,
                font=("Arial", 9)).pack(side="left", padx=(0, 20))
        
        tk.Label(ctrl_frame, text="Stop (%):", font=("Arial", 9)).pack(side="left", padx=(0, 5))
        self.var_stop = tk.StringVar(value="-15")
        tk.Entry(ctrl_frame, textvariable=self.var_stop, width=5,
                font=("Arial", 9)).pack(side="left")
        
        # ─── Botões ───────────────────────────────────────────────────
        btn_frame = tk.Frame(header)
        btn_frame.pack(fill="x", pady=(8, 0))
        
        self.btn_testar = tk.Button(btn_frame, text="▶ EXECUTAR TESTE",
                                    font=("Arial", 10, "bold"),
                                    bg="#4CAF50", fg="white",
                                    activebackground="#45a049",
                                    command=self._iniciar_teste,
                                    cursor="hand2")
        self.btn_testar.pack(side="left", padx=5)
        
        self.btn_parar = tk.Button(btn_frame, text="⏹ PARAR",
                                   font=("Arial", 10, "bold"),
                                   bg="#f44336", fg="white",
                                   activebackground="#da190b",
                                   command=self._parar_teste,
                                   cursor="hand2",
                                   state="disabled")
        self.btn_parar.pack(side="left", padx=5)
        
        tk.Label(btn_frame, text="⏳", font=("Arial", 10),
                foreground="gray").pack(side="left", padx=10)
        self.lbl_status_teste = tk.Label(btn_frame, text="pronto",
                                        font=("Arial", 9), foreground="gray")
        self.lbl_status_teste.pack(side="left")
        
        # ─── Resultados ──────────────��────────────────────────────────
        result_frame = tk.LabelFrame(self.frame, text="📈 Resultados",
                                     padx=5, pady=5, font=("Arial", 10, "bold"))
        result_frame.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.txt_resultado = scrolledtext.ScrolledText(
            result_frame,
            font=("Consolas", 9),
            bg="#1e1e1e", fg="#d4d4d4",
            wrap=tk.WORD, height=20
        )
        self.txt_resultado.pack(fill="both", expand=True)
        
        # Tags para colorir output
        self.txt_resultado.tag_configure("titulo", foreground="#569cd6", font=("Consolas", 10, "bold"))
        self.txt_resultado.tag_configure("sucesso", foreground="#4ec9b0")
        self.txt_resultado.tag_configure("erro", foreground="#f48771")
        self.txt_resultado.tag_configure("info", foreground="#dcdcaa")
        self.txt_resultado.tag_configure("vencedor", foreground="#4CAF50", font=("Consolas", 10, "bold"))
        
        # ─── Botões de ação ───────────────────────────────────────────
        acao_frame = tk.Frame(self.frame)
        acao_frame.pack(fill="x", padx=5, pady=5)
        
        tk.Button(acao_frame, text="🧹 Limpar output",
                 font=("Arial", 9), cursor="hand2",
                 command=self._limpar_output).pack(side="left", padx=5)
        
        tk.Button(acao_frame, text="📋 Copiar tudo",
                 font=("Arial", 9), cursor="hand2",
                 command=self._copiar_output).pack(side="left", padx=5)
        
        tk.Label(acao_frame, text="", font=("Arial", 8)).pack(side="left", expand=True)
        
        tk.Label(acao_frame,
                text="💡 Dica: testa qual config cumpre +10% mais frequentemente",
                font=("Arial", 8, "italic"), foreground="gray").pack(side="right", padx=5)
    
    def _iniciar_teste(self):
        """Inicia o teste em thread separada."""
        if self.teste_a_correr:
            return
        
        self.teste_a_correr = True
        self.btn_testar.config(state="disabled")
        self.btn_parar.config(state="normal")
        self.lbl_status_teste.config(text="a processar...", foreground="#FF9800")
        
        self.thread_teste = threading.Thread(target=self._executar_teste, daemon=True)
        self.thread_teste.start()
    
    def _parar_teste(self):
        """Pede paragem do teste."""
        self.teste_a_correr = False
        self.lbl_status_teste.config(text="paragem pedida...", foreground="#F57C00")
    
    def _limpar_output(self):
        """Limpa o texto de resultados."""
        self.txt_resultado.delete("1.0", tk.END)
    
    def _copiar_output(self):
        """Copia o output para clipboard."""
        try:
            conteudo = self.txt_resultado.get("1.0", tk.END)
            self.frame.clipboard_clear()
            self.frame.clipboard_append(conteudo)
            self.frame.update()
            messagebox.showinfo("Copiado", "✅ Output copiado para clipboard.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não consegui copiar:\n{e}")
    
    def _adicionar_texto(self, texto, tag="info"):
        """Adiciona texto com tag de cor."""
        self.txt_resultado.insert(tk.END, texto, tag)
        self.txt_resultado.see(tk.END)
        self.frame.update()
    
    def _executar_teste(self):
        """Executa o teste (roda em thread)."""
        try:
            # Valida inputs
            try:
                banca = float(self.var_banca.get())
                meta_pct = float(self.var_meta.get())
                stop_pct = float(self.var_stop.get())
            except ValueError:
                self._adicionar_texto("❌ Valores inválidos! Use números.\n", "erro")
                return
            
            # Carrega CSVs
            self._adicionar_texto("🔍 A procurar ficheiros de sessão...\n", "info")
            csv_files = sorted(Path("data").glob("sessao_*.csv"), reverse=True)
            
            if not csv_files:
                self._adicionar_texto("❌ Nenhuma sessão encontrada em data/\n", "erro")
                return
            
            self._adicionar_texto(f"✅ Encontradas {len(csv_files)} sessões\n\n", "sucesso")
            
            # Configurações a testar
            configs = [
                Configuracao.CONSERVADOR_1_5,
                Configuracao.ADAPTATIVO,
                Configuracao.ROSA,
                Configuracao.MODERADO_2_0,
            ]
            
            resultados_por_config = {c.value: {"cumpridas": 0, "total": 0} for c in configs}
            
            self._adicionar_texto("🚀 A simular cada configuração...\n", "info")
            self._adicionar_texto("═" * 70 + "\n\n", "info")
            
            num_testado = 0
            for csv_file in csv_files:
                if not self.teste_a_correr:
                    self._adicionar_texto("⏸️ Teste parado pelo utilizador.\n", "erro")
                    break
                
                # Para cada CSV, testa com cada config
                for config in configs:
                    try:
                        import pandas as pd
                        df = pd.read_csv(csv_file)
                        
                        # Cria missão e agente
                        missao = MissaoGestao(
                            banca_inicial=banca,
                            meta_lucro_pct=meta_pct,
                            stop_loss_pct=stop_pct,
                        )
                        
                        agente = AgenteGestao(config=config, missao=missao, logs=False)
                        
                        # Simula cada linha do CSV
                        for idx, row in df.iterrows():
                            if not self.teste_a_correr:
                                break
                            
                            try:
                                crash_real = float(row.get('multiplicador_round', 0))
                                cashout_alvo = float(row.get('cashout_alvo', 0)) or agente.calcular_cashout()
                                valor_apostado = float(row.get('valor_apostado', 0))
                                resultado = row.get('resultado', '')
                                
                                if resultado not in ['ganhou', 'perdeu'] or valor_apostado == 0:
                                    continue
                                
                                ganhou = resultado == 'ganhou'
                                agente.registar_aposta(
                                    valor_apostado=valor_apostado,
                                    crash_real=crash_real,
                                    cashout_usado=cashout_alvo,
                                    ganhou=ganhou
                                )
                                
                                # Pára se missão cumprida ou falhada
                                if agente.estado.missao_cumprida() or agente.estado.missao_falhada():
                                    break
                            
                            except (ValueError, KeyError):
                                continue
                        
                        # Registra resultado
                        resultados_por_config[config.value]["total"] += 1
                        if agente.estado.missao_cumprida():
                            resultados_por_config[config.value]["cumpridas"] += 1
                        
                        num_testado += 1
                    
                    except Exception as e:
                        self._adicionar_texto(f"⚠️ Erro ao testar {csv_file.name}: {e}\n", "erro")
                        continue
            
            # Mostra resultados
            self._adicionar_texto("═" * 70 + "\n\n", "info")
            self._adicionar_texto("📊 RESUMO FINAL\n", "titulo")
            self._adicionar_texto("═" * 70 + "\n\n", "info")
            
            # Ordena por taxa de cumprimento
            sorted_configs = sorted(
                resultados_por_config.items(),
                key=lambda x: (x[1]["cumpridas"] / x[1]["total"] * 100) if x[1]["total"] > 0 else 0,
                reverse=True
            )
            
            self._adicionar_texto(f"{'CONFIG':<25} {'CUMPRIDAS':<12} {'TAXA':<10}\n", "info")
            self._adicionar_texto("─" * 50 + "\n", "info")
            
            for i, (config_nome, stats) in enumerate(sorted_configs, 1):
                total = stats["total"]
                cumpridas = stats["cumpridas"]
                taxa = (cumpridas / total * 100) if total > 0 else 0
                
                emoji = "🏆" if i == 1 else "  "
                tag = "vencedor" if i == 1 else "sucesso"
                
                self._adicionar_texto(
                    f"{i}. {config_nome:<22} {cumpridas:>2}/{total:<8} {taxa:>6.1f}% {emoji}\n",
                    tag
                )
            
            self._adicionar_texto("\n" + "═" * 70 + "\n\n", "info")
            self._adicionar_texto("💡 CONCLUSÃO\n", "titulo")
            self._adicionar_texto("─" * 70 + "\n", "info")
            
            melhor = sorted_configs[0]
            melhor_nome, melhor_stats = melhor
            taxa_melhor = (melhor_stats["cumpridas"] / melhor_stats["total"] * 100) if melhor_stats["total"] > 0 else 0
            
            self._adicionar_texto(f"✅ Vencedor: {melhor_nome}\n", "vencedor")
            self._adicionar_texto(f"   Taxa de cumprimento: {taxa_melhor:.1f}%\n", "sucesso")
            self._adicionar_texto(f"   Apostas testadas: {num_testado}\n\n", "info")
            
            self._adicionar_texto("📋 Recomendação:\n", "info")
            self._adicionar_texto(f"   Use {melhor_nome} porque:\n", "info")
            
            if "1.5x" in melhor_nome or "Conservador" in melhor_nome:
                self._adicionar_texto("   • Cashout baixo (1.5x) reduz risco de crash\n", "sucesso")
                self._adicionar_texto("   • Precisa de menos win rate para lucrar\n", "sucesso")
                self._adicionar_texto("   • Maior consistência nos resultados\n", "sucesso")
            elif "Rosa" in melhor_nome:
                self._adicionar_texto("   • Estratégia validada empiricamente\n", "sucesso")
                self._adicionar_texto("   • Aproveita o padrão 'após rosa vem ≥2x'\n", "sucesso")
                self._adicionar_texto("   • Menor frequência de apostas = menos stress\n", "sucesso")
            else:
                self._adicionar_texto("   • Adapta conforme situação (flexível)\n", "sucesso")
                self._adicionar_texto("   • Bom compromisso entre risco e ganho\n", "sucesso")
            
            self._adicionar_texto("\n✨ Teste concluído com sucesso!\n", "sucesso")
        
        except Exception as e:
            self._adicionar_texto(f"\n❌ Erro durante teste: {e}\n", "erro")
        
        finally:
            self.teste_a_correr = False
            self.btn_testar.config(state="normal")
            self.btn_parar.config(state="disabled")
            self.lbl_status_teste.config(text="concluído", foreground="#4CAF50")


# ═════════════════════════════════════════════════════════════════════════
# Para adicionar à GUI existente (painel_controlo.py):
# ═════════════════════════════════════════════════════════════════════════

def adicionar_aba_agente_ao_painel(notebook):
    """
    Chama isto após criar o notebook em PainelControlo.__init__:
    
        self.notebook = ttk.Notebook(self.root)
        # ... adiciona abas existentes ...
        self.aba_agente = AbaAgenteAutonomo(self.notebook)
    """
    AbaAgenteAutonomo(notebook)
