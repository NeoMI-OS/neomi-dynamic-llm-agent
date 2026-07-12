"""
Diverzitás-metrika: embedding-alapú cosinus-hasonlóság a különböző modell-
kombinációk kimenetei között, ugyanazon input dokumentumon.

Csak több, egymással összevethető futásból számolható — ezért ez mindig egy
batch utáni post-processing lépés, nem az evaluate_run() (egy-futásos)
kontextusának része.
"""
import os
import numpy as np


def embed_text(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """OpenAI embedding egy szövegre. A hosszú kimeneteket biztonságos
    karakterhatárra vágja (kb. 5000 token, jó margóval a 8191 tokenes limit alatt)."""
    from langchain_openai import OpenAIEmbeddings

    embedder = OpenAIEmbeddings(model=model, api_key=os.getenv("OPENAI_API_KEY"))
    truncated = text[:20000]
    return embedder.embed_query(truncated)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    a_vec = np.array(a, dtype=float)
    b_vec = np.array(b, dtype=float)
    denom = np.linalg.norm(a_vec) * np.linalg.norm(b_vec)
    if denom == 0:
        return 0.0
    return float(np.dot(a_vec, b_vec) / denom)


def compute_diversity_for_input(runs_same_input: list[dict]) -> dict:
    """
    runs_same_input: ugyanazon input_id-hez tartozó run_record-ok, különböző
    experiment_id-kkal (a 10 kombináció ugyanazon a dokumentumon).

    Minden run `outputs.content` mezőjét embeddeli, majd páronkénti cosinus-
    hasonlóságot számol. Alacsonyabb átlag-hasonlóság = magasabb diverzitás.

    Visszaad: {"input_id", "pairwise_avg_similarity", "per_experiment_diversity"}
    ahol per_experiment_diversity[exp_id] = 1 - (adott exp átlag-hasonlósága
    az összes többihez), [0, 1] közé szorítva.
    """
    if len(runs_same_input) < 2:
        return {
            "input_id": runs_same_input[0].get("input_id") if runs_same_input else None,
            "pairwise_avg_similarity": None,
            "per_experiment_diversity": {},
        }

    input_id = runs_same_input[0].get("input_id")
    exp_ids = [r["experiment_id"] for r in runs_same_input]
    texts = [r.get("outputs", {}).get("content", "") or "" for r in runs_same_input]
    embeddings = [embed_text(t) for t in texts]

    n = len(embeddings)
    sim_matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                sim_matrix[i][j] = cosine_similarity(embeddings[i], embeddings[j])

    all_pairs = [sim_matrix[i][j] for i in range(n) for j in range(n) if i != j]
    pairwise_avg = sum(all_pairs) / len(all_pairs) if all_pairs else 0.0

    per_experiment_diversity = {}
    for i, exp_id in enumerate(exp_ids):
        others = [sim_matrix[i][j] for j in range(n) if j != i]
        avg_sim_to_others = sum(others) / len(others) if others else 0.0
        per_experiment_diversity[exp_id] = max(0.0, min(1.0, 1.0 - avg_sim_to_others))

    return {
        "input_id": input_id,
        "pairwise_avg_similarity": pairwise_avg,
        "per_experiment_diversity": per_experiment_diversity,
    }


def compute_novelty_vs_baseline(runs_same_input: list[dict], baseline_experiment_id: str) -> dict:
    """
    Novelty score (Phase 2): mennyire tér el az egyes kísérletek kimenete a
    kitüntetett "naiv" baseline stratégiától (alapértelmezésben exp-001,
    trivial_strongest) ugyanazon a dokumentumon, embedding-alapú cosinus-
    távolsággal.

    Ez KIEGÉSZÍTI, nem helyettesíti a compute_diversity_for_input()-ot: az ottani
    diverzitás az ÖSSZES kombináció EGYMÁSHOZ viszonyított átlagos különbözőségét
    méri ("mennyire más ez, mint az átlagos többi stratégia"), míg ez a novelty
    egy KONKRÉT, kitüntetett referenciához viszonyítva méri az eltérést
    ("mennyire más ez, mint amit alapból, kreativitás nélkül csinálnánk").

    Visszaad: {experiment_id: novelty_score (0-1)} -- a baseline saját maga nem
    szerepel benne (novelty vs. önmaga értelmetlen). Üres dict, ha a baseline
    nem található a csoportban.
    """
    baseline = next((r for r in runs_same_input if r.get("experiment_id") == baseline_experiment_id), None)
    if baseline is None:
        return {}

    baseline_text = baseline.get("outputs", {}).get("content", "") or ""
    baseline_emb = embed_text(baseline_text)

    result = {}
    for r in runs_same_input:
        exp_id = r.get("experiment_id")
        if exp_id == baseline_experiment_id:
            continue
        text = r.get("outputs", {}).get("content", "") or ""
        emb = embed_text(text)
        sim = cosine_similarity(baseline_emb, emb)
        result[exp_id] = max(0.0, min(1.0, 1.0 - sim))
    return result
