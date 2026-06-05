"""
Agente Autónomo de Gestão - Aviator Bot
========================================

Princípios (validados em dados reais):
1. Cashout base baixo (1.5x) — cumpre mais a missão (93% vs 84% com 2.0x)
2. Stake adaptativo — conservador perto da meta, protege lucro
3. Parar aos +10% é SAGRADO (fonte real de "lucro")
4. Arriscar cashout alto só com folga consolidada
5. Reação a Rosa/temperatura — testar, mas confiar nos dados

Sem previsão de crashes. Gestão de risco pura.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class Configuracao(Enum):
    """Configurações testadas empiricamente."""
    CONSERVADOR_1_5 = "Conservador 1.5x"
    ADAPTATIVO = "Adaptativo (1.5→2.0)"
    ROSA = "Rosa (1.5x apenas)"
    MODERADO_2_0 = "Moderado 2.0x"


@dataclass
class MissaoGestao:
    """Define a missão que o agente precisa cumprir."""
    banca_inicial: float
    meta_lucro_pct: float = 10.0  # +10%
    stop_loss_pct: float = -15.0  # -15%
    limite_stake: float = 0.0  # 0 = adaptar automaticamente
    
    @property
    def meta_absoluta(self) -> float:
        """Saldo que precisa atingir para sucesso (+10%)."""
        return self.banca_inicial * (1 + self.meta_lucro_pct / 100)
    
    @property
    def stop_absoluto(self) -> float:
        """Saldo que dispara paragem forçada."""
        return self.banca_inicial * (1 + self.stop_loss_pct / 100)
    
    def distancia_para_meta(self, saldo_atual: float) -> float:
        """Quanto falta para atingir a meta."""
        return self.meta_absoluta - saldo_atual
    
    def dentro_limite(self, saldo_atual: float) -> bool:
        """Testa se ainda está dentro dos limites da missão."""
        return saldo_atual >= self.stop_absoluto


@dataclass
class EstadoAgente:
    """Estado completo do agente durante uma sessão."""
    config: Configuracao
    missao: MissaoGestao
    saldo_atual: float
    num_apostas: int = 0
    num_vitorias: int = 0
    num_derrotas: int = 0
    lucro_total: float = 0.0
    
    # Histórico para análise
    historico_apostas: List[Dict] = field(default_factory=list)
    
    # Flags de estado
    consecutivas_vitorias: int = 0
    consecutivas_derrotas: int = 0
    
    @property
    def win_rate(self) -> float:
        """Taxa de vitória (porcentagem)."""
        if self.num_apostas == 0:
            return 0.0
        return (self.num_vitorias / self.num_apostas) * 100
    
    @property
    def roi(self) -> float:
        """Return on investment (%)."""
        if self.missao.banca_inicial == 0:
            return 0.0
        return (self.lucro_total / self.missao.banca_inicial) * 100
    
    def missao_cumprida(self) -> bool:
        """Testa se atingiu a meta (+10%)."""
        return self.saldo_atual >= self.missao.meta_absoluta
    
    def missao_falhada(self) -> bool:
        """Testa se ultrapassou o stop-loss."""
        return self.saldo_atual < self.missao.stop_absoluto


class AgenteGestao:
    """
    Agente autónomo que decide: quando apostar, quanto apostar, que cashout usar.
    
    Adaptação baseada em:
    - Proximidade à meta
    - Sequências de vitória/derrota
    - Configuração ativa
    """
    
    def __init__(self, config: Configuracao, missao: MissaoGestao, logs: bool = True):
        self.config = config
        self.missao = missao
        self.estado = EstadoAgente(config=config, missao=missao, 
                                   saldo_atual=missao.banca_inicial)
        self.logs_ativados = logs
    
    def _log(self, msg: str):
        """Log interno."""
        if self.logs_ativados:
            logger.info(f"[{self.config.value}] {msg}")
    
    # ========== DECISÃO: QUANDO APOSTAR ==========
    
    def deve_apostar(self, emoji_rosa: bool = False) -> bool:
        """
        Decide se deve apostar nesta rodada.
        
        Regras conservadoras:
        - Nunca se fora da missão
        - Pode pausar se em sequência de perdas
        - Rosa = sinal verde extra
        """
        
        if not self.missao.dentro_limite(self.estado.saldo_atual):
            self._log(f"❌ PARAGEM: Fora do limite! Saldo {self.estado.saldo_atual:.2f} < Stop {self.missao.stop_absoluto:.2f}")
            return False
        
        if self.estado.missao_cumprida():
            self._log(f"✅ MISSÃO CUMPRIDA! +{self.missao.meta_lucro_pct}% atingido.")
            return False  # Missão feita, não arrisca mais
        
        # Se em sequência de 3+ derrotas, pausa (psicologia + risco)
        if self.estado.consecutivas_derrotas >= 3:
            self._log(f"⚠️ Sequência de {self.estado.consecutivas_derrotas} derrotas. Pausa tática.")
            return False
        
        # Regra por configuração
        if self.config == Configuracao.ROSA and not emoji_rosa:
            # Rosa só aposta quando há Rosa
            return False
        
        return True
    
    # ========== DECISÃO: QUANTO APOSTAR ==========
    
    def calcular_stake(self, saldo_disponivel: Optional[float] = None) -> float:
        """
        Stake adaptativo baseado em:
        - Quanto falta para a meta
        - Configuração ativa
        - Saldo disponível
        
        Princípio: ser MUITO conservador quando perto da meta.
        """
        
        if saldo_disponivel is None:
            saldo_disponivel = self.estado.saldo_atual
        
        falta_para_meta = self.missao.distancia_para_meta(self.estado.saldo_atual)
        
        if falta_para_meta <= 0:
            # Já passou da meta
            return 0
        
        # % da banca que representa a meta restante
        pct_falta = falta_para_meta / self.missao.banca_inicial if self.missao.banca_inicial > 0 else 1.0
        
        # Base: 2% da banca (muito conservador)
        base_stake = self.missao.banca_inicial * 0.02
        
        if self.config == Configuracao.CONSERVADOR_1_5:
            # Stake fixo: sempre 2% da banca
            stake = base_stake
        
        elif self.config == Configuracao.ADAPTATIVO:
            # Se perto da meta (<2% falta), reduz para 1% 
            # Se longe (>5% falta), pode subir a 3%
            if pct_falta <= 0.02:
                stake = self.missao.banca_inicial * 0.01
            elif pct_falta <= 0.05:
                stake = base_stake
            else:
                stake = self.missao.banca_inicial * 0.03
        
        elif self.config == Configuracao.ROSA:
            # Rosa: aposta um pouco mais agressiva (2.5% em Rosa)
            stake = self.missao.banca_inicial * 0.025
        
        elif self.config == Configuracao.MODERADO_2_0:
            # Moderado com 2.0x: sobe a 3%
            stake = self.missao.banca_inicial * 0.03
        
        else:
            stake = base_stake
        
        # Nunca mais que 5% da banca por aposta
        stake = min(stake, self.missao.banca_inicial * 0.05)
        
        # Se há limite de stake definido, respeita
        if self.missao.limite_stake > 0:
            stake = min(stake, self.missao.limite_stake)
        
        # Nunca mais que saldo disponível
        stake = min(stake, saldo_disponivel)
        
        return stake
    
    # ========== DECISÃO: QUE CASHOUT USAR ==========
    
    def calcular_cashout(self) -> float:
        """
        Cashout dinâmico.
        
        Princípio:
        - Base = 1.5x (o que funciona: 93% sucesso)
        - Sobe a 2.0x só se tem folga consolidada
        - Em Rosa e perto da meta: mantém 1.5x (seguro)
        
        Dados: Conservador 1.5x = 93%, Moderado 2.0x = 84%
        """
        
        falta_para_meta = self.missao.distancia_para_meta(self.estado.saldo_atual)
        distancia_pct = falta_para_meta / self.missao.banca_inicial if self.missao.banca_inicial > 0 else 1.0
        
        if self.config == Configuracao.CONSERVADOR_1_5:
            return 1.50
        
        elif self.config == Configuracao.ROSA:
            return 1.50  # Rosa sempre 1.5x
        
        elif self.config == Configuracao.ADAPTATIVO:
            # Se perto da meta (<2%), não arrisca: 1.5x
            if distancia_pct <= 0.02:
                return 1.50
            # Se longe (>10% falta) e com 2+ vitorias seguidas, tenta 2.0x
            elif distancia_pct > 0.10 and self.estado.consecutivas_vitorias >= 2:
                return 2.00
            else:
                return 1.50
        
        elif self.config == Configuracao.MODERADO_2_0:
            # Moderado usa sempre 2.0x
            return 2.00
        
        return 1.50
    
    # ========== ATUALIZAÇÃO DE ESTADO ==========
    
    def registar_aposta(self, 
                       valor_apostado: float,
                       crash_real: float,
                       cashout_usado: float,
                       ganhou: bool) -> Dict:
        """
        Registar resultado de uma aposta e atualizar estado.
        
        Retorna dict com resultado.
        """
        
        self.estado.num_apostas += 1
        
        if ganhou:
            lucro = valor_apostado * (cashout_usado - 1.0)
            self.estado.num_vitorias += 1
            self.estado.consecutivas_vitorias += 1
            self.estado.consecutivas_derrotas = 0
        else:
            lucro = -valor_apostado
            self.estado.num_derrotas += 1
            self.estado.consecutivas_derrotas += 1
            self.estado.consecutivas_vitorias = 0
        
        self.estado.saldo_atual += lucro
        self.estado.lucro_total += lucro
        
        resultado = {
            'apostas_total': self.estado.num_apostas,
            'vitorias': self.estado.num_vitorias,
            'derrotas': self.estado.num_derrotas,
            'win_rate': self.estado.win_rate,
            'saldo_atual': self.estado.saldo_atual,
            'lucro_total': self.estado.lucro_total,
            'roi': self.estado.roi,
            'missao_cumprida': self.estado.missao_cumprida(),
            'missao_falhada': self.estado.missao_falhada(),
        }
        
        # Log
        if ganhou:
            self._log(f"✅ Vitória! +{lucro:.2f}€ | Saldo: {self.estado.saldo_atual:.2f}€ | {self.estado.win_rate:.1f}% WR")
        else:
            self._log(f"❌ Derrota. -{valor_apostado:.2f}€ | Saldo: {self.estado.saldo_atual:.2f}€ | {self.estado.win_rate:.1f}% WR")
        
        # Histórico
        self.estado.historico_apostas.append({
            'num': self.estado.num_apostas,
            'valor': valor_apostado,
            'cashout': cashout_usado,
            'crash': crash_real,
            'ganhou': ganhou,
            'lucro': lucro,
            'saldo': self.estado.saldo_atual,
        })
        
        return resultado
    
    # ========== RELATÓRIO ==========
    
    def relatorio_sessao(self) -> str:
        """Retorna relatório final da sessão."""
        
        status_meta = "✅ ATINGIDA" if self.estado.missao_cumprida() else "❌ NÃO ATINGIDA"
        status_stop = "❌ ULTRAPASSADO" if self.estado.missao_falhada() else "✅ PRESERVADO"
        
        linhas = [
            f"\n{'='*60}",
            f"RELATÓRIO DE SESSÃO - {self.config.value}",
            f"{'='*60}",
            f"Banca Inicial:       {self.missao.banca_inicial:.2f}€",
            f"Banca Final:         {self.estado.saldo_atual:.2f}€",
            f"Lucro Total:         {self.estado.lucro_total:+.2f}€",
            f"ROI:                 {self.estado.roi:+.2f}%",
            f"",
            f"Apostas Total:       {self.estado.num_apostas}",
            f"Vitórias:            {self.estado.num_vitorias}",
            f"Derrotas:            {self.estado.num_derrotas}",
            f"Win Rate:            {self.estado.win_rate:.1f}%",
            f"",
            f"Meta (+{self.missao.meta_lucro_pct}%):         {self.missao.meta_absoluta:.2f}€ {status_meta}",
            f"Stop-Loss ({self.missao.stop_loss_pct}%):    {self.missao.stop_absoluto:.2f}€ {status_stop}",
            f"{'='*60}\n",
        ]
        
        return "\n".join(linhas)
    
    def reset_sessao(self):
        """Reinicia o agente para nova simulação."""
        self.estado = EstadoAgente(config=self.config, missao=self.missao,
                                  saldo_atual=self.missao.banca_inicial)
