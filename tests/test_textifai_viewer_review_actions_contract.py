from __future__ import annotations

import json
import subprocess
import textwrap
import unittest


APP_JS = "textifai/web_viewer/static/app.js"


class TextifAIViewerReviewActionsContractTests(unittest.TestCase):
    def test_recommended_action_mapping_contract(self):
        payload = _run_viewer_helper(
            """
            const helpers = globalThis.__TEXTIFAI_REVIEW_ACTIONS__;
            emit({
              merge: helpers.mapRecommendedActionToViewerActions("review_merge_or_alias"),
              create: helpers.mapRecommendedActionToViewerActions("review_create_primary"),
              secondary: helpers.mapRecommendedActionToViewerActions("review_keep_secondary"),
              reject: helpers.mapRecommendedActionToViewerActions("review_reject_noise"),
              attach: helpers.mapRecommendedActionToViewerActions("review_attach_role_or_title"),
              enrich: helpers.mapRecommendedActionToViewerActions("review_enrich_existing_entity"),
              insufficient: helpers.mapRecommendedActionToViewerActions("review_insufficient_evidence"),
            });
            """
        )

        self.assertEqual(payload["merge"], ["merge", "mark_alias"])
        self.assertEqual(payload["create"], ["promote"])
        self.assertEqual(payload["secondary"], ["keep_secondary"])
        self.assertEqual(payload["reject"], ["reject_noise"])
        self.assertEqual(payload["attach"], ["attach_role_or_title"])
        self.assertEqual(payload["enrich"], ["enrich_existing_entity"])
        self.assertEqual(payload["insufficient"], [])

    def test_future_actions_render_disabled_and_read_only(self):
        payload = _run_viewer_helper(
            """
            const helpers = globalThis.__TEXTIFAI_REVIEW_ACTIONS__;
            const item = {
              review_type: "entity_retention_review",
              severity: "medium",
              source_entity: "brújula de plata",
              target_text: "brújula de plata",
              candidate_entities: [],
              evidence: [{ kind: "source_mention", text: "brújula de plata" }],
              suggested_action: "review_create_primary",
              metadata: {
                recommended_action: "review_create_primary",
                signal_tier: "medium",
                candidate_status: "no_clear_existing_primary",
                surface_type: "object_like",
                semantic_value: "persistent_object",
                language_hint: "es",
                future_viewer_actions: ["promote", "keep_secondary", "reject_noise"],
                do_not_auto_merge: true,
                no_clear_existing_primary: true
              }
            };
            emit({
              actionsHtml: helpers.renderReviewActionDescriptors(item),
              warningHtml: helpers.renderReviewContractWarnings(item),
              cardHtml: helpers.renderReviewItemCard(item, 0),
              presentation: helpers.reviewActionPresentation(item)
            });
            """
        )

        self.assertIn("Future action: Promote", payload["actionsHtml"])
        self.assertIn("Future action: Keep secondary", payload["actionsHtml"])
        self.assertIn("Future action: Reject noise", payload["actionsHtml"])
        self.assertIn("disabled", payload["actionsHtml"])
        self.assertIn("do_not_auto_merge", payload["warningHtml"])
        self.assertIn("No clear candidate", payload["warningHtml"])
        self.assertIn("candidate status", payload["cardHtml"].lower())
        self.assertEqual(payload["presentation"]["signalTier"], "medium")
        self.assertEqual(payload["presentation"]["candidateStatus"], "no_clear_existing_primary")

    def test_backward_compatible_item_without_new_metadata_renders(self):
        payload = _run_viewer_helper(
            """
            const helpers = globalThis.__TEXTIFAI_REVIEW_ACTIONS__;
            const item = {
              review_type: "review_entity",
              severity: "low",
              source_entity: "Ren",
              target_text: "Ren",
              candidate_entities: [],
              evidence: [],
              suggested_action: "review_insufficient_evidence"
            };
            emit({
              actionsHtml: helpers.renderReviewActionDescriptors(item),
              cardHtml: helpers.renderReviewItemCard(item, 0),
              presentation: helpers.reviewActionPresentation(item)
            });
            """
        )

        self.assertIn("inspect evidence only", payload["actionsHtml"])
        self.assertIn("Recommended action", payload["cardHtml"])
        self.assertEqual(payload["presentation"]["actions"], [])

    def test_language_agnostic_metadata_drives_rendering(self):
        payload = _run_viewer_helper(
            """
            const helpers = globalThis.__TEXTIFAI_REVIEW_ACTIONS__;
            const item = {
              review_type: "entity_retention_review",
              severity: "medium",
              source_entity: "the princess",
              target_text: "the princess",
              candidate_entities: [{ canonical_name: "Sera", entity_kind: "character" }],
              evidence: [],
              suggested_action: "review_attach_role_or_title",
              metadata: {
                recommended_action: "review_attach_role_or_title",
                signal_tier: "medium",
                candidate_status: "weak_candidate",
                surface_type: "title_like",
                semantic_value: "title",
                language_hint: "en",
                do_not_auto_merge: true
              }
            };
            emit({
              actions: helpers.normalizedFutureViewerActions(item),
              cardHtml: helpers.renderReviewItemCard(item, 0)
            });
            """
        )

        self.assertEqual(payload["actions"], ["attach_role_or_title"])
        self.assertIn("title_like", payload["cardHtml"])
        self.assertIn("title", payload["cardHtml"])
        self.assertIn("en", payload["cardHtml"])


def _run_viewer_helper(script: str) -> dict:
    node_script = textwrap.dedent(
        f"""
        const fs = require("fs");
        globalThis.document = {{
          getElementById: (id) => ({{
            id,
            dataset: {{}},
            classList: {{ toggle: () => {{}} }},
            addEventListener: () => {{}},
            innerHTML: "",
            textContent: "",
            value: "",
            checked: false
          }}),
          querySelectorAll: () => []
        }};
        globalThis.fetch = () => Promise.reject(new Error("network disabled in contract test"));
        globalThis.console = {{ log: () => {{}}, error: () => {{}}, warn: () => {{}} }};
        const code = fs.readFileSync("{APP_JS}", "utf8");
        eval(code);
        function emit(value) {{
          process.stdout.write(JSON.stringify(value));
        }}
        {script}
        """
    )
    completed = subprocess.run(["node", "-e", node_script], check=True, text=True, capture_output=True)
    return json.loads(completed.stdout)


if __name__ == "__main__":
    unittest.main()
