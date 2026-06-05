"""
Tratamento de Edge Cases — fallbacks e robustez em tempo real.

Situações tratadas:
  1. Tesseract OCR indisponível
  2. Internet/conexão casino cai
  3. Cashout timeout
  4. Leitura de saldo falha
  5. Ficheiro de config corrompido
"""

import os
import time
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════════════════════
# 1. TESSERACT OCR — Detecção e Fallback
# ════════════════════════════════════════════════════════════════════════════

_tesseract_disponivel = None


def verificar_tesseract() -> bool:
    """
    Testa se Tesseract está instalado e acessível.
    Faz cache do resultado.
    """
    global _tesseract_disponivel
    
    if _tesseract_disponivel is not None:
        return _tesseract_disponivel
    
    try:
        import pytesseract
        # Tenta execução dummy
        pytesseract.get_tesseract_version()
        _tesseract_disponivel = True
        logger.info("✅ Tesseract OCR disponível")
    except Exception as e:
        _tesseract_disponivel = False
        logger.warning(f"⚠️ Tesseract NÃO disponível: {e}")
    
    return _tesseract_disponivel


def ocr_com_fallback(area: tuple, tipo: str = "saldo") -> Optional[float]:
    """
    Tenta ler OCR (saldo/list). Se falha, retorna None (fallback via cashout).
    
    Args:
        area: tupla (x, y, w, h)
        tipo: "saldo" ou "lista"
    
    Returns:
        Valor lido ou None (fallback aplicável)
    """
    if not verificar_tesseract():
        logger.warning(f"⚠️ OCR {tipo} desactivado (Tesseract indisponível)")
        return None
    
    try:
        if tipo == "saldo":
            from ocr.leitura_saldo import ler_saldo_robusto
            return ler_saldo_robusto(area, tentativas=2)
        elif tipo == "lista":
            from ocr.leitura_lista import ler_lista_multiplicadores_atuais
            return ler_lista_multiplicadores_atuais()
    except Exception as e:
        logger.error(f"❌ Erro OCR {tipo}: {e}")
        return None


# ════════════════════════════════════════════════════════════════════════════
# 2. CASHOUT TIMEOUT e Retry Logic
# ════════════════════════════════════════════════════════════════════════════

def monitorar_cashout_com_retry(timeout: float = 30.0, 
                                 ultimo: float = 0.0,
                                 limiar: float = 1.5,
                                 max_retries: int = 2) -> Tuple[float, bool]:
    """
    Monitora cashout com retry automático se falhar.
    
    Returns:
        (multiplicador_obtido, sucesso)
    """
    from ocr.monitoramento_cashout import monitorar_cashout_preciso
    from utils.logs import log
    
    for tentativa in range(1, max_retries + 1):
        try:
            maior_mult, ok = monitorar_cashout_preciso(
                timeout=timeout,
                ultimo=ultimo,
                limiar=limiar
            )
            if ok or tentativa == max_retries:
                return (maior_mult, ok)
            
            log(f"⚠️ Cashout timeout tentativa {tentativa}/{max_retries} — retry em 2s")
            time.sleep(2.0)
        
        except Exception as e:
            log(f"❌ Erro cashout (tentativa {tentativa}): {e}")
            if tentativa == max_retries:
                return (0.0, False)
    
    return (0.0, False)


def apostar_com_retry(timeout: float = 5.0, max_retries: int = 2) -> bool:
    """
    Tenta apostar com retry automático.
    """
    from ocr.monitoramento_aposta import apostar_agora
    from utils.logs import log
    
    for tentativa in range(1, max_retries + 1):
        try:
            sucesso = apostar_agora(timeout=timeout)
            if sucesso or tentativa == max_retries:
                return sucesso
            
            log(f"⚠️ Aposta falhou (tentativa {tentativa}/{max_retries}) — retry em 1s")
            time.sleep(1.0)
        
        except Exception as e:
            log(f"❌ Erro aposta (tentativa {tentativa}): {e}")
            if tentativa == max_retries:
                return False
    
    return False


# ════════════════════════════════════════════════════════════════════════════
# 3. CONFIG.JSON — Validação e Fallback
# ════════════════════════════════════════════════════════════════════════════

CONFIG_DEFAULTS = {
    "banca_inicial": 5000.0,
    "aposta_base": 100.0,
    "objectivo_pct": 10.0,
    "stop_loss_pct": -15.0,
    "limiar_conf": 0.65,
    "limiar_cashout": 1.5,
    "modo_observador": False,
    "usar_estrategia_rosa": False,
    "usar_estrategia_padroes": True,
    "usar_estrategia_dados": False,
    "cashout_rosa": 1.9,
    "adaptive_strategy": False,
    "hot_cold_detection": False,
    "preservar_banca": False,
}


