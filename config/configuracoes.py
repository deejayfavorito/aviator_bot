# config/configuracoes.py
import json
import os

_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
_cache: dict = {}


def carregar_config() -> dict:
    """Fonte única de acesso ao config. Usa cache em memória."""
    if not _cache:
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                _cache.update(json.load(f))
        except Exception as e:
            print(f"⚠️ Erro ao carregar config.json: {e}")
    return _cache


def recarregar_config() -> dict:
    """Força releitura do disco (útil após calibração)."""
    _cache.clear()
    return carregar_config()


def salvar_config(dados: dict) -> bool:
    """Actualiza o config.json com novos dados. Usado pelos calibradores."""
    try:
        cfg = carregar_config()
        cfg.update(dados)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
        _cache.clear()  # invalida cache após escrita
        return True
    except Exception as e:
        print(f"⚠️ Erro ao salvar config.json: {e}")
        return False


# Instância global — mantida para compatibilidade
config = carregar_config()
