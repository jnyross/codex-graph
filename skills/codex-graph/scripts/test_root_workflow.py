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


def mutation_admission():
    return {
        "mutation_id": "integrate-draft",
        "action": "integrate",
        "target_state": "integrated",
        "targets": [{"identity": "draft:1", "version": "v7", "state": "ready"}],
        "fixed_predicate": {
            "identity": "selected-draft",
            "selection_fields": ["identity", "version", "state"],
            "classification_fields": ["content"],
        },
        "acceptance_path": {
            "canonical_identity": {
                "locator": "identity:draft:1",
                "target_ids": ["draft:1"],
            },
            "complete_pre_state": {
                "locator": "read:draft:1@v7",
                "target_ids": ["draft:1"],
            },
            "authoritative_receipt": {
                "locator": "receipt:commit-result",
                "target_ids": ["draft:1"],
            },
            "independent_post_state": {
                "locator": "root-read:draft:1",
                "target_ids": ["draft:1"],
                "actor": "root",
            },
        },
        "transport_proof": {
            "proof_id": "transport:integrate-draft",
            "mutation_id": "integrate-draft",
            "capability": "cursor_page",
            "requested_scope": ["draft:1"],
            "returned_scope": ["draft:1"],
            "required_fields": ["identity", "version", "state", "content"],
            "pages": [
                {
                    "cursor": "start",
                    "next_cursor": None,
                    "target_ids": ["draft:1"],
                }
            ],
            "action": "integrate",
            "target_state": "integrated",
            "predicate_identity": "selected-draft",
            "target_bindings": [
                {"identity": "draft:1", "version": "v7", "state": "ready"}
            ],
            "terminal_witness": {
                "kind": "cursor_exhausted",
                "locator": "read:draft:1:page:1",
            },
            "signals": [],
            "recovery_attempts": [],
        },
        "security_gate": {
            "transport_proof_id": "transport:integrate-draft",
            "binding": {
                "mutation_id": "integrate-draft",
                "action": "integrate",
                "target_state": "integrated",
                "predicate_identity": "selected-draft",
                "target_bindings": [
                    {"identity": "draft:1", "version": "v7", "state": "ready"}
                ],
            },
            "item_classifications": [
                {
                    "item_id": "draft:1",
                    "result": "unprotected",
                    "categories": [],
                    "evidence": ["classifier:draft:1"],
                    "deterministic_markers": [],
                    "uncertainty": [],
                    "expiry": [],
                }
            ],
            "action_classification": {
                "result": "unprotected",
                "categories": [],
                "evidence": ["classifier:integrate"],
                "deterministic_markers": [],
                "uncertainty": [],
                "expiry": [],
            },
            "authorization": None,
            "item_level_execution": True,
            "uncoupled": True,
        },
    }


def metadata():
    return {
        "queue_revision": 11,
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
        "mutation_admission": mutation_admission(),
    }


def add_target(fixture, identity="draft:2", version="v4", state="ready"):
    proposal = fixture["mutation_admission"]
    target = {"identity": identity, "version": version, "state": state}
    proposal["targets"].append(target)
    for capability in proposal["acceptance_path"].values():
        capability["target_ids"].append(identity)

    proof = proposal["transport_proof"]
    proof["target_bindings"].append(target)
    proof["requested_scope"].append(identity)
    proof["returned_scope"].append(identity)
    proof["pages"][0]["target_ids"].append(identity)

    security = proposal["security_gate"]
    security["binding"]["target_bindings"].append(target)
    security["item_classifications"].append(
        {
            "item_id": identity,
            "result": "unprotected",
            "categories": [],
            "evidence": [f"classifier:{identity}"],
            "deterministic_markers": [],
            "uncertainty": [],
            "expiry": [],
        }
    )


