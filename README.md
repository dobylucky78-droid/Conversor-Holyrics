# Conversor Missa → Holyrics (Web)

App web mobile-first que converte folhetos da Missa (PDF Versão Celular)
em arquivos TXT prontos para o Holyrics, dividindo em **Parte 1** (até a
Homilia) e **Parte 2** (da Homilia em diante).

## Como rodar localmente

```bash
cd web
pip install -r requirements.txt
python app.py
```

Abra `http://localhost:8000` no navegador.

## Como hospedar de graça (Render.com)

O Render tem free tier sem precisar de cartão de crédito.

1. Crie uma conta em https://render.com
2. Crie um repositório no GitHub e suba esta pasta `web/`
3. No Render, clique **New** → **Web Service** → conecte o repositório
4. As configurações são detectadas automaticamente pelo `render.yaml`:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 120`
5. Clique em **Create Web Service**. O Render gera uma URL tipo
   `https://conversor-missa-holyrics.onrender.com`
6. Salve a URL nos favoritos do navegador do celular

> Free tier do Render hiberna após 15 min de inatividade. A primeira
> visita depois disso demora ~30 s para "acordar" o servidor.

## Como hospedar no Fly.io (alternativa)

1. Instale o `flyctl` (https://fly.io/docs/hands-on/install-flyctl/)
2. Faça login: `fly auth login`
3. Em `web/`: `fly launch` (responda **No** para Postgres/Redis)
4. Aceite criar o `fly.toml`. Em seguida: `fly deploy`

## Como instalar como app no celular (PWA)

Depois de hospedar, abra a URL no celular e:

- **iPhone (Safari)**: botão Compartilhar → "Adicionar à Tela de Início"
- **Android (Chrome)**: menu ⋮ → "Adicionar à tela inicial" / "Instalar app"

O app passa a aparecer na home como qualquer outro app, abrindo em
tela cheia (sem barra do navegador).

## Estrutura

```
web/
├── app.py                          # Servidor Flask
├── converter_missa_holyrics.py     # Motor de conversão (mesmo do desktop)
├── templates/index.html            # Frontend mobile-first
├── static/
│   ├── manifest.webmanifest        # Manifesto PWA (instalação)
│   └── icon.svg                    # Ícone do app
├── requirements.txt
├── Procfile                        # Render / Heroku / Railway
├── render.yaml                     # Config Render automática
└── README.md
```
