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
    }

_FAMILY_CASES = {
    "record_state": {
        "target_id": "record:r_01",
        "action": "set_state",
        "intent": {"expected_state": "state_expected"},
        "pre": {"resource_id": "record:r_01", "version": "ver:41", "state": "state_before"},
        "receipt": {"resulting_version": "ver:42", "status": "committed"},
        "post": {"resource_id": "record:r_01", "version": "ver:42", "state": "state_expected"},
        "order": ("monotonic_version", ["ver:41", "ver:42", "ver:42"]),
        "contradiction": ("state", "state_contradicted"),
    },
    "relationship_set": {
        "target_id": "edge:ed_09",
        "action": "add_edge",
        "intent": {"expected_state": "edge_present"},
        "pre": {
            "subject_id": "principal:p_17",
            "relation": "member",
            "object_id": "group:g_04",
            "state": "edge_absent",
            "set_revision": "setrev:08",
        },
        "receipt": {"set_revision": "setrev:09", "status": "committed"},
        "post": {
            "subject_id": "principal:p_17",
            "relation": "member",
            "object_id": "group:g_04",
            "state": "edge_present",
            "set_revision": "setrev:09",
        },
        "order": ("revision", ["setrev:08", "setrev:09", "setrev:09"]),
        "contradiction": ("state", "state_contradicted"),
    },
    "create_append": {
        "target_id": "create-intent:ci_21",
        "action": "append",
        "intent": {"expected_state": "committed"},
        "pre": {
            "parent_id": "container:c_04",
            "client_mutation_key": "key:k_21",
            "key_state": "unused",
            "payload_digest": "sha256:payload",
        },
        "receipt": {
            "client_mutation_key": "key:k_21",
            "result_resource_id": "entry:e_88",
            "commit_sequence": "seq:19",
            "status": "committed",
        },
        "post": {
            "resource_id": "entry:e_88",
            "state": "committed",
            "commit_sequence": "seq:19",
        },
        "order": ("service_sequence", ["seq:19", "seq:19"]),
        "contradiction": ("state", "state_contradicted"),
    },
    "delete_erase": {
        "target_id": "record:r_31",
        "action": "soft_delete",
        "intent": {"expected_state": "deleted"},
        "pre": {"resource_id": "record:r_31", "version": "ver:12", "state": "present"},
        "receipt": {
            "tombstone_id": "tomb:t_31",
            "deletion_generation": "delgen:13",
            "status": "committed",
        },
        "post": {
            "witness": "authoritative_tombstone",
            "deletion_generation": "delgen:13",
        },
        "order": ("generation", ["ver:12", "delgen:13", "delgen:13"]),
        "contradiction": ("witness", "target_present"),
    },
    "blob_content": {
        "target_id": "blob:b_52",
        "action": "replace_content",
        "intent": {"expected_digest": "sha256:post"},
        "pre": {
            "object_id": "blob:b_52",
            "generation": "gen:02",
            "length": 4,
            "digest": "sha256:pre",
            "ranges": [[0, 4]],
        },
        "receipt": {
            "generation": "gen:03",
            "length": 4,
            "digest": "sha256:post",
            "status": "committed",
        },
        "post": {
            "object_id": "blob:b_52",
            "generation": "gen:03",
            "length": 4,
            "digest": "sha256:post",
            "ranges": [[0, 4]],
        },
        "order": ("generation", ["gen:02", "gen:03", "gen:03"]),
        "contradiction": ("digest", "sha256:contradicted"),
    },
    "operation_composite": {
        "target_id": "operation:o_73",
        "action": "run_operation",
        "intent": {"expected_effect_ids": ["record:r_01"]},
        "pre": {
            "operation_id": "operation:o_73",
            "authorized_effect_ids": ["record:r_01"],
            "effect_manifest_capability": True,
        },
        "receipt": {
            "operation_id": "operation:o_73",
            "operation_sequence": "opseq:01",
            "status": "accepted",
        },
        "post": {
            "operation_id": "operation:o_73",
            "terminal": True,
            "operation_sequence": "opseq:06",
            "effect_ids": ["record:r_01"],
            "effect_manifest_ref": "effectmanifest:01",
        },
        "order": ("service_sequence", ["opseq:01", "opseq:06"]),
        "contradiction": ("effect_ids", ["record:r_99"]),
    },
}


def _transport_record(target_ids, capability="single_object_blob"):
    record = {
        "kind": "transport_proof",
        "outcome": "complete",
        "capability": capability,
        "target_ids": list(target_ids),
    }
    if capability == "bounded_list":
        record["witness"] = {
            "authoritative_total": len(target_ids),
            "unique_count": len(target_ids),
        }
    else:
        record["witness"] = {
            "kind": "authoritative_object",
            "value": "version:observed",
        }
    return record


