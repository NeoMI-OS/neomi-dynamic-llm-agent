"""
Fedettségi (coverage) metrikák: mennyire fedi le a content_writer kimenete a
curriculum_designer által megtervezett struktúrát.

Ebben a projektben nincs külső gold-standard referencia dokumentum (nyitott
tananyag-generálás, nem ismert forráshoz képesti összefoglalás) — ezért a
ROUGE-L/BERTScore-t NEM egy külső referenciához, hanem a pipeline SAJÁT
tervezési lépéséhez (curriculum_designer kimenete) hasonlítjuk, ugyanazon
futáson belül: ez egy faithfulness/coverage-ellenőrzés ("a megírt tartalom
tényleg lefedi-e, amit a terv előírt?"), nem klasszikus referencia-alapú
NLG-metrika.

A "BERTScore" itt NEM a bert-score csomagot használja (az torch-függőséget
hozna be, amit korábban a diverzitás-metrikánál is szándékosan elkerültünk) —
helyette a diversity_metrics.py-ban már meglévő OpenAI embedding + cosinus-
hasonlóság adja a szemantikai hasonlóság proxy-ját.
"""
import re
from diversity_metrics import embed_text, cosine_similarity


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", (text or "").lower())


def rouge_l_f1(reference: str, hypothesis: str) -> float:
    """Longest Common Subsequence alapú ROUGE-L F1, szóhatáron tokenizálva."""
    ref = _tokenize(reference)
    hyp = _tokenize(hypothesis)
    if not ref or not hyp:
        return 0.0

    n, m = len(ref), len(hyp)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            if ref[i - 1] == hyp[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    lcs = dp[n][m]

    precision = lcs / m
    recall = lcs / n
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def semantic_similarity_score(reference: str, hypothesis: str) -> float:
    """Embedding-alapú szemantikai hasonlóság (BERTScore proxy), [0, 1]."""
    if not reference or not hypothesis:
        return 0.0
    ref_emb = embed_text(reference)
    hyp_emb = embed_text(hypothesis)
    return max(0.0, min(1.0, cosine_similarity(ref_emb, hyp_emb)))


def compute_coverage_for_run(curriculum_text: str, content_text: str) -> dict:
    """Egy futás fedettségi metrikái: mennyire fedi le a content_writer
    kimenete a curriculum_designer tervét."""
    return {
        "rouge_l": round(rouge_l_f1(curriculum_text, content_text), 4),
        "semantic_similarity": round(semantic_similarity_score(curriculum_text, content_text), 4),
    }
