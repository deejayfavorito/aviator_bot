# 🤖 Robô Aviator

Robô autónomo para o jogo Aviator com OCR, IA e gestão de banca.

---

## 📦 Instalação

```bash
pip install -r requirements.txt
```

> Requer também o **Tesseract OCR** instalado:
> - Windows: https://github.com/UB-Mannheim/tesseract/wiki
> - Linux: `sudo apt install tesseract-ocr`

---

## 🚀 Primeira utilização (passo a passo)

### 1. Calibrar as áreas do ecrã
Execute cada script abaixo, clique e arraste para seleccionar a área correcta:

```bash
python -m calibrar.calibrar_area_lista        # lista lateral de multiplicadores
python -m calibrar.calibrar_area_voo          # multiplicador ao vivo (durante o voo)
python -m calibrar.calibrar_area_apostar      # botão APOSTAR
python -m calibrar.calibrar_area_cashout      # botão CASHOUT
python -m calibrar.calibrar_area_vermelho     # área vermelha após crash
```

### 2. Treinar o modelo de IA
```bash
python -m models.treinamento
```
> Necessita de pelo menos 20 registos em `data/historico.csv`.
> O robô também pode treinar automaticamente se não encontrar o modelo.

### 3. Iniciar o robô
```bash
python main_autonomo.py
```

---

## ⚙️ Configuração principal (`config/config.json`)

| Parâmetro | Descrição | Valor sugerido |
|---|---|---|
| `saldo_inicial` | Saldo de arranque da banca | 5000.0 |
| `valor_aposta` | Valor base de cada aposta | 10.0 |
| `limiar_conf` | Confiança mínima da IA para apostar | 0.65 |
| `limiar_cashout` | Multiplicador alvo para cashout | 2.0 |
| `meta_diaria` | Lucro diário para parar (em reais) | 500.0 |
| `limite_perda` | Perda máxima diária para parar (em reais) | 500.0 |

---

## 🗂️ Estrutura do projecto

```
📂 automation/     clique e cashout automático
📂 calibrar/       scripts de calibração das áreas do ecrã
📂 config/         configurações globais
📂 core/           loop principal e decisor
📂 data/           histórico CSV e estado da banca
📂 estrategia/     estratégias de aposta (janela + Martingale)
📂 gestor/         gestão da banca
📂 gui/            painel de interface visual
📂 models/         modelo de IA (treino e previsão)
📂 ocr/            leitura de ecrã em tempo real
📂 utils/          utilitários (logs, temporizador, etc.)
📂 logs/           ficheiros de log diários
```

---

## 📊 Dados gerados

- `data/historico.csv` — todos os eventos (apostas, cashouts, crashes)
- `data/estado_banca.json` — estado persistente da banca
- `data/estado_martingale.json` — estado do Martingale entre sessões
- `models/modelo.pkl` — modelo de IA treinado
- `logs/YYYY-MM-DD.log` — log diário de execução

---

## ⚠️ Notas importantes

- Execute sempre os calibradores antes da primeira utilização
- O robô para automaticamente ao atingir a meta diária ou o limite de perdas
- Para encerrar manualmente: `Ctrl+C`
- Para resetar a banca: edite `data/estado_banca.json` ou use `gestor/banca.py::resetar_banca()`
