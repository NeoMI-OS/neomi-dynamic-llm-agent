# NeoMI v2 — Kutatási Keretrendszer Specifikáció

**Cél:** egy tiszta, új kódbázis specifikációja, ami a jelenlegi (`claude/analyze-code-overview-EMzHk` branch-en futó) rendszer egy session alatt szervesen felhalmozott technikai adósságát nem örökli tovább, de megőrzi annak működő, jól bevált részeit — és közelebb visz a NeoMI AIOS koncepció (dinamikus, feladat-függő agent-orchestration) tényleges igazolásához.

Ez a dokumentum önmagában értelmezhető — nem feltételezi az előző session ismeretét.

---

## 1. Miért új kódbázis (mit tanultunk)

A jelenlegi rendszer egy FIX, 5 node-os szekvenciális pipeline-ra épült (context_analyst → needs_analyzer → curriculum_designer → content_writer → critic), ahol csak a node-onkénti LLM-modell volt konfigurálható (YAML-fájlonként), maga a gráf-topológia és az értékelési módszertan viszont be volt égetve a kódba. Ahogy a kutatás mélyült (node-onkénti minőség-pontszám, valós diverzitás-metrika, Pareto-front, fusion_gain, kereszt-judge validáció, node-swap érzékenység, critic-modell torzítás felfedezése), egyre több eseti patch, append-only "javító" mechanizmus és egyedi végpont halmozódott fel:

- **Append-only patch-mechanizmus** (diversity patch, rejudge patch, novelty patch) — minden utólagos metrika egy külön JSONL-sorként lett hozzáfűzve, amit betöltéskor kellett a megfelelő sorrendben összefésülni a run-rekorddal. Ez működött, de minden új metrikatípus egy új, kézzel karbantartott merge-ági logikát igényelt.
- **Input-verziózás input_id-szuffixummal** (`-v2maxtok`, `-v3fix`) — amikor egy hibás batch-részletet újra kellett futtatni, az egyetlen mód a különálló futásra az volt, hogy mesterséges szuffixot kapott az input_id, ami utólag megnehezítette (és hibalehetőséget adott) a "melyik a logikailag érvényes verzió" kérdés megválaszolását minden elemzésben.
- **Végpont-burjánzás** — minden új képesség (`/pipeline/run-custom`, `/pipeline/cross-judge`, `/pipeline/diversity-batch`, `/pipeline/single-call-baseline`, `/pipeline/rejudge-batch`, `/pipeline/postprocess-batch`) külön, egyedi célú REST végpontként került be, egymástól független sémákkal.
- **Fel nem oldott mérési torzítás**: a `critic_issues_count` (és ezen keresztül a robustness dimenzió) valójában azt méri, MELYIK modell játssza a critic szerepét, nem azt, hogy ténylegesen mennyi probléma van a tartalommal — ezt a session végén azonosítottuk, de a jelenlegi architektúrában strukturálisan nehéz tisztán javítani, mert a critic node és az értékelő critic-logika nincs szétválasztva.
- **Statikus modell-hozzárendelés**: minden kísérlet egy előre megírt YAML, ami rögzíti, melyik node melyik modellt használja — nincs a rendszerben olyan komponens, ami a FELADAT tulajdonságai alapján (pl. mennyire kreatív, mennyire hosszú, mennyire kritikus a pontosság) DINAMIKUSAN választana modellt egy adott node-hoz.
- **Fix gráf-topológia**: a pipeline mindig egy lineáris lánc. Nincs támogatás elágazásra, párhuzamos ügynökökre, feltételes útvonalakra, vagy arra, hogy a feladat típusától függően más-más ügynök-elrendezés jöjjön létre.

Ezek nem "hibák" — szerves következményei annak, hogy a rendszer egy session alatt, iteratívan bővült. Egy új kódbázisban viszont ezeket a mintákat ELEJÉTŐL FOGVA tiszta, komponálható absztrakciókkal érdemes helyettesíteni.

