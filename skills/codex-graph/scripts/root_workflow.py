"""Deterministic root-owned authority admission for sanitized workflow facts."""

from __future__ import annotations


_TOPOLOGIES = {"L0", "L1", "L2", "L3", "L4"}
_TRIGGER_STATES = {"fired", "not_fired", "not_evaluated", "not_applicable"}
_PROCESS_FACTS = {"process_exit", "generated_output", "attempt_pass"}


def _string_list(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item) for item in value
    )


def _retain(target: list[str], value: object) -> bool:
    if not isinstance(value, list):
        return False
    valid = True
    for item in value:
        if not isinstance(item, str) or not item:
            valid = False
            continue
        if item not in target:
            target.append(item)
    return valid


def _worker_reasons(worker: object, prefix: str = "worker") -> list[str]:
    if not isinstance(worker, dict):
        return [f"malformed_{prefix}"]

    reasons = []
    if not isinstance(worker.get("role"), str) or not worker["role"]:
        reasons.append(f"malformed_{prefix}_role")
    if not isinstance(worker.get("environment"), str) or not worker["environment"]:
        reasons.append(f"malformed_{prefix}_environment")
    if not _string_list(worker.get("read_scope")):
        reasons.append(f"malformed_{prefix}_read_scope")
    if not _string_list(worker.get("write_scope")):
        reasons.append(f"malformed_{prefix}_write_scope")
    elif worker["write_scope"] and worker.get("environment") != "isolated_worktree":
        reasons.append(f"unproved_{prefix}_write_isolation")

    capabilities = worker.get("capabilities")
    if not isinstance(capabilities, dict):
        reasons.append(f"malformed_{prefix}_capabilities")
    elif (
        capabilities.get("durable_mutation") is not False
        or capabilities.get("real_checkout_integration") is not False
    ):
        reasons.append(f"unproved_{prefix}_capability_confinement")

    if not isinstance(worker.get("isolation_proof"), str) or not worker["isolation_proof"]:
        reasons.append(f"unproved_{prefix}_confinement")
    return reasons

_RECONCILIATION_SETS = (
    "authorized",
    "inspected",
    "intended",
    "attempted",
    "receipt_resolved",
    "post_verified",
    "accepted",
    "failed",
    "unknown",
    "skipped",
    "unauthorized",
    "duplicates",
)
_OUTCOME_SETS = (
    "accepted",
    "failed",
    "unknown",
    "skipped",
    "unauthorized",
    "duplicates",
)
_ORDERING_KINDS = {
    "monotonic_version",
    "revision",
    "generation",
    "service_sequence",
    "tool_linearized_timestamp",
}
_RETAINED_FACTS = {
    "opaque_ids",
    "generic_state_codes",
    "counts",
    "versions",
    "times",
    "locators",
    "digests",
    "completeness_status",
    "reconciliation",
    "repair_attempts",
    "outcomes",
    "terminal_reason",
}
_FAMILY_MATRIX = {
    "record_state": {
        "pre": ("resource_id", "version", "state"),
        "receipt": ("resulting_version", "status"),
        "post": ("resource_id", "version", "state"),
        "order": (
            "monotonic_version",
            (("pre", "version"), ("receipt", "resulting_version"), ("post", "version")),
        ),
        "pre_equal": (("pre", "resource_id", "target", "canonical_target_id"),),
        "post_equal": (
            ("post", "resource_id", "target", "canonical_target_id"),
            ("receipt", "resulting_version", "post", "version"),
            ("intent", "expected_state", "post", "state"),
        ),
        "receipt_status": ("committed",),
    },
    "relationship_set": {
        "pre": ("subject_id", "relation", "object_id", "state", "set_revision"),
        "receipt": ("set_revision", "status"),
        "post": ("subject_id", "relation", "object_id", "state", "set_revision"),
        "order": (
            "revision",
            (("pre", "set_revision"), ("receipt", "set_revision"), ("post", "set_revision")),
        ),
        "pre_equal": (),
        "post_equal": (
            ("pre", "subject_id", "post", "subject_id"),
            ("pre", "relation", "post", "relation"),
            ("pre", "object_id", "post", "object_id"),
            ("receipt", "set_revision", "post", "set_revision"),
            ("intent", "expected_state", "post", "state"),
        ),
        "receipt_status": ("committed",),
    },
    "create_append": {
        "pre": ("parent_id", "client_mutation_key", "key_state", "payload_digest"),
        "receipt": (
            "client_mutation_key",
            "result_resource_id",
            "commit_sequence",
            "status",
        ),
        "post": ("resource_id", "state", "commit_sequence"),
        "order": (
            "service_sequence",
            (("receipt", "commit_sequence"), ("post", "commit_sequence")),
        ),
        "pre_equal": (),
        "post_equal": (
            ("pre", "client_mutation_key", "receipt", "client_mutation_key"),
            ("receipt", "result_resource_id", "post", "resource_id"),
            ("receipt", "commit_sequence", "post", "commit_sequence"),
            ("intent", "expected_state", "post", "state"),
        ),
        "receipt_status": ("committed",),
    },
    "delete_erase": {
        "pre": ("resource_id", "version", "state"),
        "receipt": ("deletion_generation", "status"),
        "post": ("witness", "deletion_generation"),
        "order": (
            "generation",
            (("pre", "version"), ("receipt", "deletion_generation"), ("post", "deletion_generation")),
        ),
        "pre_equal": (("pre", "resource_id", "target", "canonical_target_id"),),
        "post_equal": (
            ("receipt", "deletion_generation", "post", "deletion_generation"),
        ),
        "receipt_status": ("committed",),
    },
    "blob_content": {
        "pre": ("object_id", "generation", "length", "digest", "ranges"),
        "receipt": ("generation", "length", "digest", "status"),
        "post": ("object_id", "generation", "length", "digest", "ranges"),
        "order": (
            "generation",
            (("pre", "generation"), ("receipt", "generation"), ("post", "generation")),
        ),
        "pre_equal": (("pre", "object_id", "target", "canonical_target_id"),),
        "post_equal": (
            ("post", "object_id", "target", "canonical_target_id"),
            ("receipt", "generation", "post", "generation"),
            ("receipt", "length", "post", "length"),
            ("receipt", "digest", "post", "digest"),
            ("intent", "expected_digest", "post", "digest"),
        ),
        "receipt_status": ("committed",),
    },
    "operation_composite": {
        "pre": ("operation_id", "authorized_effect_ids", "effect_manifest_capability"),
        "receipt": ("operation_id", "operation_sequence", "status"),
        "post": (
            "operation_id",
            "terminal",
            "operation_sequence",
            "effect_ids",
            "effect_manifest_ref",
        ),
        "order": (
            "service_sequence",
            (("receipt", "operation_sequence"), ("post", "operation_sequence")),
        ),
        "pre_equal": (
            ("pre", "operation_id", "target", "canonical_target_id"),
        ),
        "post_equal": (
            ("receipt", "operation_id", "target", "canonical_target_id"),
            ("post", "operation_id", "target", "canonical_target_id"),
        ),
        "receipt_status": ("accepted", "completed"),
    },
}