def _target_fixture(family, prefix):
    case = _FAMILY_CASES[family]
    target_id = case["target_id"]
    mutation_id = f"mutation:{prefix}"
    refs = {
        "alias": f"idp:{prefix}",
        "set": f"tp:set:{prefix}",
        "pre_transport": f"tp:pre:{prefix}",
        "post_transport": f"tp:post:{prefix}",
        "pre": f"pre:{prefix}",
        "receipt": f"receipt:{prefix}",
        "post": f"post:{prefix}",
        "security": f"sg:{prefix}",
    }
    records = {
        refs["alias"]: {
            "kind": "identity_mapping",
            "authoritative": True,
            "alias": f"alias:{prefix}",
            "canonical_target_ids": [target_id],
        },
        refs["set"]: _transport_record([target_id], "bounded_list"),
        refs["pre_transport"]: _transport_record([target_id]),
        refs["post_transport"]: _transport_record([target_id]),
        refs["pre"]: {
            "kind": "pre_state",
            "owner": "root",
            "authoritative": True,
            "target_id": target_id,
            "transport_ref": refs["pre_transport"],
            **copy.deepcopy(case["pre"]),
        },
        refs["receipt"]: {
            "kind": "receipt",
            "authoritative": True,
            "target_id": target_id,
            "mutation_id": mutation_id,
            "action": case["action"],
            **copy.deepcopy(case["receipt"]),
        },
        refs["post"]: {
            "kind": "post_state",
            "owner": "root",
            "authoritative": True,
            "target_id": target_id,
            "transport_ref": refs["post_transport"],
            **copy.deepcopy(case["post"]),
        },
        refs["security"]: {
            "kind": "security_gate",
            "verdict": "allow",
            "target_id": target_id,
            "mutation_id": mutation_id,
            "action": case["action"],
        },
    }
    target = {
        "canonical_target_id": target_id,
        "aliases": [{"alias": f"alias:{prefix}", "proof_ref": refs["alias"]}],
        "eligibility": {
            "eligible": True,
            "reason_code": "predicate_matched",
            "evidence_refs": [refs["pre"], refs["security"]],
        },
        "intent": {
            "mutation_id": mutation_id,
            "action": case["action"],
            **copy.deepcopy(case["intent"]),
        },
        "pre_ref": refs["pre"],
        "receipt_ref": refs["receipt"],
        "post_ref": refs["post"],
        "ordering_proof": {
            "kind": case["order"][0],
            "status": "proved",
            "values": list(case["order"][1]),
        },
        "outcome": "accepted",
    }
    if family == "create_append":
        binding_ref = f"idp:create:{prefix}"
        target["identity_binding_ref"] = binding_ref
        records[binding_ref] = {
            "kind": "create_identity_binding",
            "authoritative": True,
            "client_mutation_key": case["pre"]["client_mutation_key"],
            "result_resource_id": case["receipt"]["result_resource_id"],
        }
    evidence = {
        "identity_proofs": [refs["alias"]]
        + ([target["identity_binding_ref"]] if family == "create_append" else []),
        "transport_proofs": [
            refs["set"],
            refs["pre_transport"],
            refs["post_transport"],
        ],
        "pre": [refs["pre"]],
        "security_gate": [refs["security"]],
        "actions": [refs["receipt"]],
        "post": [refs["post"]],
    }
    return target, records, evidence, refs


