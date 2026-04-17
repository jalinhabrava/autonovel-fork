import unittest

from context_engine.policies import available_policies, get_policy


class ContextPolicyTests(unittest.TestCase):
    def test_default_policy_loads_with_required_dimensions(self):
        policy = get_policy("default")

        self.assertEqual(policy.name, "default")
        self.assertIn("canon", policy.selection_weights)
        self.assertIn("validated", policy.status_priority)
        self.assertGreater(policy.section_budgets.hard_constraints, 0)
        self.assertIn("decision", policy.literality_by_artifact_type)
        self.assertGreaterEqual(policy.literality_by_artifact_type["decision"], 0.0)
        self.assertLessEqual(policy.literality_by_artifact_type["decision"], 1.0)
        self.assertIn("scene", policy.scope_radius)

    def test_available_policies_include_expected_profiles(self):
        names = available_policies()

        self.assertIn("default", names)
        self.assertIn("strict_canon", names)
        self.assertIn("local_scene", names)


if __name__ == "__main__":
    unittest.main()