---

## 2. Amit MEG KELL ŐRIZNI a jelenlegi backendből

Ezek jól működtek, és a specifikációnak explicit módon támaszkodnia kell rájuk:

1. **GCS-backed perzisztencia mintája** — sync-down olvasás előtt, sync-up írás után, env-változóval kapcsolható (nincs, ha nincs env-változó beállítva) — ez oldotta meg a Cloud Run efemer lokális lemezének adatvesztési problémáját.
2. **Cost-cap biztonsági mechanizmus** — előzetes ellenőrzés minden fizetős hívás előtt, batch-szintű és globális napi limit, szerver-oldali AUTORITATÍV költség-lekérdezés (nem a kliens-oldali, potenciálisan hiányos válaszra támaszkodva).
3. **Retry-toleráns, szerver-igazságra támaszkodó orchestration** — a Cloud Run ~300s-os platform-timeoutja miatt a hívó oldalnak úgy kell terveznie, hogy egy "időtúllépés" NEM jelenti azt, hogy a munka nem történt meg — mindig a szerver oldali logból kell megerősíteni a tényleges állapotot, retry logikával hálózati hibákra.
4. **Valós, embedding-alapú diverzitás-metrika** (OpenAI text-embedding-3-small + cosinus-hasonlóság), placeholder-érték helyett.
5. **Node-onkénti LLM-judge pontszám** EGYETLEN Judge-hívásban (nem 5 külön hívás — ez ötszörös költséget jelentene).
6. **max_tokens sapka node-onként**, YAML-lel felülírható, hogy a kimenet mérete kontrollált és a Judge ténylegesen a teljes kimenetet lássa (ne csonkolva).
7. **Multi-input batch tesztelés** cost-cap-pel és resume-logikával (már kész párok kihagyása újraindításkor).
8. **Exportálhatóság** táblázatkezelőbe (TSV), futás-szintű ÉS node-szintű bontásban, plusz vak (anonimizált) human-eval export.
9. **Minden modult mockolt LLM-hívással tesztelünk** — ez a mintázat kivételesen jól bevált egész session alatt (166+ unit teszt, nulla élő API-hívás a tesztekben), és az új kódbázisban is alapkövetelmény kell legyen.

---

## 3. Architektúra: három ortogonálisan konfigurálható alrendszer

A kérés szerint három dolognak kell szabadon, egymástól függetlenül konfigurálhatónak lennie:

```
┌─────────────────────────────────────────────────────────────┐
│                      TASK DESCRIPTOR                         │
│   (mit kell csinálni — pl. "tananyag-generálás", "kód-       │
│    review", "piac-elemzés" stb. + a konkrét input)           │
└───────────────────────────┬───────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐
│ A) AGENT       │  │ B) MODEL         │  │ C) EVALUATION     │
│  ARCHITECTURE  │  │  SELECTION       │  │  LAYER            │
│  LAYER         │  │  LAYER           │  │                   │
│                │  │                  │  │  - per-agent      │
│ Milyen ügynök- │  │ Melyik LLM-model │  │    (node) szintű  │
│ gráf oldja meg │  │ fusson az adott  │  │  - kompozit       │
│ a feladatot?   │  │ ügynökön, a      │  │    (teljes        │
│ (max 5 ügynök) │  │ RÁ SZABOTT       │  │    kísérlet)      │
│                │  │ feladat alapján  │  │    szintű         │
└───────┬────────┘  └────────┬─────────┘  └─────────┬─────────┘
        │                    │                      │
        └────────────────────┴──────────────────────┘
                             ▼
                    ┌──────────────────┐
                    │   ORCHESTRATOR    │
                    │  (végrehajtás +   │
                    │   naplózás)       │
                    └──────────────────┘
```

Mindhárom réteg **saját, önálló konfigurációs objektum** — egyik sem hivatkozik a másik belső részleteire. Egy kísérlet = `(AgentGraphSpec, ModelSelectionSpec, EvaluationSpec, TaskInput)` négyes.