def _present_field(record: object, field: str) -> bool:
    if not isinstance(record, dict) or field not in record:
        return False
    value = record[field]
    return value is not None and (not isinstance(value, str) or bool(value))


def _valid_string_set(value: object) -> bool:
    return _string_list(value) and len(value) == len(set(value))


def _manifest_sets(manifest: object) -> tuple[dict[str, list[str]], list[str]]:
    reconciliation = (
        manifest.get("reconciliation") if isinstance(manifest, dict) else None
    )
    sets = {}
    reasons = []
    for name in _RECONCILIATION_SETS:
        value = reconciliation.get(name) if isinstance(reconciliation, dict) else None
        retained = []
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item and item not in retained:
                    retained.append(item)
                else:
                    reasons.append(f"malformed_{name}_set")
        else:
            reasons.append(f"malformed_{name}_set")
        sets[name] = retained

    seen: set[str] = set()
    for name in _OUTCOME_SETS:
        current = set(sets[name])
        if seen & current:
            reasons.append("overlapping_outcome_sets")
        seen.update(current)
    return sets, reasons


def _linked_evidence(manifest: dict) -> tuple[dict[str, list[str]], list[str]]:
    evidence = manifest.get("evidence")
    linked = {}
    reasons = []
    for name in (
        "identity_proofs",
        "transport_proofs",
        "pre",
        "security_gate",
        "actions",
        "post",
    ):
        value = evidence.get(name) if isinstance(evidence, dict) else None
        if not _valid_string_set(value):
            reasons.append(f"malformed_{name}_evidence")
            value = []
        linked[name] = list(value)
    return linked, reasons


def _transport_complete(
    ref: object,
    expected_targets: list[str],
    linked: dict[str, list[str]],
    records: dict,
) -> bool:
    record = records.get(ref) if isinstance(ref, str) else None
    if (
        ref not in linked["transport_proofs"]
        or not isinstance(record, dict)
        or record.get("kind") != "transport_proof"
        or record.get("outcome") != "complete"
        or not _valid_string_set(record.get("target_ids"))
        or set(record["target_ids"]) != set(expected_targets)
    ):
        return False

    witness = record.get("witness")
    capability = record.get("capability")
    if capability == "bounded_list":
        return (
            isinstance(witness, dict)
            and isinstance(witness.get("authoritative_total"), int)
            and not isinstance(witness["authoritative_total"], bool)
            and witness["authoritative_total"] == len(record["target_ids"])
            and witness.get("unique_count") == len(record["target_ids"])
        )
    if capability == "cursor_page":
        return isinstance(witness, dict) and _present_field(
            witness, "terminal_condition"
        )
    if capability == "single_object_blob":
        return (
            len(record["target_ids"]) == 1
            and isinstance(witness, dict)
            and witness.get("kind")
            in {
                "authoritative_object",
                "authoritative_length",
                "authoritative_digest",
                "gap_free_ranges",
            }
            and _present_field(witness, "value")
        )
    return False


def _complete_ranges(record: object) -> bool:
    if not isinstance(record, dict):
        return False
    length = record.get("length")
    ranges = record.get("ranges")
    if (
        not isinstance(length, int)
        or isinstance(length, bool)
        or length < 0
        or not isinstance(ranges, list)
    ):
        return False
    if length == 0:
        return ranges == []

    cursor = 0
    for byte_range in ranges:
        if (
            not isinstance(byte_range, list)
            or len(byte_range) != 2
            or any(
                not isinstance(bound, int) or isinstance(bound, bool)
                for bound in byte_range
            )
            or byte_range[0] != cursor
            or byte_range[1] <= byte_range[0]
            or byte_range[1] > length
        ):
            return False
        cursor = byte_range[1]
    return cursor == length


def _source_value(sources: dict[str, dict], source: str, field: str) -> object:
    record = sources.get(source)
    return record.get(field) if isinstance(record, dict) else None


def _mismatches(
    checks: tuple[tuple[str, str, str, str], ...],
    sources: dict[str, dict],
) -> bool:
    return any(
        _source_value(sources, left_source, left_field)
        != _source_value(sources, right_source, right_field)
        for left_source, left_field, right_source, right_field in checks
    )