def family_manifest(family="record_state"):
    target, records, evidence, refs = _target_fixture(family, "01")
    if family == "operation_composite":
        leaf, leaf_records, leaf_evidence, _ = _target_fixture(
            "record_state", "leaf"
        )
        leaf["family"] = "record_state"
        target["leaf_entries"] = [leaf]
        records.update(leaf_records)
        for name, values in leaf_evidence.items():
            evidence[name].extend(values)

    target_id = target["canonical_target_id"]
    return {
        "schema": "codexgraph.acceptance-manifest/v1",
        "workflow": {
            "workflow_id": "workflow:w_01",
            "revision": 7,
            "attempt_id": "attempt:a_01",
            "root_actor": "root",
        },
        "adapter": {
            "family": family,
            "adapter_id": "adapter:a_01",
            "adapter_version": "v1",
            "tool_contract_digest": "sha256:tool",
        },
        "authorization": {
            "scope_id": "scope:s_01",
            "decision_ref": "decision:d_01@queue:q_01",
            "exact_action": _FAMILY_CASES[family]["action"],
            "canonical_target_ids": [target_id],
            "set_proof_ref": refs["set"],
        },
        "evidence": evidence,
        "evidence_records": records,
        "targets": [target],
        "reconciliation": {
            "authorized": [target_id],
            "inspected": [target_id],
            "intended": [target_id],
            "attempted": [target_id],
            "receipt_resolved": [target_id],
            "post_verified": [target_id],
            "accepted": [target_id],
            "failed": [],
            "unknown": [],
            "skipped": [],
            "unauthorized": [],
            "duplicates": [],
            "derived_counts": {"accepted": 99},
        },
        "repair": {
            "allowed": ["narrow_read", "normalize_and_reconcile"],
            "forbidden": ["mutation_retry", "corrective_mutation"],
            "attempts": [],
        },
        "retention": {
            "policy_id": "privacy_minimized",
            "retained": [
                "opaque_ids",
                "generic_state_codes",
                "counts",
                "versions",
                "locators",
                "digests",
                "terminal_reason",
            ],
            "raw_payload": "not_retained",
            "evidence_locator_expiry": "time:locator",
            "manifest_expiry": "time:manifest",
            "redaction_proof_ref": "redaction:01",
        },
        "terminal": {"status": "accepted", "reason_code": "untrusted_claim"},
    }


def acceptance_manifest():
    return family_manifest()


def evidence_record(manifest, target, name):
    return manifest["evidence_records"][target[f"{name}_ref"]]