### 3.A Agent Architecture Layer

**Cél:** a feladattól függően más-más ügynök-elrendezés (nem csak modellválasztás, hanem maga a GRÁF) legyen definiálható, legfeljebb 5 ügynökkel.

```yaml
# agent_graphs/curriculum_linear.yaml
graph_id: curriculum_linear
description: "Szekvenciális lánc, mint a jelenlegi 5-node pipeline"
max_agents: 5
nodes:
  - id: context_analyst
    role: "Kontextus-elemzés: cél, közönség, korlátok kinyerése"
    depends_on: []
    output_schema: ContextOutput
  - id: needs_analyzer
    role: "Szükséglet-elemzés"
    depends_on: [context_analyst]
    output_schema: NeedsOutput
  - id: curriculum_designer
    role: "Tananyag-struktúra tervezése"
    depends_on: [context_analyst, needs_analyzer]
    output_schema: CurriculumOutput
  - id: content_writer
    role: "Tartalom megírása"
    depends_on: [context_analyst, curriculum_designer, needs_analyzer]
    output_schema: ContentOutput
  - id: critic
    role: "Kritikai önértékelés"
    depends_on: [context_analyst, needs_analyzer, curriculum_designer, content_writer]
    output_schema: CriticOutput
edges: "implicit a depends_on-ból (DAG)"
```

```yaml
# agent_graphs/code_review_parallel.yaml
graph_id: code_review_parallel
description: "Példa egy MÁS topológiára: 2 párhuzamos elemző + 1 szintetizáló + 1 kritikus"
max_agents: 4
nodes:
  - id: security_analyst
    role: "Biztonsági szempontú elemzés"
    depends_on: []
  - id: performance_analyst
    role: "Teljesítmény szempontú elemzés"
    depends_on: []
  - id: synthesizer
    role: "A két elemzés szintetizálása egy javaslattá"
    depends_on: [security_analyst, performance_analyst]
  - id: critic
    role: "A javaslat kritikája"
    depends_on: [synthesizer]
```

**Követelmények:**
- A gráf egy **DAG** (irányított, körmentes gráf) `depends_on` élekkel — ez általánosítja a jelenlegi fix láncot, támogatva elágazást és párhuzamos ügynököket is.
- **Validáció**: max 5 node, nincs kör, minden `depends_on` hivatkozás létező node-ra mutat.
- Minden node-hoz tartozik egy **output_schema** (strukturált, típusos kimenet — nem szabad szöveg), hogy a downstream node-ok és az Evaluation Layer is megbízhatóan tudjon rá hivatkozni.
- **Task → Graph feloldás**: egy `TaskDescriptor` (pl. `{"task_type": "curriculum_generation", ...}`) egy `GraphRegistry`-n keresztül old fel egy konkrét `AgentGraphSpec`-re. Kezdetben lehet 1:1 statikus megfeleltetés (task_type → graph_id), később bővíthető szabály-alapú vagy LLM-alapú kiválasztásra.
- A végrehajtó motor (executor) a `depends_on` gráf alapján automatikusan eldönti, mely node-ok futtathatók párhuzamosan (nincs egymás közötti függőség) — ez természetesen általánosítja a jelenlegi tisztán szekvenciális végrehajtást.

### 3.B Model Selection Layer

**Cél:** ne egy statikus YAML rögzítse előre, melyik node melyik modellt használja — helyette egy **Task Characterization → Model Selection** folyamat döntsön, node-onként, a node FELADATÁNAK jellemzői alapján. Ez formalizálja és általánosítja a jelenlegi "meta-agent" koncepciót (ami eddig csak utólagos, történeti log-elemzésre szorítkozott, nem élő döntéshozatalra).

