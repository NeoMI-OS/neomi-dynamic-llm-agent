# NeoMI – Modell Kombinációs Kísérletek

Ez a könyvtár tartalmazza a NeoMI Core multi-agent pipeline modell-kombinációs kísérleteit.

## Pipeline Architektúra

```
Context Analyst → Needs Analyzer → Curriculum Designer → Content Writer → Critic
```

Minden node-hoz külön LLM rendelhető (provider + model + temperature).

## Kísérletek Összefoglalója

| ID | Stratégia | Hipotézis röviden |
|----|-----------|-------------------|
| exp-001 | Trivial Strongest (OpenAI) | GPT-4o mindenhol – felső minőségi határ, magas cost |
| exp-002 | Trivial Strongest (Anthropic) | Claude Opus mindenhol – kreatív alternatív baseline |
| exp-003 | Kognitív Specializáció | Szerepalapú hozzárendelés – ~baseline Q, 40–60% cost csökkentés |
| exp-004 | Költség-optimalizált | Erős modell csak kritikus node-okon – legjobb ROI jelölt |
| exp-005 | Kognitív Diverzitás | Provider-rotáció – legjobb Diversity & Novelty pontszám |
| exp-006 | Szándékos Eltérés | Deliberate mismatch – Critic hit rate +15–20% |
| exp-007 | Writer-Heavy | Legjobb modell az output node-okon – User-élmény maximalizálás |
| exp-008 | Analyst-Heavy | GIGO: befektetés az input node-okra – exp-007 ablációs párja |
| exp-009 | Ultra Költség-hatékony | Performance cliff keresés – 80–90% cost csökkentés |
| exp-010 | Hibrid Eszkaláció | Confidence-based routing – legjobb átlagos Q/Cost arány |

## Értékelési Keretrendszer

```
Final_Score = (0.4 × Quality) + (0.2 × (1/Cost)) + (0.15 × (1/Latency)) + (0.15 × Robustness) + (0.1 × Diversity)
```

Részletek: [`evaluation_framework.yaml`](evaluation_framework.yaml)

## Futtatás

```bash
# Kísérlet futtatása (API endpoint)
POST /pipeline/experiments
{
  "experiment_id": "exp-003",
  "input_document": "...",
  "purpose": "..."
}
```

## Referencia Dokumentumok

- `NeoMI_Handbook.docx` – Model Selection & Optimization Handbook
- `modelcombinationexperiments.md.docx` – 8-kísérlet sprint tervdokumentum
- `hogyan_lehet_kiertékelni_a_compound_modelleket.docx` – Compound model értékelési metodológia
- `AIOS_Konyv_I_Fejezet.docx` – AI Operating Systems architektúra

## Várható Kimenetel

A Pareto-fronton várhatóan **exp-003** (Specializáció) és **exp-007** (Writer-Heavy)
versenyeznek majd a legjobb Q/Cost arányért. **exp-010** (Hibrid Eszkaláció) production
kontextusban a legjobb hosszú távú megoldás, de a legkomplexebb implementációt igényli.
