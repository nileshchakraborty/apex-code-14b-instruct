#!/usr/bin/env python3
"""Hierarchical Invariant Archetype Taxonomy & Synthetic Diagnostic Engine.

Provides:
1. Multi-pillar domain archetype classifier for System 1 (Fast-Path Invariant Priming)
2. Graceful fallback for System 2 (Novel / unmapped logic)
3. Synthetic ACI diagnostic generator for non-traceback failures (deadlocks, OOM kills)
4. Automatic test harness discovery and invocation
"""

import ast
import re
from typing import Optional, Tuple


# ==============================================================================
# HIERARCHICAL 5-PILLAR ARCHETYPE TAXONOMY
# ==============================================================================

ARCHETYPE_SCHEMAS = {
    # --------------------------------------------------------------------------
    # Pillar 1: Stateful Range & Augmented Trees
    # --------------------------------------------------------------------------
    "range_augmented_tree": {
        "name": "Stateful Range & Augmented Search Tree",
        "keywords": [
            r"interval\s*tree", r"augmented.*tree", r"segment\s*tree",
            r"max_high", r"overlapping", r"range\s*query"
        ],
        "schema": (
            "MANDATORY CLRS AUGMENTED TREE INVARIANT CONTRACT:\n"
            "1. Overlap Predicate: Two intervals [a, b] and [c, d] overlap iff (a <= d) and (c <= b).\n"
            "2. Subtree Max Propagation: node.max_high = max(node.high, "
            "node.left.max_high if node.left else -float('inf'), "
            "node.right.max_high if node.right else -float('inf')).\n"
            "3. Left-Subtree Prune: If node.left is not None and node.left.max_high >= q_low, search left subtree.\n"
            "4. Right-Subtree Prune: If node.right is not None and node.low <= q_high, search right subtree.\n"
            "5. Dynamic Oracle: In unit tests, assert tree results match a brute-force O(N) linear filter oracle exactly."
        ),
    },

    # --------------------------------------------------------------------------
    # Pillar 2: Concurrency & Synchronization
    # --------------------------------------------------------------------------
    "concurrency_rwlock": {
        "name": "Fair Concurrency & Mutex Primitives",
        "keywords": [
            r"readwritelock", r"rwlock", r"writer\s*preference",
            r"starvation", r"threading\.condition", r"fair.*lock"
        ],
        "schema": (
            "MANDATORY CONCURRENCY & SYNCHRONIZATION INVARIANT CONTRACT:\n"
            "1. Exclusivity Invariant: Active writers must strictly equal 0 when any readers are active; "
            "active readers must equal 0 when a writer is active.\n"
            "2. Writer Preference: Incoming readers must block if writers_waiting > 0 to prevent writer starvation.\n"
            "3. State Protection: Wrap all state checks and modifications inside with self._lock or Condition.\n"
            "4. Context Managers: Provide read_lock() and write_lock() with proper acquire() and release() in finally.\n"
            "5. Sub-second Timings: In tests, keep sleep delays under 0.05s so test execution finishes in under 1 second."
        ),
    },

    # --------------------------------------------------------------------------
    # Pillar 3: Stateful Caching & Sliding Window Rate Limiting
    # --------------------------------------------------------------------------
    "stateful_cache_lru": {
        "name": "Stateful LRU Cache with Eviction Boundaries",
        "keywords": [
            r"lru\s*cache", r"lrucache", r"max_size.*ttl", r"time-to-live",
            r"cleanup_expired", r"least\s*recently"
        ],
        "schema": (
            "MANDATORY CACHE & EVICTION INVARIANT CONTRACT:\n"
            "1. Capacity Boundary: Eviction occurs if and only if len(cache) > max_size AFTER inserting a new key.\n"
            "   (Example: With max_size=2 and keys 'a', 'b', 'c' inserted, 'a' is evicted, 'b' and 'c' remain).\n"
            "2. OrderedDict Invariant: When using collections.OrderedDict, the least recently used item is at the start (popitem(last=False)).\n"
            "   Upon access (get or update), promote key to most-recently-used using move_to_end(key).\n"
            "3. TTL Expiration: Expired items return None on get(key) and are immediately removed; cleanup_expired() purges all expired keys.\n"
            "4. Thread Safety: Wrap all public methods (get, put, delete, cleanup) in with self._lock (threading.RLock).\n"
            "5. Sub-second Tests: In tests, keep TTL sleep timings under 0.05s so execution completes swiftly."
        ),
    },
    "rate_limiter_sliding_window": {
        "name": "Sliding Window Rate Limiter",
        "keywords": [
            r"sliding\s*window", r"rate\s*limiter", r"ratelimiter",
            r"window_seconds", r"max_requests", r"allow_request"
        ],
        "schema": (
            "MANDATORY SLIDING WINDOW RATE LIMITER INVARIANT CONTRACT:\n"
            "1. Window Invariant: A request at time T is allowed iff count(timestamps in [T - window_seconds, T]) < max_requests.\n"
            "2. Memory Bounding: Prune timestamps older than T - window_seconds on every access to avoid unbounded memory growth.\n"
            "3. Data Structure: Use collections.deque for O(1) popleft() or a monotonic float timestamp list.\n"
            "4. Thread Safety: Synchronize all client state modifications under a lock.\n"
            "5. Sub-second Tests: Use small sub-second test windows (e.g. window_seconds=0.05, sleep=0.06s)."
        ),
    },

    # --------------------------------------------------------------------------
    # Pillar 4: Distributed Consensus & Transaction Protocols
    # --------------------------------------------------------------------------
    "distributed_2pc": {
        "name": "Two-Phase Commit (2PC) Consensus & Transactions",
        "keywords": [
            r"two-phase\s*commit", r"2pc", r"coordinator.*participant",
            r"prepare.*commit.*abort", r"transaction\s*journal"
        ],
        "schema": (
            "MANDATORY TWO-PHASE COMMIT INVARIANT CONTRACT:\n"
            "1. Phase 1 (Prepare): Coordinator broadcasts prepare to all participants. "
            "   If ANY participant returns False or raises an exception, coordinator IMMEDIATELY broadcasts abort to all and returns False.\n"
            "2. Phase 2 (Commit): Coordinator broadcasts commit IF AND ONLY IF ALL participants voted True in Phase 1.\n"
            "3. Participant Idempotence: Participant.abort(tx_id) must be idempotent: if tx_id in pending, delete it; "
            "   if not pending, return True safely (NEVER raise an exception on abort).\n"
            "4. Participant Prepare/Commit: prepare stores uncommitted intent; commit applies intent to state and clears pending.\n"
            "5. Atomicity: Either all participants commit the mutation, or all roll back to previous state.\n"
            "6. Imports: Include `from typing import Dict, List, Optional, Tuple, Any, Set` at top.\n"
            "7. Test Isolation: Use fresh Participant and Coordinator instances for each test case (or define separate helper functions) so that simulated rejections on one test do not contaminate subsequent tests."
        ),
    },
    "distributed_consistent_hash": {
        "name": "Consistent Hashing Ring & Partitioning",
        "keywords": [
            r"consistent\s*hash", r"hash\s*ring", r"virtual\s*nodes",
            r"preference\s*list", r"clockwise"
        ],
        "schema": (
            "MANDATORY CONSISTENT HASH RING INVARIANT CONTRACT:\n"
            "1. Standard Library Only: Use ONLY Python standard library (`bisect`, `hashlib`, `typing`). NEVER import third-party packages like `sortedcontainers`.\n"
            "2. Virtual Node Replication: For physical node S and i in range(virtual_nodes), token = int(hashlib.md5(f'{S}:{i}'.encode('utf-8')).hexdigest(), 16). Store token -> physical node in a dictionary and maintain sorted tokens in a list.\n"
            "3. Dynamic Node Membership: In add_node(node), insert tokens using bisect.insort; in remove_node(node), remove tokens from both the dictionary and sorted list. If ring has no nodes, get_node(key) returns None and get_preference_list(key, count) returns [].\n"
            "4. Clockwise Lookup: idx = bisect.bisect_right(sorted_tokens, key_hash). If idx == len(sorted_tokens), wrap around to index 0. Return the mapped physical node.\n"
            "5. Preference List: Starting from clockwise idx, walk circularly along sorted_tokens collecting distinct physical nodes until min(count, len(physical_nodes)) distinct nodes are gathered.\n"
            "6. Test Assertions: Populate with nodes=['nodeA', 'nodeB', 'nodeC']. Assert get_node('key1') is not None, assert len(set(get_preference_list('key1', 2))) == 2. In minimal disruption test, record assignments for 10 keys, remove 'nodeC', assert keys that were on 'nodeA' or 'nodeB' are strictly unchanged."
        ),
    },

    # --------------------------------------------------------------------------
    # Pillar 5: Dynamic Programming & String Algorithms
    # --------------------------------------------------------------------------
    "dp_path_reconstruction": {
        "name": "Dynamic Programming with Optimal Path Reconstruction",
        "keywords": [
            r"coin\s*change.*path", r"path\s*reconstruction", r"optimal\s*combination",
            r"minimum\s*coins", r"knapsack.*path"
        ],
        "schema": (
            "MANDATORY DYNAMIC PROGRAMMING INVARIANT CONTRACT:\n"
            "1. Recurrence: dp[i] = min(dp[i - c] + 1) for c in coins if i >= c and dp[i - c] != inf.\n"
            "2. Path Tracking: Track parent or chosen coin in parent_coin[i] to backtrack the exact combination.\n"
            "3. Base Cases: dp[0] = 0 (returns (0, [])); unreachable amount returns (-1, []).\n"
            "4. Dynamic Verification: In tests, verify DP against a recursive brute-force oracle on small amounts."
        ),
    },
    "unicode_frequency_string": {
        "name": "Unicode String Normalization & Frequency Mapping",
        "keywords": [
            r"anagram", r"unicode.*frequency", r"is_anagram", r"case-insensitive",
            r"string\s*normalization"
        ],
        "schema": (
            "MANDATORY STRING & UNICODE INVARIANT CONTRACT:\n"
            "1. Normalization: Strip leading/trailing whitespace. If ignore_case is True, use s.casefold() or s.lower().\n"
            "2. Unicode Safety: Support arbitrary Unicode code points (accents, emojis) using collections.Counter.\n"
            "3. Edge Cases: Empty strings are anagrams of empty strings; mismatched string lengths immediately return False."
        ),
    },
    "logarithmic_median_partition": {
        "name": "Logarithmic Binary Search Partitioning",
        "keywords": [
            r"median\s*of\s*two\s*sorted", r"log\(min\(m,\s*n\)\)", r"find_median_sorted_arrays"
        ],
        "schema": (
            "MANDATORY LOGARITHMIC PARTITION INVARIANT CONTRACT:\n"
            "1. Binary Search Range: Always binary search on the shorter array nums1 (ensure len(nums1) <= len(nums2)).\n"
            "2. Partition Invariant: partitionX + partitionY == (m + n + 1) // 2.\n"
            "3. Valid Partition Condition: maxLeftX <= minRightY and maxLeftY <= minRightX.\n"
            "4. Parity: If (m + n) is odd, median = max(maxLeftX, maxLeftY); if even, avg(max(lefts), min(rights)).\n"
            "5. Dynamic Oracle: In tests, verify against sorted(a + b) oracle across empty, single-element, and even/odd arrays."
        ),
    },
}


