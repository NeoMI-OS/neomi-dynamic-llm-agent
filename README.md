# 🤖 Dynamic LLM Router Agent

Automatikusan kiválasztja a legjobb LLM modellt a feladat alapján.

## 🚀 Gyors indítás (MacBook)

```bash
cd dynamic-llm-agent

# Virtuális környezet
python3 -m venv venv
source venv/bin/activate

# Függőségek
pip install -r requirements.txt

# API kulcs
cp .env.example .env
# Szerkeszd: GOOGLE_API_KEY=AIza...

# Teszt
cd src
python agent.py
```

## 🌐 API indítás

```bash
cd src
python api.py
# → http://localhost:8080
```

## 📡 API használat

```bash
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Mi a főváros?"}'
```

## ☁️ Cloud Run Deploy

```bash
gcloud run deploy dynamic-llm-agent \
  --source . \
  --region europe-west1 \
  --set-env-vars GOOGLE_API_KEY=xxx
```
