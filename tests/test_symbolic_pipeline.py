from __future__ import annotations

import unittest

from app.core.graph.system_graph import SystemGraph
from app.core.graph.validators import GraphValidator
from app.core.models.mechanical import Damper, Mass, MechanicalGround, Spring
from app.core.models.sources import StepForce
from app.core.probes import RelativeProbe
from app.core.symbolic.dae_reducer import DAEReducer
from app.core.symbolic.equation_builder import EquationBuilder
from app.core.symbolic.state_space_builder import StateSpaceBuilder
from tests.fixtures.graph_factories import build_single_mass_template_def as build_single_mass_template
from tests.fixtures.graph_factories import build_two_mass_template_def as build_two_mass_template
from tests.fixtures.minimal_wheel_road import build_wheel_road_graph
from app.core.templates.template_definition import TemplateDefinition


def _build_quarter_car_fixture():
    graph = build_wheel_road_graph()
    return TemplateDefinition(
        id="quarter_car", name="Quarter-Car Suspension", graph=graph,
        default_input_id="road_source", default_output_id="body_displacement",
    )

build_quarter_car_template = _build_quarter_car_fixture


class SymbolicPipelineTests(unittest.TestCase):
    def build_pipeline(self, template_builder):
        template = template_builder()
        symbolic = EquationBuilder().build(template.graph)
        reduced = DAEReducer().reduce(template.graph, symbolic)
        state_space = StateSpaceBuilder().build(template.graph, reduced, symbolic)
        return template, symbolic, reduced, state_space

    def assert_matrix_close(self, left, right, places=7):
        self.assertEqual(len(left), len(right))
        for left_row, right_row in zip(left, right):
            self.assertEqual(len(left_row), len(right_row))
            for left_value, right_value in zip(left_row, right_row):
                self.assertAlmostEqual(left_value, right_value, places=places)

    def test_single_mass_matches_reference_state_space(self):
        _, symbolic, reduced, state_space = self.build_pipeline(build_single_mass_template)

        self.assertEqual(symbolic.state_variables, ["x_mass", "v_mass"])
        self.assertEqual(reduced.state_variables, ["x_mass", "v_mass"])
        self.assertEqual(reduced.input_variables, ["u_input_force"])
        self.assertTrue(symbolic.equation_records)
        self.assertTrue(symbolic.dae_equation_records)
        self.assertIn("x_mass", symbolic.variable_registry)
        self.assertIn("ddt_x_mass", symbolic.variable_registry)
        self.assertEqual(symbolic.variable_registry["ddt_x_mass"]["base_variable_id"], "x_mass")
        self.assertIn("component_records", symbolic.metadata)
        self.assertIn("output_records", symbolic.metadata)
        self.assertIn("derivative_links", symbolic.metadata)
        self.assertEqual(reduced.metadata["state_index_lookup"]["x_mass"], 0)
        self.assertEqual(reduced.metadata["state_index_lookup"]["v_mass"], 1)
        self.assertEqual(reduced.metadata["derivative_links"]["x_mass"], "ddt_x_mass")
        self.assertGreaterEqual(reduced.metadata["sympy_equation_count"], 0)
        expected_a = [
            [0.0, 1.0],
            [-5.0, -1.5],
        ]
        expected_b = [
            [0.0],
            [0.5],
        ]
        self.assert_matrix_close(state_space.a_matrix, expected_a)
        self.assert_matrix_close(state_space.b_matrix, expected_b)
        if symbolic.metadata["sympy_available"]:
            self.assertTrue(any(record.sympy_expression is not None for record in symbolic.equation_records))
        self.assertTrue(any(record.derivative_variables for record in symbolic.differential_records))
        self.assertTrue(any(record.involved_variables for record in symbolic.equation_records))
        self.assertTrue(any(record.involved_parameters for record in symbolic.equation_records))
        self.assertTrue(any(record.metadata.get("source_type") == "component" for record in symbolic.equation_records))
        self.assertTrue(any(record.metadata.get("source_type") == "node" for record in symbolic.equation_records))
        self.assertTrue(
            all(
                key in record.metadata
                for record in symbolic.equation_records
                for key in ["source_type", "source_id", "source_name", "origin_layer", "domain", "tags", "owner_component_id", "owner_node_id"]
            )
        )

    def test_two_mass_matches_reference_state_space(self):
        _, symbolic, reduced, state_space = self.build_pipeline(build_two_mass_template)

        self.assertEqual(len(symbolic.state_variables), 4)
        expected_a = [
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
            [-14.0, 4.0, -3.5, 1.0],
            [8.0, -8.0, 2.0, -2.0],
        ]
        expected_b = [
            [0.0],
            [0.0],
            [0.5],
            [0.0],
        ]
        self.assert_matrix_close(state_space.a_matrix, expected_a)
        self.assert_matrix_close(state_space.b_matrix, expected_b)
        self.assertIn("relative_deflection", state_space.output_variables)
        relative_index = state_space.output_variables.index("relative_deflection")
        self.assertEqual(state_space.c_matrix[relative_index][:2], [1.0, -1.0])

    def test_quarter_car_pipeline_shapes_and_outputs(self):
        _, symbolic, reduced, state_space = self.build_pipeline(build_quarter_car_template)

        self.assertEqual(len(symbolic.all_equations), 32)
        self.assertEqual(len(symbolic.algebraic_constraints), 14)
        self.assertEqual(
            reduced.state_variables,
            ["x_body_mass", "x_wheel_mass", "v_body_mass", "v_wheel_mass"],
        )
        self.assertEqual(reduced.metadata["canonical_state_source"], "symbolic_records")
        self.assertEqual(len(reduced.first_order_a), 4)
        self.assertEqual(len(reduced.first_order_a[0]), 4)
        self.assertEqual(len(reduced.first_order_b), 4)
        self.assertEqual(len(reduced.first_order_b[0]), 2)
        self.assertEqual(
            state_space.output_variables,
            [
                "body_displacement",
                "wheel_displacement",
                "body_acceleration",
                "suspension_force",
                "suspension_deflection",
                "tire_deflection",
            ],
        )
        self.assertEqual(len(reduced.metadata["state_trace"]), len(reduced.state_variables))
        self.assertTrue(
            all(
                {"state_id", "node_id", "origin_layer", "variable_kind", "derivative_id"} <= set(trace.keys())
                for trace in reduced.metadata["state_trace"]
            )
        )
        self.assertEqual(len(state_space.metadata["output_trace"]), len(state_space.output_variables))
        self.assertTrue(
            all(
                {"output_id", "origin_layer", "source_type", "quantity", "state_columns"} <= set(trace.keys())
                for trace in state_space.metadata["output_trace"]
            )
        )

    def test_quarter_car_damping_changes_velocity_feedback_strength(self):
        template_low = build_quarter_car_template()
        template_high = build_quarter_car_template()
        template_high.graph.components["suspension_damper"].parameters["damping"] = 2400.0

        symbolic_low = EquationBuilder().build(template_low.graph)
        reduced_low = DAEReducer().reduce(template_low.graph, symbolic_low)
        state_space_low = StateSpaceBuilder().build(template_low.graph, reduced_low, symbolic_low)

        symbolic_high = EquationBuilder().build(template_high.graph)
        reduced_high = DAEReducer().reduce(template_high.graph, symbolic_high)
        state_space_high = StateSpaceBuilder().build(template_high.graph, reduced_high, symbolic_high)

        self.assertGreater(abs(state_space_high.a_matrix[2][2]), abs(state_space_low.a_matrix[2][2]))

    def test_quarter_car_stiffness_changes_restoring_coupling_strength(self):
        template_soft = build_quarter_car_template()
        template_stiff = build_quarter_car_template()
        template_stiff.graph.components["suspension_spring"].parameters["stiffness"] = 30000.0

        symbolic_soft = EquationBuilder().build(template_soft.graph)
        reduced_soft = DAEReducer().reduce(template_soft.graph, symbolic_soft)
        state_space_soft = StateSpaceBuilder().build(template_soft.graph, reduced_soft, symbolic_soft)

        symbolic_stiff = EquationBuilder().build(template_stiff.graph)
        reduced_stiff = DAEReducer().reduce(template_stiff.graph, symbolic_stiff)
        state_space_stiff = StateSpaceBuilder().build(template_stiff.graph, reduced_stiff, symbolic_stiff)

        self.assertGreater(abs(state_space_stiff.a_matrix[2][0]), abs(state_space_soft.a_matrix[2][0]))

    def test_quarter_car_tire_stiffness_changes_wheel_mode_strength(self):
        template_soft = build_quarter_car_template()
        template_stiff = build_quarter_car_template()
        # Faz 4j-1 -- tire_stiffness Spring removed; tire stiffness now
        # lives on the Wheel as contact_stiffness. The semantics of this
        # test (a stiffer tire raises the wheel-mode A-matrix entry) are
        # unchanged.
        template_stiff.graph.components["wheel_mass"].parameters["contact_stiffness"] = 360000.0

        symbolic_soft = EquationBuilder().build(template_soft.graph)
        reduced_soft = DAEReducer().reduce(template_soft.graph, symbolic_soft)
        state_space_soft = StateSpaceBuilder().build(template_soft.graph, reduced_soft, symbolic_soft)

        symbolic_stiff = EquationBuilder().build(template_stiff.graph)
        reduced_stiff = DAEReducer().reduce(template_stiff.graph, symbolic_stiff)
        state_space_stiff = StateSpaceBuilder().build(template_stiff.graph, reduced_stiff, symbolic_stiff)

        self.assertGreater(abs(state_space_stiff.a_matrix[3][1]), abs(state_space_soft.a_matrix[3][1]))

    def test_quarter_car_suspension_deflection_output_is_relative_state(self):
        _, _, _, state_space = self.build_pipeline(build_quarter_car_template)
        output_index = state_space.output_variables.index("suspension_deflection")
        self.assertEqual(state_space.c_matrix[output_index][:2], [1.0, -1.0])
        self.assertEqual(state_space.d_matrix[output_index], [0.0, 0.0])
        trace = state_space.metadata["output_trace"][output_index]
        self.assertEqual(trace["source_type"], "relative_probe")
        self.assertEqual(trace["quantity"], "displacement")
        self.assertEqual(trace["state_columns"], ["x_body_mass", "x_wheel_mass"])

    def test_invalid_topology_reports_unconnected_spring(self):
        graph = SystemGraph()
        graph.add_component(Spring("orphan_spring", stiffness=5.0))
        messages = GraphValidator().validate(graph)
        texts = [message.text for message in messages]
        self.assertTrue(any("not connected" in text for text in texts))

    def test_parallel_branch_accumulates_equivalent_stiffness_and_damping(self):
        graph = SystemGraph()
        mass = graph.add_component(Mass("mass", mass=2.0))
        spring_a = graph.add_component(Spring("spring_a", stiffness=10.0))
        spring_b = graph.add_component(Spring("spring_b", stiffness=5.0))
        damper_a = graph.add_component(Damper("damper_a", damping=3.0))
        damper_b = graph.add_component(Damper("damper_b", damping=1.0))
        source = graph.add_component(StepForce("input_force", amplitude=1.0))
        ground = graph.add_component(MechanicalGround("ground"))

        graph.connect(mass.port("port_a").id, spring_a.port("port_a").id)
        graph.connect(mass.port("port_a").id, spring_b.port("port_a").id)
        graph.connect(mass.port("port_a").id, damper_a.port("port_a").id)
        graph.connect(mass.port("port_a").id, damper_b.port("port_a").id)
        graph.connect(mass.port("port_a").id, source.port("port").id)
        graph.connect(spring_a.port("port_b").id, ground.port("port").id)
        graph.connect(spring_b.port("port_b").id, ground.port("port").id)
        graph.connect(damper_a.port("port_b").id, ground.port("port").id)
        graph.connect(damper_b.port("port_b").id, ground.port("port").id)
        graph.connect(mass.port("reference_port").id, ground.port("port").id)
        graph.connect(source.port("reference_port").id, ground.port("port").id)

        symbolic = EquationBuilder().build(graph)
        reduced = DAEReducer().reduce(graph, symbolic)
        state_space = StateSpaceBuilder().build(graph, reduced, symbolic)

        expected_a = [[0.0, 1.0], [-7.5, -2.0]]
        expected_b = [[0.0], [0.5]]
        self.assert_matrix_close(state_space.a_matrix, expected_a)
        self.assert_matrix_close(state_space.b_matrix, expected_b)

    def test_traceability_schema_stays_consistent_across_equation_records(self):
        _, symbolic, _, _ = self.build_pipeline(build_quarter_car_template)
        trace_records = [record for record in symbolic.equation_records if record.metadata]

        self.assertTrue(trace_records)
        self.assertTrue(
            all(
                {
                    "source_type",
                    "source_id",
                    "source_name",
                    "origin_layer",
                    "domain",
                    "tags",
                    "owner_component_id",
                    "owner_node_id",
                }
                <= set(record.metadata.keys())
                for record in trace_records
            )
        )
        self.assertTrue(any(record.metadata["source_type"] == "component" for record in trace_records))
        self.assertTrue(any(record.metadata["source_type"] == "node" for record in trace_records))

    def test_invalid_topology_reports_duplicate_source_conflict(self):
        graph = SystemGraph()
        mass = graph.add_component(Mass("mass", mass=1.0))
        source_a = graph.add_component(StepForce("source_a", amplitude=1.0, name="Source A"))
        source_b = graph.add_component(StepForce("source_b", amplitude=2.0, name="Source B"))
        ground = graph.add_component(MechanicalGround("ground"))

        graph.connect(mass.port("port_a").id, source_a.port("port").id)
        graph.connect(mass.port("port_a").id, source_b.port("port").id)
        graph.connect(mass.port("reference_port").id, ground.port("port").id)
        graph.connect(source_a.port("reference_port").id, ground.port("port").id)
        graph.connect(source_b.port("reference_port").id, ground.port("port").id)

        messages = GraphValidator().validate(graph)
        texts = [message.text for message in messages]
        self.assertTrue(any("Multiple force sources" in text for text in texts))

    def test_invalid_topology_reports_broken_relative_probe_target(self):
        graph = SystemGraph()
        graph.add_component(MechanicalGround("ground"))
        graph.attach_probe(
            RelativeProbe(
                id="broken_probe",
                name="Broken relative probe",
                quantity="displacement",
                target_component_id="missing_a",
                reference_component_id="missing_b",
            )
        )
        messages = GraphValidator().validate(graph)
        texts = [message.text for message in messages]
        self.assertTrue(any("targets missing component" in text or "references missing component" in text for text in texts))


if __name__ == "__main__":
    unittest.main()