def classify_archetype(prompt: str) -> Tuple[Optional[str], Optional[str]]:
    """Inspect prompt tokens and return (archetype_id, schema) if matched, else (None, None)."""
    p_lower = prompt.lower()
    for arch_id, data in ARCHETYPE_SCHEMAS.items():
        for pattern in data["keywords"]:
            if re.search(pattern, p_lower):
                return arch_id, data["schema"]
    return None, None


# ==============================================================================
# NON-TRACEBACK SYNTHETIC DIAGNOSTIC ENGINE (ACI)
# ==============================================================================

def generate_synthetic_diagnostic_frame(
    failure_category: str,
    raw_stderr: str,
    code_str: str,
    exit_code: int = -1,
) -> dict:
    """Produce structured ACI diagnostic frames for non-traceback failures (deadlock, OOM, timeouts)."""
    frame = {
        "status": "FAILED",
        "failure_type": failure_category or "RuntimeError",
        "exit_code": exit_code,
        "failing_function": None,
        "failing_line_number": None,
        "failing_code_snippet": None,
        "exception_message": raw_stderr.strip() if raw_stderr else "Execution failed without stderr",
        "raw_traceback": raw_stderr,
        "remediation_guidance": "",
    }

    if failure_category == "DeadlockOrTimeout" or exit_code == 124:
        frame["failure_type"] = "DeadlockOrInfiniteLoop"
        frame["exception_message"] = "Execution timed out (suspected thread lock deadlock, condition wait, or infinite loop)."
        frame["remediation_guidance"] = (
            "- Ensure every acquired lock is released via a `with self._lock:` context manager.\n"
            "- Check all `threading.Condition` waits; ensure `notify()` or `notify_all()` is called on state changes.\n"
            "- Ensure test sleep timings do not exceed 0.05s."
        )
        # Attempt to find while loops or lock acquires in code
        lines = code_str.split("\n")
        for idx, line in enumerate(lines, 1):
            if re.search(r"\bwhile\b|\.acquire\(", line):
                frame["failing_line_number"] = idx
                frame["failing_code_snippet"] = line.strip()
                break

    elif failure_category == "OutOfMemoryAllocation" or exit_code == 137:
        frame["failure_type"] = "OutOfMemoryAllocation"
        frame["exception_message"] = "Process exceeded 512 MB memory boundary and was terminated by cgroups (SIGKILL)."
        frame["remediation_guidance"] = (
            "- Do not allocate large arrays, buffers, or pre-computed lists in memory.\n"
            "- Use generators or stream items iteratively.\n"
            "- Ensure data structures clean up stale nodes or items."
        )

    return frame


