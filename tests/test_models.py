import os
import sys
import unittest

from pydantic import ValidationError

from wf_runtime.dsl.models import Workflow  # noqa: E402


class TestDSLModels(unittest.TestCase):

    def test_noop_node_happy_path(self):
        wf = Workflow.model_validate(
            {
                "id": "noop_wf",
                "version": 1,
                "input": {"schema": {"type": "object"}},
                "output": {
                    "schema": {"type": "object"},
                    "input_mapping": {
                        "doubled": "$nodes.transform.doubled",
                        "all": "$nodes.transform.all",
                    },
                },
                "nodes": [
                    {
                        "id": "step_one",
                        "kind": "noop",
                        "config": {},
                        "input_mapping": {"x": "$inputs.x"},
                        "output_mapping": {"y": "$result.x"},
                    }
                ],
                "edges": [
                    {"from": "start", "to": "step_one"},
                    {"from": "step_one", "to": "end"},
                ],
            }
        )

        self.assertEqual(wf.id, "noop_wf")
        self.assertEqual(wf.nodes[0].id, "step_one")
        self.assertEqual(wf.edges[0].from_, "start")
        self.assertEqual(wf.edges[1].to, "end")

    def test_workflow_happy_path_parses_and_alias_from_works(self):
        wf = Workflow.model_validate(
            {
                "id": "wf_one",
                "version": 1,
                "input": {"schema": {"type": "object"}},
                "output": {
                    "schema": {"type": "object"},
                    "input_mapping": {
                        "doubled": "$nodes.transform.doubled",
                        "all": "$nodes.transform.all",
                    },
                },
                "nodes": [
                    {
                        "id": "step_one",
                        "kind": "tool",
                        "type": "noop",
                        "config": {},
                        "input_mapping": {"x": "$inputs.x"},
                        "output_mapping": {"y": "$result.y"},
                    }
                ],
                "edges": [
                    {"from": "start", "to": "step_one"},
                    {"from": "step_one", "to": "end"},
                ],
            }
        )

        self.assertEqual(wf.id, "wf_one")
        self.assertEqual(wf.nodes[0].id, "step_one")
        self.assertEqual(wf.edges[0].from_, "start")

    def test_invalid_node_id_rejected(self):
        with self.assertRaises(ValidationError):
            Workflow.model_validate(
                {
                    "id": "wf_one",
                    "version": 1,
                    "input": {"schema": {"type": "object"}},
                    "output": {"schema": {"type": "object"}},
                    "nodes": [
                        {"id": "BadID", "kind": "tool", "type": "noop", "config": {}}
                    ],
                    "edges": [{"from": "start", "to": "end"}],
                }
            )

    def test_edge_to_unknown_node_rejected(self):
        with self.assertRaises(ValidationError):
            Workflow.model_validate(
                {
                    "id": "wf_one",
                    "version": 1,
                    "input": {"schema": {"type": "object"}},
                    "output": {"schema": {"type": "object"}},
                    "nodes": [
                        {"id": "step_one", "kind": "tool", "type": "noop", "config": {}}
                    ],
                    "edges": [{"from": "start", "to": "missing_node"}],
                }
            )


if __name__ == "__main__":
    unittest.main()
