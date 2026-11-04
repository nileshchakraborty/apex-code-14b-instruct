#!/usr/bin/env python3
"""AST Typed Invariant Contract Engine & Structural Contract Linter.

Provides:
1. Production Contract primitives: Contract.pre(), Contract.post(), Contract.invariant()
2. Structural AST Contract Linter to enforce that generated code embeds binding constraints
3. Prompt contract injectors to instruct models to synthesize binding AST contracts
"""

import ast
from typing import Dict, List, Optional, Tuple, Any


# ==============================================================================
# PRODUCTION RUNTIME CONTRACT RUNTIME
# ==============================================================================

CONTRACT_RUNTIME_CODE = """
class Contract:
    @staticmethod
    def pre(condition: bool, msg: str = "Precondition violated"):
        if not condition:
            raise ValueError(f"Contract Precondition Violated: {msg}")

    @staticmethod
    def post(condition: bool, msg: str = "Postcondition violated"):
        if not condition:
            raise AssertionError(f"Contract Postcondition Violated: {msg}")

    @staticmethod
    def invariant(condition: bool, msg: str = "Invariant violated"):
        if not condition:
            raise AssertionError(f"Contract Invariant Violated: {msg}")
""".strip()


# ==============================================================================
# AST STRUCTURAL CONTRACT LINTER
# ==============================================================================

class ContractVisitor(ast.NodeVisitor):
    """Inspects AST nodes for preconditions, postconditions, and class invariants."""

    def __init__(self):
        self.functions_found = 0
        self.precondition_count = 0
        self.postcondition_count = 0
        self.class_invariants_found = 0
        self.classes_found = 0
        self.current_class: Optional[str] = None
        self.violations: List[str] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        if node.name in ("Contract", "Contracts"):
            # Skip the helper definition itself
            return
        self.classes_found += 1
        has_invariant_method = False
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                if item.name in ("__invariant__", "check_invariants", "validate_state"):
                    has_invariant_method = True
                    self.class_invariants_found += 1
        if not has_invariant_method:
            self.violations.append(f"Class '{node.name}' lacks an explicit __invariant__() state validation method.")
        old_class = self.current_class
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self.current_class in ("Contract", "Contracts"):
            return
        # Exclude private helpers, dunder methods (except __init__), and tests
        if node.name.startswith("test_") or (node.name.startswith("__") and node.name != "__init__"):
            self.generic_visit(node)
            return

        self.functions_found += 1
        has_pre = False
        has_post = False

        # Scan initial statements for Contract.pre / assert / ValueError checks
        for stmt in node.body:
            # Check Contract.pre(...) or Contract.post(...)
            if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                func = stmt.value.func
                if isinstance(func, ast.Attribute) and getattr(func.value, "id", None) == "Contract":
                    if func.attr in ("pre", "require"):
                        has_pre = True
                        self.precondition_count += 1
                    elif func.attr in ("post", "ensure"):
                        has_post = True
                        self.postcondition_count += 1

            # Check explicit assert or if not ... raise ValueError (valid precondition idioms)
            elif isinstance(stmt, ast.Assert):
                has_pre = True
                self.precondition_count += 1
            elif isinstance(stmt, ast.If):
                # Check for if not condition: raise (ValueError|TypeError|KeyError)
                for handler in stmt.body:
                    if isinstance(handler, ast.Raise):
                        has_pre = True
                        self.precondition_count += 1
                        break

        # Check return statements for postconditions
        for sub in ast.walk(node):
            if isinstance(sub, ast.Expr) and isinstance(sub.value, ast.Call):
                func = sub.value.func
                if isinstance(func, ast.Attribute) and getattr(func.value, "id", None) == "Contract":
                    if func.attr in ("post", "ensure"):
                        has_post = True

        if not has_pre:
            self.violations.append(f"Function/Method '{node.name}' has no precondition argument checks.")

        self.generic_visit(node)


