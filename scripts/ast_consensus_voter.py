#!/usr/bin/env python3
"""Canonical AST Hash Consensus Voter (Unsupervised Self-Consistency).

Implements unsupervised majority voting over K candidate solutions (Wang et al., 2022; Chen et al., 2023)
without executing test cases:
1. Generates K=3 diverse candidates using Min-P sampling (temp=0.2, min_p=0.05).
2. Normalizes variable names, identifiers, and syntax trees into a canonical AST representation.
3. Groups candidates into equivalence clusters via canonical AST SHA256 hashes.
4. Selects the consensus candidate representing the majority algorithmic structure.
5. Breaks ties using static Semantic Bug Scanner and Contract Linter scores.
"""

import ast
import hashlib
from collections import Counter
from typing import Dict, List, Optional, Tuple, Any

try:
    from scripts.ast_contract_compiler import audit_semantic_bugs, verify_contract_coverage
    from scripts.clean_decoding_pipeline import query_calibrated_model, extract_python_code, CODE_MODEL
except ImportError:
    from ast_contract_compiler import audit_semantic_bugs, verify_contract_coverage
    from clean_decoding_pipeline import query_calibrated_model, extract_python_code, CODE_MODEL


# ==============================================================================
# CANONICAL AST NORMALIZER
# ==============================================================================

class CanonicalASTNormalizer(ast.NodeTransformer):
    """Normalizes AST variable names and structure to identify algorithmic equivalence."""

    def __init__(self):
        super().__init__()
        self.var_map: Dict[str, str] = {}
        self.var_counter = 0
        self.preserved_names = {
            "solve", "main", "Solution", "__init__", "__name__", "__main__",
            "self", "Contract", "sys", "math", "collections", "itertools",
            "heapq", "bisect", "typing", "List", "Dict", "Optional", "Set",
            "Tuple", "Any", "int", "str", "float", "bool", "len", "range",
            "print", "min", "max", "sum", "abs", "sorted", "map", "filter",
        }

    def _get_canonical_name(self, original: str) -> str:
        if original in self.preserved_names or original.startswith("__"):
            return original
        if original not in self.var_map:
            self.var_map[original] = f"var_{self.var_counter}"
            self.var_counter += 1
        return self.var_map[original]

    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = self._get_canonical_name(node.id)
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        node.arg = self._get_canonical_name(node.arg)
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if node.name not in self.preserved_names:
            node.name = self._get_canonical_name(node.name)
        # Strip docstring to ensure structural comparison
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
            if isinstance(node.body[0].value.value, str):
                node.body = node.body[1:]
        self.generic_visit(node)
        return node


