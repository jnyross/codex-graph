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


def classification_binding(targets, target=None):
    binding = {
        "transport_proof_id": "transport:integrate-draft",
        "mutation_id": "integrate-draft",
        "action": "integrate",
        "target_state": "integrated",
        "predicate_identity": "selected-draft",
        "required_fields": ["identity", "version", "state", "content"],
        "content_fields": ["content"],
        "aggregate_scope": {
            "identity": "aggregate:selected-drafts",
            "target_ids": [item["identity"] for item in targets],
            "requires_complete_set": False,
        },
        "target_bindings": copy.deepcopy(targets),
    }
    if target is not None:
        binding["target_binding"] = copy.deepcopy(target)
    return binding



def parent_authorization(identity):
    decision = {
        "identity": identity,
        "choice": "authorize_exact_mutation",
        "queue_revision": 11,
        "mutation_id": "integrate-draft",
        "action": "integrate",
        "target_state": "integrated",
        "item_ids": ["draft:1"],
    }
    return {
        "receipt_id": f"receipt:{identity}",
        "decision_identity": identity,
        "parent_receipt": {
            "reference": f"checkpoint:{identity}",
            "validator": "root_parent",
            "validated_decision_identity": identity,
        },
        "normalized_decision": decision,
    }

def mutation_admission():
    target = {"identity": "draft:1", "version": "v7", "state": "ready"}
    return {
        "mutation_id": "integrate-draft",
        "action": "integrate",
        "target_state": "integrated",
        "targets": [target],
        "fixed_predicate": {
            "identity": "selected-draft",
            "selection_fields": ["identity", "version", "state"],
            "classification_fields": ["content"],
            "content_fields": ["content"],
            "aggregate_scope": {
                "identity": "aggregate:selected-drafts",
                "target_ids": ["draft:1"],
                "requires_complete_set": False,
            },
        },
        "acceptance_path": {
            "canonical_identity": {
                "tool_contract": {
                    "reference": "tool:repository-read:v1",
                    "digest": "sha256:repository-read-v1",
                },
                "target_bindings": [
                    {
                        "identity": "draft:1",
                        "version": "v7",
                        "state": "ready",
                        "locator": "identity:draft:1",
                    }
                ],
            },
            "complete_pre_state": {
                "tool_contract": {
                    "reference": "tool:repository-read:v1",
                    "digest": "sha256:repository-read-v1",
                },
                "target_bindings": [
                    {
                        "identity": "draft:1",
                        "version": "v7",
                        "state": "ready",
                        "locator": "read:draft:1@v7",
                    }
                ],
            },
            "authoritative_receipt": {
                "tool_contract": {
                    "reference": "tool:repository-write:v1",
                    "digest": "sha256:repository-write-v1",
                },
                "target_bindings": [
                    {
                        "identity": "draft:1",
                        "version": "v7",
                        "state": "ready",
                        "locator": "receipt:commit-result",
                    }
                ],
            },
            "independent_post_state": {
                "tool_contract": {
                    "reference": "tool:repository-read:v1",
                    "digest": "sha256:repository-read-v1",
                },
                "target_bindings": [
                    {
                        "identity": "draft:1",
                        "version": "v7",
                        "state": "ready",
                        "locator": "root-read:draft:1",
                    }
                ],
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
            "content_fields": ["content"],
            "aggregate_scope": {
                "identity": "aggregate:selected-drafts",
                "target_ids": ["draft:1"],
                "requires_complete_set": False,
            },
            "field_coverage": [
                {
                    "item_id": "draft:1",
                    "field": "identity",
                    "kind": "complete_field",
                    "locator": "read:draft:1:identity",
                },
                {
                    "item_id": "draft:1",
                    "field": "version",
                    "kind": "complete_field",
                    "locator": "read:draft:1:version",
                },
                {
                    "item_id": "draft:1",
                    "field": "state",
                    "kind": "complete_field",
                    "locator": "read:draft:1:state",
                },
                {
                    "item_id": "draft:1",
                    "field": "content",
                    "kind": "gap_free_content",
                    "locator": "read:draft:1:content",
                    "total_length": 12,
                    "ranges": [[0, 12]],
                },
            ],
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
            "recovery_seed": {
                "request_fingerprint": "cursor:failed",
                "completed_units": 0,
                "remaining_units": 2,
            },
        },
        "security_gate": {
            "transport_proof_id": "transport:integrate-draft",
            "binding": classification_binding([target]),
            "item_classifications": [
                {
                    "item_id": "draft:1",
                    "result": "unprotected",
                    "categories": [],
                    "evidence": ["classifier:draft:1"],
                    "deterministic_markers": [],
                    "uncertainty": [],
                    "expiry": [],
                    "input_binding": classification_binding([target], target),
                }
            ],
            "action_classification": {
                "result": "unprotected",
                "categories": [],
                "evidence": ["classifier:integrate"],
                "deterministic_markers": [],
                "uncertainty": [],
                "expiry": [],
                "input_binding": classification_binding([target]),
            },
            "authorization": None,
            "item_level_execution": True,
            "uncoupled": True,
        },
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
        "design_digest": "sha256:design-7",
        "design_review": review(),
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


def _transport_record(
    target_ids,
    capability="single_object_blob",
    mutation_id="mutation:proof",
    required_fields=("canonical_target_id",),
    aggregate_scope="scope:s_01",
    fixed_predicate="fixture_predicate",
):
    record = {
        "kind": "transport_proof",
        "mutation_id": mutation_id,
        "target_ids": list(target_ids),
        "aggregate_scope": aggregate_scope,
        "fixed_predicate": fixed_predicate,
        "required_fields": list(required_fields),
        "capability": capability,
        "read_locator": f"read:{mutation_id}",
        "requested_scope": list(target_ids),
        "returned_scope": list(target_ids),
        "relevant_versions": {},
        "signals": [],
        "recovery_attempts": [],
        "no_progress_stop": "not_applicable",
        "outcome": "complete",
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
        refs["set"]: _transport_record(
            [target_id], "bounded_list", mutation_id
        ),
        refs["pre_transport"]: _transport_record(
            [target_id], mutation_id=mutation_id, fixed_predicate=case["action"]
        ),
        refs["post_transport"]: _transport_record(
            [target_id], mutation_id=mutation_id, fixed_predicate=case["action"]
        ),
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
            "owner": "root",
            "authoritative": True,
            "item_id": f"item:{prefix}",
            "batch_id": "batch:01",
            "target_id": target_id,
            "mutation_id": mutation_id,
            "action": case["action"],
            "target_state": "intended",
            "transport_proof_ref": refs["pre_transport"],
            "item_axis": "unprotected",
            "action_axis": "unprotected",
            "categories": [],
            "deterministic_markers": [],
            "evidence_locators": [f"locator:sanitized:{prefix}"],
            "classification_reasons": ["no_protected_signal"],
            "uncertainty": False,
            "expiry": {
                "expired": False,
                "classification_preserved": True,
                "material_usable": True,
            },
            "authorization_current": True,
            "authorization_ref": "decision:d_01@queue:q_01",
            "authorization_scope_id": "scope:s_01",
            "partition_sets": {"allowed": [target_id], "blocked": []},
            "verdict": "allow",
        },
    }
    records[refs["set"]]["aggregate_scope"] = "scope:s_01"
    records[refs["set"]]["fixed_predicate"] = case["action"]
    records[refs["pre_transport"]]["aggregate_scope"] = "scope:s_01"
    records[refs["pre_transport"]]["fixed_predicate"] = case["action"]
    records[refs["post_transport"]]["aggregate_scope"] = "scope:s_01"
    records[refs["post_transport"]]["fixed_predicate"] = case["action"]
    records[refs["pre_transport"]]["required_fields"] = [
        "canonical_target_id",
        *case["pre"],
    ]
    records[refs["post_transport"]]["required_fields"] = [
        "canonical_target_id",
        *case["post"],
    ]
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
    manifest_mutation = "integrate-draft"
    old_mutation = target["intent"]["mutation_id"]
    target["intent"]["mutation_id"] = manifest_mutation
    for record in records.values():
        if isinstance(record, dict) and record.get("mutation_id") == old_mutation:
            record["mutation_id"] = manifest_mutation
    if family == "operation_composite":
        leaf, leaf_records, leaf_evidence, _ = _target_fixture(
            "record_state", "leaf"
        )
        leaf["family"] = "record_state"
        parent_mutation = target["intent"]["mutation_id"]
        old_leaf_mutation = leaf["intent"]["mutation_id"]
        leaf["intent"]["mutation_id"] = parent_mutation
        for record in leaf_records.values():
            if not isinstance(record, dict):
                continue
            if record.get("mutation_id") == old_leaf_mutation:
                record["mutation_id"] = parent_mutation
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
            "mutation_id": target["intent"]["mutation_id"],
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

def add_target(manifest, family, prefix):
    target, records, evidence, refs = _target_fixture(family, prefix)
    old_id = target["canonical_target_id"]
    target_id = f"{old_id}:{prefix}"
    old_mutation = target["intent"]["mutation_id"]
    manifest_mutation = manifest["authorization"]["mutation_id"]
    target["intent"]["mutation_id"] = manifest_mutation
    target["canonical_target_id"] = target_id
    for record in records.values():
        if not isinstance(record, dict):
            continue
        for field in ("target_id", "resource_id", "object_id"):
            if record.get(field) == old_id:
                record[field] = target_id
        if record.get("mutation_id") == old_mutation:
            record["mutation_id"] = manifest_mutation
        if record.get("canonical_target_ids") == [old_id]:
            record["canonical_target_ids"] = [target_id]
        if record.get("target_ids") == [old_id]:
            record["target_ids"] = [target_id]
            record["requested_scope"] = [target_id]
            record["returned_scope"] = [target_id]
        partitions = record.get("partition_sets")
        if isinstance(partitions, dict) and partitions.get("allowed") == [old_id]:
            partitions["allowed"] = [target_id]

    manifest["targets"].append(target)
    manifest["evidence_records"].update(records)
    for name, values in evidence.items():
        manifest["evidence"][name].extend(values)
    manifest["authorization"]["canonical_target_ids"].append(target_id)
    for name in (
        "authorized",
        "inspected",
        "intended",
        "attempted",
        "receipt_resolved",
        "post_verified",
        "accepted",
    ):
        manifest["reconciliation"][name].append(target_id)

    set_ref = manifest["authorization"]["set_proof_ref"]
    set_record = manifest["evidence_records"][set_ref]
    all_targets = manifest["authorization"]["canonical_target_ids"]
    set_record["target_ids"] = list(all_targets)
    set_record["requested_scope"] = list(all_targets)
    set_record["returned_scope"] = list(all_targets)
    set_record["witness"]["authoritative_total"] = len(all_targets)
    set_record["witness"]["unique_count"] = len(all_targets)
    return target, refs


def acceptance_manifest():
    return family_manifest()


def evidence_record(manifest, target, name):
    return manifest["evidence_records"][target[f"{name}_ref"]]


def contradict_family(manifest):
    target = manifest["targets"][0]
    field, value = _FAMILY_CASES[manifest["adapter"]["family"]]["contradiction"]
    evidence_record(manifest, target, "post")[field] = value
    return manifest


def add_admission_target(fixture, identity="draft:2", version="v4", state="ready"):
    proposal = fixture["mutation_admission"]
    target = {"identity": identity, "version": version, "state": state}
    proposal["targets"].append(target)
    for name, capability in proposal["acceptance_path"].items():
        capability["target_bindings"].append(
            {**target, "locator": f"{name}:{identity}"}
        )
    proposal["fixed_predicate"]["aggregate_scope"]["target_ids"].append(identity)
    proposal["transport_proof"]["aggregate_scope"]["target_ids"].append(identity)

    proof = proposal["transport_proof"]
    proof["target_bindings"].append(target)
    proof["requested_scope"].append(identity)
    proof["returned_scope"].append(identity)
    for field in proposal["transport_proof"]["required_fields"]:
        coverage = {
            "item_id": identity,
            "field": field,
            "kind": "complete_field",
            "locator": f"read:{identity}:{field}",
        }
        if field in proposal["fixed_predicate"]["content_fields"]:
            coverage.update(
                {
                    "kind": "gap_free_content",
                    "total_length": 12,
                    "ranges": [[0, 12]],
                }
            )
        proposal["transport_proof"]["field_coverage"].append(coverage)
    proof["pages"][0]["target_ids"].append(identity)

    security = proposal["security_gate"]
    security["binding"] = classification_binding(proposal["targets"])
    for item in security["item_classifications"]:
        item_target = next(
            candidate
            for candidate in proposal["targets"]
            if candidate["identity"] == item["item_id"]
        )
        item["input_binding"] = classification_binding(
            proposal["targets"], item_target
        )
    security["item_classifications"].append(
        {
            "item_id": identity,
            "result": "unprotected",
            "categories": [],
            "evidence": [f"classifier:{identity}"],
            "deterministic_markers": [],
            "uncertainty": [],
            "expiry": [],
            "input_binding": classification_binding(proposal["targets"], target),
        }
    )
    security["action_classification"]["input_binding"] = classification_binding(
        proposal["targets"]
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

        short_page = metadata()
        short_page_proof = short_page["mutation_admission"]["transport_proof"]
        short_page_proof["capability"] = "bounded_list"
        short_page_proof["terminal_witness"] = {
            "kind": "documented_short_page_terminal",
            "locator": "read:drafts:page:1",
            "tool_contract": {
                "reference": "tool:bounded-list:v1",
                "digest": "sha256:bounded-list-v1",
                "short_page_rule": "returned_count_lt_page_limit",
            },
            "returned_count": 1,
            "page_limit": 50,
        }
        self.assertEqual(
            evaluate_root_workflow(short_page)["mutation_admission"]["status"],
            "allow",
        )

        missing_contract = copy.deepcopy(short_page)
        del missing_contract["mutation_admission"]["transport_proof"][
            "terminal_witness"
        ]["tool_contract"]
        self.assertEqual(
            evaluate_root_workflow(missing_contract)["mutation_admission"][
                "status"
            ],
            "blocked",
        )

        not_short = copy.deepcopy(short_page)
        not_short["mutation_admission"]["transport_proof"]["terminal_witness"][
            "returned_count"
        ] = 50
        self.assertEqual(
            evaluate_root_workflow(not_short)["mutation_admission"]["status"],
            "blocked",
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
        acceptance["independent_post_state"]["target_bindings"][0][
            "locator"
        ] = acceptance["authoritative_receipt"]["target_bindings"][0]["locator"]

        invalid_bindings["capability provenance"] = metadata()
        del invalid_bindings["capability provenance"]["mutation_admission"][
            "acceptance_path"
        ]["complete_pre_state"]["tool_contract"]["digest"]

        invalid_bindings["per-target capability binding"] = metadata()
        invalid_bindings["per-target capability binding"]["mutation_admission"][
            "acceptance_path"
        ]["canonical_identity"]["target_bindings"] = []

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
        add_admission_target(localized)
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
        aggregate["mutation_admission"]["fixed_predicate"]["aggregate_scope"][
            "requires_complete_set"
        ] = True
        aggregate["mutation_admission"]["transport_proof"]["aggregate_scope"][
            "requires_complete_set"
        ] = True
        aggregate_result = evaluate_root_workflow(aggregate)
        self.assertEqual(
            aggregate_result["mutation_admission"]["status"], "blocked"
        )

        missing_aggregate_scope = metadata()
        del missing_aggregate_scope["mutation_admission"]["fixed_predicate"][
            "aggregate_scope"
        ]
        del missing_aggregate_scope["mutation_admission"]["transport_proof"][
            "aggregate_scope"
        ]
        self.assertEqual(
            evaluate_root_workflow(missing_aggregate_scope)[
                "mutation_admission"
            ]["status"],
            "blocked",
        )



    def test_every_predicate_field_has_per_target_complete_coverage(self):
        missing_field = metadata()
        missing_field["mutation_admission"]["transport_proof"][
            "field_coverage"
        ].pop()
        self.assertEqual(
            evaluate_root_workflow(missing_field)["mutation_admission"]["status"],
            "blocked",
        )

        byte_gap = metadata()
        content = byte_gap["mutation_admission"]["transport_proof"][
            "field_coverage"
        ][-1]
        content["ranges"] = [[0, 5], [6, 12]]
        self.assertEqual(
            evaluate_root_workflow(byte_gap)["mutation_admission"]["status"],
            "blocked",
        )

        for key, value in (("item_id", []), ("field", {})):
            with self.subTest(malformed_coverage_key=key):
                malformed = metadata()
                malformed["mutation_admission"]["transport_proof"][
                    "field_coverage"
                ][0][key] = value
                self.assertEqual(
                    evaluate_root_workflow(malformed)["mutation_admission"][
                        "status"
                    ],
                    "blocked",
                )

    def test_recovery_requires_progress_and_returns_bounded_forensics(self):
        fixture = metadata()
        proof = fixture["mutation_admission"]["transport_proof"]
        proof["pages"][0]["next_cursor"] = "next"
        proof["recovery_bound"] = 2
        proof["recovery_attempts"] = [
            {
                "request_fingerprint": "cursor:next",
                "completed_units": 1,
                "remaining_units": 1,
            },
            {
                "request_fingerprint": "cursor:next",
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
        no_progress_attempts[1]["request_fingerprint"] = "cursor:smaller-page"
        no_progress_result = evaluate_root_workflow(no_progress)[
            "mutation_admission"
        ]
        self.assertIn("recovery_no_progress", no_progress_result["reasons"])

        over_bound = copy.deepcopy(no_progress)
        over_bound["mutation_admission"]["transport_proof"]["recovery_bound"] = 1
        over_bound_result = evaluate_root_workflow(over_bound)["mutation_admission"]
        self.assertIn("recovery_bound_exceeded", over_bound_result["reasons"])

        first_repeat = metadata()
        first_repeat["mutation_admission"]["transport_proof"][
            "recovery_attempts"
        ] = [
            {
                "request_fingerprint": "cursor:failed",
                "completed_units": 1,
                "remaining_units": 1,
            }
        ]
        self.assertIn(
            "repeated_incomplete_input",
            evaluate_root_workflow(first_repeat)["mutation_admission"]["reasons"],
        )

        first_no_progress = metadata()
        first_no_progress["mutation_admission"]["transport_proof"][
            "recovery_attempts"
        ] = [
            {
                "request_fingerprint": "cursor:alternate",
                "completed_units": 0,
                "remaining_units": 2,
            }
        ]
        self.assertIn(
            "recovery_no_progress",
            evaluate_root_workflow(first_no_progress)[
                "mutation_admission"
            ]["reasons"],
        )

        monotonic = metadata()
        monotonic["mutation_admission"]["transport_proof"][
            "recovery_attempts"
        ] = [
            {
                "request_fingerprint": "cursor:first",
                "completed_units": 1,
                "remaining_units": 1,
            },
            {
                "request_fingerprint": "cursor:second",
                "completed_units": 2,
                "remaining_units": 0,
            },
        ]
        self.assertEqual(
            evaluate_root_workflow(monotonic)["mutation_admission"]["status"],
            "allow",
        )

    def test_forensics_cap_rejects_self_attested_unbounded_raw_output(self):
        fixture = metadata()
        proof = fixture["mutation_admission"]["transport_proof"]
        proof["signals"] = [{"scope": "call", "kind": "truncation_warning"}]
        proof["forensics"] = {
            "cap_bytes": 10**9,
            "last_raw": "x" * 5000,
            "completed_evidence": [],
            "live_handles": [],
            "failed_scope": ["draft:1"],
            "signals": proof["signals"],
        }
        blocked = evaluate_root_workflow(fixture)["mutation_admission"]
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("forensics_incomplete", blocked["reasons"])
        self.assertEqual(blocked["forensics"]["cap_bytes"], 0)

    def test_forensics_accepts_harness_truncation_suffix(self):
        fixture = metadata()
        proof = fixture["mutation_admission"]["transport_proof"]
        proof["signals"] = [{"scope": "call", "kind": "truncation_warning"}]
        prefix = "x" * 2000
        proof["forensics"] = {
            "cap_bytes": 2000,
            "last_raw": f"{prefix} … [truncated 5000 chars]",
            "completed_evidence": [],
            "live_handles": [],
            "failed_scope": ["draft:1"],
            "signals": proof["signals"],
        }
        blocked = evaluate_root_workflow(fixture)["mutation_admission"]
        self.assertEqual(blocked["status"], "blocked")
        self.assertNotIn("forensics_incomplete", blocked["reasons"])
        self.assertEqual(blocked["forensics"]["last_raw"], proof["forensics"]["last_raw"])

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
                fixture["mutation_admission"]["security_gate"][
                    "authorization"
                ] = parent_authorization(f"decision:11:{category}")
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
        authorized["mutation_admission"]["security_gate"][
            "authorization"
        ] = parent_authorization("decision:11:2")
        self.assertEqual(
            evaluate_root_workflow(authorized)["mutation_admission"]["status"],
            "allow",
        )

        missing_current_revision = copy.deepcopy(authorized)
        del missing_current_revision["queue_revision"]
        del missing_current_revision["mutation_admission"]["security_gate"][
            "authorization"
        ]["normalized_decision"]["queue_revision"]
        self.assertEqual(
            evaluate_root_workflow(missing_current_revision)[
                "mutation_admission"
            ]["status"],
            "blocked",
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
                    "normalized_decision"
                ][field] = value
                self.assertEqual(
                    evaluate_root_workflow(fixture)["mutation_admission"]["status"],
                    "blocked",
                )

        unvalidated = copy.deepcopy(authorized)
        unvalidated["mutation_admission"]["security_gate"]["authorization"][
            "parent_receipt"
        ]["validator"] = "worker"
        self.assertEqual(
            evaluate_root_workflow(unvalidated)["mutation_admission"]["status"],
            "blocked",
        )

        identity_mismatch = copy.deepcopy(authorized)
        identity_mismatch["mutation_admission"]["security_gate"][
            "authorization"
        ]["normalized_decision"]["identity"] = "decision:other"
        self.assertEqual(
            evaluate_root_workflow(identity_mismatch)["mutation_admission"][
                "status"
            ],
            "blocked",
        )

        fixture = metadata()
        add_admission_target(fixture)
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

        missing_proof_id = metadata()
        del missing_proof_id["mutation_admission"]["transport_proof"]["proof_id"]
        missing_proof_id["mutation_admission"]["security_gate"][
            "transport_proof_id"
        ] = None
        self.assertEqual(
            evaluate_root_workflow(missing_proof_id)["mutation_admission"][
                "status"
            ],
            "blocked",
        )

        stale_item_binding = metadata()
        stale_item_binding["mutation_admission"]["security_gate"][
            "item_classifications"
        ][0]["input_binding"]["target_binding"]["version"] = "v6"
        stale_item_result = evaluate_root_workflow(stale_item_binding)[
            "mutation_admission"
        ]
        self.assertEqual(stale_item_result["status"], "blocked")
        self.assertEqual(
            stale_item_result["evaluated_gates"], ["transport", "classification"]
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
        self.assertEqual(
            blocked_result["mutation_admission"]["status"], "blocked"
        )
        self.assertEqual(
            blocked_result["workflow_state"], {"state": "continue", "final": False}
        )

        waiting_on_human = evaluate_root_workflow(
            blocked_mutation,
            [{"type": "human_decision_required", "path": "approval"}],
        )
        self.assertEqual(
            waiting_on_human["workflow_state"],
            {"state": "human_decision_required", "final": False},
        )

        no_proposal = metadata()
        del no_proposal["mutation_admission"]
        no_proposal_result = evaluate_root_workflow(no_proposal)
        self.assertFalse(no_proposal_result["execution_permission"]["root_mutation"])
        self.assertTrue(no_proposal_result["execution_permission"]["delegated_work"])

    def test_blocked_mutation_is_not_final_for_l0_and_repair(self):
        l0 = metadata()
        l0["authority_preflight"]["generic_topology"] = "L0"
        l0["authority_preflight"]["workers"] = []
        l0["mutation_admission"]["transport_proof"]["signals"] = [
            {"scope": "call", "kind": "truncation_warning"}
        ]
        l0_result = evaluate_root_workflow(l0)
        self.assertEqual(l0_result["selected_topology"], "L0")
        self.assertEqual(
            l0_result["workflow_state"], {"state": "continue", "final": False}
        )
        self.assertFalse(l0_result["execution_permission"]["root_mutation"])
        self.assertFalse(l0_result["execution_permission"]["delegated_work"])

        repair = metadata()
        repair["design_review"]["independent_review"]["verdict"] = "repair"
        repair["design_review"]["independent_review"]["findings"] = [finding()]
        repair["mutation_admission"]["transport_proof"]["signals"] = [
            {"scope": "call", "kind": "truncation_warning"}
        ]
        repair_result = evaluate_root_workflow(repair)
        self.assertEqual(repair_result["review_gate"]["status"], "repair_required")
        self.assertEqual(
            repair_result["workflow_state"], {"state": "continue", "final": False}
        )
        self.assertFalse(repair_result["execution_permission"]["root_mutation"])
        self.assertFalse(repair_result["execution_permission"]["delegated_work"])

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


        discovered_metadata = metadata()
        proposal = discovered_metadata["mutation_admission"]
        proposal["mutation_id"] = "publish-draft"
        proof = proposal["transport_proof"]
        proof["proof_id"] = "transport:publish-draft"
        proof["mutation_id"] = "publish-draft"
        security = proposal["security_gate"]
        security["transport_proof_id"] = "transport:publish-draft"
        bindings = [
            security["binding"],
            security["action_classification"]["input_binding"],
            *[
                item["input_binding"]
                for item in security["item_classifications"]
            ],
        ]
        for binding in bindings:
            binding["transport_proof_id"] = "transport:publish-draft"
            binding["mutation_id"] = "publish-draft"

        discovered = evaluate_root_workflow(
            discovered_metadata, [reproved_discovery]
        )
        self.assertEqual(
            discovered["mutation_admission"]["status"], "allow"
        )
        self.assertEqual(
            discovered["mutation_admission"]["mutation_id"], "publish-draft"
        )
        self.assertTrue(discovered["execution_permission"]["root_mutation"])
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
        repair_ref = "repair-progress:01"
        private["evidence_records"][repair_ref] = {
            "kind": "repair_progress",
            "owner": "root",
            "authoritative": True,
            "action": "narrow_read",
            "scope_before": ["record:r_01", "record:r_02"],
            "scope_after": ["record:r_01"],
            "progress": "scope_narrowed",
            "request_id": "request:repair:01",
            "coverage_before": 0,
            "coverage_after": 1,
            "raw_private_payload": "not durable",
        }
        private["evidence"]["pre"].append(repair_ref)
        private["repair"]["attempts"] = [
            {
                "action": "narrow_read",
                "scope_before": ["record:r_01", "record:r_02"],
                "scope_after": ["record:r_01"],
                "progress": "scope_narrowed",
                "evidence_ref": repair_ref,
                "request_id": "request:repair:01",
                "coverage_before": 0,
                "coverage_after": 1,
                "raw_private_payload": "not durable",
            }
        ]
        private_metadata = metadata()
        private_metadata["acceptance_manifest"] = private
        retained = evaluate_root_workflow(private_metadata)["acceptance_manifest"]
        self.assertNotIn("raw_private_payload", retained)
        self.assertNotIn("evidence_records", retained)
        self.assertNotIn("raw_private_payload", retained["targets"][0])
        self.assertIn("evidence_summaries", retained)
        self.assertNotIn(
            "raw_private_payload", retained["repair"]["attempts"][0]
        )

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

        controls["transport truncation"] = acceptance_manifest()
        target = controls["transport truncation"]["targets"][0]
        pre = evidence_record(controls["transport truncation"], target, "pre")
        controls["transport truncation"]["evidence_records"][
            pre["transport_ref"]
        ]["signals"] = ["truncated"]
        controls["unbound set mutation"] = acceptance_manifest()
        set_ref = controls["unbound set mutation"]["authorization"]["set_proof_ref"]
        controls["unbound set mutation"]["evidence_records"][set_ref][
            "mutation_id"
        ] = "mutation:unrelated"

        controls["unbound set scope"] = acceptance_manifest()
        set_ref = controls["unbound set scope"]["authorization"]["set_proof_ref"]
        controls["unbound set scope"]["evidence_records"][set_ref][
            "aggregate_scope"
        ] = "scope:unrelated"

        controls["unbound set action"] = acceptance_manifest()
        set_ref = controls["unbound set action"]["authorization"]["set_proof_ref"]
        controls["unbound set action"]["evidence_records"][set_ref][
            "fixed_predicate"
        ] = "different_action"

        controls["incomplete security gate"] = acceptance_manifest()
        security_ref = controls["incomplete security gate"]["evidence"][
            "security_gate"
        ][0]
        del controls["incomplete security gate"]["evidence_records"][security_ref][
            "item_axis"
        ]

        controls["declared failed outcome"] = acceptance_manifest()
        failed_id = controls["declared failed outcome"]["targets"][0][
            "canonical_target_id"
        ]
        controls["declared failed outcome"]["reconciliation"]["accepted"] = []
        controls["declared failed outcome"]["reconciliation"]["failed"] = [failed_id]

        controls["mutating evidence repair"] = acceptance_manifest()
        controls["mutating evidence repair"]["repair"]["allowed"].append(
            "mutation_retry"
        )

        controls["non-progressing evidence repair"] = acceptance_manifest()
        controls["non-progressing evidence repair"]["repair"]["attempts"] = [
            {
                "action": "narrow_read",
                "scope_before": ["record:r_01"],
                "scope_after": ["record:r_01"],
                "progress": "scope_narrowed",
                "evidence_ref": "pre:01",
                "request_id": "request:no-progress",
                "coverage_before": 1,
                "coverage_after": 1,
            }
        ]
        controls["fabricated repair evidence"] = acceptance_manifest()
        controls["fabricated repair evidence"]["repair"]["attempts"] = [
            {
                "action": "narrow_read",
                "scope_before": ["record:r_01", "record:r_02"],
                "scope_after": ["record:r_01"],
                "progress": "scope_narrowed",
                "evidence_ref": "pre:fabricated",
                "request_id": "request:fabricated",
                "coverage_before": 0,
                "coverage_after": 1,
            }
        ]
        controls["non-root repair evidence"] = acceptance_manifest()
        repair_ref = "repair-progress:worker"
        repair_progress = {
            "kind": "repair_progress",
            "owner": "worker",
            "authoritative": True,
            "action": "narrow_read",
            "scope_before": ["record:r_01", "record:r_02"],
            "scope_after": ["record:r_01"],
            "progress": "scope_narrowed",
            "request_id": "request:worker",
            "coverage_before": 0,
            "coverage_after": 1,
        }
        controls["non-root repair evidence"]["evidence_records"][
            repair_ref
        ] = repair_progress
        controls["non-root repair evidence"]["evidence"]["pre"].append(repair_ref)
        controls["non-root repair evidence"]["repair"]["attempts"] = [
            {
                **repair_progress,
                "evidence_ref": repair_ref,
            }
        ]

        controls["repeated repair request"] = acceptance_manifest()
        controls["repeated repair request"]["repair"]["attempts"] = [
            {
                "action": "narrow_read",
                "scope_before": ["record:r_01", "record:r_02"],
                "scope_after": ["record:r_01"],
                "progress": "scope_narrowed",
                "evidence_ref": "pre:01",
                "request_id": "request:repair:01",
                "coverage_before": 0,
                "coverage_after": 1,
            },
            {
                "action": "narrow_read",
                "scope_before": ["record:r_01", "record:r_03"],
                "scope_after": ["record:r_01"],
                "progress": "scope_narrowed",
                "evidence_ref": "post:01",
                "request_id": "request:repair:02",
                "coverage_before": 1,
                "coverage_after": 2,
            },
        ]

        controls["malformed family"] = acceptance_manifest()
        controls["malformed family"]["adapter"]["family"] = []
        controls["incomplete transport predicate"] = acceptance_manifest()
        target = controls["incomplete transport predicate"]["targets"][0]
        pre = evidence_record(
            controls["incomplete transport predicate"], target, "pre"
        )
        controls["incomplete transport predicate"]["evidence_records"][
            pre["transport_ref"]
        ]["required_fields"].remove("state")

        controls["malformed ordering kind"] = acceptance_manifest()
        controls["malformed ordering kind"]["targets"][0]["ordering_proof"][
            "kind"
        ] = []

        controls["malformed alias collection"] = acceptance_manifest()
        controls["malformed alias collection"]["targets"][0]["aliases"] = None

        controls["unknown security category"] = acceptance_manifest()
        security_ref = controls["unknown security category"]["evidence"][
            "security_gate"
        ][0]
        controls["unknown security category"]["evidence_records"][security_ref][
            "categories"
        ] = ["unknown"]

        controls["expired security gate"] = acceptance_manifest()
        security_ref = controls["expired security gate"]["evidence"][
            "security_gate"
        ][0]
        controls["expired security gate"]["evidence_records"][security_ref][
            "expiry"
        ]["expired"] = True
        expired_gate = controls["expired security gate"]["evidence_records"][
            security_ref
        ]
        expired_gate["expiry"]["material_usable"] = False
        expired_gate["item_axis"] = "protected"
        expired_gate["action_axis"] = "protected"
        expired_gate["categories"] = ["security_account_control"]
        expired_gate["classification_reasons"] = ["matched_security_signal"]

        controls["stale gate authorization"] = acceptance_manifest()
        security_ref = controls["stale gate authorization"]["evidence"][
            "security_gate"
        ][0]
        controls["stale gate authorization"]["evidence_records"][security_ref][
            "authorization_current"
        ] = False

        controls["missing security locator"] = acceptance_manifest()
        security_ref = controls["missing security locator"]["evidence"][
            "security_gate"
        ][0]
        controls["missing security locator"]["evidence_records"][security_ref][
            "evidence_locators"
        ] = []

        controls["partial mutation with blocked target"] = acceptance_manifest()
        second_target, second_refs = add_target(
            controls["partial mutation with blocked target"], "record_state", "02"
        )
        del second_target["receipt_ref"]
        del second_target["post_ref"]
        controls["partial mutation with blocked target"]["evidence"]["actions"].remove(
            second_refs["receipt"]
        )
        controls["partial mutation with blocked target"]["evidence"]["post"].remove(
            second_refs["post"]
        )
        second_id = second_target["canonical_target_id"]
        for name in ("attempted", "receipt_resolved", "post_verified", "accepted"):
            controls["partial mutation with blocked target"]["reconciliation"][
                name
            ].remove(second_id)

        expected = {
            "shaped JSON": "failed",
            "worker post-state claim": "indeterminate",
            "receipt only": "indeterminate",
            "generic timestamp": "failed",
            "intended target not inspected": "failed",
            "mismatched receipt action": "failed",
            "failure omitted from attempted set": "failed",
            "transport truncation": "failed",
            "unbound set mutation": "failed",
            "unbound set scope": "failed",
            "unbound set action": "failed",
            "incomplete security gate": "failed",
            "declared failed outcome": "failed",
            "mutating evidence repair": "failed",
            "non-progressing evidence repair": "failed",
            "malformed family": "failed",
            "incomplete transport predicate": "failed",
            "malformed ordering kind": "failed",
            "fabricated repair evidence": "failed",
            "non-root repair evidence": "failed",
            "repeated repair request": "failed",
            "malformed alias collection": "failed",
            "unknown security category": "failed",
            "expired security gate": "failed",
            "stale gate authorization": "failed",
            "missing security locator": "failed",
            "partial mutation with blocked target": "failed",
        }
        for name, manifest in controls.items():
            with self.subTest(name=name):
                control_metadata = metadata()
                control_metadata["acceptance_manifest"] = manifest
                self.assertEqual(
                    evaluate_root_workflow(control_metadata)["workflow_state"],
                    {"state": expected[name], "final": True},
                )
                if name == "declared failed outcome":
                    self.assertEqual(
                        evaluate_root_workflow(control_metadata)[
                            "acceptance_manifest"
                        ]["reconciliation"]["failed"],
                        ["record:r_01"],
                    )

    def test_manifest_uses_reproved_authority_revision(self):
        reproved_metadata = metadata()
        reproved_review = review(design_digest="sha256:design-8")
        reproved_review["design_revision"] = 8
        reproved_review["independent_review"]["identity"] = "review-8"
        manifest = acceptance_manifest()
        manifest["workflow"]["revision"] = 8
        reproved_metadata["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(
            reproved_metadata,
            [
                {
                    "type": "worker_mutation_discovered",
                    "worker_role": "writer",
                    "mutation": {"identity": "publish-draft", "owner": "root"},
                    "revision": 8,
                    "worker_confinement": worker(),
                    "design_digest": "sha256:design-8",
                    "design_review": reproved_review,
                }
            ],
        )
        self.assertEqual(
            result["workflow_state"], {"state": "accepted", "final": True}
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
                used_key = family_manifest(family)
                target = used_key["targets"][0]
                evidence_record(used_key, target, "pre")["key_state"] = "used"
                controls["used create key"] = (used_key, "failed")

                duplicate_binding = family_manifest(family)
                add_target(duplicate_binding, family, "02")
                controls["duplicate create binding"] = (
                    duplicate_binding,
                    "failed",
                )
                non_string_binding = family_manifest(family)
                target = non_string_binding["targets"][0]
                binding = non_string_binding["evidence_records"][
                    target["identity_binding_ref"]
                ]
                evidence_record(non_string_binding, target, "pre")[
                    "client_mutation_key"
                ] = ["create-intent:ci_21"]
                evidence_record(non_string_binding, target, "receipt")[
                    "result_resource_id"
                ] = ["note:n_21"]
                binding["client_mutation_key"] = ["create-intent:ci_21"]
                binding["result_resource_id"] = ["note:n_21"]
                controls["non-string create binding"] = (
                    non_string_binding,
                    "failed",
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
                malformed_leaf = family_manifest(family)
                malformed_leaf["targets"][0]["leaf_entries"] = None
                controls["malformed leaf collection"] = (
                    malformed_leaf,
                    "failed",
                )

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
        empty["authorization"]["mutation_id"] = "integrate-draft"
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
            set_ref: _transport_record(
                [], "bounded_list", empty["authorization"]["mutation_id"]
            )
        }
        empty["evidence_records"][set_ref]["aggregate_scope"] = empty[
            "authorization"
        ]["scope_id"]
        empty["evidence_records"][set_ref]["fixed_predicate"] = empty[
            "authorization"
        ]["exact_action"]
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
            list(reversed(candidates)), "bounded_list", "integrate-draft"
        )
        excluded["evidence_records"][set_ref]["aggregate_scope"] = excluded[
            "authorization"
        ]["scope_id"]
        excluded["evidence_records"][set_ref]["fixed_predicate"] = excluded[
            "authorization"
        ]["exact_action"]
        exclusions = {}
        for suffix, candidate_id in zip(("a", "b"), candidates):
            transport_ref = f"tp:exclude:{suffix}"
            pre_ref = f"pre:exclude:{suffix}"
            predicate_ref = f"exclusion:{suffix}"
            excluded["evidence_records"][transport_ref] = _transport_record(
                [candidate_id],
                mutation_id="integrate-draft",
                fixed_predicate=excluded["authorization"]["exact_action"],
            )
            excluded["evidence_records"][pre_ref] = {
                "kind": "pre_state",
                "owner": "root",
                "authoritative": True,
                "target_id": candidate_id,
                "transport_ref": transport_ref,
                "version": "ver:observed",
                "state": "candidate",
            }
            excluded["evidence_records"][predicate_ref] = {
                "kind": "exclusion",
                "owner": "root",
                "authoritative": True,
                "target_id": candidate_id,
                "eligible": False,
                "reason_code": "predicate_miss",
                "fixed_predicate": excluded["authorization"]["exact_action"],
                "pre_ref": pre_ref,
            }
            excluded["evidence"]["transport_proofs"].append(transport_ref)
            excluded["evidence"]["pre"].extend([pre_ref, predicate_ref])
            exclusions[candidate_id] = {
                "reason_code": "predicate_miss",
                "pre_ref": pre_ref,
                "predicate_evidence_ref": predicate_ref,
            }
        excluded["zero_mutation_proof"] = {
            "kind": "complete_exclusions",
            "transport_proof_ref": set_ref,
            "candidate_ids": candidates,
            "exclusions": exclusions,
        }
        excluded_metadata = metadata()
        excluded_metadata["acceptance_manifest"] = excluded
        self.assertEqual(
            evaluate_root_workflow(excluded_metadata)["workflow_state"],
            {"state": "accepted", "final": True},
        )

        invalid_exclusions = copy.deepcopy(excluded)
        invalid_exclusions["zero_mutation_proof"]["exclusions"] = {}
        missing_exclusion_evidence = copy.deepcopy(excluded)
        first_pre_ref = missing_exclusion_evidence["zero_mutation_proof"][
            "exclusions"
        ]["record:r_a"]["pre_ref"]
        del missing_exclusion_evidence["evidence_records"][first_pre_ref]
        missing_exclusion_reason = copy.deepcopy(excluded)
        exclusion = missing_exclusion_reason["zero_mutation_proof"]["exclusions"][
            "record:r_a"
        ]
        predicate_ref = exclusion["predicate_evidence_ref"]
        del exclusion["reason_code"]
        del missing_exclusion_reason["evidence_records"][predicate_ref][
            "reason_code"
        ]
        unbound_zero_proof = copy.deepcopy(empty)
        unbound_zero_proof["evidence_records"][set_ref][
            "mutation_id"
        ] = "mutation:unrelated"
        for name, invalid in {
            "missing proof": {
                key: value
                for key, value in empty.items()
                if key != "zero_mutation_proof"
            },
            "incomplete exclusions": invalid_exclusions,
            "missing exclusion evidence": missing_exclusion_evidence,
            "missing exclusion reason": missing_exclusion_reason,
            "unbound zero proof": unbound_zero_proof,
        }.items():
            with self.subTest(name=name):
                invalid_metadata = metadata()
                invalid_metadata["acceptance_manifest"] = invalid
                self.assertEqual(
                    evaluate_root_workflow(invalid_metadata)["workflow_state"],
                    {"state": "blocked", "final": True},
                )
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

    def test_early_blocks_preserve_consumed_repair_checkpoint(self):
        first_revision = metadata()
        first_revision["design_review"]["independent_review"]["verdict"] = "repair"
        first_revision["design_review"]["independent_review"]["findings"] = [finding()]
        consumed_checkpoint = evaluate_root_workflow(first_revision)[
            "review_checkpoint"
        ]

        missing_preflight = metadata()
        del missing_preflight["authority_preflight"]
        malformed_preflight = metadata()
        malformed_preflight["authority_preflight"] = "invalid"
        blocked_inputs = {
            "malformed_workflow_metadata": "invalid",
            "missing_authority_preflight": missing_preflight,
            "malformed_authority_preflight": malformed_preflight,
        }

        reset = metadata()
        reset["revision"] = 8
        reset["authority_preflight"]["revision"] = 8
        reset["design_digest"] = "sha256:design-8"
        reset["design_review"] = review(
            design_digest="sha256:design-8",
            verdict="repair",
            repair_count=0,
        )
        reset["design_review"]["design_revision"] = 8
        reset["design_review"]["independent_review"]["identity"] = "review-8"
        reset_finding = finding()
        reset_finding["identity"] = "F-2"
        reset["design_review"]["independent_review"]["findings"] = [reset_finding]

        for reason, blocked_input in blocked_inputs.items():
            with self.subTest(reason=reason):
                blocked_result = evaluate_root_workflow(
                    blocked_input,
                    review_checkpoint=consumed_checkpoint,
                )
                self.assertEqual(
                    blocked_result["workflow_state"],
                    {"state": "blocked", "final": True},
                )
                self.assertIn(reason, blocked_result["authority_preflight"]["reasons"])
                self.assertEqual(
                    blocked_result["review_checkpoint"], consumed_checkpoint
                )

                persisted_result = evaluate_root_workflow(
                    copy.deepcopy(reset),
                    review_checkpoint=blocked_result["review_checkpoint"],
                )
                self.assertEqual(persisted_result["review_gate"]["status"], "block")
                self.assertIn(
                    "repair_limit_exceeded",
                    persisted_result["review_gate"]["reasons"],
                )

    def test_unhashable_manifest_identifiers_fail_closed(self):
        """Malformed identifier values must not crash the acceptance evaluator."""
        cases = [
            ("pre_ref list", lambda m: m["targets"][0].__setitem__("pre_ref", [])),
            (
                "receipt_ref dict",
                lambda m: m["targets"][0].__setitem__("receipt_ref", {}),
            ),
            (
                "canonical_target_id list",
                lambda m: m["targets"][0].__setitem__("canonical_target_id", ["bad"]),
            ),
            (
                "required_fields contains dict",
                lambda m: [
                    m["evidence_records"][ref].__setitem__(
                        "required_fields", ["canonical_target_id", {}]
                    )
                    for ref in m["evidence_records"]
                    if m["evidence_records"][ref].get("kind") == "transport_proof"
                ],
            ),
        ]
        for label, mutate in cases:
            with self.subTest(case=label):
                manifest = family_manifest("create_append")
                mutate(manifest)
                md = metadata()
                md["acceptance_manifest"] = manifest
                result = evaluate_root_workflow(md)
                self.assertNotEqual(
                    result["workflow_state"],
                    {"state": "accepted", "final": True},
                )

    def test_target_intent_must_match_authorized_mutation_id(self):
        """A target cannot claim a mutation_id different from the authorization."""
        manifest = family_manifest("record_state")
        manifest["targets"][0]["intent"]["mutation_id"] = "mutation:forged"
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )

    def test_authorized_targets_must_be_covered_by_intent_or_dispositions(self):
        """An authorized target that is not intended, skipped, unauthorized, or duplicate is blocked."""
        manifest = acceptance_manifest()
        target_id = manifest["targets"][0]["canonical_target_id"]
        extra = "record:uncovered"
        manifest["authorization"]["canonical_target_ids"].append(extra)
        manifest["reconciliation"]["authorized"].append(extra)
        set_ref = manifest["authorization"]["set_proof_ref"]
        set_record = manifest["evidence_records"][set_ref]
        set_record["target_ids"].append(extra)
        set_record["requested_scope"].append(extra)
        set_record["returned_scope"].append(extra)
        set_record["witness"]["authoritative_total"] = 2
        set_record["witness"]["unique_count"] = 2
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )

    def test_composite_leaf_action_and_mutation_bound(self):
        """A composite operation's leaf entries must use the leaf family action and the parent mutation."""
        manifest = family_manifest("operation_composite")
        leaf = manifest["targets"][0]["leaf_entries"][0]

        def result_for(mutator):
            m = copy.deepcopy(manifest)
            mutator(m["targets"][0]["leaf_entries"][0])
            md = metadata()
            md["acceptance_manifest"] = m
            return evaluate_root_workflow(md)

        def forge_action(leaf):
            leaf["intent"]["action"] = "run_operation"

        def forge_mutation(leaf):
            leaf["intent"]["mutation_id"] = "mutation:forged"

        for label, mutator in [("action", forge_action), ("mutation", forge_mutation)]:
            with self.subTest(forgery=label):
                result = result_for(mutator)
                self.assertNotEqual(
                    result["workflow_state"],
                    {"state": "accepted", "final": True},
                )

    def test_blocked_target_is_not_recorded_as_accepted(self):
        """A blocked target must not keep an untrusted 'accepted' label in the reconciliation."""
        manifest = acceptance_manifest()
        target = manifest["targets"][0]
        target_id = target["canonical_target_id"]
        del target["receipt_ref"]
        del target["post_ref"]
        manifest["evidence"]["actions"] = []
        manifest["evidence"]["post"] = []
        for name in ("attempted", "receipt_resolved", "post_verified"):
            manifest["reconciliation"][name] = []
        # reconciliation["accepted"] is intentionally left populated with the untrusted claim.
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertEqual(
            result["workflow_state"], {"state": "blocked", "final": True}
        )
        self.assertNotIn(
            target_id,
            result["acceptance_manifest"]["reconciliation"]["accepted"],
        )
        self.assertEqual(
            result["acceptance_manifest"]["reconciliation"]["derived_counts"][
                "accepted"
            ],
            0,
        )

    def test_declared_failed_target_with_no_evidence_stays_failed(self):
        """A target the manifest reports as failed must stay failed even when the evaluator has no action evidence."""
        manifest = acceptance_manifest()
        target = manifest["targets"][0]
        target_id = target["canonical_target_id"]
        del target["receipt_ref"]
        del target["post_ref"]
        manifest["evidence"]["actions"] = []
        manifest["evidence"]["post"] = []
        for name in ("attempted", "receipt_resolved", "post_verified", "accepted"):
            manifest["reconciliation"][name] = []
        manifest["reconciliation"]["failed"] = [target_id]
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertEqual(
            result["workflow_state"], {"state": "failed", "final": True}
        )
        self.assertEqual(
            result["acceptance_manifest"]["reconciliation"]["failed"],
            [target_id],
        )
        self.assertNotIn(
            target_id,
            result["acceptance_manifest"]["reconciliation"]["skipped"],
        )

    def test_bounded_list_unique_count_rejects_boolean(self):
        """A bounded-list transport witness must reject a boolean unique_count."""
        manifest = acceptance_manifest()
        set_ref = manifest["authorization"]["set_proof_ref"]
        manifest["evidence_records"][set_ref]["witness"]["unique_count"] = True
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertIn(
            result["workflow_state"]["state"], ("blocked", "failed")
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_deeply_nested_composite_target_fails_closed(self):
        """A deeply nested operation_composite target must not crash with RecursionError."""
        base = family_manifest("operation_composite")["targets"][0]
        current = {**base, "canonical_target_id": "op:leaf", "leaf_entries": []}
        for i in range(600):
            current = {**base, "canonical_target_id": f"op:{i}", "leaf_entries": [current]}
        manifest = family_manifest("operation_composite")
        manifest["targets"][0] = current
        target_id = current["canonical_target_id"]
        for name in (
            "authorized",
            "inspected",
            "intended",
            "attempted",
            "receipt_resolved",
            "post_verified",
            "accepted",
        ):
            manifest["reconciliation"][name] = [target_id]
        manifest["authorization"]["canonical_target_ids"] = [target_id]
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertIn(
            result["workflow_state"]["state"], ("blocked", "failed")
        )
        self.assertTrue(result["workflow_state"]["final"])


    def test_bounded_list_witness_non_dict_rejects_without_crash(self):
        """A bounded-list transport witness that is not a dict must not crash the evaluator."""
        manifest = acceptance_manifest()
        set_ref = manifest["authorization"]["set_proof_ref"]
        manifest["evidence_records"][set_ref]["witness"] = "not-a-dict"
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertIn(
            result["workflow_state"]["state"], ("blocked", "failed")
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_malformed_target_entry_blocks_acceptance(self):
        """A target entry without a usable identifier must prevent the manifest from being accepted."""
        manifest = acceptance_manifest()
        manifest["targets"].append({"family": "record_state"})
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertIn(
            result["workflow_state"]["state"], ("blocked", "failed")
        )
        self.assertTrue(result["workflow_state"]["final"])


    def test_blocked_mutation_admission_prevents_accepted_manifest(self):
        """A blocked mutation admission must not be overridden by an acceptance manifest verdict."""
        md = metadata()
        md["acceptance_manifest"] = acceptance_manifest()
        md["mutation_admission"]["transport_proof"]["returned_scope"] = []
        result = evaluate_root_workflow(md)
        self.assertIn(
            result["workflow_state"]["state"], ("blocked", "failed")
        )
        self.assertTrue(result["workflow_state"]["final"])
        self.assertNotEqual(
            result["workflow_state"]["state"], "accepted"
        )

    def test_placeholder_transport_field_rejected(self):
        """Transport proof fields that are empty/False/0 placeholders must not count as present."""
        manifest = acceptance_manifest()
        pre_ref = manifest["targets"][0]["pre_ref"]
        transport_ref = manifest["evidence_records"][pre_ref]["transport_ref"]
        manifest["evidence_records"][transport_ref]["fixed_predicate"] = 0
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertIn(
            result["workflow_state"]["state"], ("blocked", "failed")
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_post_state_transport_cannot_reuse_pre_state_read(self):
        """A post-state observation must cite a different transport proof than the pre-state read."""
        manifest = acceptance_manifest()
        target = manifest["targets"][0]
        pre = evidence_record(manifest, target, "pre")
        post = evidence_record(manifest, target, "post")
        original_post_transport_ref = post["transport_ref"]
        post["transport_ref"] = pre["transport_ref"]
        manifest["evidence"]["transport_proofs"] = [
            ref
            for ref in manifest["evidence"]["transport_proofs"]
            if ref != original_post_transport_ref
        ]
        manifest["evidence_records"].pop(original_post_transport_ref, None)
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_ordering_proof_requires_advancement_between_pre_and_post(self):
        """An ordering proof must show the state move between pre and post observations."""
        manifest = acceptance_manifest()
        target = manifest["targets"][0]
        pre = evidence_record(manifest, target, "pre")
        post = evidence_record(manifest, target, "post")
        receipt = evidence_record(manifest, target, "receipt")
        pre_value = pre["version"]
        post["version"] = pre_value
        receipt["resulting_version"] = pre_value
        target["ordering_proof"]["values"] = [pre_value, pre_value, pre_value]
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_acceptance_manifest_mutation_id_must_match_admitted_mutation(self):
        """The manifest's authorized mutation identity must match the admitted mutation identity."""
        manifest = acceptance_manifest()
        manifest["authorization"]["mutation_id"] = "mutation:forged"
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_security_gate_must_be_root_owned_and_authoritative(self):
        """A delegated worker must not be able to satisfy the security gate with a self-authored record."""
        manifest = acceptance_manifest()
        security_ref = manifest["evidence"]["security_gate"][0]
        for mutation in (
            {"owner": "worker"},
            {"authoritative": False},
        ):
            with self.subTest(mutation=mutation):
                m = copy.deepcopy(manifest)
                m["evidence_records"][security_ref].update(mutation)
                md = metadata()
                md["acceptance_manifest"] = m
                result = evaluate_root_workflow(md)
                self.assertNotEqual(
                    result["workflow_state"],
                    {"state": "accepted", "final": True},
                )
                self.assertTrue(result["workflow_state"]["final"])

    def test_unproven_skipped_targets_block_acceptance(self):
        """A skipped authorized target with no exclusion proof must not be accepted."""
        manifest = acceptance_manifest()
        target_id = manifest["targets"][0]["canonical_target_id"]
        skipped_id = "record:r_skipped"
        manifest["authorization"]["canonical_target_ids"].append(skipped_id)
        manifest["reconciliation"]["authorized"].append(skipped_id)
        manifest["reconciliation"]["inspected"].append(skipped_id)
        manifest["reconciliation"]["skipped"].append(skipped_id)
        set_ref = manifest["authorization"]["set_proof_ref"]
        set_record = manifest["evidence_records"][set_ref]
        set_record["target_ids"].append(skipped_id)
        set_record["requested_scope"].append(skipped_id)
        set_record["returned_scope"].append(skipped_id)
        set_record["witness"]["authoritative_total"] = 2
        set_record["witness"]["unique_count"] = 2
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_skipped_targets_with_exclusion_proof_accepted(self):
        """A skipped authorized target with a complete zero-mutation exclusion proof is accepted."""
        manifest = acceptance_manifest()
        target_id = manifest["targets"][0]["canonical_target_id"]
        skipped_id = "record:r_skipped"
        manifest["authorization"]["canonical_target_ids"].append(skipped_id)
        for name in ("authorized", "inspected"):
            manifest["reconciliation"][name].append(skipped_id)
        manifest["reconciliation"]["skipped"].append(skipped_id)
        set_ref = manifest["authorization"]["set_proof_ref"]
        set_record = manifest["evidence_records"][set_ref]
        set_record["target_ids"] = [target_id, skipped_id]
        set_record["requested_scope"] = [target_id, skipped_id]
        set_record["returned_scope"] = [target_id, skipped_id]
        set_record["witness"]["authoritative_total"] = 2
        set_record["witness"]["unique_count"] = 2
        scope_id = manifest["authorization"]["scope_id"]
        exact_action = manifest["authorization"]["exact_action"]
        mutation = manifest["authorization"]["mutation_id"]
        skip_tp = "tp:skip"
        pre_ref = "pre:skip"
        predicate_ref = "exclusion:skip"
        manifest["evidence_records"][skip_tp] = _transport_record(
            [skipped_id], "bounded_list", mutation
        )
        manifest["evidence_records"][skip_tp]["aggregate_scope"] = scope_id
        manifest["evidence_records"][skip_tp]["fixed_predicate"] = exact_action
        manifest["evidence_records"][pre_ref] = {
            "kind": "pre_state",
            "owner": "root",
            "authoritative": True,
            "target_id": skipped_id,
            "transport_ref": skip_tp,
            "version": "ver:observed",
            "state": "candidate",
        }
        manifest["evidence_records"][predicate_ref] = {
            "kind": "exclusion",
            "owner": "root",
            "authoritative": True,
            "target_id": skipped_id,
            "eligible": False,
            "reason_code": "predicate_miss",
            "fixed_predicate": exact_action,
            "pre_ref": pre_ref,
        }
        manifest["evidence"]["transport_proofs"].append(skip_tp)
        manifest["evidence"]["pre"].extend([pre_ref, predicate_ref])
        manifest["zero_mutation_proof"] = {
            "kind": "complete_exclusions",
            "transport_proof_ref": skip_tp,
            "candidate_ids": [skipped_id],
            "exclusions": {
                skipped_id: {
                    "reason_code": "predicate_miss",
                    "pre_ref": pre_ref,
                    "predicate_evidence_ref": predicate_ref,
                }
            },
        }
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertEqual(
            result["acceptance_manifest"]["terminal"]["reason_code"],
            "all_targets_verified",
        )

    def test_out_of_scope_action_receipt_blocks_acceptance(self):
        """An action receipt for a target outside the manifest must prevent acceptance."""
        manifest = acceptance_manifest()
        receipt_ref = "receipt:outside"
        manifest["evidence"]["actions"].append(receipt_ref)
        manifest["evidence_records"][receipt_ref] = {
            "kind": "receipt",
            "authoritative": True,
            "target_id": "record:r_outside",
            "mutation_id": manifest["authorization"]["mutation_id"],
            "action": manifest["authorization"]["exact_action"],
            "resulting_version": "ver:99",
            "status": "committed",
        }
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_unhashable_action_receipt_target_id_blocked(self):
        """A non-string action receipt target_id must fail closed, not crash."""
        manifest = acceptance_manifest()
        receipt_ref = "receipt:weird"
        manifest["evidence"]["actions"].append(receipt_ref)
        manifest["evidence_records"][receipt_ref] = {
            "kind": "receipt",
            "authoritative": True,
            "target_id": [],
            "mutation_id": manifest["authorization"]["mutation_id"],
            "action": manifest["authorization"]["exact_action"],
            "resulting_version": "ver:99",
            "status": "committed",
        }
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_unverified_accepted_identifier_not_emitted(self):
        """A ghost identifier in reconciliation.accepted must not appear in the normalized accepted set or counts."""
        manifest = acceptance_manifest()
        manifest["reconciliation"]["accepted"].append("ghost:1")
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotIn(
            "ghost:1",
            result["acceptance_manifest"]["reconciliation"]["accepted"],
        )
        self.assertEqual(
            result["acceptance_manifest"]["reconciliation"]["derived_counts"]["accepted"],
            1,
        )

    def test_forged_exact_action_blocks_acceptance(self):
        """Manifest exact_action must match the canonical action for the declared family."""
        manifest = acceptance_manifest()
        manifest["authorization"]["exact_action"] = "forged_action"
        for ref in manifest["evidence"]["actions"]:
            receipt = manifest["evidence_records"].get(ref)
            if isinstance(receipt, dict):
                receipt["action"] = "forged_action"
        set_ref = manifest["authorization"]["set_proof_ref"]
        set_record = manifest["evidence_records"].get(set_ref)
        if isinstance(set_record, dict):
            set_record["fixed_predicate"] = "forged_action"
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertTrue(result["workflow_state"]["final"])

    def test_reported_failure_for_unlisted_identifier_not_erased(self):
        """A self-reported failure for an identifier outside the target list must fail the run."""
        manifest = acceptance_manifest()
        manifest["reconciliation"]["failed"] = ["ghost:failed"]
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertEqual(
            result["workflow_state"],
            {"state": "failed", "final": True},
        )
        self.assertIn(
            "ghost:failed",
            result["acceptance_manifest"]["reconciliation"]["failed"],
        )

    def test_reported_unknown_for_unlisted_identifier_not_erased(self):
        """A self-reported unresolved outcome for an unlisted identifier must stay indeterminate."""
        manifest = acceptance_manifest()
        manifest["reconciliation"]["unknown"] = ["ghost:unknown"]
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertEqual(
            result["workflow_state"],
            {"state": "indeterminate", "final": True},
        )
        self.assertIn(
            "ghost:unknown",
            result["acceptance_manifest"]["reconciliation"]["unknown"],
        )

    def test_per_target_transport_scope_and_predicate_bound(self):
        """A per-target pre-state transport must match the authorized scope and predicate."""
        manifest = acceptance_manifest()
        pre_ref = manifest["targets"][0]["pre_ref"]
        transport_ref = manifest["evidence_records"][pre_ref]["transport_ref"]
        manifest["evidence_records"][transport_ref]["aggregate_scope"] = "scope:forged"
        md = metadata()
        md["acceptance_manifest"] = manifest
        result = evaluate_root_workflow(md)
        self.assertNotEqual(
            result["workflow_state"],
            {"state": "accepted", "final": True},
        )
        self.assertTrue(result["workflow_state"]["final"])


if __name__ == "__main__":
    unittest.main()