# ==============================================================================
# TEST HARNESS AUTO-DISCOVERY & TIMING HARDENER
# ==============================================================================

def wrap_code_with_auto_test_runner(code_str: str) -> str:
    """Ensure test functions and test classes are automatically invoked if __main__ is missing."""
    try:
        tree = ast.parse(code_str)
    except SyntaxError:
        return code_str

    has_main = False
    test_functions = []
    has_unittest_classes = False

    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            # Check for if __name__ == '__main__':
            try:
                comp = node.test
                if isinstance(comp, ast.Compare) and getattr(comp.left, "id", None) == "__name__":
                    has_main = True
            except Exception:
                pass
        elif isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            test_functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            for base in node.bases:
                if getattr(base, "id", None) == "TestCase" or getattr(base, "attr", None) == "TestCase":
                    has_unittest_classes = True

    # If code already has a runnable __main__, return as is
    if has_main:
        return code_str

    harness = "\n\n# --- AUTO-DISCOVERED TEST HARNESS INVOCATION ---\n"
    harness += "if __name__ == '__main__':\n"
    if has_unittest_classes:
        harness += "    import unittest\n    unittest.main(exit=False)\n"
    elif test_functions:
        harness += "    print('Running auto-discovered test functions...')\n"
        for fn in test_functions:
            harness += f"    {fn}()\n"
        harness += "    print('All auto-discovered tests passed.')\n"
    else:
        # Check if there are top-level asserts
        return code_str

    return code_str + harness