def compute_canonical_ast_hash(code_str: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse, normalize, and hash the canonical AST structure of a Python program."""
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return None, f"SyntaxError: {e.msg}"

    normalizer = CanonicalASTNormalizer()
    normalized_tree = normalizer.visit(tree)
    ast.fix_missing_locations(normalized_tree)

    # Dump structure without line numbers or source positions
    dump_str = ast.dump(normalized_tree, annotate_fields=False, include_attributes=False)
    ast_hash = hashlib.sha256(dump_str.encode("utf-8")).hexdigest()[:16]
    return ast_hash, None


# ==============================================================================
# CONSENSUS VOTER ENGINE
# ==============================================================================

def select_consensus_candidate(candidates: List[str]) -> Dict[str, Any]:
    """Select the majority consensus candidate from a list of generated solutions."""
    scored_candidates = []

    for idx, code in enumerate(candidates):
        ast_hash, err = compute_canonical_ast_hash(code)
        semantic_report = audit_semantic_bugs(code)
        contract_report = verify_contract_coverage(code)

        # Quality score: 100 base, penalize semantic bugs and syntax errors
        quality_score = 100
        if not semantic_report.get("clean", True):
            quality_score -= 40 * len(semantic_report.get("bugs", []))
        if not semantic_report.get("ast_valid", True):
            quality_score = 0
        if contract_report.get("passed_linter", False):
            quality_score += 10

        scored_candidates.append({
            "index": idx,
            "code": code,
            "ast_hash": ast_hash,
            "ast_error": err,
            "quality_score": quality_score,
            "semantic_bugs": semantic_report.get("bugs", []),
            "contract_passed": contract_report.get("passed_linter", False),
        })

    # Group by valid AST hashes
    hash_counts = Counter(
        c["ast_hash"] for c in scored_candidates if c["ast_hash"] is not None
    )

    if hash_counts:
        majority_hash, count = hash_counts.most_common(1)[0]
        majority_cluster = [c for c in scored_candidates if c["ast_hash"] == majority_hash]
        # Pick the highest quality member in majority cluster
        majority_cluster.sort(key=lambda x: x["quality_score"], reverse=True)
        winner = majority_cluster[0]
        consensus_strength = count / len(candidates)
    else:
        # Fallback if all have syntax errors or no hashes: pick highest score
        scored_candidates.sort(key=lambda x: x["quality_score"], reverse=True)
        winner = scored_candidates[0]
        consensus_strength = 0.0

    return {
        "winner_code": winner["code"],
        "winner_index": winner["index"],
        "winner_hash": winner["ast_hash"],
        "consensus_strength": consensus_strength,
        "total_candidates": len(candidates),
        "cluster_distribution": dict(hash_counts),
        "winner_quality_score": winner["quality_score"],
        "winner_semantic_bugs": winner["semantic_bugs"],
    }


def generate_with_ast_consensus(
    prompt: str,
    system_prompt: Optional[str] = None,
    k: int = 3,
    model: str = CODE_MODEL,
) -> Dict[str, Any]:
    """Generate K=3 candidates via Min-P sampling and select the canonical AST consensus winner."""
    candidates = []
    total_tokens = 0
    total_latency = 0.0

    for _ in range(k):
        res = query_calibrated_model(
            prompt=prompt,
            system_prompt=system_prompt,
            mode="calibrated",  # temp=0.2, min_p=0.05
            model=model,
            max_tokens=1536,
        )
        code = extract_python_code(res.get("content", ""))
        candidates.append(code)
        total_tokens += res.get("tokens", 0)
        total_latency += res.get("latency_sec", 0.0)

    consensus_res = select_consensus_candidate(candidates)
    consensus_res["total_tokens"] = total_tokens
    consensus_res["total_latency_sec"] = round(total_latency, 2)
    return consensus_res


def _test_ast_consensus():
    print("🧪 Testing Canonical AST Hash Consensus Voter...")

    # Candidate 1 and Candidate 2 have different variable names but IDENTICAL algorithmic structure
    cand1 = """
def solve():
    n = 10
    total = 0
    for i in range(n):
        total += i
    print(total)
"""
    cand2 = """
def solve():
    limit = 10
    acc = 0
    for idx in range(limit):
        acc += idx
    print(acc)
"""
    # Candidate 3 has a different algorithm (closed-form formula)
    cand3 = """
def solve():
    n = 10
    total = n * (n - 1) // 2
    print(total)
"""
    h1, _ = compute_canonical_ast_hash(cand1)
    h2, _ = compute_canonical_ast_hash(cand2)
    h3, _ = compute_canonical_ast_hash(cand3)

    print(f"  Cand1 Canonical Hash: {h1}")
    print(f"  Cand2 Canonical Hash: {h2}")
    print(f"  Cand3 Canonical Hash: {h3}")

    assert h1 == h2, "Canonical AST Normalizer must identify cand1 and cand2 as identical!"
    assert h1 != h3, "Cand3 should have a distinct structural hash!"
    print("  ✅ Canonical AST Hash equivalence verified across diverse identifier names.")

    consensus = select_consensus_candidate([cand1, cand2, cand3])
    print(f"  Consensus winner index: {consensus['winner_index']} (Strength: {consensus['consensus_strength']:.2f})")
    assert consensus["consensus_strength"] >= 0.66
    assert consensus["winner_hash"] == h1

    print("🎉 Canonical AST Hash Consensus Voter verified successfully!")


if __name__ == "__main__":
    _test_ast_consensus()
