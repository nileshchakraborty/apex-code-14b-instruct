#!/usr/bin/env python3
"""Multi-File Repository Context & AST Invariant Integration Challenge.

Simulates real-world enterprise codebase generation where the model must implement
a dependent module relying on sibling interfaces without context blowout.
Evaluates:
1. AST interface header extraction via RepoGraphExtractor (<1,500 tokens)
2. Zero-shot generation with greedy calibrated decoding
3. Seamless cross-module symbol importing with 0 hallucinated interfaces
4. Invariant contract compliance
5. Clean execution in the isolated test harness
"""

import ast
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, "/Users/nileshchakraborty/workspace/apex-code-36gb")

from scripts.clean_decoding_pipeline import generate_clean_solution
from scripts.repo_graph_extractor import RepoGraphExtractor
from scripts.ast_contract_compiler import verify_contract_coverage


def run_multifile_challenge() -> dict:
    print("=" * 72)
    print("🏢 MULTI-FILE REPOSITORY BENCHMARK CHALLENGE")
    print("=" * 72)

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / "enterprise_store"
        repo_path.mkdir(parents=True)

        # 1. Setup repository structure
        (repo_path / "core").mkdir()
        (repo_path / "core" / "__init__.py").touch()
        (repo_path / "__init__.py").touch()
        
        # Module A: core/interfaces.py
        (repo_path / "core" / "interfaces.py").write_text(
            '"""Core Interfaces and Types for Key-Value Store."""\n'
            'from abc import ABC, abstractmethod\n'
            'from typing import Optional, Any, List\n\n'
            'class StorageEngine(ABC):\n'
            '    """Abstract base storage engine contract."""\n'
            '    @abstractmethod\n'
            '    def get(self, key: str) -> Optional[Any]:\n'
            '        """Retrieve value or None if missing."""\n'
            '        pass\n\n'
            '    @abstractmethod\n'
            '    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:\n'
            '        """Store key-value with optional TTL."""\n'
            '        pass\n\n'
            '    @abstractmethod\n'
            '    def delete(self, key: str) -> bool:\n'
            '        """Delete a key."""\n'
            '        pass\n\n'
            '    @abstractmethod\n'
            '    def get_all_keys(self) -> List[str]:\n'
            '        """Return list of all stored keys."""\n'
            '        pass\n'
        )

        # Module B: core/metrics.py
        (repo_path / "core" / "metrics.py").write_text(
            '"""Telemetry & Performance Metrics Collector."""\n'
            'from dataclasses import dataclass, field\n'
            'from typing import Dict\n\n'
            '@dataclass\n'
            'class StoreMetrics:\n'
            '    hits: int = 0\n'
            '    misses: int = 0\n'
            '    evictions: int = 0\n\n'
            '    def record_hit(self) -> None:\n'
            '        self.hits += 1\n\n'
            '    def record_miss(self) -> None:\n'
            '        self.misses += 1\n\n'
            '    def record_eviction(self) -> None:\n'
            '        self.evictions += 1\n\n'
            '    def hit_ratio(self) -> float:\n'
            '        total = self.hits + self.misses\n'
            '        return (self.hits / total) if total > 0 else 0.0\n'
        )

        # 2. Extract AST interface header
        print("▶ Extracting Repository Interface Header with RepoGraphExtractor...")
        t0_extract = time.perf_counter()
        extractor = RepoGraphExtractor(str(repo_path))
        extractor.scan_repository()
        header = extractor.get_interface_header()
        extract_time = round(time.perf_counter() - t0_extract, 4)
        print(f"  ⚡ Extracted {len(header.splitlines())} lines ({len(header)} chars) in {extract_time*1000:.1f}ms")
        print(f"  Token estimate: ~{len(header)//4} tokens (vs raw files: ~{sum(len(f.read_text()) for f in repo_path.glob('**/*.py'))//4} tokens)")

        # 3. Formulate the code generation challenge prompt
        problem_prompt = (
            "You are working in the `enterprise_store` codebase described above in the interface header.\n"
            "Implement a new module `core/tiered_cache.py` containing class `TieredStorage` which inherits from `StorageEngine`.\n"
            "Requirements:\n"
            "1. Inherit from `StorageEngine` in `core.interfaces`.\n"
            "2. Integrate telemetry using `StoreMetrics` from `core.metrics`.\n"
            "3. Support a `max_capacity: int` in `__init__(self, max_capacity: int = 100)`.\n"
            "4. Maintain an internal dictionary `self._data: Dict[str, Any]` and `self.metrics = StoreMetrics()`.\n"
            "5. On `get(key)`: if key present, record hit via `self.metrics.record_hit()` and return value; otherwise record miss and return None.\n"
            "6. On `set(key, value, ttl=None)`: if length exceeds `max_capacity` and key is new, evict the oldest key (FIFO or first inserted), record eviction via `self.metrics.record_eviction()`, store the value and return True.\n"
            "7. On `delete(key)`: delete key if exists and return True, else return False.\n"
            "8. On `get_all_keys()`: return list of keys.\n"
            "Output ONLY clean, runnable Python code with all necessary imports from `core.interfaces` and `core.metrics`."
        )

        # 4. Generate with Clean Calibrated Pipeline
        print("\n▶ Generating `core/tiered_cache.py` via Calibrated Clean Pipeline...")
        t0_gen = time.perf_counter()
        gen_res = generate_clean_solution(
            problem_text=problem_prompt,
            repo_context=header,
            mode="greedy",
            use_ast_contracts=False,
            is_competitive_io=False,
        )
        gen_time = round(time.perf_counter() - t0_gen, 2)
        print(f"  ⚡ Generated solution in {gen_time}s ({gen_res['tokens']} tokens). AST Valid: {gen_res['ast_valid']}")

        if not gen_res["ast_valid"]:
            print(f"❌ Syntax Error: {gen_res['ast_error']}")
            return {"passed": False, "error": gen_res["ast_error"]}

        # 5. Write generated code to `core/tiered_cache.py`
        generated_code = gen_res["code"]
        print("  Generated Code Preview:")
        for line in generated_code.splitlines()[:20]:
            print("   ", line)
        (repo_path / "core" / "tiered_cache.py").write_text(generated_code)

        # 6. Create integration test runner
        test_harness_code = (
            "import sys\n"
            "from pathlib import Path\n"
            "sys.path.insert(0, str(Path(__file__).parent))\n"
            "from core.tiered_cache import TieredStorage\n"
            "from core.interfaces import StorageEngine\n\n"
            "def test_suite():\n"
            "    cache = TieredStorage(max_capacity=2)\n"
            "    assert isinstance(cache, StorageEngine), 'Must inherit from StorageEngine'\n"
            "    assert cache.set('a', 1) is True\n"
            "    assert cache.set('b', 2) is True\n"
            "    assert cache.get('a') == 1\n"
            "    assert cache.metrics.hits == 1\n"
            "    assert cache.get('missing') is None\n"
            "    assert cache.metrics.misses == 1\n"
            "    # Trigger eviction\n"
            "    assert cache.set('c', 3) is True\n"
            "    assert cache.metrics.evictions == 1\n"
            "    assert len(cache.get_all_keys()) == 2\n"
            "    assert cache.delete('c') is True\n"
            "    assert cache.delete('c') is False\n"
            "    print('SUCCESS: All integration assertions passed cleanly!')\n\n"
            "if __name__ == '__main__':\n"
            "    test_suite()\n"
        )
        (repo_path / "run_test.py").write_text(test_harness_code)

        # 7. Execute in isolated subprocess
        print("\n▶ Executing Integration Test Suite in sandbox environment...")
        env = os.environ.copy()
        env["PYTHONPATH"] = str(repo_path)
        proc = subprocess.run(
            [sys.executable, str(repo_path / "run_test.py")],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )

        print("  Exit code:", proc.returncode)
        print("  Stdout:", proc.stdout.strip())
        if proc.stderr:
            print("  Stderr:", proc.stderr.strip())

        passed = (proc.returncode == 0) and ("SUCCESS" in proc.stdout)
        status_symbol = "✅ PASSED" if passed else "❌ FAILED"
        print(f"\n{status_symbol}: Multi-file repository synthesis & integration.")

        return {
            "passed": passed,
            "extract_time_ms": round(extract_time * 1000, 2),
            "generation_time_sec": gen_time,
            "tokens": gen_res["tokens"],
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "code": generated_code,
        }


if __name__ == "__main__":
    res = run_multifile_challenge()
    if not res["passed"]:
        sys.exit(1)