def _target_action_started(
    target: dict,
    target_id: object,
    linked: dict[str, list[str]],
    records: dict,
    sets: dict[str, list[str]],
) -> bool:
    receipt_ref = target.get("receipt_ref")
    receipt = records.get(receipt_ref) if isinstance(receipt_ref, str) else None
    return bool(
        target_id in sets["attempted"]
        or receipt_ref in linked["actions"]
        or (isinstance(receipt, dict) and receipt.get("kind") == "receipt")
    )


def _evaluate_target(
    target: object,
    family: object,
    exact_action: object,
    tool_contract_digest: object,
    linked: dict[str, list[str]],
    records: dict,
    sets: dict[str, list[str]],
) -> tuple[str, bool, bool, bool, list[str], list[str]]:
    if not isinstance(target, dict) or family not in _FAMILY_MATRIX:
        return "failed", False, False, False, ["malformed_target"], []

    row = _FAMILY_MATRIX[family]
    target_id = target.get("canonical_target_id")
    action_started = _target_action_started(
        target, target_id, linked, records, sets
    )
    pre_issues = []
    post_issues = []
    failures = []
    duplicates = []

    if not isinstance(target_id, str) or not target_id:
        pre_issues.append("missing_canonical_target_id")
    if target_id not in sets["authorized"] or target_id not in sets["intended"]:
        pre_issues.append("target_outside_declared_scope")
    if target_id not in sets["inspected"]:
        pre_issues.append("target_not_inspected")

    aliases = target.get("aliases")
    if not isinstance(aliases, list):
        pre_issues.append("malformed_aliases")
        aliases = []
    for alias in aliases:
        proof_ref = alias.get("proof_ref") if isinstance(alias, dict) else None
        proof = records.get(proof_ref) if isinstance(proof_ref, str) else None
        if (
            not isinstance(alias, dict)
            or not _present_field(alias, "alias")
            or proof_ref not in linked["identity_proofs"]
            or not isinstance(proof, dict)
            or proof.get("kind") != "identity_mapping"
            or proof.get("authoritative") is not True
            or proof.get("alias") != alias.get("alias")
            or not _valid_string_set(proof.get("canonical_target_ids"))
            or proof["canonical_target_ids"] != [target_id]
        ):
            pre_issues.append("unproved_alias")

    intent = target.get("intent")
    mutation_id = intent.get("mutation_id") if isinstance(intent, dict) else None
    action = intent.get("action") if isinstance(intent, dict) else None
    if (
        not isinstance(intent, dict)
        or not isinstance(mutation_id, str)
        or not mutation_id
        or not isinstance(action, str)
        or not action
        or action != exact_action
    ):
        pre_issues.append("malformed_exact_intent")

    pre_ref = target.get("pre_ref")
    pre = records.get(pre_ref) if isinstance(pre_ref, str) else None
    pre_transport_ref = pre.get("transport_ref") if isinstance(pre, dict) else None
    pre_valid = (
        pre_ref in linked["pre"]
        and isinstance(pre, dict)
        and pre.get("kind") == "pre_state"
        and pre.get("owner") == "root"
        and pre.get("authoritative") is True
        and pre.get("target_id") == target_id
        and _transport_complete(
            pre_transport_ref, [target_id], linked, records
        )
    )
    if not pre_valid:
        pre_issues.append("unproved_root_pre_state")
    if any(not _present_field(pre, field) for field in row["pre"]):
        pre_issues.append(f"incomplete_{family}_pre_state")

    eligibility = target.get("eligibility")
    eligibility_refs = (
        eligibility.get("evidence_refs") if isinstance(eligibility, dict) else None
    )
    security_refs = [
        ref
        for ref in (eligibility_refs if isinstance(eligibility_refs, list) else [])
        if ref in linked["security_gate"]
    ]
    security = records.get(security_refs[0]) if len(security_refs) == 1 else None
    if (
        not isinstance(eligibility, dict)
        or eligibility.get("eligible") is not True
        or not _present_field(eligibility, "reason_code")
        or not _valid_string_set(eligibility_refs)
        or pre_ref not in eligibility_refs
        or not isinstance(security, dict)
        or security.get("kind") != "security_gate"
        or security.get("verdict") != "allow"
        or security.get("target_id") != target_id
        or security.get("mutation_id") != mutation_id
        or security.get("action") != action
    ):
        pre_issues.append("unproved_eligibility_or_authorization")

    receipt_ref = target.get("receipt_ref")
    receipt = records.get(receipt_ref) if isinstance(receipt_ref, str) else None
    receipt_core = (
        receipt_ref in linked["actions"]
        and isinstance(receipt, dict)
        and receipt.get("kind") == "receipt"
        and receipt.get("authoritative") is True
    )
    if receipt_core and (
        receipt.get("target_id") != target_id
        or receipt.get("mutation_id") != mutation_id
        or receipt.get("action") != action
    ):
        failures.append("authoritative_receipt_contradiction")
    receipt_resolved = receipt_core and not failures
    if not receipt_resolved:
        post_issues.append("unresolved_authoritative_receipt")
    if any(not _present_field(receipt, field) for field in row["receipt"]):
        post_issues.append(f"incomplete_{family}_receipt")
    if isinstance(receipt, dict):
        if receipt.get("status") == "rejected":
            failures.append("authoritative_rejection")
        elif _present_field(receipt, "status") and receipt.get(
            "status"
        ) not in row["receipt_status"]:
            post_issues.append("unresolved_receipt")

    post_ref = target.get("post_ref")
    post = records.get(post_ref) if isinstance(post_ref, str) else None
    post_transport_ref = post.get("transport_ref") if isinstance(post, dict) else None
    post_verified = (
        post_ref in linked["post"]
        and isinstance(post, dict)
        and post.get("kind") == "post_state"
        and post.get("owner") == "root"
        and post.get("authoritative") is True
        and post.get("target_id") == target_id
        and _transport_complete(
            post_transport_ref, [target_id], linked, records
        )
    )
    if not post_verified:
        post_issues.append("unproved_root_post_state")
    if any(not _present_field(post, field) for field in row["post"]):
        post_issues.append(f"incomplete_{family}_post_state")

    sources = {
        "target": target,
        "intent": intent if isinstance(intent, dict) else {},
        "pre": pre if isinstance(pre, dict) else {},
        "receipt": receipt if isinstance(receipt, dict) else {},
        "post": post if isinstance(post, dict) else {},
    }
    if _mismatches(row["pre_equal"], sources):
        pre_issues.append(f"ambiguous_{family}_identity")
    if post_verified and receipt_core and _mismatches(row["post_equal"], sources):
        failures.append("authoritative_contradiction")

    ordering = target.get("ordering_proof")
    expected_kind, order_sources = row["order"]
    expected_values = [
        _source_value(sources, source, field) for source, field in order_sources
    ]
    ordering_kind = ordering.get("kind") if isinstance(ordering, dict) else None
    timestamp_is_bound = (
        ordering_kind == "tool_linearized_timestamp"
        and isinstance(ordering, dict)
        and ordering.get("linearization_contract_ref") == tool_contract_digest
    )
    ordering_is_admissible = (
        isinstance(ordering, dict)
        and ordering.get("status") == "proved"
        and ordering_kind in _ORDERING_KINDS
        and (ordering_kind == expected_kind or timestamp_is_bound)
    )
    if not ordering_is_admissible:
        failures.append("inadmissible_ordering")
    elif ordering.get("values") != expected_values:
        if pre_valid and receipt_core and post_verified:
            failures.append("ordering_process_violation")
        else:
            post_issues.append("unresolved_ordering")

    if family == "create_append":
        binding_ref = target.get("identity_binding_ref")
        binding = records.get(binding_ref) if isinstance(binding_ref, str) else None
        if (
            binding_ref not in linked["identity_proofs"]
            or not isinstance(binding, dict)
            or binding.get("kind") != "create_identity_binding"
            or binding.get("authoritative") is not True
        ):
            post_issues.append("unresolved_create_identity")
        elif not isinstance(pre, dict) or not isinstance(receipt, dict):
            post_issues.append("unresolved_create_identity")
        elif (
            binding.get("client_mutation_key") != pre.get("client_mutation_key")
            or binding.get("result_resource_id")
            != receipt.get("result_resource_id")
        ):
            failures.append("authoritative_create_identity_contradiction")
    elif family == "delete_erase" and post_verified:
        witness = post.get("witness")
        if witness == "target_present":
            failures.append("authoritative_contradiction")
        elif witness not in {
            "authoritative_tombstone",
            "deletion_audit",
            "authenticated_strong_negative",
        }:
            post_issues.append("weak_deletion_witness")
    elif family == "blob_content":
        if not _complete_ranges(pre):
            pre_issues.append("incomplete_pre_ranges")
        if not _complete_ranges(post):
            post_issues.append("incomplete_post_ranges")
    elif family == "operation_composite":
        leaf_entries = target.get("leaf_entries")
        if sources["pre"].get("effect_manifest_capability") is not True:
            pre_issues.append("aggregate_only_operation")
        if not isinstance(leaf_entries, list) or not leaf_entries:
            post_issues.append("missing_leaf_entries")
            leaf_entries = []
        leaf_ids = [
            leaf.get("canonical_target_id")
            for leaf in leaf_entries
            if isinstance(leaf, dict)
            and isinstance(leaf.get("canonical_target_id"), str)
        ]
        expected_ids = (
            intent.get("expected_effect_ids") if isinstance(intent, dict) else None
        )
        declared_lists = [
            sources["pre"].get("authorized_effect_ids"),
            expected_ids,
            sources["post"].get("effect_ids"),
            leaf_ids,
        ]
        if any(
            _string_list(value) and len(value) != len(set(value))
            for value in declared_lists
        ):
            duplicates.append(target_id)
            failures.append("duplicate_composite_effect")
        elif not _valid_string_set(declared_lists[0]):
            pre_issues.append("unproved_authorized_effect_set")
        elif any(not _valid_string_set(value) for value in declared_lists[1:]):
            post_issues.append("incomplete_leaf_effect_set")
        elif post_verified and any(
            set(value) != set(expected_ids) for value in declared_lists
        ):
            failures.append("authoritative_effect_set_contradiction")
        if post_verified and sources["post"].get("terminal") is not True:
            post_issues.append("nonterminal_effect_manifest")
        for leaf in leaf_entries:
            leaf_id = (
                leaf.get("canonical_target_id") if isinstance(leaf, dict) else None
            )
            leaf_sets = {
                name: [leaf_id]
                if name
                in {
                    "authorized",
                    "inspected",
                    "intended",
                    "attempted",
                    "receipt_resolved",
                    "post_verified",
                    "accepted",
                }
                and isinstance(leaf_id, str)
                else []
                for name in _RECONCILIATION_SETS
            }
            leaf_intent = leaf.get("intent") if isinstance(leaf, dict) else None
            leaf_action = (
                leaf_intent.get("action") if isinstance(leaf_intent, dict) else None
            )
            leaf_result = _evaluate_target(
                leaf,
                leaf.get("family") if isinstance(leaf, dict) else None,
                leaf_action,
                tool_contract_digest,
                linked,
                records,
                leaf_sets,
            )
            if leaf_result[0] == "failed":
                failures.extend(leaf_result[4] or ["failed_leaf_entry"])
            elif leaf_result[0] != "accepted":
                post_issues.extend(leaf_result[4] or ["incomplete_leaf_entry"])
            duplicates.extend(leaf_result[5])

    if target.get("outcome") == "failed":
        failures.append("reported_failure")
    elif target.get("outcome") == "unknown":
        post_issues.append("reported_unknown")
    elif target.get("outcome") != "accepted":
        pre_issues.append("malformed_target_outcome")

    reasons = list(dict.fromkeys(pre_issues + post_issues + failures))
    if failures:
        status = "failed" if action_started else "blocked"
    elif pre_issues:
        status = "failed" if action_started else "blocked"
    elif post_issues:
        status = "indeterminate" if action_started else "blocked"
    elif not action_started:
        status = "blocked"
        reasons.append("target_not_attempted")
    else:
        status = "accepted"
    return (
        status,
        receipt_resolved,
        post_verified,
        action_started,
        reasons,
        list(dict.fromkeys(duplicates)),
    )


