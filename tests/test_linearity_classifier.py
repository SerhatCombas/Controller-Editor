"""Tests for LinearityClassifier and SystemClass (Wave 1, Commit 7).

Covers:
- LTI candidate verdict for standard mechanical components
- Honest confidence / caveat population
- topology_assumptions_modeled is always False
- Nonlinear and time-varying overrides via custom component stubs
- Empty graph edge case
- Per-component verdict entries (ComponentVerdictEntry)
- SystemClass frozen immutability
"""
from __future__ import annotations

import unittest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_single_mass_graph():
    """Return a simple single-mass spring-damper graph."""
    from app.core.graph.system_graph import SystemGraph
    from app.core.models.mechanical import Mass, Spring, Damper, MechanicalGround
    from app.core.models.sources import StepForce

    g = SystemGraph()
    m = g.add_component(Mass("mass", mass=2.0))
    k = g.add_component(Spring("spring", stiffness=10.0))
    d = g.add_component(Damper("damper", damping=3.0))
    src = g.add_component(StepForce("force", amplitude=1.0))
    gnd = g.add_component(MechanicalGround("ground"))

    g.connect(m.port("port_a").id, k.port("port_a").id)
    g.connect(m.port("port_a").id, d.port("port_a").id)
    g.connect(m.port("port_a").id, src.port("port").id)
    g.connect(k.port("port_b").id, gnd.port("port").id)
    g.connect(d.port("port_b").id, gnd.port("port").id)
    g.connect(m.port("reference_port").id, gnd.port("port").id)
    g.connect(src.port("reference_port").id, gnd.port("port").id)
    return g


def _make_quarter_car_graph():
    """Return the quarter-car template graph."""
    from app.core.templates import build_quarter_car_template
    return build_quarter_car_template().graph


class _MockGraph:
    """Minimal graph-like object with a dict of components."""
    def __init__(self, components: dict):
        self.components = components


class _LinearComp:
    """Stub component reporting linear + time-invariant."""
    def __init__(self, cid="lc"):
        self.id = cid
    def linearity_profile(self):
        from app.core.base.linearity import LinearityProfile
        return LinearityProfile(is_linear=True, is_time_invariant=True)


class _NonlinearComp:
    """Stub component reporting nonlinear behaviour."""
    def __init__(self, cid="nlc", kind="smooth"):
        self.id = cid
        self._kind = kind
    def linearity_profile(self):
        from app.core.base.linearity import LinearityProfile
        return LinearityProfile(
            is_linear=False,
            is_time_invariant=True,
            nonlinearity_kind=self._kind,
            notes=("Stub nonlinear component",),
        )


class _TimeVaryingComp:
    """Stub component reporting linear but time-varying behaviour."""
    def __init__(self, cid="tvc"):
        self.id = cid
    def linearity_profile(self):
        from app.core.base.linearity import LinearityProfile
        return LinearityProfile(is_linear=True, is_time_invariant=False)


class _NonlinearTimeVaryingComp:
    """Stub component: nonlinear AND time-varying."""
    def __init__(self, cid="nltvc"):
        self.id = cid
    def linearity_profile(self):
        from app.core.base.linearity import LinearityProfile
        return LinearityProfile(
            is_linear=False,
            is_time_invariant=False,
            nonlinearity_kind="hard",
        )


# ---------------------------------------------------------------------------
# SystemClass dataclass
# ---------------------------------------------------------------------------

class TestSystemClass(unittest.TestCase):

    def _make_lti_system_class(self):
        from app.core.symbolic.linearity_classifier import SystemClass, ComponentVerdictEntry
        entry = ComponentVerdictEntry(
            component_id="c1", component_type="Mass",
            is_linear=True, is_time_invariant=True,
            nonlinearity_kind=None, notes=(),
        )
        return SystemClass(
            is_lti_candidate=True,
            component_level_verdict="LTI candidate (component-level only)",
            verdict_confidence="component_level_only",
            topology_assumptions_modeled=False,
            nonlinear_component_ids=(),
            time_varying_component_ids=(),
            component_verdicts=(entry,),
            caveats=("Caveat A",),
            component_count=1,
        )

    def test_frozen(self):
        sc = self._make_lti_system_class()
        with self.assertRaises((AttributeError, TypeError)):
            sc.is_lti_candidate = False  # type: ignore[misc]

    def test_slots(self):
        sc = self._make_lti_system_class()
        with self.assertRaises(AttributeError):
            sc.__dict__  # type: ignore[attr-defined]

    def test_lti_candidate_true(self):
        sc = self._make_lti_system_class()
        self.assertTrue(sc.is_lti_candidate)

    def test_caveats_non_empty(self):
        sc = self._make_lti_system_class()
        self.assertGreater(len(sc.caveats), 0)