def contradict_family(manifest):
    target = manifest["targets"][0]
    field, value = _FAMILY_CASES[manifest["adapter"]["family"]]["contradiction"]
    evidence_record(manifest, target, "post")[field] = value
    return manifest


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

    def test_manifest_accepts_only_resolved_root_owned_target_chains(self):
        accepted_metadata = metadata()
        accepted_metadata["acceptance_manifest"] = acceptance_manifest()
        accepted = evaluate_root_workflow(accepted_metadata)

        self.assertEqual(
            accepted["workflow_state"], {"state": "accepted", "final": True}
        )
        self.assertEqual(
            accepted["acceptance_manifest"]["terminal"],
            {"status": "accepted", "reason_code": "all_targets_verified"},
        )
        self.assertEqual(
            accepted["acceptance_manifest"]["reconciliation"]["derived_counts"],
            {
                "authorized": 1,
                "inspected": 1,
                "intended": 1,
                "attempted": 1,
                "receipt_resolved": 1,
                "post_verified": 1,
                "accepted": 1,
                "failed": 0,
                "unknown": 0,
                "skipped": 0,
                "unauthorized": 0,
                "duplicates": 0,
            },
        )
        self.assertEqual(
            accepted["acceptance_manifest"]["replay_prohibited"],
            ["record:r_01"],
        )

        private = acceptance_manifest()
        private["raw_private_payload"] = "not durable"
        private["targets"][0]["raw_private_payload"] = "not durable"
        private["evidence_records"][private["targets"][0]["pre_ref"]][
            "raw_private_payload"
        ] = "not durable"
        private_metadata = metadata()
        private_metadata["acceptance_manifest"] = private
        retained = evaluate_root_workflow(private_metadata)["acceptance_manifest"]
        self.assertNotIn("raw_private_payload", retained)
        self.assertNotIn("evidence_records", retained)
        self.assertNotIn("raw_private_payload", retained["targets"][0])

        controls = {}
        controls["shaped JSON"] = acceptance_manifest()
        controls["shaped JSON"]["evidence_records"] = {}

        controls["worker post-state claim"] = acceptance_manifest()
        target = controls["worker post-state claim"]["targets"][0]
        evidence_record(controls["worker post-state claim"], target, "post")[
            "owner"
        ] = "worker"

        controls["receipt only"] = acceptance_manifest()
        del controls["receipt only"]["targets"][0]["post_ref"]

        controls["generic timestamp"] = acceptance_manifest()
        controls["generic timestamp"]["targets"][0]["ordering_proof"]["kind"] = (
            "generic_timestamp"
        )

        controls["intended target not inspected"] = acceptance_manifest()
        controls["intended target not inspected"]["reconciliation"]["inspected"] = []

        controls["mismatched receipt action"] = acceptance_manifest()
        target = controls["mismatched receipt action"]["targets"][0]
        evidence_record(controls["mismatched receipt action"], target, "receipt")[
            "action"
        ] = "different_action"

        controls["failure omitted from attempted set"] = contradict_family(
            acceptance_manifest()
        )
        controls["failure omitted from attempted set"]["reconciliation"][
            "attempted"
        ] = []

        expected = {
            "shaped JSON": "failed",
            "worker post-state claim": "indeterminate",
            "receipt only": "indeterminate",
            "generic timestamp": "failed",
            "intended target not inspected": "failed",
            "mismatched receipt action": "failed",
            "failure omitted from attempted set": "failed",
        }
        for name, manifest in controls.items():
            with self.subTest(name=name):
                control_metadata = metadata()
                control_metadata["acceptance_manifest"] = manifest
                self.assertEqual(
                    evaluate_root_workflow(control_metadata)["workflow_state"],
                    {"state": expected[name], "final": True},
                )

    def test_compact_family_matrix_and_shared_terminal_controls(self):
        for family in _FAMILY_CASES:
            with self.subTest(family=family, control="valid"):
                valid_metadata = metadata()
                valid_metadata["acceptance_manifest"] = family_manifest(family)
                self.assertEqual(
                    evaluate_root_workflow(valid_metadata)["workflow_state"],
                    {"state": "accepted", "final": True},
                )

            blocked = family_manifest(family)
            target = blocked["targets"][0]
            alias_record = blocked["evidence_records"][
                target["aliases"][0]["proof_ref"]
            ]
            alias_record["canonical_target_ids"].append("target:ambiguous")
            del target["receipt_ref"]
            del target["post_ref"]
            blocked["evidence"]["actions"] = []
            blocked["evidence"]["post"] = []
            for name in ("attempted", "receipt_resolved", "post_verified", "accepted"):
                blocked["reconciliation"][name] = []

            indeterminate = family_manifest(family)
            del indeterminate["targets"][0]["post_ref"]

            failed = {
                "authoritative contradiction": contradict_family(
                    family_manifest(family)
                ),
                "duplicate mutation": family_manifest(family),
                "unauthorized effect": family_manifest(family),
                "process violation": family_manifest(family),
            }
            failed["duplicate mutation"]["reconciliation"]["duplicates"] = [
                failed["duplicate mutation"]["targets"][0]["canonical_target_id"]
            ]
            failed["unauthorized effect"]["reconciliation"]["unauthorized"] = [
                "effect:outside_scope"
            ]
            failed["process violation"]["targets"][0]["ordering_proof"]["kind"] = (
                "generic_timestamp"
            )

            controls = {
                "pre-action ambiguity": (blocked, "blocked"),
                "missing post-evidence": (indeterminate, "indeterminate"),
                **{name: (manifest, "failed") for name, manifest in failed.items()},
            }
            if family == "create_append":
                unresolved_identity = family_manifest(family)
                binding_ref = unresolved_identity["targets"][0][
                    "identity_binding_ref"
                ]
                del unresolved_identity["evidence_records"][binding_ref]
                controls["unresolved create identity"] = (
                    unresolved_identity,
                    "indeterminate",
                )
            elif family == "delete_erase":
                weak_negative = family_manifest(family)
                target = weak_negative["targets"][0]
                evidence_record(weak_negative, target, "post")[
                    "witness"
                ] = "naked_not_found"
                controls["naked not-found"] = (weak_negative, "indeterminate")
            elif family == "blob_content":
                incomplete_ranges = family_manifest(family)
                target = incomplete_ranges["targets"][0]
                evidence_record(incomplete_ranges, target, "post")[
                    "ranges"
                ] = [[0, 1], [2, 4]]
                controls["incomplete post-ranges"] = (
                    incomplete_ranges,
                    "indeterminate",
                )
            elif family == "operation_composite":
                duplicate_leaf = family_manifest(family)
                target = duplicate_leaf["targets"][0]
                leaf_id = target["leaf_entries"][0]["canonical_target_id"]
                target["leaf_entries"].append(copy.deepcopy(target["leaf_entries"][0]))
                target["intent"]["expected_effect_ids"] = [leaf_id, leaf_id]
                evidence_record(duplicate_leaf, target, "pre")[
                    "authorized_effect_ids"
                ] = [leaf_id, leaf_id]
                evidence_record(duplicate_leaf, target, "post")["effect_ids"] = [
                    leaf_id,
                    leaf_id,
                ]
                controls["duplicate leaf effect"] = (duplicate_leaf, "failed")

            for name, (manifest, terminal) in controls.items():
                with self.subTest(family=family, control=name):
                    control_metadata = metadata()
                    control_metadata["acceptance_manifest"] = manifest
                    result = evaluate_root_workflow(control_metadata)
                    self.assertEqual(
                        result["workflow_state"],
                        {"state": terminal, "final": True},
                    )
                    if name == "unresolved create identity":
                        self.assertEqual(
                            result["acceptance_manifest"]["replay_prohibited"],
                            ["create-intent:ci_21"],
                        )

        zero_blob = family_manifest("blob_content")
        target = zero_blob["targets"][0]
        target["intent"]["expected_digest"] = "sha256:empty"
        for name in ("pre", "post"):
            record = evidence_record(zero_blob, target, name)
            record["length"] = 0
            record["digest"] = "sha256:empty"
            record["ranges"] = []
        receipt = evidence_record(zero_blob, target, "receipt")
        receipt["length"] = 0
        receipt["digest"] = "sha256:empty"
        zero_blob_metadata = metadata()
        zero_blob_metadata["acceptance_manifest"] = zero_blob
        self.assertEqual(
            evaluate_root_workflow(zero_blob_metadata)["workflow_state"],
            {"state": "accepted", "final": True},
        )

        aggregate_only = family_manifest("operation_composite")
        target = aggregate_only["targets"][0]
        evidence_record(aggregate_only, target, "pre")[
            "effect_manifest_capability"
        ] = False
        target["leaf_entries"] = []
        del target["receipt_ref"]
        del target["post_ref"]
        aggregate_only["evidence"]["actions"] = []
        aggregate_only["evidence"]["post"] = []
        for name in ("attempted", "receipt_resolved", "post_verified", "accepted"):
            aggregate_only["reconciliation"][name] = []
        aggregate_only["receipt_total"] = 1
        aggregate_metadata = metadata()
        aggregate_metadata["acceptance_manifest"] = aggregate_only
        self.assertEqual(
            evaluate_root_workflow(aggregate_metadata)["workflow_state"],
            {"state": "blocked", "final": True},
        )

    def test_zero_mutation_requires_complete_empty_set_or_exclusions(self):
        empty = acceptance_manifest()
        set_ref = empty["authorization"]["set_proof_ref"]
        empty["targets"] = []
        empty["authorization"]["canonical_target_ids"] = []
        empty["evidence"] = {
            "identity_proofs": [],
            "transport_proofs": [set_ref],
            "pre": [],
            "security_gate": [],
            "actions": [],
            "post": [],
        }
        empty["evidence_records"] = {
            set_ref: _transport_record([], "bounded_list")
        }
        for name in (
            "authorized",
            "inspected",
            "intended",
            "attempted",
            "receipt_resolved",
            "post_verified",
            "accepted",
        ):
            empty["reconciliation"][name] = []
        empty["zero_mutation_proof"] = {
            "kind": "complete_empty_set",
            "transport_proof_ref": set_ref,
            "candidate_ids": [],
        }
        empty_metadata = metadata()
        empty_metadata["acceptance_manifest"] = empty
        empty_result = evaluate_root_workflow(empty_metadata)
        self.assertEqual(
            empty_result["workflow_state"], {"state": "accepted", "final": True}
        )
        self.assertEqual(
            empty_result["acceptance_manifest"]["terminal"]["reason_code"],
            "zero_mutation_proved",
        )

        excluded = copy.deepcopy(empty)
        candidates = ["record:r_a", "record:r_b"]
        excluded["reconciliation"]["inspected"] = list(reversed(candidates))
        excluded["reconciliation"]["skipped"] = candidates
        excluded["evidence_records"][set_ref] = _transport_record(
            list(reversed(candidates)), "bounded_list"
        )
        excluded["zero_mutation_proof"] = {
            "kind": "complete_exclusions",
            "transport_proof_ref": set_ref,
            "candidate_ids": candidates,
            "exclusions": {
                "record:r_a": "exclusion:predicate_miss",
                "record:r_b": "exclusion:predicate_miss",
            },
        }
        excluded_metadata = metadata()
        excluded_metadata["acceptance_manifest"] = excluded
        self.assertEqual(
            evaluate_root_workflow(excluded_metadata)["workflow_state"],
            {"state": "accepted", "final": True},
        )

        invalid_exclusions = copy.deepcopy(excluded)
        invalid_exclusions["zero_mutation_proof"]["exclusions"] = {}
        for name, invalid in {
            "missing proof": {
                key: value
                for key, value in empty.items()
                if key != "zero_mutation_proof"
            },
            "incomplete exclusions": invalid_exclusions,
        }.items():
            with self.subTest(name=name):
                invalid_metadata = metadata()
                invalid_metadata["acceptance_manifest"] = invalid
                self.assertEqual(
                    evaluate_root_workflow(invalid_metadata)["workflow_state"],
                    {"state": "blocked", "final": True},
                )

if __name__ == "__main__":
    unittest.main()