def validar_config(config: dict) -> dict:
    """
    Valida config e preenche valores em falta com defaults.
    
    Retorna config limpo e validado.
    """
    validado = {}
    
    for chave, valor_default in CONFIG_DEFAULTS.items():
        valor = config.get(chave, valor_default)
        
        # Validação básica
        if isinstance(valor_default, (int, float)):
            try:
                valor = float(valor)
            except (ValueError, TypeError):
                logger.warning(f"⚠️ Config '{chave}': valor inválido {valor}, usando default {valor_default}")
                valor = valor_default
        
        elif isinstance(valor_default, bool):
            if not isinstance(valor, bool):
                valor = bool(valor)
        
        validado[chave] = valor
    
    # Validações de negócio
    if validado["banca_inicial"] <= 0:
        logger.warning("⚠️ Banca inicial <= 0, usando 5000")
        validado["banca_inicial"] = 5000.0
    
    if validado["aposta_base"] <= 0:
        logger.warning("⚠️ Aposta base <= 0, usando 2% da banca")
        validado["aposta_base"] = validado["banca_inicial"] * 0.02
    
    # Apenas UMA estratégia activa
    estrategias_ativas = sum([
        validado.get("usar_estrategia_rosa", False),
        validado.get("usar_estrategia_padroes", False),
        validado.get("usar_estrategia_dados", False),
    ])
    
    if estrategias_ativas == 0:
        logger.warning("⚠️ Nenhuma estratégia activa, activando Padrões")
        validado["usar_estrategia_padroes"] = True
    elif estrategias_ativas > 1:
        logger.warning("⚠️ Múltiplas estratégias activas, desactivando todas menos Padrões")
        validado["usar_estrategia_rosa"] = False
        validado["usar_estrategia_dados"] = False
        validado["usar_estrategia_padroes"] = True
    
    return validado


def carregar_config_seguro(caminho: str = "config/config.json") -> dict:
    """
    Carrega config.json com tratamento de erros.
    Se ficheiro está corrompido, usa defaults.
    """
    import json
    
    try:
        path = Path(caminho)
        if not path.exists():
            logger.warning(f"⚠️ {caminho} não encontrado, usando defaults")
            return CONFIG_DEFAULTS.copy()
        
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        logger.info(f"✅ Config carregado: {caminho}")
        return validar_config(config)
    
    except json.JSONDecodeError as e:
        logger.error(f"❌ Config.json corrompido: {e}, usando defaults")
        return CONFIG_DEFAULTS.copy()
    
    except Exception as e:
        logger.error(f"❌ Erro ao carregar config: {e}, usando defaults")
        return CONFIG_DEFAULTS.copy()


# ════════════════════════════════════════════════════════════════════════════
# 4. Leitura de Saldo — com Fallback
# ════════════════════════════════════════════════════════════════════════════

_ultimo_saldo_fiavel = None


def ler_saldo_com_fallback(area: Optional[tuple] = None,
                            ultimo_conhecida: Optional[float] = None) -> Tuple[Optional[float], bool]:
    """
    Tenta ler saldo. Se falha, tenta usar último conhecida.
    
    Returns:
        (valor_saldo, é_leitura_fiável)
    """
    global _ultimo_saldo_fiavel
    
    if area is None or len(area) != 4:
        logger.warning("⚠️ Saldo: area não calibrada")
        return (ultimo_conhecida, False)
    
    try:
        from ocr.leitura_saldo import ler_saldo_robusto
        valor = ler_saldo_robusto(area, tentativas=2)
        if valor is not None:
            _ultimo_saldo_fiavel = valor
            return (valor, True)
    except Exception as e:
        logger.warning(f"⚠️ OCR saldo falhou: {e}")
    
    # Fallback: último saldo conhecido
    if _ultimo_saldo_fiavel is not None:
        logger.info(f"ℹ️ Usando último saldo conhecido: {_ultimo_saldo_fiavel}")
        return (_ultimo_saldo_fiavel, False)
    
    # Último recurso: valor passado
    return (ultimo_conhecida, False)


# ════════════════════════════════════════════════════════════════════════════
# 5. Detecção de Inatividade / Desconexão
# ══���═════════════════════════════════════════════════════════════════════════

class DetectorDesconexao:
    """Detecta se o casino está inativo ou desconectado."""
    
    def __init__(self, timeout_rodada: float = 60.0, max_leituras_falhadas: int = 5):
        self.timeout_rodada = timeout_rodada
        self.max_leituras_falhadas = max_leituras_falhadas
        self.leituras_falhadas = 0
        self.ultima_rodada = time.time()
    
    def registar_rodada_sucesso(self):
        """Rodada lida com sucesso."""
        self.ultima_rodada = time.time()
        self.leituras_falhadas = 0
    
    def registar_falha_leitura(self):
        """Tentativa de leitura falhou."""
        self.leituras_falhadas += 1
    
    def verificar_desconexao(self) -> bool:
        """Retorna True se detecta desconexão."""
        tempo_sem_rodada = time.time() - self.ultima_rodada
        
        if tempo_sem_rodada > self.timeout_rodada:
            logger.error(f"❌ Timeout: sem rodada por {tempo_sem_rodada:.0f}s")
            return True
        
        if self.leituras_falhadas >= self.max_leituras_falhadas:
            logger.error(f"❌ Leituras: {self.leituras_falhadas} falhas seguidas")
            return True
        
        return False
    
    def reset(self):
        """Reset do detector."""
        self.leituras_falhadas = 0
        self.ultima_rodada = time.time()


# ════════════════════════════════════════════════════════════════════════════
# 6. Helper para Alertas
# ════════════════════════════════════════════════════════════════════════════

def alerta_producao(tipo: str, mensagem: str):
    """
    Emite alerta de produção (para logging/notificação futura).
    
    Tipos: "erro_critico", "aviso", "info"
    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    if tipo == "erro_critico":
        logger.critical(f"🚨 [{timestamp}] {mensagem}")
    elif tipo == "aviso":
        logger.warning(f"⚠️ [{timestamp}] {mensagem}")
    else:
        logger.info(f"ℹ️ [{timestamp}] {mensagem}")