# ---------------------------------------------------------------------------
# LinearityClassifier — standard mechanical graphs
# ---------------------------------------------------------------------------

class TestClassifierSingleMass(unittest.TestCase):

    def _classify(self):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _make_single_mass_graph()
        return LinearityClassifier().classify(graph)

    def test_is_lti_candidate_true(self):
        sc = self._classify()
        self.assertTrue(sc.is_lti_candidate)

    def test_verdict_contains_lti(self):
        sc = self._classify()
        self.assertIn("LTI", sc.component_level_verdict)

    def test_verdict_confidence_component_level_only(self):
        sc = self._classify()
        self.assertEqual(sc.verdict_confidence, "component_level_only")

    def test_topology_assumptions_not_modeled(self):
        sc = self._classify()
        self.assertFalse(sc.topology_assumptions_modeled)

    def test_no_nonlinear_components(self):
        sc = self._classify()
        self.assertEqual(sc.nonlinear_component_ids, ())

    def test_no_time_varying_components(self):
        sc = self._classify()
        self.assertEqual(sc.time_varying_component_ids, ())

    def test_caveats_always_populated(self):
        sc = self._classify()
        self.assertTrue(len(sc.caveats) >= 1)
        # Every caveat must be non-empty string
        for c in sc.caveats:
            self.assertIsInstance(c, str)
            self.assertTrue(len(c) > 0)

    def test_caveats_mention_topology(self):
        sc = self._classify()
        joined = " ".join(sc.caveats).lower()
        self.assertIn("topology", joined)

    def test_component_count_matches(self):
        from app.core.graph.system_graph import SystemGraph
        graph = _make_single_mass_graph()
        sc_count = len(graph.components)
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        sc = LinearityClassifier().classify(graph)
        self.assertEqual(sc.component_count, sc_count)

    def test_component_verdicts_non_empty(self):
        sc = self._classify()
        self.assertGreater(len(sc.component_verdicts), 0)

    def test_component_verdicts_all_lti(self):
        sc = self._classify()
        for entry in sc.component_verdicts:
            self.assertTrue(entry.is_linear)
            self.assertTrue(entry.is_time_invariant)


class TestClassifierQuarterCar(unittest.TestCase):

    def _classify(self):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _make_quarter_car_graph()
        return LinearityClassifier().classify(graph)

    def test_quarter_car_is_lti_candidate(self):
        sc = self._classify()
        self.assertTrue(sc.is_lti_candidate)

    def test_quarter_car_component_count(self):
        graph = _make_quarter_car_graph()
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        sc = LinearityClassifier().classify(graph)
        self.assertEqual(sc.component_count, len(graph.components))

    def test_verdict_confidence_unchanged(self):
        sc = self._classify()
        self.assertEqual(sc.verdict_confidence, "component_level_only")


# ---------------------------------------------------------------------------
# LinearityClassifier — nonlinear components
# ---------------------------------------------------------------------------

class TestClassifierNonlinear(unittest.TestCase):

    def _classify_with(self, *comps):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({c.id: c for c in comps})
        return LinearityClassifier().classify(graph)

    def test_single_nonlinear_detected(self):
        sc = self._classify_with(_NonlinearComp("nl1"))
        self.assertFalse(sc.is_lti_candidate)
        self.assertIn("nl1", sc.nonlinear_component_ids)

    def test_verdict_contains_nonlinear(self):
        sc = self._classify_with(_NonlinearComp())
        self.assertIn("Nonlinear", sc.component_level_verdict)

    def test_mixed_linear_nonlinear(self):
        sc = self._classify_with(_LinearComp("lc"), _NonlinearComp("nlc"))
        self.assertFalse(sc.is_lti_candidate)
        self.assertIn("nlc", sc.nonlinear_component_ids)
        self.assertNotIn("lc", sc.nonlinear_component_ids)

    def test_nonlinearity_kind_in_entry(self):
        sc = self._classify_with(_NonlinearComp("nlc", kind="hard"))
        entry = next(e for e in sc.component_verdicts if e.component_id == "nlc")
        self.assertEqual(entry.nonlinearity_kind, "hard")

    def test_two_nonlinear_components(self):
        sc = self._classify_with(_NonlinearComp("a"), _NonlinearComp("b"))
        self.assertFalse(sc.is_lti_candidate)
        self.assertEqual(len(sc.nonlinear_component_ids), 2)

    def test_caveats_still_populated_for_nonlinear(self):
        sc = self._classify_with(_NonlinearComp())
        self.assertGreater(len(sc.caveats), 0)


# ---------------------------------------------------------------------------
# LinearityClassifier — time-varying components
# ---------------------------------------------------------------------------