def _zero_mutation_proved(
    manifest: dict,
    sets: dict[str, list[str]],
    linked: dict[str, list[str]],
    records: dict,
) -> bool:
    proof = manifest.get("zero_mutation_proof")
    if (
        not isinstance(proof, dict)
        or not _valid_string_set(proof.get("candidate_ids"))
        or set(proof["candidate_ids"]) != set(sets["inspected"])
        or sets["intended"]
        or sets["attempted"]
        or linked["actions"]
        or linked["post"]
        or not _transport_complete(
            proof.get("transport_proof_ref"),
            proof["candidate_ids"],
            linked,
            records,
        )
    ):
        return False
    if proof.get("kind") == "complete_empty_set":
        return not proof["candidate_ids"] and not sets["skipped"]
    if proof.get("kind") != "complete_exclusions":
        return False

    exclusions = proof.get("exclusions")
    return (
        isinstance(exclusions, dict)
        and set(exclusions) == set(proof["candidate_ids"])
        and all(isinstance(reason, str) and reason for reason in exclusions.values())
        and set(sets["skipped"]) == set(proof["candidate_ids"])
    )


def _sanitize_target(target: object) -> dict:
    if not isinstance(target, dict):
        return {}
    sanitized = {
        key: target[key]
        for key in (
            "family",
            "canonical_target_id",
            "pre_ref",
            "receipt_ref",
            "post_ref",
            "identity_binding_ref",
            "outcome",
        )
        if key in target
    }
    sanitized["aliases"] = [
        {"alias": alias.get("alias"), "proof_ref": alias.get("proof_ref")}
        for alias in target.get("aliases", [])
        if isinstance(alias, dict)
    ]
    eligibility = target.get("eligibility")
    sanitized["eligibility"] = {
        key: eligibility[key]
        for key in ("eligible", "reason_code", "evidence_refs")
        if isinstance(eligibility, dict) and key in eligibility
    }
    intent = target.get("intent")
    sanitized["intent"] = {
        key: intent[key]
        for key in (
            "mutation_id",
            "action",
            "expected_state",
            "expected_digest",
            "expected_effect_ids",
        )
        if isinstance(intent, dict) and key in intent
    }
    ordering = target.get("ordering_proof")
    sanitized["ordering_proof"] = {
        key: ordering[key]
        for key in (
            "kind",
            "status",
            "values",
            "linearization_contract_ref",
        )
        if isinstance(ordering, dict) and key in ordering
    }
    if "leaf_entries" in target:
        sanitized["leaf_entries"] = [
            _sanitize_target(leaf) for leaf in target["leaf_entries"]
        ]
    return sanitized


