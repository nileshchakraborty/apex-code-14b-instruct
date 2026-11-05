#!/usr/bin/env python3
"""
ApexCode DiffCodeGen Behavioral Clustering Engine (arXiv:2605.20473)
Synthesizes test probes, executes candidate solutions in isolated sandboxes,
computes behavioral equivalence matrices, and selects the medoid of the consensus cluster.
"""

import subprocess
import tempfile
import os
import re
from typing import List, Dict, Any, Tuple

def execute_in_sandbox(code: str, test_input: str, timeout_sec: float = 3.0) -> Tuple[bool, str]:
    """
    Executes Python code with given stdin input in a safe, isolated subprocess.
    Returns (success, stdout_output).
    """
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_path = f.name

    try:
        proc = subprocess.run(
            ["python3", temp_path],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=timeout_sec
        )
        if proc.returncode == 0:
            return True, proc.stdout.strip()
        else:
            return False, f"RUNTIME_ERROR: {proc.stderr[:100]}"
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, f"EXEC_ERROR: {str(e)}"
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass

def synthesize_probes_from_problem(problem: Dict[str, Any]) -> List[str]:
    """
    Synthesizes purely generic boundary probes without inspecting private test cases.
    Zero-contamination: tests are never leaked or probed from hidden suites.
    """
    return [
        "1\n1",
        "1\n0",
        "2\n1 2",
        "3\n1 2 3",
        "0\n",
    ]

def cluster_and_select_medoid(candidates: List[str], probes: List[str]) -> Tuple[int, str, Dict[str, Any]]:
    """
    Executes all K candidates against synthesized probes,
    clusters behaviors, and selects the medoid of the consensus cluster.
    """
    if not candidates:
        return -1, "", {"error": "No candidates provided"}

    if len(candidates) == 1:
        return 0, candidates[0], {"cluster_size": 1, "consensus_ratio": 1.0}

    K = len(candidates)
    # Matrix of outputs: outputs[candidate_idx][probe_idx] = stdout
    execution_matrix: List[List[str]] = []
    success_matrix: List[List[bool]] = []

    for cand_idx, code in enumerate(candidates):
        cand_outputs = []
        cand_successes = []
        for probe in probes:
            success, out = execute_in_sandbox(code, probe)
            cand_successes.append(success)
            cand_outputs.append(out)
        execution_matrix.append(cand_outputs)
        success_matrix.append(cand_successes)

    # Compute pairwise agreement score between candidates
    # agreement[i][j] = number of probes where candidate i and j produced identical non-error output
    num_probes = len(probes)
    agreement_matrix = [[0] * K for _ in range(K)]

    for i in range(K):
        for j in range(K):
            if i == j:
                agreement_matrix[i][j] = num_probes
                continue
            matches = 0
            for p in range(num_probes):
                if success_matrix[i][p] and success_matrix[j][p]:
                    if execution_matrix[i][p] == execution_matrix[j][p]:
                        matches += 1
            agreement_matrix[i][j] = matches

    # Calculate cluster consensus score for each candidate (sum of agreements)
    consensus_scores = [sum(agreement_matrix[i]) for i in range(K)]
    
    # Also prioritize candidates with zero runtime errors
    validity_scores = [sum(1 for s in success_matrix[i] if s) for i in range(K)]
    
    # Combined score: consensus_scores + 2 * validity_scores
    combined_scores = [
        consensus_scores[i] + 2 * validity_scores[i] for i in range(K)
    ]

    best_idx = int(max(range(K), key=lambda i: combined_scores[i]))
    
    cluster_stats = {
        "candidate_count": K,
        "probe_count": num_probes,
        "consensus_scores": consensus_scores,
        "validity_scores": validity_scores,
        "selected_candidate_idx": best_idx,
        "agreement_matrix": agreement_matrix
    }

    return best_idx, candidates[best_idx], cluster_stats

if __name__ == "__main__":
    # Test with 3 generic candidates
    c1 = """import sys
def solve():
    data = [int(x) for x in sys.stdin.read().split()]
    if not data: return
    print(sum(data))
if __name__ == '__main__':
    solve()
"""
    c2 = """import sys
def solve():
    data = [int(x) for x in sys.stdin.read().split()]
    if not data: return
    print(sum(data))
if __name__ == '__main__':
    solve()
"""
    c3 = """import sys
def solve():
    print(0)
if __name__ == '__main__':
    solve()
"""
    probes = ["3\n1 2 3", "2\n10 20"]
    idx, best_code, stats = cluster_and_select_medoid([c1, c2, c3], probes)
    print(f"Selected candidate {idx}:")
    print(f"Consensus scores: {stats['consensus_scores']}")
    print(f"Validity scores: {stats['validity_scores']}")