class TestClassifierTimeVarying(unittest.TestCase):

    def _classify_with(self, *comps):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({c.id: c for c in comps})
        return LinearityClassifier().classify(graph)

    def test_time_varying_detected(self):
        sc = self._classify_with(_TimeVaryingComp("tv1"))
        self.assertFalse(sc.is_lti_candidate)
        self.assertIn("tv1", sc.time_varying_component_ids)

    def test_verdict_mentions_ltv(self):
        sc = self._classify_with(_TimeVaryingComp())
        # Linear but time-varying: verdict mentions LTV or "time-varying"
        verdict_lower = sc.component_level_verdict.lower()
        self.assertTrue(
            "time-varying" in verdict_lower or "ltv" in verdict_lower,
            f"Expected LTV mention in verdict: {sc.component_level_verdict!r}",
        )

    def test_time_varying_not_in_nonlinear_list(self):
        sc = self._classify_with(_TimeVaryingComp("tv"))
        self.assertNotIn("tv", sc.nonlinear_component_ids)


# ---------------------------------------------------------------------------
# LinearityClassifier — nonlinear AND time-varying
# ---------------------------------------------------------------------------

class TestClassifierNonlinearTimeVarying(unittest.TestCase):

    def test_verdict_mentions_both(self):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({"nltvc": _NonlinearTimeVaryingComp()})
        sc = LinearityClassifier().classify(graph)
        self.assertFalse(sc.is_lti_candidate)
        verdict_lower = sc.component_level_verdict.lower()
        self.assertIn("nonlinear", verdict_lower)
        self.assertIn("time-varying", verdict_lower)

    def test_both_id_lists_populated(self):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({"nltvc": _NonlinearTimeVaryingComp()})
        sc = LinearityClassifier().classify(graph)
        self.assertIn("nltvc", sc.nonlinear_component_ids)
        self.assertIn("nltvc", sc.time_varying_component_ids)


# ---------------------------------------------------------------------------
# LinearityClassifier — empty graph edge case
# ---------------------------------------------------------------------------

class TestClassifierEmpty(unittest.TestCase):

    def test_empty_graph_is_lti_candidate(self):
        """Empty graph: no nonlinear components → vacuously LTI candidate."""
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({})
        sc = LinearityClassifier().classify(graph)
        # Vacuous truth: no nonlinear components found → is_lti_candidate=True
        self.assertTrue(sc.is_lti_candidate)

    def test_empty_graph_component_count_zero(self):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({})
        sc = LinearityClassifier().classify(graph)
        self.assertEqual(sc.component_count, 0)

    def test_empty_graph_caveats_still_present(self):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({})
        sc = LinearityClassifier().classify(graph)
        self.assertGreater(len(sc.caveats), 0)


# ---------------------------------------------------------------------------
# ComponentVerdictEntry
# ---------------------------------------------------------------------------

class TestComponentVerdictEntry(unittest.TestCase):

    def test_frozen(self):
        from app.core.symbolic.linearity_classifier import ComponentVerdictEntry
        entry = ComponentVerdictEntry(
            component_id="c1", component_type="Mass",
            is_linear=True, is_time_invariant=True,
            nonlinearity_kind=None, notes=(),
        )
        with self.assertRaises((AttributeError, TypeError)):
            entry.is_linear = False  # type: ignore[misc]

    def test_notes_forwarded(self):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({"nlc": _NonlinearComp("nlc", kind="smooth")})
        sc = LinearityClassifier().classify(graph)
        entry = next(e for e in sc.component_verdicts if e.component_id == "nlc")
        self.assertIn("Stub nonlinear component", entry.notes)

    def test_component_type_is_class_name(self):
        """component_type carries class name — diagnostic use only, not logic."""
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _MockGraph({"lc": _LinearComp("lc")})
        sc = LinearityClassifier().classify(graph)
        entry = sc.component_verdicts[0]
        self.assertEqual(entry.component_type, "_LinearComp")


# ---------------------------------------------------------------------------
# Stateless classifier — two calls on same graph produce identical result
# ---------------------------------------------------------------------------

class TestClassifierStateless(unittest.TestCase):

    def test_repeated_classify_identical(self):
        from app.core.symbolic.linearity_classifier import LinearityClassifier
        graph = _make_single_mass_graph()
        clf = LinearityClassifier()
        sc1 = clf.classify(graph)
        sc2 = clf.classify(graph)
        self.assertEqual(sc1.is_lti_candidate, sc2.is_lti_candidate)
        self.assertEqual(sc1.component_count, sc2.component_count)
        self.assertEqual(sc1.verdict_confidence, sc2.verdict_confidence)


if __name__ == "__main__":
    unittest.main()