def _copy_fields(value: object, fields: tuple[str, ...]) -> dict:
    return {
        field: value[field]
        for field in fields
        if isinstance(value, dict) and field in value
    }


def _evaluate_acceptance_manifest(
    manifest: object, revision: object
) -> tuple[dict, str]:
    sets, set_reasons = _manifest_sets(manifest)
    if not isinstance(manifest, dict):
        normalized_sets = {
            **sets,
            "derived_counts": {name: len(sets[name]) for name in _RECONCILIATION_SETS},
        }
        return {
            "schema": None,
            "reconciliation": normalized_sets,
            "replay_prohibited": [],
            "terminal": {
                "status": "blocked",
                "reason_code": "pre_action_evidence_gap",
            },
        }, "blocked"

    linked, evidence_reasons = _linked_evidence(manifest)
    records = manifest.get("evidence_records")
    records = records if isinstance(records, dict) else {}
    shape_reasons = set_reasons + evidence_reasons
    if not isinstance(manifest.get("evidence_records"), dict):
        shape_reasons.append("missing_evidence_records")
    if manifest.get("schema") != "codexgraph.acceptance-manifest/v1":
        shape_reasons.append("unsupported_acceptance_manifest_schema")

    workflow = manifest.get("workflow")
    if (
        not isinstance(workflow, dict)
        or workflow.get("root_actor") != "root"
        or workflow.get("revision") != revision
        or not _present_field(workflow, "workflow_id")
        or not _present_field(workflow, "attempt_id")
    ):
        shape_reasons.append("malformed_acceptance_workflow")

    adapter = manifest.get("adapter")
    family = adapter.get("family") if isinstance(adapter, dict) else None
    if (
        family not in _FAMILY_MATRIX
        or not all(
            _present_field(adapter, field)
            for field in ("adapter_id", "adapter_version", "tool_contract_digest")
        )
    ):
        shape_reasons.append("malformed_acceptance_adapter")

    authorization = manifest.get("authorization")
    authorized_ids = (
        authorization.get("canonical_target_ids")
        if isinstance(authorization, dict)
        else None
    )
    exact_action = (
        authorization.get("exact_action")
        if isinstance(authorization, dict)
        else None
    )
    if (
        not isinstance(authorization, dict)
        or not all(
            _present_field(authorization, field)
            for field in ("scope_id", "decision_ref", "exact_action", "set_proof_ref")
        )
        or not _valid_string_set(authorized_ids)
        or set(authorized_ids) != set(sets["authorized"])
    ):
        shape_reasons.append("malformed_acceptance_authorization")

    repair = manifest.get("repair")
    if (
        not isinstance(repair, dict)
        or not _string_list(repair.get("allowed"))
        or not _string_list(repair.get("forbidden"))
        or not isinstance(repair.get("attempts"), list)
    ):
        shape_reasons.append("malformed_evidence_repair")

    retention = manifest.get("retention")
    retained = retention.get("retained") if isinstance(retention, dict) else None
    if (
        not isinstance(retention, dict)
        or retention.get("raw_payload") != "not_retained"
        or not _valid_string_set(retained)
        or not set(retained).issubset(_RETAINED_FACTS)
        or not all(
            _present_field(retention, field)
            for field in (
                "policy_id",
                "evidence_locator_expiry",
                "manifest_expiry",
                "redaction_proof_ref",
            )
        )
    ):
        shape_reasons.append("non_minimal_evidence_retention")

    targets = manifest.get("targets")
    if not isinstance(targets, list):
        targets = []
        shape_reasons.append("malformed_targets")
    target_ids = [
        target.get("canonical_target_id")
        for target in targets
        if isinstance(target, dict)
        and isinstance(target.get("canonical_target_id"), str)
        and target.get("canonical_target_id")
    ]
    if len(target_ids) != len(set(target_ids)):
        shape_reasons.append("duplicate_target_entries")
    if set(target_ids) != set(sets["intended"]):
        shape_reasons.append("target_reconciliation_mismatch")
    if not set(sets["intended"]).issubset(sets["authorized"]):
        shape_reasons.append("unauthorized_intent")
    if not set(sets["intended"]).issubset(sets["inspected"]):
        shape_reasons.append("uninspected_intent")
    if not set(sets["attempted"]).issubset(sets["intended"]):
        shape_reasons.append("out_of_scope_attempt")
    if not set(sets["receipt_resolved"]).issubset(sets["attempted"]):
        shape_reasons.append("receipt_without_attempt")
    if not set(sets["post_verified"]).issubset(sets["receipt_resolved"]):
        shape_reasons.append("post_without_receipt")

    zero_proof = manifest.get("zero_mutation_proof")
    expected_set_scope = (
        zero_proof.get("candidate_ids")
        if not sets["intended"] and isinstance(zero_proof, dict)
        else sets["authorized"]
    )
    if not _valid_string_set(expected_set_scope) or not _transport_complete(
        authorization.get("set_proof_ref")
        if isinstance(authorization, dict)
        else None,
        expected_set_scope if isinstance(expected_set_scope, list) else [],
        linked,
        records,
    ):
        shape_reasons.append("unproved_authorized_set")

    alias_targets: dict[str, set[str]] = {}
    for target in targets:
        if not isinstance(target, dict):
            continue
        target_id = target.get("canonical_target_id")
        for alias in target.get("aliases", []):
            if isinstance(alias, dict) and isinstance(alias.get("alias"), str):
                alias_targets.setdefault(alias["alias"], set()).add(target_id)
    if any(len(canonical_ids) != 1 for canonical_ids in alias_targets.values()):
        shape_reasons.append("ambiguous_alias_mapping")

    statuses = {}
    receipt_resolved = []
    post_verified = []
    replay_prohibited = list(sets["attempted"])
    target_reasons = []
    detected_duplicates = []
    for target in targets:
        result = _evaluate_target(
            target,
            family,
            exact_action,
            adapter.get("tool_contract_digest")
            if isinstance(adapter, dict)
            else None,
            linked,
            records,
            sets,
        )
        target_id = (
            target.get("canonical_target_id") if isinstance(target, dict) else None
        )
        if isinstance(target_id, str) and target_id:
            statuses[target_id] = result[0]
            if result[1]:
                receipt_resolved.append(target_id)
            if result[2]:
                post_verified.append(target_id)
            if result[3] and target_id not in replay_prohibited:
                replay_prohibited.append(target_id)
        target_reasons.extend(result[4])
        detected_duplicates.extend(result[5])

    outcome_priority = {}
    for name in ("skipped", "accepted", "unknown", "failed", "unauthorized", "duplicates"):
        for target_id in sets[name]:
            outcome_priority[target_id] = name
    for target_id, target_status in statuses.items():
        outcome_priority[target_id] = {
            "accepted": "accepted",
            "indeterminate": "unknown",
            "failed": "failed",
        }.get(target_status, outcome_priority.get(target_id, "skipped"))
    for target_id in detected_duplicates:
        outcome_priority[target_id] = "duplicates"

    normalized_sets = {
        **sets,
        "receipt_resolved": receipt_resolved,
        "post_verified": post_verified,
        **{
            name: [
                target_id
                for target_id, outcome in outcome_priority.items()
                if outcome == name
            ]
            for name in _OUTCOME_SETS
        },
    }
    normalized_sets["derived_counts"] = {
        name: len(normalized_sets[name]) for name in _RECONCILIATION_SETS
    }

    any_action = bool(replay_prohibited or linked["actions"])
    failed = bool(
        normalized_sets["failed"]
        or normalized_sets["unauthorized"]
        or normalized_sets["duplicates"]
        or any(status == "failed" for status in statuses.values())
        or (shape_reasons and any_action)
    )
    unresolved = bool(
        normalized_sets["unknown"]
        or any(status == "indeterminate" for status in statuses.values())
    )
    blocked = bool(
        shape_reasons
        or any(status == "blocked" for status in statuses.values())
        or set(sets["intended"])
        != set(normalized_sets["accepted"])
        | set(normalized_sets["failed"])
        | set(normalized_sets["unknown"])
    )
    zero_mutation_proved = not sets["intended"] and _zero_mutation_proved(
        manifest, sets, linked, records
    )
    if failed:
        status = "failed"
        reason_code = (
            "authoritative_or_process_failure"
            if target_reasons
            else "manifest_process_violation"
        )
    elif unresolved:
        status = "indeterminate"
        reason_code = "missing_post_action_evidence"
    elif blocked:
        status = "blocked"
        reason_code = "pre_action_evidence_gap"
    elif zero_mutation_proved:
        status = "accepted"
        reason_code = "zero_mutation_proved"
    elif not sets["intended"]:
        status = "blocked"
        reason_code = "pre_action_evidence_gap"
    else:
        status = "accepted"
        reason_code = "all_targets_verified"

    normalized = {
        "schema": manifest.get("schema"),
        "workflow": _copy_fields(
            workflow,
            ("workflow_id", "revision", "attempt_id", "root_actor"),
        ),
        "adapter": _copy_fields(
            adapter,
            ("family", "adapter_id", "adapter_version", "tool_contract_digest"),
        ),
        "authorization": _copy_fields(
            authorization,
            (
                "scope_id",
                "decision_ref",
                "exact_action",
                "canonical_target_ids",
                "set_proof_ref",
            ),
        ),
        "evidence": linked,
        "targets": [_sanitize_target(target) for target in targets],
        "reconciliation": normalized_sets,
        "repair": _copy_fields(repair, ("allowed", "forbidden", "attempts")),
        "retention": _copy_fields(
            retention,
            (
                "policy_id",
                "retained",
                "raw_payload",
                "evidence_locator_expiry",
                "manifest_expiry",
                "redaction_proof_ref",
            ),
        ),
        "replay_prohibited": replay_prohibited,
        "terminal": {"status": status, "reason_code": reason_code},
    }
    if isinstance(zero_proof, dict):
        normalized["zero_mutation_proof"] = _copy_fields(
            zero_proof,
            ("kind", "transport_proof_ref", "candidate_ids", "exclusions"),
        )
    return normalized, status


