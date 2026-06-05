# models/modelo.py
import os
from models.predictor import carregar_modelo as _carregar, prever
from models.treinamento import treinar_modelo as _treinar

MODELO_PATH = "models/modelo.pkl"


def carregar_modelo():
    """Carrega do disco se existir; caso contrário, tenta treinar."""
    if os.path.exists(MODELO_PATH):
        return _carregar()
    print("⚠️ Modelo não encontrado. Tentando treinar com dados existentes...")
    return _treinar()


def prever_aposta(lista_multiplicadores: list, modelo=None) -> tuple:
    """
    Interface única de previsão para o core.
    O parâmetro 'modelo' é mantido por compatibilidade mas não é necessário.
    """
    return prever(lista_multiplicadores)
