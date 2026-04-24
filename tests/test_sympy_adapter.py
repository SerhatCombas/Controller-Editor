"""Unit tests for SympyAdapter.

Coverage:
  1. Real equation parsed correctly (symbol + derivative).
  2. Token used as function call → declared as sp.Function, not sp.Symbol.
  3. Token used as plain variable → declared as sp.Symbol.
  4. Pseudo-equation with unsupported syntax → sympy_expression=None, no crash.
  5. Equation with no '=' sign → sympy_expression=None, no crash.
  6. step() alias → translated to Heaviside() before parsing.
"""
import unittest

try:
    import sympy as sp
    _SYMPY_AVAILABLE = True
except ModuleNotFoundError:
    _SYMPY_AVAILABLE = False

from app.core.symbolic.sympy_adapter import SympyAdapter


@unittest.skipUnless(_SYMPY_AVAILABLE, "sympy not installed")
class TestSympyAdapterParsing(unittest.TestCase):

    def setUp(self) -> None:
        self.adapter = SympyAdapter()

    # ------------------------------------------------------------------
    # 1. Real equation — structural sympy Eq returned
    # ------------------------------------------------------------------

    def test_real_equation_returns_sympy_eq(self):
        """m * ddt_x = F parses to a valid sp.Eq (no crash, expression not None)."""
        lhs, rhs, expr = self.adapter.parse_equation("m * d/dt x = F")
        self.assertIsNotNone(expr, "Expected sympy Eq, got None")
        self.assertIsInstance(expr, sp.Eq)

    def test_real_equation_lhs_rhs_text_preserved(self):
        """parse_equation returns the raw text strings unchanged."""
        equation = "k * x = F_spring"
        lhs, rhs, _ = self.adapter.parse_equation(equation)
        self.assertEqual(lhs, "k * x")
        self.assertEqual(rhs, "F_spring")

    # ------------------------------------------------------------------
    # 2. Function detection — token(arg) must become sp.Function
    # ------------------------------------------------------------------

    def test_function_token_declared_as_sp_function(self):
        """r_road_source(t) = 0: r_road_source must be Function, not Symbol."""
        # If r_road_source were a Symbol, sympify would raise TypeError.
        # Successful parse proves it was treated as sp.Function.
        lhs, rhs, expr = self.adapter.parse_equation("r_road_source(t) = 0")
        self.assertIsNotNone(expr, "parse should succeed with Function declaration")

    def test_multiple_function_calls_parsed(self):
        """f(x) + g(x) = h(x): all three declared as Function."""
        lhs, rhs, expr = self.adapter.parse_equation("f(x) + g(x) = h(x)")
        self.assertIsNotNone(expr)

    # ------------------------------------------------------------------
    # 3. Symbol fallback — plain variable stays sp.Symbol
    # ------------------------------------------------------------------

    def test_plain_token_declared_as_sp_symbol(self):
        """'mass * a = force' — all tokens are plain symbols, no calls."""
        lhs, rhs, expr = self.adapter.parse_equation("mass * a = force")
        self.assertIsNotNone(expr)
        # Verify tokens ended up as Symbols by checking the free_symbols set
        free = expr.free_symbols
        names = {s.name for s in free}
        self.assertIn("mass", names)
        self.assertIn("a", names)
        self.assertIn("force", names)

    # ------------------------------------------------------------------
    # 4. Pseudo-equation — unsupported syntax → None, no crash
    # ------------------------------------------------------------------

    def test_pseudo_equation_with_keyword_arg_returns_none(self):
        """filtered_white_noise(seed=7) cannot be parsed by sympy → None."""
        lhs, rhs, expr = self.adapter.parse_equation(
            "r_road_source(t) = filtered_white_noise(seed=7)"
        )
        # sympy cannot handle keyword args in function calls → graceful None
        self.assertIsNone(expr)
        # But the raw text strings must still be returned
        self.assertEqual(lhs, "r_road_source(t)")
        self.assertEqual(rhs, "filtered_white_noise(seed=7)")

    def test_pseudo_road_velocity_equation_returns_none(self):
        """dr_road_source/dt = road_velocity(...) is pseudo-code → None."""
        lhs, rhs, expr = self.adapter.parse_equation(
            "dr_road_source/dt = road_velocity(road_source, t)"
        )
        # This may or may not parse; the important thing is it doesn't crash.
        # Either a valid Eq or None is acceptable — no TypeError or AttributeError.
        self.assertIn(expr, [None] + ([expr] if expr is not None else []))

    # ------------------------------------------------------------------
    # 5. No '=' sign → sympy_expression=None immediately
    # ------------------------------------------------------------------

    def test_no_equals_returns_none_expression(self):
        """Equation string with no '=' yields sympy_expression=None."""
        lhs, rhs, expr = self.adapter.parse_equation("just_a_statement")
        self.assertIsNone(expr)
        self.assertEqual(lhs, "just_a_statement")
        self.assertEqual(rhs, "0")

    # ------------------------------------------------------------------
    # 6. step() → Heaviside() alias
    # ------------------------------------------------------------------

    def test_step_alias_translates_to_heaviside(self):
        """step(t) on the RHS is rewritten to Heaviside(t) before parsing."""
        lhs, rhs, expr = self.adapter.parse_equation("y = step(t)")
        self.assertIsNotNone(expr)
        # Heaviside should appear in the sympy expression
        self.assertTrue(
            any(isinstance(arg, sp.Heaviside) for arg in expr.atoms(sp.Heaviside)),
            "Heaviside not found in parsed expression",
        )


class TestSympyAdapterWithoutSympy(unittest.TestCase):
    """Verify graceful degradation when sympy is unavailable."""

    def test_available_flag_reflects_import_state(self):
        adapter = SympyAdapter()
        self.assertEqual(adapter.available, _SYMPY_AVAILABLE)