def _blocked_result(
    reasons: list[str],
    retained_evidence: list[str],
    observed_effects: list[str],
    stopped_workers: list[str],
    revision: object = None,
) -> dict:
    preflight = {
        "revision": revision,
        "status": "block",
        "reasons": reasons,
        "interactivity": {"verdict": "unknown", "evidence": []},
        "authority": {"verdict": "unknown", "evidence": []},
        "selected_topology": "L0",
    }
    return {
        "authority_preflight": preflight,
        "selected_topology": "L0",
        "execution_permission": {
            "root_mutation": False,
            "delegated_work": False,
            "delegated_mutation": False,
            "stopped_workers": stopped_workers,
        },
        "retained_evidence": retained_evidence,
        "observed_effects": observed_effects,
        "workflow_state": {"state": "blocked", "final": True},
    }


def evaluate_root_workflow(metadata: object, events: object = ()) -> dict:
    """Evaluate authority admission without performing or accepting any work."""
    if not isinstance(metadata, dict):
        return _blocked_result(
            ["malformed_workflow_metadata"], [], [], [], revision=None
        )

    retained_evidence: list[str] = []
    observed_effects: list[str] = []
    effects_valid = _retain(observed_effects, metadata.get("observed_effects", []))
    preflight = metadata.get("authority_preflight")
    if preflight is None:
        return _blocked_result(
            ["missing_authority_preflight"],
            retained_evidence,
            observed_effects,
            [],
            revision=metadata.get("revision"),
        )
    if not isinstance(preflight, dict):
        return _blocked_result(
            ["malformed_authority_preflight"],
            retained_evidence,
            observed_effects,
            [],
            revision=metadata.get("revision"),
        )

    reasons: list[str] = []
    revision = preflight.get("revision")
    preflight_revision = revision
    if not isinstance(revision, int) or isinstance(revision, bool):
        reasons.append("malformed_authority_preflight_revision")
    elif revision != metadata.get("revision"):
        reasons.append("stale_authority_preflight")

    decision_loops = preflight.get("reachable_decision_loops")
    if not _string_list(decision_loops):
        reasons.append("malformed_decision_loop_evidence")
        decision_loops = []
    else:
        decision_loops = list(decision_loops)

    mutations = preflight.get("reachable_mutations")
    mutation_owners: dict[str, set[str]] = {}
    if not isinstance(mutations, list):
        reasons.append("malformed_mutation_evidence")
        mutations = []
    else:
        mutations = list(mutations)
        for mutation in mutations:
            if (
                not isinstance(mutation, dict)
                or not isinstance(mutation.get("identity"), str)
                or not mutation["identity"]
                or not isinstance(mutation.get("owner"), str)
                or not mutation["owner"]
            ):
                reasons.append("malformed_mutation_evidence")
                continue
            mutation_owners.setdefault(mutation["identity"], set()).add(
                mutation["owner"]
            )
        if any(len(owners) > 1 for owners in mutation_owners.values()):
            reasons.append("ambiguous_mutation_owner")
        if any(owner != "root" for owners in mutation_owners.values() for owner in owners):
            reasons.append("worker_owns_durable_mutation")

    workers = preflight.get("workers")
    if not isinstance(workers, list):
        reasons.append("malformed_worker_evidence")
        workers = []
    else:
        workers = list(workers)
        roles = []
        for worker in workers:
            reasons.extend(_worker_reasons(worker))
            if isinstance(worker, dict) and isinstance(worker.get("role"), str):
                roles.append(worker["role"])
        if len(roles) != len(set(roles)):
            reasons.append("ambiguous_worker_role")

    trigger_state = preflight.get("generic_trigger_state")
    if not isinstance(trigger_state, dict) or any(
        not isinstance(trigger, str)
        or not trigger
        or not isinstance(state, str)
        or state not in _TRIGGER_STATES
        for trigger, state in (
            trigger_state.items() if isinstance(trigger_state, dict) else ()
        )
    ):
        reasons.append("malformed_generic_trigger_state")
        trigger_state = {}
    else:
        trigger_state = dict(trigger_state)

    generic_topology = preflight.get("generic_topology")
    if not isinstance(generic_topology, str) or generic_topology not in _TOPOLOGIES:
        reasons.append("malformed_generic_topology")
        generic_topology = "L0"
    elif generic_topology != "L0" and not workers:
        reasons.append("unproved_worker_confinement")

    if not _retain(retained_evidence, preflight.get("evidence")):
        reasons.append("malformed_authority_evidence")
    if not effects_valid:
        reasons.append("malformed_observed_effects")

    if not isinstance(events, (list, tuple)):
        reasons.append("malformed_runtime_events")
        events = ()

    runtime_decision = False
    human_decision_required = False
    stopped_workers: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            reasons.append("malformed_runtime_event")
            continue
        if "evidence" in event and not _retain(retained_evidence, event["evidence"]):
            reasons.append("malformed_runtime_evidence")
        if "observed_effects" in event and not _retain(
            observed_effects, event["observed_effects"]
        ):
            reasons.append("malformed_runtime_effects")
        if not isinstance(event.get("type"), str):
            reasons.append("malformed_runtime_event")
            continue

        event_type = event["type"]
        if event_type in _PROCESS_FACTS:
            continue
        if event_type in {"decision_loop_discovered", "human_decision_required"}:
            path = event.get("path")
            if not isinstance(path, str) or not path:
                reasons.append("malformed_runtime_decision")
                continue
            if path not in decision_loops:
                decision_loops.append(path)
            runtime_decision = True
            human_decision_required = (
                human_decision_required or event_type == "human_decision_required"
            )
        elif event_type == "worker_mutation_discovered":
            role = event.get("worker_role")
            if not isinstance(role, str) or not role:
                reasons.append("malformed_worker_mutation_discovery")
                continue
            if role not in stopped_workers:
                stopped_workers.append(role)

            mutation = event.get("mutation")
            if (
                not isinstance(mutation, dict)
                or not isinstance(mutation.get("identity"), str)
                or not mutation["identity"]
                or mutation.get("owner") != "root"
            ):
                reasons.append("worker_mutation_not_root_owned")
            else:
                mutations.append(mutation)

            reproved_worker = event.get("worker_confinement")
            reproof_reasons = _worker_reasons(
                reproved_worker, "worker_confinement_reproof"
            )
            if (
                isinstance(reproved_worker, dict)
                and reproved_worker.get("role") != role
            ):
                reproof_reasons.append("worker_confinement_reproof_role_mismatch")
            event_revision = event.get("revision")
            if (
                not isinstance(event_revision, int)
                or isinstance(event_revision, bool)
                or not isinstance(preflight_revision, int)
                or isinstance(preflight_revision, bool)
                or event_revision <= preflight_revision
            ):
                reproof_reasons.append("stale_worker_confinement_reproof")
            if reproof_reasons:
                reasons.extend(reproof_reasons)
            else:
                workers = [
                    reproved_worker
                    if isinstance(item, dict) and item.get("role") == role
                    else item
                    for item in workers
                ]
                if not any(
                    isinstance(item, dict) and item.get("role") == role
                    for item in workers
                ):
                    workers.append(reproved_worker)
                revision = max(revision, event_revision)
        else:
            reasons.append("unknown_runtime_event")


    if reasons:
        return _blocked_result(
            list(dict.fromkeys(reasons)),
            retained_evidence,
            observed_effects,
            stopped_workers,
            revision=revision,
        )

    selected_topology = "L0" if decision_loops else generic_topology
    status = "runtime_replan" if runtime_decision else "allow_generation"
    authority_preflight = {
        "revision": revision,
        "status": status,
        "reasons": [],
        "interactivity": {
            "verdict": "interactive" if decision_loops else "non_interactive",
            "evidence": decision_loops,
        },
        "authority": {
            "verdict": "authority_bearing" if mutations else "read_only",
            "evidence": [
                mutation["identity"]
                for mutation in mutations
                if isinstance(mutation, dict) and "identity" in mutation
            ],
        },
        "reachable_mutations": mutations,
        "workers": workers,
        "generic_trigger_state": trigger_state,
        "selected_topology": selected_topology,
    }
    if runtime_decision:
        authority_preflight["required_action"] = "root_l0_plan"

    may_execute = not runtime_decision and not human_decision_required
    result = {
        "authority_preflight": authority_preflight,
        "selected_topology": selected_topology,
        "execution_permission": {
            "root_mutation": may_execute and bool(mutations),
            "delegated_work": may_execute and selected_topology != "L0",
            "delegated_mutation": False,
            "stopped_workers": stopped_workers,
        },
        "retained_evidence": retained_evidence,
        "observed_effects": observed_effects,
        "workflow_state": {
            "state": "human_decision_required"
            if human_decision_required
            else "continue",
            "final": False,
        },
    }
    if "acceptance_manifest" in metadata and may_execute:
        manifest, terminal = _evaluate_acceptance_manifest(
            metadata["acceptance_manifest"], metadata.get("revision")
        )
        result["acceptance_manifest"] = manifest
        result["workflow_state"] = {"state": terminal, "final": True}
        result["execution_permission"] = {
            "root_mutation": False,
            "delegated_work": False,
            "delegated_mutation": False,
            "stopped_workers": stopped_workers,
        }
    return result