```python
# Pszeudo-interfész

class TaskCharacteristics:
    creativity_required: float       # 0-1: mennyire nyitott végű / kreatív a feladat
    precision_required: float        # 0-1: mennyire kritikus a pontosság/tényszerűség
    expected_output_length: int      # becsült token-igény
    reasoning_depth_required: float  # 0-1: mennyi többlépéses következtetés kell
    cost_sensitivity: float          # 0-1: mennyire számít a költség ennél a node-nál

class ModelCapabilityProfile:
    model_id: str
    provider: str
    strengths: dict[str, float]      # pl. {"creativity": 0.9, "precision": 0.6, ...}
    cost_per_1k_input: float
    cost_per_1k_output: float
    max_context: int

class ModelSelector(Protocol):
    def select(self, node: AgentNodeSpec, task: TaskCharacteristics,
               registry: list[ModelCapabilityProfile]) -> ModelChoice: ...
```

**Két megvalósítási mód, UGYANAZON interfészen:**
1. **StaticModelSelector** — visszaadja a YAML-ban rögzített modellt (ez a jelenlegi rendszer viselkedésének megfelelője, visszafelé kompatibilitásért és determinisztikus kísérletekért).
2. **DynamicModelSelector** — a `TaskCharacteristics` és a `ModelCapabilityProfile` regiszter alapján, szabály-alapú (pl. súlyozott illesztés) vagy LLM-alapú (a régi meta-agent gondolat élő, döntéshozó változata) modellt választ.

**Kulcsfontosságú tervezési döntés:** a `ModelSelector` interfész NEM tudja, milyen a gráf-topológia (A réteg), és az Evaluation Layer (C réteg) sem tudja, hogyan született a modellválasztás — csak azt kapja meg eredményül, hogy "ez a node ezzel a modellel futott". Ez a fajta szétválasztás teszi lehetővé, hogy a három réteg valóban FÜGGETLENÜL cserélhető legyen.

### 3.C Evaluation Layer

**Cél:** mind a per-agent (node-szintű), mind a kompozit (teljes kísérlet) értékelés **konfigurálható kritérium-készlet** legyen, nem beégetett dimenziólista.

```python
class DimensionScore:
    name: str              # pl. "quality", "cost", "critic_strictness_adjusted_robustness"
    score: float            # 0-100
    weight_eligible: bool   # bekerülhet-e a kompozit számításba
    metadata: dict          # pl. judge indoklás, nyers mérési adatok

class NodeEvaluator(Protocol):
    """Egy node kimenetét értékeli — pluggable kritérium-modul."""
    def evaluate(self, node_id: str, node_output: Any, context: RunContext) -> list[DimensionScore]: ...

class CompositeEvaluator(Protocol):
    """A node-szintű DimensionScore-okból számol egy teljes-kísérlet pontszámot."""
    def compute(self, node_scores: dict[str, list[DimensionScore]],
                weights: dict[str, float]) -> float: ...
```

**Beépítendő NodeEvaluator modulok (a jelenlegi rendszerből átvéve/általánosítva):**
- `LLMJudgeEvaluator` — konfigurálható judge-modellel és rubrika-dimenziókkal (nem beégetett "goal_alignment, logical_consistency, ..." lista, hanem YAML-ből betöltött kritérium-lista).
- `CoverageEvaluator` — ROUGE-L + embedding-alapú szemantikai fedettség, konfigurálható forrás/cél node-párral (nem csak content_writer vs curriculum_designer — bármelyik node-pár közötti fedettség mérhető).
- `StructuralCriticEvaluator` — **ITT KELL MEGOLDANI A CRITIC-TORZÍTÁST**: egy FIX, a pipeline-tól FÜGGETLEN, mindig ugyanazzal a modellel futó kiértékelő olvassa a tényleges kimenetet, és MAGA azonosítja a valós problémákat — nem a pipeline saját (változó modellű) critic node-jának önjelentésére támaszkodik. Ez a réteg architekturálisan különbözik a pipeline `critic` node-jától (ami a FELADAT RÉSZE, a tananyag minőségét javító visszacsatolás), szemben ezzel, ami a MÉRÉS RÉSZE (objektív, állandó mérce).

