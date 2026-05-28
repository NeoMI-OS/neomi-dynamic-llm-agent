# NEOMI Pipeline Runner — Felhasználói Kézikönyv

**Verzió:** 1.0  
**Dátum:** 2026. május  
**URL:** https://neomi-pipeline-ui-643234238822.europe-west1.run.app

---

## 1. Áttekintés

A NEOMI Pipeline Runner egy mesterséges intelligencia alapú tartalomgeneráló eszköz, amellyel vállalati AI-oktatási anyagokat lehet automatikusan létrehozni. A rendszer egy 5 lépéses ügynök-pipeline-t futtat: kontextuselemzés → igényfelmérés → tantervtervezés → tartalomírás → kritikai értékelés.

---

## 2. A felhasználói felület felépítése

Az alkalmazás két fő panelre osztott:

```
┌─────────────────────┬──────────────────────────────────┐
│   BAL PANEL         │   JOBB PANEL                     │
│   (bemeneti adatok) │   (eredmények)                   │
└─────────────────────┴──────────────────────────────────┘
```

### Fejléc

![Kezdőképernyő](../tests/ui/screenshots/01_initial_load.png)

A fejlécben látható:
- **Zöld pont** — a rendszer aktív állapotát jelzi
- **NEOMI Pipeline Runner** — az alkalmazás neve
- **`// exp-001`** — a jelenleg kiválasztott kísérlet azonosítója (jobb oldalon)

---

## 3. Bal panel — Bemeneti adatok

### 3.1 Kísérlet kiválasztása

![Kísérlet választó](../tests/ui/screenshots/02_experiment_selector.png)

A **KÍSÉRLET** szekcióban választható ki, hogy melyik LLM-konfigurációt használja a pipeline. Három előre definiált kísérlet érhető el:

| Kísérlet | Leírás |
|----------|--------|
| `exp-001` — Baseline, GPT-4o mindenhol | Referencia pont: azonos erős modell minden szerepben |
| `exp-002` — Claude diverzitás | Claude Sonnet minden pipeline csomópontban |
| `exp-003` — Vegyes optimális | Különböző modellek az egyes szerepekhez optimalizálva |

A kísérlet neve és leírása a választó alatt jelenik meg.

### 3.2 Bemeneti adatok kitöltése

![Cégnév kitöltve](../tests/ui/screenshots/03_company_name_filled.png)

Az alábbi mezőket kell kitölteni:

| Mező | Kötelező | Leírás |
|------|----------|--------|
| **CÉG NEVE** | ✅ Igen | A vállalat neve (pl. Acme Solutions Kft.) |
| **CÉG TÍPUSA** | Nem | Az iparág/tevékenység típusa |
| **CÉLKÖZÖNSÉG** | Nem | Kiknek szól a tartalom (pl. Középvezetők) |
| **CÉL** | Nem | Mi a képzés célja |
| **KONTEXTUS** | Nem | További háttérinformáció |

> **Megjegyzés:** A **Cég neve** mező kitöltése kötelező. Amíg üres, a „PIPELINE FUTTATÁSA" gomb inaktív (szürke), és a „A cég neve kötelező" figyelmeztetés látható.

### 3.3 Az összes mező kitöltve

![Összes mező kitöltve](../tests/ui/screenshots/04_all_fields_filled.png)

Ha a Cég neve mező ki van töltve, a „PIPELINE FUTTATÁSA" gomb aktívvá válik (zöld). Az opcionális mezők előre kitöltött alapértékekkel rendelkeznek, amelyek igény szerint módosíthatók.

---

## 4. A pipeline futtatása

### 4.1 Indítás

Kattints a **„PIPELINE FUTTATÁSA"** gombra. A gomb felirata „PIPELINE FUT..." -ra változik, és letiltódik a dupla küldés elkerülése érdekében.

### 4.2 Betöltési állapot

![Pipeline betöltés](../tests/ui/screenshots/05_pipeline_loading.png)

A jobb panelen megjelenik:
- **Animált pontok** — a feldolgozás folyamatban van
- **„Pipeline fut..."** felirat
- Tájékoztató szöveg: „A pipeline futtatása 30–60 másodpercet vehet igénybe."

> **Fontos:** A pipeline futtatása általában 30–90 másodpercig tart, mivel 5 LLM ügynök dolgozik sorban egymás után. Ne zárd be a böngésző lapot!

---

## 5. Az eredmények értelmezése

A pipeline befejezése után a jobb panel megjeleníti az eredményeket.

### 5.1 Pipeline nyomkövetés (Node Trace)