class RootWorkflowTests(unittest.TestCase):
    def test_complete_transport_and_unprotected_classification_admit_mutation(self):
        result = evaluate_root_workflow(metadata())

        self.assertEqual(
            result["mutation_admission"],
            {
                "mutation_id": "integrate-draft",
                "status": "allow",
                "evaluated_gates": [
                    "transport",
                    "classification",
                    "authorization",
                    "mutation",
                ],
                "allowed_items": ["draft:1"],
                "blocked_items": [],
                "reasons": [],
            },
        )
        self.assertTrue(result["execution_permission"]["root_mutation"])

    def test_transport_capabilities_require_positive_terminal_witnesses(self):
        valid_witnesses = {
            "bounded_list": {
                "kind": "authoritative_total",
                "total": 1,
                "locator": "read:drafts:total",
            },
            "object_blob": {
                "kind": "complete_content",
                "length": 12,
                "checksum": "sha256:draft",
                "locator": "read:draft:1",
            },
            "range": {
                "kind": "gap_free_ranges",
                "total_length": 12,
                "ranges": [[0, 5], [5, 12]],
                "locator": "read:draft:1:ranges",
            },
        }
        for capability, witness in valid_witnesses.items():
            with self.subTest(capability=capability):
                fixture = metadata()
                proof = fixture["mutation_admission"]["transport_proof"]
                proof["capability"] = capability
                proof["terminal_witness"] = witness
                self.assertEqual(
                    evaluate_root_workflow(fixture)["mutation_admission"]["status"],
                    "allow",
                )

        for boundary in (
            {"complete_marker": "complete"},
            {"length": 12},
            {"checksum": "sha256:draft"},
        ):
            with self.subTest(object_boundary=boundary):
                fixture = metadata()
                fixture["mutation_admission"]["transport_proof"][
                    "capability"
                ] = "object_blob"
                fixture["mutation_admission"]["transport_proof"][
                    "terminal_witness"
                ] = {
                    "kind": "complete_content",
                    "locator": "read:draft:1",
                    **boundary,
                }
                self.assertEqual(
                    evaluate_root_workflow(fixture)["mutation_admission"]["status"],
                    "allow",
                )

        cursor_chain = metadata()
        pages = cursor_chain["mutation_admission"]["transport_proof"]["pages"]
        pages[0]["next_cursor"] = "page:2"
        pages.append(
            {"cursor": "page:2", "next_cursor": None, "target_ids": []}
        )
        self.assertEqual(
            evaluate_root_workflow(cursor_chain)["mutation_admission"]["status"],
            "allow",
        )
        pages[1]["cursor"] = "skipped"
        self.assertEqual(
            evaluate_root_workflow(cursor_chain)["mutation_admission"]["status"],
            "blocked",
        )

        invalid_witnesses = {
            "opaque display": ("opaque_display_only", {"kind": "visible"}),
            "warning": (
                "cursor_page",
                {"kind": "cursor_exhausted", "locator": "read:draft:1:page:1"},
            ),
            "naked completeness": ("object_blob", {"complete": True}),
            "unsupported short page": (
                "bounded_list",
                {"kind": "short_page", "count": 1},
            ),
            "byte gap": (
                "range",
                {
                    "kind": "gap_free_ranges",
                    "total_length": 12,
                    "ranges": [[0, 5], [6, 12]],
                    "locator": "read:draft:1:ranges",
                },
            ),
        }
        for name, (capability, witness) in invalid_witnesses.items():
            with self.subTest(name=name):
                fixture = metadata()
                proof = fixture["mutation_admission"]["transport_proof"]
                proof["capability"] = capability
                proof["terminal_witness"] = witness
                if name == "warning":
                    proof["signals"] = [
                        {"scope": "draft:1", "kind": "truncation_warning"}
                    ]
                result = evaluate_root_workflow(fixture)
                self.assertEqual(result["mutation_admission"]["status"], "blocked")
                self.assertEqual(
                    result["mutation_admission"]["evaluated_gates"], ["transport"]
                )
                self.assertFalse(result["execution_permission"]["root_mutation"])

    def test_transport_scope_binding_and_localized_incompleteness(self):
        invalid_bindings = {}

        invalid_bindings["acceptance path"] = metadata()
        del invalid_bindings["acceptance path"]["mutation_admission"][
            "acceptance_path"
        ]["independent_post_state"]

        invalid_bindings["receipt as post-state"] = metadata()
        acceptance = invalid_bindings["receipt as post-state"][
            "mutation_admission"
        ]["acceptance_path"]
        acceptance["independent_post_state"]["locator"] = acceptance[
            "authoritative_receipt"
        ]["locator"]

        invalid_bindings["mutation"] = metadata()
        invalid_bindings["mutation"]["mutation_admission"]["transport_proof"][
            "mutation_id"
        ] = "other"

        invalid_bindings["fields"] = metadata()
        invalid_bindings["fields"]["mutation_admission"]["transport_proof"][
            "required_fields"
        ].remove("content")

        invalid_bindings["scope"] = metadata()
        invalid_bindings["scope"]["mutation_admission"]["transport_proof"][
            "returned_scope"
        ] = []

        invalid_bindings["target version"] = metadata()
        del invalid_bindings["target version"]["mutation_admission"]["targets"][0][
            "version"
        ]

        for name, fixture in invalid_bindings.items():
            with self.subTest(name=name):
                admission = evaluate_root_workflow(fixture)["mutation_admission"]
                self.assertEqual(admission["status"], "blocked")
                self.assertEqual(admission["evaluated_gates"], ["transport"])

        localized = metadata()
        add_target(localized)
        proof = localized["mutation_admission"]["transport_proof"]
        proof["signals"] = [
            {"scope": "draft:1", "kind": "truncation_warning"}
        ]

        partitioned = evaluate_root_workflow(localized)
        self.assertEqual(partitioned["mutation_admission"]["status"], "allow")
        self.assertEqual(
            partitioned["mutation_admission"]["allowed_items"], ["draft:2"]
        )
        self.assertEqual(
            partitioned["mutation_admission"]["blocked_items"], ["draft:1"]
        )

        generic = copy.deepcopy(localized)
        generic["mutation_admission"]["transport_proof"]["signals"][0][
            "scope"
        ] = "call"
        generic_result = evaluate_root_workflow(generic)
        self.assertEqual(generic_result["mutation_admission"]["status"], "blocked")
        self.assertEqual(
            generic_result["mutation_admission"]["blocked_items"],
            ["draft:1", "draft:2"],
        )

        aggregate = copy.deepcopy(localized)
        aggregate["mutation_admission"]["transport_proof"][
            "aggregate_required"
        ] = True
        aggregate_result = evaluate_root_workflow(aggregate)
        self.assertEqual(
            aggregate_result["mutation_admission"]["status"], "blocked"
        )



    def test_recovery_requires_progress_and_returns_bounded_forensics(self):
        fixture = metadata()
        proof = fixture["mutation_admission"]["transport_proof"]
        proof["pages"][0]["next_cursor"] = "next"
        proof["recovery_bound"] = 2
        proof["recovery_attempts"] = [
            {
                "input": "cursor:next",
                "completed_units": 1,
                "remaining_units": 1,
            },
            {
                "input": "cursor:next",
                "completed_units": 1,
                "remaining_units": 1,
            },
        ]
        proof["forensics"] = {
            "cap_bytes": 64,
            "last_raw": "truncated page",
            "completed_evidence": ["read:draft:1:page:1"],
            "live_handles": ["cursor:next"],
            "failed_scope": ["draft:1"],
            "signals": [],
        }
        proof["unblock_condition"] = "Obtain the authoritative terminal page."

        blocked = evaluate_root_workflow(fixture)["mutation_admission"]
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("repeated_incomplete_input", blocked["reasons"])
        self.assertEqual(blocked["recovery_attempts"], proof["recovery_attempts"])
        self.assertEqual(blocked["forensics"], proof["forensics"])
        self.assertEqual(
            blocked["unblock_condition"],
            "Obtain the authoritative terminal page.",
        )

        no_progress = copy.deepcopy(fixture)
        no_progress_attempts = no_progress["mutation_admission"][
            "transport_proof"
        ]["recovery_attempts"]
        no_progress_attempts[1]["input"] = "cursor:smaller-page"
        no_progress_result = evaluate_root_workflow(no_progress)[
            "mutation_admission"
        ]
        self.assertIn("recovery_no_progress", no_progress_result["reasons"])

        over_bound = copy.deepcopy(no_progress)
        over_bound["mutation_admission"]["transport_proof"]["recovery_bound"] = 1
        over_bound_result = evaluate_root_workflow(over_bound)["mutation_admission"]
        self.assertIn("recovery_bound_exceeded", over_bound_result["reasons"])

        monotonic = metadata()
        monotonic["mutation_admission"]["transport_proof"][
            "recovery_attempts"
        ] = [
            {
                "input": "cursor:first",
                "completed_units": 0,
                "remaining_units": 2,
            },
            {
                "input": "cursor:second",
                "completed_units": 1,
                "remaining_units": 1,
            },
        ]
        self.assertEqual(
            evaluate_root_workflow(monotonic)["mutation_admission"]["status"],
            "allow",
        )


    def test_protected_domains_require_exact_current_authorization(self):
        categories = [
            "security_account_control",
            "identity_official_status",
            "financial_assets_obligations",
            "legal_rights_obligations",
            "health_medical_care",
            "physical_safety_emergency",
            "privacy_consent_data_control",
            "high_impact_eligibility_essential_services",
        ]
        for category in categories:
            with self.subTest(category=category):
                fixture = metadata()
                item = fixture["mutation_admission"]["security_gate"][
                    "item_classifications"
                ][0]
                item.update(
                    {
                        "result": "protected",
                        "categories": [category],
                        "deterministic_markers": [f"marker:{category}"],
                    }
                )
                fixture["mutation_admission"]["security_gate"]["authorization"] = {
                    "receipt_id": "decision:11:1",
                    "queue_revision": 11,
                    "mutation_id": "integrate-draft",
                    "action": "integrate",
                    "target_state": "integrated",
                    "item_ids": ["draft:1"],
                }
                self.assertEqual(
                    evaluate_root_workflow(fixture)["mutation_admission"]["status"],
                    "allow",
                )

        blocked = metadata()
        item = blocked["mutation_admission"]["security_gate"][
            "item_classifications"
        ][0]
        item.update(
            {
                "result": "uncertain",
                "categories": ["security_account_control"],
                "uncertainty": ["conflicting initiator", "missing content"],
                "expiry": ["expired"],
                "model_confidence": 1.0,
            }
        )
        result = evaluate_root_workflow(blocked)["mutation_admission"]
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(
            result["evaluated_gates"],
            ["transport", "classification", "authorization"],
        )

        authorized = copy.deepcopy(blocked)

        authorized["mutation_admission"]["security_gate"]["authorization"] = {
            "receipt_id": "decision:11:2",
            "queue_revision": 11,
            "mutation_id": "integrate-draft",
            "action": "integrate",
            "target_state": "integrated",
            "item_ids": ["draft:1"],
        }
        missing_current_revision = copy.deepcopy(authorized)
        del missing_current_revision["queue_revision"]
        del missing_current_revision["mutation_admission"]["security_gate"][
            "authorization"
        ]["queue_revision"]
        self.assertEqual(
            evaluate_root_workflow(missing_current_revision)[
                "mutation_admission"
            ]["status"],
            "blocked",
        )
        self.assertEqual(
            evaluate_root_workflow(authorized)["mutation_admission"]["status"],
            "allow",
        )

        mismatches = {
            "stale revision": ("queue_revision", 10),
            "mutation": ("mutation_id", "other"),
            "action": ("action", "archive"),
            "state": ("target_state", "archived"),
            "scope": ("item_ids", ["draft:2"]),
        }
        for name, (field, value) in mismatches.items():
            with self.subTest(name=name):
                fixture = copy.deepcopy(authorized)
                fixture["mutation_admission"]["security_gate"]["authorization"][
                    field
                ] = value
                self.assertEqual(
                    evaluate_root_workflow(fixture)["mutation_admission"]["status"],
                    "blocked",
                )

        fixture = metadata()
        add_target(fixture)
        proposed = fixture["mutation_admission"]
        proposed["security_gate"]["item_classifications"][0].update(
            {
                "result": "protected",
                "categories": ["security_account_control"],
                "deterministic_markers": ["marker:account"],
            }
        )

        partitioned = evaluate_root_workflow(fixture)["mutation_admission"]
        self.assertEqual(partitioned["status"], "allow")
        self.assertEqual(partitioned["allowed_items"], ["draft:2"])
        self.assertEqual(partitioned["blocked_items"], ["draft:1"])

        coupled = copy.deepcopy(fixture)
        coupled["mutation_admission"]["security_gate"]["uncoupled"] = False
        coupled_result = evaluate_root_workflow(coupled)["mutation_admission"]
        self.assertEqual(coupled_result["status"], "blocked")
        self.assertEqual(
            coupled_result["blocked_items"], ["draft:1", "draft:2"]
        )

    def test_item_action_predicate_and_scope_changes_restart_the_gate(self):
        changes = {}

        changes["mutation"] = metadata()
        proposal = changes["mutation"]["mutation_admission"]
        proposal["mutation_id"] = "other"
        proposal["transport_proof"]["mutation_id"] = "other"

        changes["action"] = metadata()
        changes["action"]["mutation_admission"]["action"] = "archive"

        changes["target state"] = metadata()
        changes["target state"]["mutation_admission"]["target_state"] = "archived"

        changes["predicate"] = metadata()
        changes["predicate"]["mutation_admission"]["fixed_predicate"][
            "identity"
        ] = "other-predicate"

        changes["item version"] = metadata()
        changes["item version"]["mutation_admission"]["targets"][0][
            "version"
        ] = "v8"

        for name, fixture in changes.items():
            with self.subTest(name=name):
                result = evaluate_root_workflow(fixture)["mutation_admission"]
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["evaluated_gates"], ["transport"])

        reclassified = metadata()
        reclassified["mutation_admission"]["security_gate"][
            "item_classifications"
        ][0].update(
            {
                "result": "protected",
                "categories": ["privacy_consent_data_control"],
                "deterministic_markers": ["marker:privacy"],
            }
        )
        reclassified_result = evaluate_root_workflow(reclassified)[
            "mutation_admission"
        ]
        self.assertEqual(
            reclassified_result["evaluated_gates"],
            ["transport", "classification", "authorization"],
        )

        stale_classification = metadata()
        stale_classification["mutation_admission"]["action"] = "archive"
        proof = stale_classification["mutation_admission"]["transport_proof"]
        proof["action"] = "archive"
        security = stale_classification["mutation_admission"]["security_gate"]
        security["authorization"] = None
        stale_result = evaluate_root_workflow(stale_classification)[
            "mutation_admission"
        ]
        self.assertEqual(stale_result["status"], "blocked")
        self.assertEqual(
            stale_result["evaluated_gates"], ["transport", "classification"]
        )

        unsupported = metadata()
        unsupported["mutation_admission"]["security_gate"][
            "item_classifications"
        ][0]["evidence"] = []
        unsupported_result = evaluate_root_workflow(unsupported)[
            "mutation_admission"
        ]
        self.assertEqual(unsupported_result["status"], "blocked")
        self.assertEqual(
            unsupported_result["evaluated_gates"], ["transport", "classification"]
        )


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

        blocked_mutation = metadata()
        blocked_mutation["mutation_admission"]["transport_proof"]["signals"] = [
            {"scope": "call", "kind": "truncation_warning"}
        ]
        blocked_result = evaluate_root_workflow(blocked_mutation)
        self.assertFalse(blocked_result["execution_permission"]["root_mutation"])
        self.assertTrue(blocked_result["execution_permission"]["delegated_work"])

        no_proposal = metadata()
        del no_proposal["mutation_admission"]
        no_proposal_result = evaluate_root_workflow(no_proposal)
        self.assertFalse(no_proposal_result["execution_permission"]["root_mutation"])
        self.assertTrue(no_proposal_result["execution_permission"]["delegated_work"])

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


if __name__ == "__main__":
    unittest.main()