**Kompozit réteg:**
- Súlyozási képlet és a bevonandó dimenziók YAML-ből konfigurálhatók (nem kódba égetve) — ez oldja meg azt a problémát, hogy a session közben a költség be- majd kikerült a kompozit képletből, ami minden alkalommal kódmódosítást igényelt.
- **Post-hoc elemzési modulok** (Pareto-front, fusion_gain egylépéses baseline-hoz képest, kereszt-judge validáció, node-swap érzékenység, novelty-score) mind a **RunRecord + EvaluationRecord tiszta, verziózott adatmodellre épülnek** (lásd 4. pont), NEM egyedi, ad-hoc szkriptekre és input_id-szuffix hackekre.

---

## 4. Adatmodell — verziózott, nem-patch-elt

**A jelenlegi rendszer legnagyobb szerkezeti gyengesége**: egy run-rekord `evaluation` mezője MUTABLE volt, és utólagos metrikák (diverzitás, novelty, rejudge) append-only JSONL-patch-ekként lettek hozzáfűzve, amiket BETÖLTÉSKOR kellett a helyes sorrendben összefésülni. Ez törékeny (lásd: a rejudge-patch egyszer tévesen felülírta a diverzitást egy placeholder-értékkel, amíg ki nem javítottuk), és minden új metrikatípus új merge-ági logikát igényelt `load_all_runs()`-ban.

**Új modell:**

```python
class RunRecord:
    """Egyetlen kísérlet-végrehajtás, TELJESEN IMMUTABLE a naplózás után."""
    run_id: str
    graph_id: str                    # melyik AgentGraphSpec futott
    model_selection_id: str          # melyik ModelSelectionSpec/döntés-log
    task_input_id: str               # a bemenet stabil azonosítója (NEM szuffixolt verzió!)
    batch_id: str | None             # melyik batch-hez tartozik (ha van)
    attempt_number: int              # hányadik próbálkozás erre a (graph, model_selection, input) hármasra
    node_outputs: dict[str, Any]     # node_id -> strukturált kimenet
    node_metrics: dict[str, NodeMetrics]  # tokens, cost, latency node-onként
    errors: list[str]
    started_at: datetime
    finished_at: datetime

class EvaluationRecord:
    """Egy RunRecord egy értékelése. TÖBB is tartozhat egy run_id-hoz
    (pl. elsődleges + másodlagos judge, vagy egy rejudge új séma-verzióval) —
    NEM patch, hanem ÚJ, önálló rekord, verzió-jelöléssel."""
    evaluation_id: str
    run_id: str
    evaluator_spec_id: str            # melyik EvaluationSpec-cel készült
    node_dimension_scores: dict[str, list[DimensionScore]]
    composite_score: float | None
    created_at: datetime
```

**Ennek előnyei a jelenlegi mechanizmushoz képest:**
- Nincs betöltéskori merge-sorrend-függőség — egy elemzés egyszerűen lekérdezi "az adott run_id-hoz tartozó evaluation_record-ok közül melyiket akarom használni" (pl. legfrissebb, vagy egy adott `evaluator_spec_id` szerint).
- Egy run **több, egymástól független újraértékelése** (elsődleges judge, másodlagos judge, jövőbeli új rubrika) természetesen, ütközés nélkül fér el egymás mellett.
- **Nincs szükség input_id-szuffix hackre** újrafuttatáshoz: az `attempt_number` és `batch_id` mezők natívan kezelik "ez ugyanannak az inputnak egy javított újrafuttatása" esetet — az elemző kód explicit döntheti el (pl. "mindig a legmagasabb attempt_number-ű sikeres futást használd"), nem string-szuffix egyezés alapján.
- **A diverzitás/novelty-számítás csoportosítása** a `task_input_id` (stabil, verzió-mentes) mezőre épül, nem a törékeny, szuffixolt input_id string-egyezésre.

