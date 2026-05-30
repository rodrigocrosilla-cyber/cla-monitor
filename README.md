# CLA eFootball Monitor — Deploy no Railway

## O que esse bot faz
- Acessa winnershub.net/cla-efootball a cada 2 minutos
- Detecta sequências de vitórias ou derrotas por jogador
- Te avisa no Telegram quando um jogador atingir 3+ vitórias ou 3+ derrotas seguidas
- Roda 24h na nuvem, sem precisar do seu PC ligado

---

## Passo 1 — Criar conta no GitHub (gratuito)
1. Acesse https://github.com e crie uma conta
2. Clique em "New repository"
3. Nome: `cla-monitor`
4. Deixe como **Public**
5. Clique em "Create repository"

---

## Passo 2 — Fazer upload dos arquivos
Na página do repositório criado, clique em "uploading an existing file" e suba:
- `monitor.py`
- `requirements.txt`
- `Dockerfile`

Clique em "Commit changes".

---

## Passo 3 — Deploy no Railway
1. Acesse https://railway.app e faça login com sua conta GitHub
2. Clique em **"New Project"**
3. Escolha **"Deploy from GitHub repo"**
4. Selecione o repositório `cla-monitor`
5. O Railway vai detectar o Dockerfile automaticamente
6. Clique em **"Deploy"**

---

## Passo 4 — Aguardar o deploy
O primeiro deploy leva ~5 minutos (instala o browser headless).
Quando terminar, você receberá uma mensagem no Telegram:

```
✅ CLA Monitor iniciado!
```

---

## Ajustar os thresholds
Se quiser mudar de 3 para 2 vitórias (por exemplo), edite no arquivo monitor.py:
```python
WIN_STREAK_THRESHOLD = 2   # vitórias seguidas para alertar
LOSS_STREAK_THRESHOLD = 2  # derrotas seguidas para alertar
```

---

## Custo
- GitHub: gratuito
- Railway: plano Hobby = $5/mês (500h gratuitas no trial)
  → Para uso contínuo 24h, o plano Hobby de $5/mês é suficiente

---

## Suporte
Em caso de dúvidas, verifique os logs no painel do Railway em "Deployments > View Logs"
