import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from root_workflow import evaluate_root_workflow  # noqa: E402


def worker(role="writer"):
    return {
        "role": role,
        "environment": "isolated_worktree",
        "read_scope": ["repository"],
        "write_scope": ["isolated draft"],
        "capabilities": {
            "durable_mutation": False,
            "real_checkout_integration": False,
        },
        "isolation_proof": "worktree:writer",
    }


def review(design_digest="sha256:design-7", verdict="pass", repair_count=0):
    return {
        "design_revision": 7,
        "design_digest": design_digest,
        "repair_count": repair_count,
        "self_check": {
            "design_digest": design_digest,
            "verdict": "pass",
            "evidence_locators": ["artifact:self-check"],
        },
        "independent_review": {
            "status": "complete",
            "identity": "review-7",
            "design_digest": design_digest,
            "verdict": verdict,
            "independence": {
                "separate_context": True,
                "read_only": True,
                "design_authority": False,
                "mutation_authority": False,
            },
            "findings": [],
            "evidence_locators": ["artifact:independent-review"],
        },
    }


def finding(classification="must-fix", disposition="unresolved"):
    return {
        "identity": "F-1",
        "classification": classification,
        "criterion": "AC-4",
        "affected_nodes": ["design-gate"],
        "sanitized_evidence": "The gate can admit an unresolved finding.",
        "rationale": "Must-fix findings are binding.",
        "clearance_condition": "An independent reviewer clears this finding.",
        "waiver_policy": "unwaivable",
        "disposition": disposition,
    }


def metadata():
    return {
        "revision": 7,
        "authority_preflight": {
            "revision": 7,
            "reachable_decision_loops": [],
            "reachable_mutations": [
                {"identity": "integrate-draft", "owner": "root"}
            ],
            "workers": [worker()],
            "generic_trigger_state": {"T1-WORKER-NEED": "fired"},
            "generic_topology": "L1",
            "evidence": ["evidence:preflight"],
        },
        "observed_effects": ["effect:read-complete"],
        "design_digest": "sha256:design-7",
        "design_review": review(),
    }