---

## 5. Orchestration & API réteg

**Egyetlen, komponálható végpont-készlet** a jelenlegi hét egyedi célú végpont helyett:

```
POST /experiments/run
  body: {agent_graph_spec_ref, model_selection_spec_ref, evaluation_spec_ref, task_input, batch_id?}
  → egyetlen RunRecord + (ha auto_evaluate) EvaluationRecord

POST /experiments/batch
  body: {agent_graph_spec_ref, model_selection_spec_ref, evaluation_spec_ref, task_inputs: [...], cost_cap_usd}
  → resume-képes, cost-cap-elt batch futtatás (a jelenlegi multi-input logika általánosítva)

POST /evaluations/run
  body: {run_ids: [...], evaluation_spec_ref}
  → ÚJ EvaluationRecord-okat hoz létre a megadott run_id-khoz, a meglévőket NEM írja felül
  (ez helyettesíti a rejudge-batch ÉS a cross-judge végpontot is — a különbség csak az
   evaluation_spec_ref-ben van, nem külön API-ban)

POST /analysis/run
  body: {analysis_type: "pareto_front" | "fusion_gain" | "node_swap_sensitivity" | "diversity" | "novelty", run_ids: [...], params}
  → egységes belépési pont minden post-hoc elemzéshez (ez helyettesíti a diversity-batch,
   single-call-baseline, run-custom végpontok egy részét — a "node-swap" és "single-call
   baseline" valójában egy ALTERNATÍV AgentGraphSpec + /experiments/run hívás, nem külön
   végpont: egy 1-node-os gráf = az egylépéses baseline; egy 5-node-os gráf egyetlen
   node-ja lecserélve = a node-swap variáns).
```

Ez a négy végpont lefedi a jelenlegi ~10 végpont funkcionalitását, mert a **konfigurálhatóság a spec-objektumokban van, nem az API felületben**.

---

## 6. Mit NE ismételjünk meg (konkrét, session alatt tanult hibák)

| Hiba | Következmény | Hogyan kerüljük el |
|---|---|---|
| A Judge csonkította a node-kimeneteket (500-1000 karakter) | A minőség-értékelés <5%-át látta a valós tartalomnak | Az EvaluationSpec sose tartalmazzon hardkódolt karakterlimitet; a node kimenete és a max_tokens sapka legyen a jogosultsági forrás |
| Nem volt max_tokens sapka kezdetben | Kontrollálatlan, 60-160k karakteres kimenetek | Minden AgentNodeSpec-nek KÖTELEZŐ mezője legyen a max_tokens |
| A költség utólag került ki/be a kompozit képletből | Minden alkalommal kódmódosítás + visszamenőleges újraszámolás kellett | A súlyozás és a bevont dimenziók YAML-ből jöjjenek, ne kódba égetve |
| input_id-szuffix hack újrafuttatáshoz | Törékeny, hibalehetőséget adó "melyik verzió érvényes" logika minden elemzésben | `attempt_number`/`batch_id` natív mezők a RunRecord-ban |
| Append-only patch-mechanizmus (diversity/rejudge/novelty patch) | Minden új metrika saját merge-logikát igényelt, egyszer tényleges adatvesztési hibát okozott | Verziózott, többszörös EvaluationRecord run_id-nként |
| `critic_issues_count` modellfüggő szigorúsága torzítja a robustness-t | Egy erősebb critic-modell ront a mért pontszámon | Külön, FIX StructuralCriticEvaluator, elválasztva a pipeline saját critic node-jától |
| Végpont-burjánzás (7+ egyedi célú REST végpont) | Nehezen áttekinthető, minden új képesség új végpontot igényelt | 4 komponálható végpont, ahol a viselkedést a spec-objektumok határozzák meg |

---

## 7. Tesztelési stratégia