def verify_contract_coverage(code_str: str) -> Dict[str, Any]:
    """Statically verify whether generated code contains binding AST contracts."""
    try:
        tree = ast.parse(code_str)
    except SyntaxError as e:
        return {
            "ast_valid": False,
            "error": f"SyntaxError on line {e.lineno}: {e.msg}",
            "passed_linter": False,
            "contract_density": 0.0,
            "violations": [f"SyntaxError: {e.msg}"],
        }

    visitor = ContractVisitor()
    visitor.visit(tree)

    total_units = visitor.functions_found + visitor.classes_found
    contracts_found = visitor.precondition_count + visitor.postcondition_count + visitor.class_invariants_found
    density = round(contracts_found / max(1, total_units), 2)

    # A sound implementation must have at least 1 contract check per 2 units
    passed_linter = (visitor.precondition_count >= 1) and (len(visitor.violations) <= max(1, total_units // 2))

    return {
        "ast_valid": True,
        "functions_count": visitor.functions_found,
        "classes_count": visitor.classes_found,
        "preconditions": visitor.precondition_count,
        "postconditions": visitor.postcondition_count,
        "class_invariants": visitor.class_invariants_found,
        "contract_density": density,
        "passed_linter": passed_linter,
        "violations": visitor.violations,
    }


# ==============================================================================
# PROMPT CONTRACT INJECTOR
# ==============================================================================

def get_ast_contract_prompt_instruction(include_runtime: bool = True) -> str:
    """Generate prompt instructions requiring binding AST contracts in generated code."""
    instr = (
        "MANDATORY BINDING AST CONTRACT CONTRACT:\n"
        "Do NOT write non-binding natural language thoughts. Instead, embed binding runtime contracts directly into your code:\n"
        "1. PRECONDITIONS: At the start of every public function/method, validate argument boundaries and types using `Contract.pre(condition, 'msg')` or explicit `if not cond: raise ValueError(...)`.\n"
        "2. CLASS INVARIANTS: For stateful classes, define an explicit `def __invariant__(self):` method asserting internal state consistency.\n"
        "3. POSTCONDITIONS: On non-trivial calculations, verify return values via `Contract.post(condition, 'msg')` or assert before returning.\n"
    )
    if include_runtime:
        instr += f"\nInclude this lightweight contract helper at the top of your code:\n```python\n{CONTRACT_RUNTIME_CODE}\n```\n"
    return instr


# ==============================================================================
# UNIT TESTS
# ==============================================================================

def _test_contract_compiler():
    print("🧪 Running Contract Visitor Unit Tests...")

    code_with_contracts = """
class Contract:
    @staticmethod
    def pre(condition, msg="Precondition violated"):
        if not condition: raise ValueError(msg)

class ConsistentHashRing:
    def __init__(self, nodes=None, virtual_nodes=100):
        Contract.pre(virtual_nodes > 0, "virtual_nodes must be positive")
        self.virtual_nodes = virtual_nodes
        self.ring = {}
        self.sorted_tokens = []

    def __invariant__(self):
        assert len(self.ring) == len(self.sorted_tokens)

    def get_node(self, key: str):
        Contract.pre(isinstance(key, str) and len(key) > 0, "key must be non-empty string")
        if not self.sorted_tokens:
            return None
        return self.ring[self.sorted_tokens[0]]
"""
    res1 = verify_contract_coverage(code_with_contracts)
    assert res1["ast_valid"] is True
    assert res1["preconditions"] == 2
    assert res1["class_invariants"] == 1
    assert res1["passed_linter"] is True
    print("  ✅ Code with contracts verified successfully (Density:", res1["contract_density"], ")")

    code_without_contracts = """
def naive_sort(arr):
    return sorted(arr)
"""
    res2 = verify_contract_coverage(code_without_contracts)
    assert res2["preconditions"] == 0
    assert res2["passed_linter"] is False
    assert len(res2["violations"]) > 0
    print("  ✅ Code without contracts correctly rejected by linter.")

    print("🎉 All Contract Engine unit tests passed!\n")


if __name__ == "__main__":
    _test_contract_compiler()