Az eredménypanel tetején egy összesítő sor látható:
- **csomópontok** — hány ügynök futott le (általában 5)
- **össz. idő** — a teljes futási idő másodpercben
- **össz. token** — az összes felhasznált LLM token száma

Alatta minden egyes ügynök egy **kártyán** jelenik meg:

```
┌─────────────────────────────────────────────────┐
│ ● context_analyst          claude-sonnet  42.1s │
│   model: gpt-4o    idő: 12.3s    tok: 2.1k      │
│                                        SRS 34.8 │
└─────────────────────────────────────────────────┘
```

**A kártya elemei:**
- **Színes pont** (bal oldal) — zöld: sikeres, sárga: közepes teljesítmény, piros: hiba
- **Csomópont neve** — az ügynök szerepe
- **Model** — a használt LLM modell neve
- **Idő** — az ügynök futási ideje
- **Token** — a felhasznált tokenek száma
- **SRS badge** — Service Readiness Score (0–100)

#### Kártya kinyitása

Kattints bármelyik kártyára a részletes kimenet megtekintéséhez. A kártya kinyílik és megmutatja az ügynök által generált teljes szöveget.

### 5.2 SRS (Service Readiness Score)

Az SRS badge fölé húzva az egeret egy tooltip jelenik meg a részletes bontással:

| Kategória | Súly | Leírás |
|-----------|------|--------|
| **Tudás** | 25% | Factual knowledge benchmark |
| **Érvelés** | 35% | Reasoning & logic benchmark |
| **Használhatóság** | 40% | AI Index alapú minőségmutató |

**Értelmezés:**
- 🟢 70+ : Kiváló
- 🟡 40–70 : Elfogadható
- 🔴 0–40 : Gyenge

### 5.3 Kritikai összefoglaló

A pipeline utolsó eleme a **Critic ügynök** értékelése, amely egy összesítő kártyán jelenik meg:

- **Érettségi pontszám** (0–100) — a generált tartalom átfogó minősége
- **Relevancia** — mennyire releváns a célközönségnek
- **Mélység** — a tartalom szakmai mélysége
- **Alkalmazhatóság** — mennyire alkalmazható a gyakorlatban
- **Visszajelzés** — szöveges értékelés és javaslatok

---

## 6. Hibaelhárítás

| Hiba | Lehetséges ok | Megoldás |
|------|---------------|----------|
| „A cég neve kötelező" | CEG NEVE mező üres | Töltsd ki a Cég neve mezőt |
| „Pipeline futtatása sikertelen" | Backend nem elérhető | Ellenőrizd az internetkapcsolatot, próbáld újra |
| Fekete/üres jobb panel | Timeout vagy hálózati hiba | Töltsd újra az oldalt és futtasd újra |
| Hosszú betöltési idő (90s+) | Sok token, lassú modell | Normális jelenség komplex bemeneteknél |

---

## 7. Kísérletek és modellek

### Elérhető kísérletek

**exp-001 — Baseline (GPT-4o mindenhol)**
- Minden pipeline csomópontban GPT-4o
- Referencia pont a többi kísérlet értékeléséhez

**exp-002 — Claude diverzitás**
- Minden csomópontban Claude Sonnet
- Antropic modell teljesítményének mérése

**exp-003 — Vegyes optimális**
- Gemini Flash: kontextuselemzés
- GPT-4o-mini: igényfelmérés
- GPT-4o: tantervtervezés + tartalomírás
- Claude Sonnet: kritikus értékelés

### Modellek és tier-ek

| Tier | Provider | Modell | Jellemző |
|------|----------|--------|----------|
| FAST | Google | gemini-2.5-flash-lite | Gyors, egyszerű feladatokhoz |
| BALANCED | OpenAI | gpt-4o-mini | Kiegyensúlyozott |
| POWERFUL | OpenAI | gpt-4o | Komplex feladatokhoz |
| CREATIVE | Anthropic | claude-sonnet-4-6 | Kreatív tartalmakhoz |

---

## 8. Műszaki információk

- **Backend:** FastAPI + LangGraph, Google Cloud Run (europe-west1)
- **Frontend:** React + Vite, Google Cloud Run (europe-west1)
- **Backend URL:** `https://dynamic-llm-agent-dev-643234238822.europe-west1.run.app`
- **Frontend URL:** `https://neomi-pipeline-ui-643234238822.europe-west1.run.app`
- **GitHub:** `https://github.com/zsigacsaba/neomi-dynamic-llm-agent`
- **Branch:** `feature/multi-agent-pipeline`