- **Minden réteg (Agent Architecture, Model Selection, Evaluation) önállóan, mockolt LLM-hívásokkal tesztelendő** — ez a mintázat kiválóan bevált (166+ teszt, 0 élő hívás a tesztekben az előző session végére).
- Egy **dry-run mód** minden batch-futtatáshoz, ami megbecsüli a várható költséget éles hívás nélkül (a node_configs + a bemenet hossza + a modell árazása alapján), mielőtt valós pénzt költenénk.
- **Cheap smoke test** kötelező lépés minden új képesség után, mielőtt egy nagyobb (10+ eurós) batch-et elindítanánk — ez a mintázat ismételten hasznosnak bizonyult ebben a sessionben.

---

## 8. Migrációs jegyzetek — mi vihető át közvetlenül

| Jelenlegi fájl | Átvihető? | Megjegyzés |
|---|---|---|
| `src/cost_guard.py` | ✅ szinte változtatás nélkül | Már jól elkülönített, tiszta modul |
| `src/diversity_metrics.py` | ✅ kisebb módosítással | A `task_input_id` stabil azonosítóra állítva (nem input_id-szuffix) |
| `src/coverage_metrics.py` | ✅ szinte változtatás nélkül | ROUGE-L + embedding-hasonlóság, már paraméterezhető forrás/cél szöveggel |
| `src/pipeline.py` | ⚠️ újratervezendő | A fix 5-node lánc helyett generikus DAG-executor kell, AgentGraphSpec-ből |
| `src/experiment_runner.py` | ⚠️ újratervezendő | Az orchestration logika (cost-cap, resume) megőrzendő, de a YAML-lookup + patch-mechanizmus lecserélendő a tiszta adatmodellre |
| `src/experiment_evaluator.py` | ⚠️ újratervezendő | A Judge-hívás logika megőrzendő, de konfigurálható rubrika-rendszerré alakítva; a `critic_issues_count` torzítás itt oldandó meg strukturálisan |
| `src/experiment_logger.py` | ❌ újraírandó | A patch-append-merge mechanizmus a fő ok, amiért ez a fájl a legproblémásabb — a verziózott adatmodell (4. pont) ezt teljesen kiváltja |
| `src/api.py` | ⚠️ jelentősen egyszerűsítendő | 7+ végpont → 4 komponálható végpont |
| `scripts/export_for_sheet.py`, `scripts/export_blind_human_eval.py` | ✅ átvihető | Csak az adatforrás-lekérdezést kell az új adatmodellhez igazítani |

---

## 9. Javasolt megvalósítási sorrend

1. Adatmodell (RunRecord, EvaluationRecord) + GCS-perzisztencia (a meglévő mintát követve)
2. Agent Architecture Layer: DAG-validáció + generikus executor, kezdetben egyetlen (a jelenlegivel megegyező, lineáris) AgentGraphSpec-cel
3. Model Selection Layer: StaticModelSelector először (visszafelé kompatibilis viselkedés), DynamicModelSelector második lépésben
4. Evaluation Layer: LLMJudgeEvaluator (konfigurálható rubrikával) + CompositeEvaluator (konfigurálható súlyozással)
5. StructuralCriticEvaluator — a critic-torzítás strukturális javítása
6. Post-hoc elemzési modulok (Pareto, fusion_gain, node-swap, diversity/novelty, kereszt-judge) a tiszta adatmodellre építve
7. API réteg (4 végpont) + orchestration (cost-cap, resume, retry-tolerancia)
8. Export eszközök (TSV, vak human-eval)
9. Egy kis, kontrollált pilot-batch a teljes rendszer végigfuttatására, MIELŐTT a teljes 10×10-es (vagy nagyobb) kísérleti rácsot elindítanánk

Ez a sorrend biztosítja, hogy minden réteg önállóan tesztelhető legyen, mielőtt a következőre építenénk, és hogy a "meg kell őrizni a jelenlegi backend előnyeit" követelmény (cost-cap, GCS, retry-tolerancia, exportálhatóság) már a legelső lépéstől jelen legyen, ne utólagos toldásként.