class RootWorkflowTests(unittest.TestCase):
    def test_safety_precedes_complexity_without_forbidding_isolated_drafts(self):
        delegated = evaluate_root_workflow(metadata())
        self.assertEqual(delegated["selected_topology"], "L1")
        self.assertEqual(delegated["authority_preflight"]["status"], "allow_generation")
        self.assertTrue(delegated["execution_permission"]["delegated_work"])
        self.assertTrue(delegated["execution_permission"]["root_mutation"])
        self.assertFalse(delegated["execution_permission"]["delegated_mutation"])

        interactive_metadata = metadata()
        interactive_metadata["authority_preflight"]["reachable_decision_loops"] = [
            "review > human choice"
        ]
        interactive = evaluate_root_workflow(interactive_metadata)
        self.assertEqual(interactive["selected_topology"], "L0")
        self.assertEqual(
            interactive["authority_preflight"]["interactivity"]["verdict"],
            "interactive",
        )
        self.assertFalse(interactive["execution_permission"]["delegated_work"])
        self.assertEqual(interactive["workflow_state"], {"state": "continue", "final": False})

    def test_exact_revision_independent_review_gates_authority_bearing_design(self):
        admitted = evaluate_root_workflow(metadata())
        self.assertEqual(admitted["review_gate"]["status"], "pass")
        self.assertTrue(admitted["execution_permission"]["root_mutation"])

        fixtures = {}
        fixtures["missing"] = metadata()
        del fixtures["missing"]["design_review"]

        fixtures["malformed"] = metadata()
        fixtures["malformed"]["design_review"] = "invalid"

        fixtures["stale"] = metadata()
        fixtures["stale"]["design_review"]["design_revision"] = 6

        fixtures["timed_out"] = metadata()
        fixtures["timed_out"]["design_review"]["independent_review"] = {
            "status": "timed_out"
        }

        fixtures["digest_mismatch"] = metadata()
        fixtures["digest_mismatch"]["design_review"]["independent_review"][
            "design_digest"
        ] = "sha256:other-design"

        fixtures["frozen_digest_mismatch"] = metadata()
        fixtures["frozen_digest_mismatch"][
            "design_digest"
        ] = "sha256:different-frozen-design"

        fixtures["empty_self_check_evidence"] = metadata()
        fixtures["empty_self_check_evidence"]["design_review"]["self_check"][
            "evidence_locators"
        ] = []

        fixtures["empty_review_evidence"] = metadata()
        fixtures["empty_review_evidence"]["design_review"]["independent_review"][
            "evidence_locators"
        ] = []

        fixtures["not_independent"] = metadata()
        fixtures["not_independent"]["design_review"]["independent_review"][
            "independence"
        ]["separate_context"] = False

        expected_reasons = {
            "missing": "missing_design_review",
            "timed_out": "independent_review_timed_out",
            "digest_mismatch": "review_digest_mismatch",
            "not_independent": "unproved_reviewer_independence",
            "malformed": "malformed_design_review",
            "stale": "stale_design_review",
            "frozen_digest_mismatch": "frozen_design_digest_mismatch",
            "empty_self_check_evidence": "malformed_self_check_evidence",
            "empty_review_evidence": "malformed_review_evidence",
        }
        for name, fixture in fixtures.items():
            with self.subTest(name=name):
                result = evaluate_root_workflow(fixture)
                self.assertEqual(result["review_gate"]["status"], "block")
                self.assertIn(expected_reasons[name], result["review_gate"]["reasons"])
                self.assertEqual(
                    result["workflow_state"], {"state": "blocked", "final": True}
                )
                self.assertFalse(result["execution_permission"]["root_mutation"])

        read_only = metadata()
        read_only["authority_preflight"]["reachable_mutations"] = []
        del read_only["design_review"]
        del read_only["design_digest"]
        read_only_result = evaluate_root_workflow(read_only)
        self.assertEqual(read_only_result["review_gate"]["status"], "not_applicable")
        self.assertEqual(
            read_only_result["workflow_state"], {"state": "continue", "final": False}
        )

    def test_invalid_preflight_matrix_fails_closed(self):
        fixtures = {}

        fixtures["missing"] = metadata()
        del fixtures["missing"]["authority_preflight"]

        fixtures["malformed"] = metadata()
        fixtures["malformed"]["authority_preflight"] = "invalid"

        fixtures["stale"] = metadata()
        fixtures["stale"]["authority_preflight"]["revision"] = 6

        fixtures["ambiguous"] = metadata()
        fixtures["ambiguous"]["authority_preflight"]["reachable_mutations"].append(
            {"identity": "integrate-draft", "owner": "worker"}
        )

        fixtures["contradicted"] = metadata()
        fixtures["contradicted"]["authority_preflight"]["reachable_mutations"][0][
            "owner"
        ] = "worker"

        fixtures["unproved confinement"] = metadata()
        fixtures["unproved confinement"]["authority_preflight"]["workers"][0][
            "isolation_proof"
        ] = ""

        fixtures["missing worker confinement"] = metadata()
        fixtures["missing worker confinement"]["authority_preflight"]["workers"] = []

        fixtures["read-only L4 without confinement"] = metadata()
        read_only_l4 = fixtures["read-only L4 without confinement"][
            "authority_preflight"
        ]
        read_only_l4["reachable_mutations"] = []
        read_only_l4["workers"] = []
        read_only_l4["generic_trigger_state"] = {"T4-SHARDED-RECOVERY": "fired"}
        read_only_l4["generic_topology"] = "L4"

        fixtures["malformed trigger value"] = metadata()
        fixtures["malformed trigger value"]["authority_preflight"][
            "generic_trigger_state"
        ] = {"T1-WORKER-NEED": []}

        fixtures["malformed topology"] = metadata()
        fixtures["malformed topology"]["authority_preflight"]["generic_topology"] = []

        for name, fixture in fixtures.items():
            with self.subTest(name=name):
                result = evaluate_root_workflow(fixture)
                self.assertEqual(result["selected_topology"], "L0")
                self.assertEqual(result["authority_preflight"]["status"], "block")
                self.assertEqual(
                    result["execution_permission"],
                    {
                        "root_mutation": False,
                        "delegated_work": False,
                        "delegated_mutation": False,
                        "stopped_workers": [],
                    },
                )
                self.assertEqual(result["workflow_state"], {"state": "blocked", "final": True})
                self.assertTrue(result["authority_preflight"]["reasons"])

    def test_runtime_decision_discovery_requires_a_root_l0_plan_and_retains_facts(self):
        result = evaluate_root_workflow(
            metadata(),
            [
                {
                    "type": "decision_loop_discovered",
                    "path": "draft > human approval",
                    "evidence": ["evidence:runtime-decision"],
                    "observed_effects": ["effect:draft-created"],
                }
            ],
        )

        self.assertEqual(result["selected_topology"], "L0")
        self.assertEqual(result["authority_preflight"]["status"], "runtime_replan")
        self.assertEqual(result["authority_preflight"]["required_action"], "root_l0_plan")
        self.assertFalse(result["execution_permission"]["delegated_work"])
        self.assertEqual(result["workflow_state"], {"state": "continue", "final": False})
        self.assertEqual(
            result["retained_evidence"],
            ["evidence:preflight", "evidence:runtime-decision"],
        )
        self.assertEqual(
            result["observed_effects"],
            ["effect:read-complete", "effect:draft-created"],
        )

        malformed = evaluate_root_workflow(
            metadata(),
            [
                {
                    "type": "decision_loop_discovered",
                    "path": "",
                    "evidence": ["evidence:valid-before-invalidation"],
                    "observed_effects": ["effect:already-observed-at-runtime"],
                }
            ],
        )
        self.assertEqual(malformed["workflow_state"], {"state": "blocked", "final": True})
        self.assertIn(
            "evidence:valid-before-invalidation", malformed["retained_evidence"]
        )
        self.assertIn(
            "effect:already-observed-at-runtime", malformed["observed_effects"]
        )

    def test_mixed_validity_evidence_and_effect_lists_retain_valid_facts(self):
        mixed = metadata()
        mixed["authority_preflight"]["evidence"] = [
            "evidence:preflight",
            None,
            "evidence:second",
        ]
        mixed["observed_effects"] = [
            "effect:read-complete",
            3,
            "effect:second",
        ]
        result = evaluate_root_workflow(
            mixed,
            [
                {
                    "type": "decision_loop_discovered",
                    "path": "runtime choice",
                    "evidence": [
                        "evidence:runtime",
                        {},
                        "evidence:runtime-second",
                    ],
                    "observed_effects": [
                        "effect:runtime",
                        "",
                        "effect:runtime-second",
                    ],
                }
            ],
        )

        self.assertEqual(result["workflow_state"], {"state": "blocked", "final": True})
        self.assertEqual(
            result["retained_evidence"],
            [
                "evidence:preflight",
                "evidence:second",
                "evidence:runtime",
                "evidence:runtime-second",
            ],
        )
        self.assertEqual(
            result["observed_effects"],
            [
                "effect:read-complete",
                "effect:second",
                "effect:runtime",
                "effect:runtime-second",
            ],
        )
        self.assertTrue(
            {
                "malformed_authority_evidence",
                "malformed_observed_effects",
                "malformed_runtime_evidence",
                "malformed_runtime_effects",
            }.issubset(result["authority_preflight"]["reasons"])
        )

    def test_worker_discovered_mutation_stops_before_action_and_requires_reproof(self):
        discovery = {
            "type": "worker_mutation_discovered",
            "worker_role": "writer",
            "mutation": {"identity": "publish-draft", "owner": "root"},
            "evidence": ["evidence:mutation-discovery"],
        }

        blocked = evaluate_root_workflow(metadata(), [discovery])
        self.assertEqual(blocked["selected_topology"], "L0")
        self.assertEqual(blocked["authority_preflight"]["status"], "block")
        self.assertEqual(blocked["execution_permission"]["stopped_workers"], ["writer"])
        self.assertFalse(blocked["execution_permission"]["root_mutation"])

        wrong_worker = copy.deepcopy(discovery)
        wrong_worker["revision"] = 8
        wrong_worker["worker_confinement"] = worker("reviewer")
        wrong_worker_result = evaluate_root_workflow(metadata(), [wrong_worker])
        self.assertEqual(
            wrong_worker_result["workflow_state"], {"state": "blocked", "final": True}
        )

        reproved_discovery = copy.deepcopy(discovery)
        reproved_discovery["revision"] = 8
        reproved_discovery["worker_confinement"] = worker()
        stale_review = evaluate_root_workflow(metadata(), [reproved_discovery])
        self.assertIn(
            "stale_design_review", stale_review["review_gate"]["reasons"]
        )
        self.assertFalse(stale_review["execution_permission"]["root_mutation"])

        current_review = review(design_digest="sha256:design-8")
        current_review["design_revision"] = 8
        current_review["independent_review"]["identity"] = "review-8"
        reproved_discovery["design_review"] = current_review
        reproved_discovery["design_digest"] = "sha256:design-8"
        reproved = evaluate_root_workflow(metadata(), [reproved_discovery])
        self.assertEqual(reproved["selected_topology"], "L1")
        self.assertEqual(reproved["authority_preflight"]["status"], "allow_generation")
        self.assertEqual(reproved["authority_preflight"]["revision"], 8)
        self.assertEqual(reproved["execution_permission"]["stopped_workers"], ["writer"])
        self.assertTrue(reproved["execution_permission"]["root_mutation"])
        self.assertTrue(reproved["execution_permission"]["delegated_work"])
        self.assertFalse(reproved["execution_permission"]["delegated_mutation"])
        self.assertIn("evidence:preflight", reproved["retained_evidence"])

        parallel_metadata = metadata()
        parallel_metadata["authority_preflight"]["workers"].append(worker("reviewer"))
        writer_reproof = copy.deepcopy(reproved_discovery)
        reviewer_reproof = {
            "type": "worker_mutation_discovered",
            "worker_role": "reviewer",
            "mutation": {"identity": "publish-review", "owner": "root"},
            "revision": 8,
            "worker_confinement": worker("reviewer"),
        }
        parallel = evaluate_root_workflow(
            parallel_metadata, [writer_reproof, reviewer_reproof]
        )
        self.assertEqual(parallel["authority_preflight"]["status"], "allow_generation")
        self.assertEqual(parallel["authority_preflight"]["revision"], 8)
        self.assertEqual(
            parallel["execution_permission"]["stopped_workers"], ["writer", "reviewer"]
        )
        self.assertTrue(parallel["execution_permission"]["delegated_work"])

    def test_process_facts_and_attempt_verdicts_never_become_workflow_success(self):
        process_facts = [
            {"type": "process_exit", "code": 0},
            {"type": "generated_output", "artifact": "candidate.json"},
            {"type": "attempt_pass", "attempt": "validator-1"},
        ]
        result = evaluate_root_workflow(metadata(), process_facts)
        self.assertEqual(result["workflow_state"], {"state": "continue", "final": False})
        self.assertNotEqual(result["workflow_state"]["state"], "accepted")

        waiting = evaluate_root_workflow(
            metadata(),
            [
                {"type": "human_decision_required", "path": "approval"},
                {"type": "decision_loop_discovered", "path": "later choice"},
            ],
        )
        self.assertEqual(
            waiting["workflow_state"],
            {"state": "human_decision_required", "final": False},
        )
        self.assertEqual(waiting["selected_topology"], "L0")

    def test_findings_require_complete_binding_dispositions_and_clearance(self):
        advisory = metadata()
        advisory_finding = finding("advisory", disposition="advisory")
        advisory["design_review"]["independent_review"]["findings"] = [
            advisory_finding
        ]
        advisory_result = evaluate_root_workflow(advisory)
        self.assertEqual(advisory_result["review_gate"]["status"], "pass")
        self.assertEqual(
            advisory_result["review_gate"]["independent_review"]["findings"],
            [advisory_finding],
        )

        for field in (
            "identity",
            "classification",
            "criterion",
            "affected_nodes",
            "sanitized_evidence",
            "rationale",
            "clearance_condition",
            "waiver_policy",
        ):
            with self.subTest(missing_finding_field=field):
                malformed = metadata()
                malformed_finding = finding()
                del malformed_finding[field]
                malformed["design_review"]["independent_review"]["findings"] = [
                    malformed_finding
                ]
                malformed_result = evaluate_root_workflow(malformed)
                self.assertIn(
                    "malformed_review_finding",
                    malformed_result["review_gate"]["reasons"],
                )

        duplicate = metadata()
        duplicate["design_review"]["independent_review"]["findings"] = [
            finding("advisory", disposition="advisory"),
            finding("advisory", disposition="advisory"),
        ]
        self.assertIn(
            "duplicate_finding_identity",
            evaluate_root_workflow(duplicate)["review_gate"]["reasons"],
        )

        unresolved = metadata()
        unresolved["design_review"]["independent_review"]["findings"] = [finding()]
        unresolved_result = evaluate_root_workflow(unresolved)
        self.assertIn(
            "unresolved_must_fix", unresolved_result["review_gate"]["reasons"]
        )

        repaired_without_clearance = metadata()
        repaired_without_clearance["design_review"]["independent_review"][
            "findings"
        ] = [finding(disposition="repaired")]
        repaired_without_clearance_result = evaluate_root_workflow(
            repaired_without_clearance
        )
        self.assertIn(
            "missing_independent_clearance",
            repaired_without_clearance_result["review_gate"]["reasons"],
        )

        repaired_without_repair = metadata()
        repaired_finding = finding(disposition="repaired")
        repaired_finding["clearance"] = {
            "finding_identity": "F-1",
            "review_identity": "review-7",
            "design_digest": "sha256:design-7",
        }
        repaired_without_repair["design_review"]["independent_review"]["findings"] = [
            repaired_finding
        ]
        self.assertIn(
            "repair_count_mismatch",
            evaluate_root_workflow(repaired_without_repair)["review_gate"]["reasons"],
        )

        exact_deviation = metadata()
        deviation_finding = finding(disposition="human-authorized-deviation")
        deviation_finding["waiver_policy"] = "human-authorized"
        deviation_finding["clearance"] = {
            "finding_identity": "F-1",
            "design_revision": 7,
            "decision_receipt": "decision:D-1",
        }
        exact_deviation["design_review"]["independent_review"]["findings"] = [
            deviation_finding
        ]
        self.assertEqual(
            evaluate_root_workflow(exact_deviation)["review_gate"]["status"], "pass"
        )

        unwaivable = copy.deepcopy(exact_deviation)
        unwaivable["design_review"]["independent_review"]["findings"][0][
            "waiver_policy"
        ] = "unwaivable"
        self.assertIn(
            "unwaivable_finding",
            evaluate_root_workflow(unwaivable)["review_gate"]["reasons"],
        )

        broad_approval = copy.deepcopy(exact_deviation)
        broad_approval["design_review"]["independent_review"]["findings"][0][
            "clearance"
        ] = {"decision_receipt": "approval:all"}
        self.assertIn(
            "inexact_human_deviation",
            evaluate_root_workflow(broad_approval)["review_gate"]["reasons"],
        )


    def test_one_repair_repeats_the_full_stack_and_a_second_repair_blocks(self):
        repair_required = metadata()
        repair_required["design_review"]["independent_review"]["verdict"] = "repair"
        repair_required["design_review"]["independent_review"]["findings"] = [finding()]
        repair_result = evaluate_root_workflow(repair_required)
        self.assertEqual(repair_result["review_gate"]["status"], "repair_required")
        self.assertEqual(
            repair_result["review_gate"]["required_action"], "repair_design"
        )
        self.assertEqual(
            repair_result["workflow_state"], {"state": "continue", "final": False}
        )
        self.assertFalse(repair_result["execution_permission"]["root_mutation"])
        self.assertFalse(repair_result["execution_permission"]["delegated_work"])
        review_checkpoint = repair_result["review_checkpoint"]

        repaired = metadata()
        repaired["revision"] = 8
        repaired["authority_preflight"]["revision"] = 8
        repaired["design_digest"] = "sha256:design-8"
        repaired["design_review"] = review(
            design_digest="sha256:design-8", repair_count=1
        )
        repaired["design_review"]["design_revision"] = 8
        repaired["design_review"]["previous_review"] = copy.deepcopy(
            repair_required["design_review"]
        )
        repaired["design_review"]["independent_review"]["identity"] = "review-8"
        omitted = evaluate_root_workflow(
            repaired, review_checkpoint=review_checkpoint
        )
        self.assertIn("missing_prior_finding", omitted["review_gate"]["reasons"])

        repaired_finding = finding(disposition="repaired")
        repaired_finding["clearance"] = {
            "finding_identity": "F-1",
            "review_identity": "review-8",
            "design_digest": "sha256:design-8",
        }
        repaired["design_review"]["independent_review"]["findings"] = [
            repaired_finding
        ]
        repaired_result = evaluate_root_workflow(
            repaired, review_checkpoint=review_checkpoint
        )
        self.assertEqual(repaired_result["review_gate"]["status"], "pass")
        self.assertTrue(repaired_result["execution_permission"]["root_mutation"])
        self.assertEqual(repaired_result["review_checkpoint"], review_checkpoint)
        resumed_result = evaluate_root_workflow(
            repaired,
            review_checkpoint=repaired_result["review_checkpoint"],
        )
        self.assertEqual(resumed_result["review_gate"]["status"], "pass")

        stale_self_check = copy.deepcopy(repaired)
        stale_self_check["design_review"]["self_check"][
            "design_digest"
        ] = "sha256:design-7"
        blocked_repaired_result = evaluate_root_workflow(
            stale_self_check, review_checkpoint=review_checkpoint
        )
        self.assertIn(
            "self_check_digest_mismatch",
            blocked_repaired_result["review_gate"]["reasons"],
        )
        self.assertEqual(
            blocked_repaired_result["review_checkpoint"], review_checkpoint
        )
        corrected_result = evaluate_root_workflow(
            repaired,
            review_checkpoint=blocked_repaired_result["review_checkpoint"],
        )
        self.assertEqual(corrected_result["review_gate"]["status"], "pass")

        missing_previous_review = copy.deepcopy(repaired)
        del missing_previous_review["design_review"]["previous_review"]
        self.assertIn(
            "missing_previous_review",
            evaluate_root_workflow(
                missing_previous_review, review_checkpoint=review_checkpoint
            )["review_gate"]["reasons"],
        )

        unchanged_revision = copy.deepcopy(repaired)
        unchanged_revision["design_review"]["previous_review"]["design_revision"] = 8
        self.assertIn(
            "repair_did_not_create_new_revision",
            evaluate_root_workflow(
                unchanged_revision, review_checkpoint=review_checkpoint
            )["review_gate"]["reasons"],
        )

        substituted_finding = copy.deepcopy(repaired)
        replacement = copy.deepcopy(repaired_finding)
        replacement["identity"] = "F-2"
        replacement["clearance"]["finding_identity"] = "F-2"
        substituted_finding["design_review"]["independent_review"]["findings"] = [
            replacement
        ]
        self.assertIn(
            "missing_prior_finding",
            evaluate_root_workflow(
                substituted_finding, review_checkpoint=review_checkpoint
            )["review_gate"]["reasons"],
        )

        altered_finding = copy.deepcopy(repaired)
        altered_finding["design_review"]["independent_review"]["findings"][0][
            "criterion"
        ] = "different-criterion"
        self.assertIn(
            "altered_prior_finding",
            evaluate_root_workflow(
                altered_finding, review_checkpoint=review_checkpoint
            )["review_gate"]["reasons"],
        )

        human_deviation = copy.deepcopy(repaired)
        human_deviation["design_review"]["previous_review"]["independent_review"][
            "findings"
        ][0]["waiver_policy"] = "human-authorized"
        human_finding = human_deviation["design_review"]["independent_review"][
            "findings"
        ][0]
        human_finding["disposition"] = "human-authorized-deviation"
        human_finding["waiver_policy"] = "human-authorized"
        human_finding["clearance"] = {
            "finding_identity": "F-1",
            "design_revision": 8,
            "decision_receipt": "decision:D-1",
        }
        self.assertEqual(
            evaluate_root_workflow(
                human_deviation, review_checkpoint=review_checkpoint
            )["review_gate"]["status"],
            "pass",
        )

        second_repair = copy.deepcopy(repaired)
        second_repair["design_review"]["independent_review"]["verdict"] = "repair"
        second_finding = finding()
        second_finding["identity"] = "F-2"
        second_repair["design_review"]["independent_review"]["findings"].append(
            second_finding
        )
        self.assertIn(
            "repair_limit_exceeded",
            evaluate_root_workflow(
                second_repair, review_checkpoint=review_checkpoint
            )["review_gate"]["reasons"],
        )

        blocked = metadata()
        blocked["design_review"]["independent_review"]["verdict"] = "block"
        blocked_result = evaluate_root_workflow(blocked)
        self.assertIn(
            "independent_review_blocked", blocked_result["review_gate"]["reasons"]
        )
        self.assertEqual(
            blocked_result["workflow_state"], {"state": "blocked", "final": True}
        )

    def test_root_checkpoint_prevents_repair_count_reset_on_new_revision(self):
        first_revision = metadata()
        first_revision["design_review"]["independent_review"]["verdict"] = "repair"
        first_revision["design_review"]["independent_review"]["findings"] = [finding()]
        first_result = evaluate_root_workflow(first_revision)
        self.assertEqual(first_result["review_gate"]["status"], "repair_required")
        self.assertTrue(first_result["review_checkpoint"]["automatic_repair_used"])

        next_revision = metadata()
        next_revision["revision"] = 8
        next_revision["authority_preflight"]["revision"] = 8
        next_revision["design_digest"] = "sha256:design-8"
        next_revision["design_review"] = review(
            design_digest="sha256:design-8",
            verdict="repair",
            repair_count=0,
        )
        next_revision["design_review"]["design_revision"] = 8
        next_revision["design_review"]["independent_review"]["identity"] = "review-8"
        next_finding = finding()
        next_finding["identity"] = "F-2"
        next_revision["design_review"]["independent_review"]["findings"] = [
            next_finding
        ]

        reset_result = evaluate_root_workflow(
            next_revision,
            review_checkpoint=first_result["review_checkpoint"],
        )
        self.assertEqual(reset_result["review_gate"]["status"], "block")
        self.assertIn(
            "repair_limit_exceeded", reset_result["review_gate"]["reasons"]
        )
        self.assertFalse(reset_result["execution_permission"]["root_mutation"])

    def test_malformed_checkpoint_cannot_restore_repair_allowance(self):
        prior_revision = metadata()
        prior_revision["design_review"]["independent_review"]["verdict"] = "repair"
        prior_revision["design_review"]["independent_review"]["findings"] = [finding()]

        repaired = metadata()
        repaired["revision"] = 8
        repaired["authority_preflight"]["revision"] = 8
        repaired["design_digest"] = "sha256:design-8"
        repaired["design_review"] = review(
            design_digest="sha256:design-8", repair_count=1
        )
        repaired["design_review"]["design_revision"] = 8
        repaired["design_review"]["previous_review"] = copy.deepcopy(
            prior_revision["design_review"]
        )
        repaired["design_review"]["independent_review"]["identity"] = "review-8"
        repaired_finding = finding(disposition="repaired")
        repaired_finding["clearance"] = {
            "finding_identity": "F-1",
            "review_identity": "review-8",
            "design_digest": "sha256:design-8",
        }
        repaired["design_review"]["independent_review"]["findings"] = [
            repaired_finding
        ]

        malformed_result = evaluate_root_workflow(
            repaired,
            review_checkpoint={
                "design_revision": 7,
                "design_digest": "sha256:design-7",
            },
        )
        self.assertEqual(malformed_result["review_gate"]["status"], "block")
        self.assertIn(
            "malformed_review_checkpoint",
            malformed_result["authority_preflight"]["reasons"],
        )
        self.assertEqual(
            malformed_result["review_checkpoint"],
            {
                "design_revision": 7,
                "design_digest": "sha256:design-7",
                "automatic_repair_used": True,
            },
        )

        reset = metadata()
        reset["revision"] = 9
        reset["authority_preflight"]["revision"] = 9
        reset["design_digest"] = "sha256:design-9"
        reset["design_review"] = review(
            design_digest="sha256:design-9",
            verdict="repair",
            repair_count=0,
        )
        reset["design_review"]["design_revision"] = 9
        reset["design_review"]["independent_review"]["identity"] = "review-9"
        reset_finding = finding()
        reset_finding["identity"] = "F-2"
        reset["design_review"]["independent_review"]["findings"] = [reset_finding]

        reset_result = evaluate_root_workflow(
            reset,
            review_checkpoint=malformed_result["review_checkpoint"],
        )
        self.assertEqual(reset_result["review_gate"]["status"], "block")
        self.assertIn(
            "repair_limit_exceeded", reset_result["review_gate"]["reasons"]
        )

if __name__ == "__main__":
    unittest.main()
