"""Deterministic root-owned authority admission for sanitized workflow facts."""

from __future__ import annotations

import re


_TOPOLOGIES = {"L0", "L1", "L2", "L3", "L4"}
_TRIGGER_STATES = {"fired", "not_fired", "not_evaluated", "not_applicable"}
_PROCESS_FACTS = {"process_exit", "generated_output", "attempt_pass"}

# Maximum self-reported forensics cap in characters; must match the JS harness constant.
_FORENSIC_RESULT_CAP = 2000

# Truncation suffix produced by the JS harness: " … [truncated N chars]".
_FORENSIC_TRUNCATION_SUFFIX_RE = re.compile(r"^ … \[truncated (\d+) chars\]$")

_CLASSIFICATION_RESULTS = {"protected", "unprotected", "uncertain"}
_PROTECTED_CATEGORIES = {
    "security_account_control",
    "identity_official_status",
    "financial_assets_obligations",
    "legal_rights_obligations",
    "health_medical_care",
    "physical_safety_emergency",
    "privacy_consent_data_control",
    "high_impact_eligibility_essential_services",
}


def _blocked_admission(
    mutation_id: object,
    gate: str,
    reasons: list[str],
    blocked_items: list[str] | None = None,
    proof: object = None,
) -> dict:
    blocked_items = blocked_items or []
    gate_order = ["transport", "classification", "authorization", "mutation"]
    result = {
        "mutation_id": mutation_id,
        "status": "blocked",
        "evaluated_gates": gate_order[: gate_order.index(gate) + 1],
        "allowed_items": [],
        "blocked_items": blocked_items,
        "reasons": list(reasons),
    }
    if gate != "transport":
        return result

    attempts = proof.get("recovery_attempts", []) if isinstance(proof, dict) else []
    signals = proof.get("signals", []) if isinstance(proof, dict) else []
    if not isinstance(signals, list):
        signals = []
    supplied = proof.get("forensics") if isinstance(proof, dict) else None
    cap_bytes = supplied.get("cap_bytes") if isinstance(supplied, dict) else None
    last_raw = supplied.get("last_raw") if isinstance(supplied, dict) else None
    fits_cap = False
    if isinstance(last_raw, str) and isinstance(cap_bytes, int) and not isinstance(cap_bytes, bool) and 0 <= cap_bytes <= _FORENSIC_RESULT_CAP:
        last_len = len(last_raw)
        if last_len <= cap_bytes:
            fits_cap = True
        elif cap_bytes > 0:
            prefix = last_raw[:cap_bytes]
            suffix = last_raw[cap_bytes:]
            match = _FORENSIC_TRUNCATION_SUFFIX_RE.match(suffix)
            if match:
                reported_extra = int(match.group(1))
                fits_cap = reported_extra > 0 and last_len == cap_bytes + len(suffix) and len(prefix) == cap_bytes
    forensics_valid = (
        isinstance(supplied, dict)
        and fits_cap
        and _string_list(supplied.get("completed_evidence"))
        and _string_list(supplied.get("live_handles"))
        and supplied.get("failed_scope") == blocked_items
        and supplied.get("signals") == signals
    )
    if forensics_valid:
        forensics = supplied
    else:
        forensics = {
            "cap_bytes": 0,
            "last_raw": "",
            "completed_evidence": [],
            "live_handles": [],
            "failed_scope": blocked_items,
            "signals": signals,
        }
        result["reasons"] = list(dict.fromkeys([*result["reasons"], "forensics_incomplete"]))

    capability = proof.get("capability") if isinstance(proof, dict) else None
    if not isinstance(capability, str) or not capability:
        capability = "transport"
    scope = ", ".join(blocked_items) or "the fixed mutation scope"
    unblock = proof.get("unblock_condition") if isinstance(proof, dict) else None
    result.update(
        {
            "recovery_attempts": attempts if isinstance(attempts, list) else [],
            "forensics": forensics,
            "unblock_condition": (
                unblock
                if isinstance(unblock, str) and unblock
                else f"Obtain a {capability} terminal witness for {scope}."
            ),
        }
    )
    return result


def _gap_free_ranges(total: object, ranges: object) -> bool:
    if (
        not isinstance(total, int)
        or isinstance(total, bool)
        or total < 0
        or not isinstance(ranges, list)
    ):
        return False
    covered = 0
    for byte_range in ranges:
        if (
            not isinstance(byte_range, list)
            or len(byte_range) != 2
            or not all(
                isinstance(offset, int) and not isinstance(offset, bool)
                for offset in byte_range
            )
            or byte_range[0] != covered
            or byte_range[1] <= byte_range[0]
        ):
            return False
        covered = byte_range[1]
    return covered == total


def _terminal_complete(
    capability: object,
    terminal: object,
    pages: object,
    returned_ids: list[str],
    target_ids: list[str],
) -> bool:
    if not isinstance(terminal, dict):
        return False
    locator = terminal.get("locator")
    if not isinstance(locator, str) or not locator:
        return False
    if capability == "cursor_page":
        return (
            terminal.get("kind") == "cursor_exhausted"
            and isinstance(pages, list)
            and bool(pages)
            and all(
                isinstance(page, dict)
                and isinstance(page.get("cursor"), str)
                and bool(page["cursor"])
                and (
                    page.get("next_cursor") is None
                    or isinstance(page["next_cursor"], str)
                    and bool(page["next_cursor"])
                )
                and _string_list(page.get("target_ids"))
                for page in pages
            )
            and all(
                pages[index]["cursor"] == pages[index - 1].get("next_cursor")
                for index in range(1, len(pages))
            )
            and returned_ids == target_ids
            and pages[-1].get("next_cursor") is None
        )
    if capability == "bounded_list":
        if returned_ids != target_ids:
            return False
        if terminal.get("kind") == "authoritative_total":
            total = terminal.get("total")
            return (
                isinstance(total, int)
                and not isinstance(total, bool)
                and total == len(set(returned_ids))
            )
        contract = terminal.get("tool_contract")
        count = terminal.get("returned_count")
        limit = terminal.get("page_limit")
        return (
            terminal.get("kind") == "documented_short_page_terminal"
            and isinstance(contract, dict)
            and isinstance(contract.get("reference"), str)
            and bool(contract["reference"])
            and isinstance(contract.get("digest"), str)
            and contract["digest"].startswith("sha256:")
            and contract.get("short_page_rule")
            == "returned_count_lt_page_limit"
            and isinstance(count, int)
            and not isinstance(count, bool)
            and count == len(returned_ids)
            and isinstance(limit, int)
            and not isinstance(limit, bool)
            and count < limit
        )
    if capability == "object_blob":
        positive_boundary = (
            isinstance(terminal.get("complete_marker"), str)
            and bool(terminal["complete_marker"])
            or isinstance(terminal.get("length"), int)
            and not isinstance(terminal["length"], bool)
            and terminal["length"] >= 0
            or isinstance(terminal.get("checksum"), str)
            and bool(terminal["checksum"])
        )
        return (
            len(target_ids) == 1
            and terminal.get("kind") == "complete_content"
            and positive_boundary
        )
    if capability != "range":
        return False

    return (
        len(target_ids) == 1
        and terminal.get("kind") == "gap_free_ranges"
        and _gap_free_ranges(
            terminal.get("total_length"), terminal.get("ranges")
        )
    )


def _recovery_reasons(proof: object) -> list[str]:
    if not isinstance(proof, dict):
        return []
    attempts = proof.get("recovery_attempts")
    if not isinstance(attempts, list):
        return ["malformed_recovery_attempts"]

    reasons = []
    bound = proof.get("recovery_bound")
    if bound is not None and (
        not isinstance(bound, int) or isinstance(bound, bool) or bound < 0
    ):
        reasons.append("malformed_recovery_bound")
    elif isinstance(bound, int) and len(attempts) > bound:
        reasons.append("recovery_bound_exceeded")

    seed = proof.get("recovery_seed")
    seed_valid = (
        isinstance(seed, dict)
        and isinstance(seed.get("request_fingerprint"), str)
        and bool(seed["request_fingerprint"])
        and isinstance(seed.get("completed_units"), int)
        and not isinstance(seed["completed_units"], bool)
        and seed["completed_units"] >= 0
        and isinstance(seed.get("remaining_units"), int)
        and not isinstance(seed["remaining_units"], bool)
        and seed["remaining_units"] >= 0
    )
    if attempts and not seed_valid:
        reasons.append("missing_recovery_seed")

    seen_inputs = {seed["request_fingerprint"]} if seed_valid else set()
    prior_completed = seed["completed_units"] if seed_valid else None
    prior_remaining = seed["remaining_units"] if seed_valid else None
    for index, attempt in enumerate(attempts):
        if (
            not isinstance(attempt, dict)
            or not isinstance(attempt.get("request_fingerprint"), str)
            or not attempt["request_fingerprint"]
            or not isinstance(attempt.get("completed_units"), int)
            or isinstance(attempt["completed_units"], bool)
            or attempt["completed_units"] < 0
            or not isinstance(attempt.get("remaining_units"), int)
            or isinstance(attempt["remaining_units"], bool)
            or attempt["remaining_units"] < 0
        ):
            reasons.append("malformed_recovery_attempt")
            continue
        if attempt["request_fingerprint"] in seen_inputs:
            reasons.append("repeated_incomplete_input")
        seen_inputs.add(attempt["request_fingerprint"])

        if prior_completed is not None and not (
            attempt["completed_units"] > prior_completed
            or attempt["remaining_units"] < prior_remaining
        ):
            reasons.append("recovery_no_progress")
            if index != len(attempts) - 1:
                reasons.append("recovery_after_stop")
        prior_completed = attempt["completed_units"]
        prior_remaining = attempt["remaining_units"]
    return list(dict.fromkeys(reasons))


def _acceptance_path_complete(path: object, targets: list[dict]) -> bool:
    if not isinstance(path, dict):
        return False
    capabilities = []
    for name in (
        "canonical_identity",
        "complete_pre_state",
        "authoritative_receipt",
        "independent_post_state",
    ):
        capability = path.get(name)
        contract = capability.get("tool_contract") if isinstance(capability, dict) else None
        bindings = capability.get("target_bindings") if isinstance(capability, dict) else None
        if (
            not isinstance(contract, dict)
            or not isinstance(contract.get("reference"), str)
            or not contract["reference"]
            or not isinstance(contract.get("digest"), str)
            or not contract["digest"].startswith("sha256:")
            or not isinstance(bindings, list)
            or len(bindings) != len(targets)
            or any(
                not isinstance(binding, dict)
                or {
                    key: binding.get(key)
                    for key in ("identity", "version", "state")
                }
                != target
                or not isinstance(binding.get("locator"), str)
                or not binding["locator"]
                for binding, target in zip(bindings, targets)
            )
            or len({binding["locator"] for binding in bindings}) != len(bindings)
        ):
            return False
        capabilities.append(capability)
    return (
        capabilities[3].get("actor") == "root"
        and all(
            receipt["locator"] != post_state["locator"]
            for receipt, post_state in zip(
                capabilities[2]["target_bindings"],
                capabilities[3]["target_bindings"],
            )
        )
    )


def _field_coverage_complete(
    proof: dict,
    predicate: dict,
    target_ids: list[str],
    required_fields: list[str],
) -> bool:
    content_fields = predicate.get("content_fields")
    coverage = proof.get("field_coverage")
    if (
        not _string_list(content_fields)
        or not set(content_fields) <= set(required_fields)
        or proof.get("content_fields") != content_fields
        or not isinstance(coverage, list)
        or len(coverage) != len(target_ids) * len(required_fields)
    ):
        return False
    expected = {
        (target_id, field)
        for target_id in target_ids
        for field in required_fields
    }
    if not all(
        isinstance(entry, dict)
        and isinstance(entry.get("item_id"), str)
        and bool(entry["item_id"])
        and isinstance(entry.get("field"), str)
        and bool(entry["field"])
        for entry in coverage
    ):
        return False
    actual = {
        (entry.get("item_id"), entry.get("field"))
        for entry in coverage
        if isinstance(entry, dict)
    }
    if actual != expected or len(actual) != len(coverage):
        return False
    return all(
        isinstance(entry.get("locator"), str)
        and bool(entry["locator"])
        and (
            entry.get("kind") == "gap_free_content"
            and _gap_free_ranges(
                entry.get("total_length"), entry.get("ranges")
            )
            if entry["field"] in content_fields
            else entry.get("kind") == "complete_field"
        )
        for entry in coverage
    )


def _aggregate_scope_complete(
    predicate: dict, proof: dict, target_ids: list[str]
) -> bool:
    aggregate_scope = predicate.get("aggregate_scope")
    return (
        isinstance(aggregate_scope, dict)
        and isinstance(aggregate_scope.get("identity"), str)
        and bool(aggregate_scope["identity"])
        and aggregate_scope.get("target_ids") == target_ids
        and isinstance(aggregate_scope.get("requires_complete_set"), bool)
        and proof.get("aggregate_scope") == aggregate_scope
    )


def _transport_gate(
    admission: dict, reachable_mutation_ids: set[str]
) -> tuple[dict | None, dict]:
    mutation_id = admission.get("mutation_id")
    targets = admission.get("targets")
    raw_target_ids = (
        [
            target["identity"]
            for target in targets
            if isinstance(target, dict)
            and isinstance(target.get("identity"), str)
            and target["identity"]
        ]
        if isinstance(targets, list)
        else []
    )
    targets_valid = (
        isinstance(targets, list)
        and bool(targets)
        and len(raw_target_ids) == len(targets)
        and len(raw_target_ids) == len(set(raw_target_ids))
        and all(
            isinstance(target.get("version"), str)
            and target["version"]
            and isinstance(target.get("state"), str)
            and target["state"]
            for target in targets
        )
    )
    target_ids = raw_target_ids if targets_valid else []
    predicate = admission.get("fixed_predicate")
    required_fields = (
        predicate.get("selection_fields", []) + predicate.get("classification_fields", [])
        if isinstance(predicate, dict)
        and isinstance(predicate.get("identity"), str)
        and predicate["identity"]
        and _string_list(predicate.get("selection_fields"))
        and _string_list(predicate.get("classification_fields"))
        else []
    )
    proof = admission.get("transport_proof")
    pages = proof.get("pages") if isinstance(proof, dict) else None
    pages_valid = (
        isinstance(pages, list)
        and bool(pages)
        and all(
            isinstance(page, dict)
            and _string_list(page.get("target_ids"))
            and "next_cursor" in page
            for page in pages
        )
    )
    returned_ids = (
        [target_id for page in pages for target_id in page["target_ids"]]
        if pages_valid
        else []
    )
    signals = proof.get("signals") if isinstance(proof, dict) else None
    transport_complete = (
        isinstance(mutation_id, str)
        and bool(mutation_id)
        and mutation_id in reachable_mutation_ids
        and isinstance(admission.get("action"), str)
        and bool(admission["action"])
        and isinstance(admission.get("target_state"), str)
        and bool(admission["target_state"])
        and targets_valid
        and bool(required_fields)
        and len(required_fields) == len(set(required_fields))
        and _acceptance_path_complete(admission.get("acceptance_path"), targets)
        and isinstance(proof, dict)
        and isinstance(proof.get("proof_id"), str)
        and bool(proof["proof_id"])
        and proof.get("mutation_id") == mutation_id
        and proof.get("action") == admission["action"]
        and proof.get("target_state") == admission["target_state"]
        and proof.get("predicate_identity") == predicate.get("identity")
        and proof.get("target_bindings") == targets
        and proof.get("requested_scope") == target_ids
        and proof.get("returned_scope") == target_ids
        and proof.get("required_fields") == required_fields
        and _field_coverage_complete(
            proof, predicate, target_ids, required_fields
        )
        and _aggregate_scope_complete(predicate, proof, target_ids)
        and _terminal_complete(
            proof.get("capability"),
            proof.get("terminal_witness"),
            pages,
            returned_ids,
            target_ids,
        )
        and isinstance(signals, list)
        and all(
            isinstance(signal, dict)
            and isinstance(signal.get("kind"), str)
            and bool(signal["kind"])
            and isinstance(signal.get("scope"), str)
            and signal["scope"] in {*target_ids, "call"}
            for signal in signals
        )
    )
    recovery_reasons = _recovery_reasons(proof)
    if not transport_complete or recovery_reasons:
        reasons = recovery_reasons[:]
        if not transport_complete:
            reasons.append("transport_incomplete")
        return (
            _blocked_admission(
                mutation_id,
                "transport",
                list(dict.fromkeys(reasons)),
                raw_target_ids,
                proof,
            ),
            {},
        )

    blocked_items = [
        target_id
        for target_id in target_ids
        if any(signal["scope"] in {target_id, "call"} for signal in signals)
    ]
    if (
        predicate["aggregate_scope"]["requires_complete_set"]
        and blocked_items
    ):
        blocked_items = target_ids
    candidate_ids = [
        target_id for target_id in target_ids if target_id not in blocked_items
    ]
    if not candidate_ids:
        return (
            _blocked_admission(
                mutation_id,
                "transport",
                ["transport_incomplete"],
                blocked_items,
                proof,
            ),
            {},
        )
    return (
        None,
        {
            "mutation_id": mutation_id,
            "targets": targets,
            "target_ids": target_ids,
            "predicate": predicate,
            "proof": proof,
            "blocked_items": blocked_items,
            "candidate_ids": candidate_ids,
        },
    )


def _classification_record_complete(record: object) -> bool:
    return (
        isinstance(record, dict)
        and isinstance(record.get("result"), str)
        and record["result"] in _CLASSIFICATION_RESULTS
        and _string_list(record.get("categories"))
        and len(record["categories"]) == len(set(record["categories"]))
        and set(record["categories"]) <= _PROTECTED_CATEGORIES
        and _string_list(record.get("evidence"))
        and bool(record["evidence"])
        and _string_list(record.get("deterministic_markers"))
        and _string_list(record.get("uncertainty"))
        and _string_list(record.get("expiry"))
        and not (
            record["result"] == "unprotected"
            and (
                record["categories"]
                or record["deterministic_markers"]
                or record["uncertainty"]
                or record["expiry"]
            )
        )
        and not (record["result"] == "protected" and not record["categories"])
        and not (record["result"] == "uncertain" and not record["uncertainty"])
    )


def _expected_classification_binding(
    admission: dict, context: dict, target: dict | None = None
) -> dict:
    binding = {
        "transport_proof_id": context["proof"]["proof_id"],
        "mutation_id": context["mutation_id"],
        "action": admission["action"],
        "target_state": admission["target_state"],
        "predicate_identity": context["predicate"]["identity"],
        "required_fields": context["proof"]["required_fields"],
        "content_fields": context["predicate"]["content_fields"],
        "aggregate_scope": context["predicate"]["aggregate_scope"],
        "target_bindings": context["targets"],
    }
    if target is not None:
        binding["target_binding"] = target
    return binding


def _classification_gate(
    admission: dict, context: dict
) -> tuple[dict | None, dict]:
    security = admission.get("security_gate")
    item_records = (
        security.get("item_classifications") if isinstance(security, dict) else None
    )
    action_record = (
        security.get("action_classification") if isinstance(security, dict) else None
    )
    binding = security.get("binding") if isinstance(security, dict) else None
    binding_complete = binding == _expected_classification_binding(
        admission, context
    )
    records_complete = (
        isinstance(item_records, list)
        and len(item_records) == len(context["target_ids"])
        and [
            item.get("item_id") for item in item_records if isinstance(item, dict)
        ]
        == context["target_ids"]
        and all(
            _classification_record_complete(item)
            and item.get("input_binding")
            == _expected_classification_binding(admission, context, target)
            for item, target in zip(item_records, context["targets"])
        )
        and _classification_record_complete(action_record)
        and action_record.get("input_binding")
        == _expected_classification_binding(admission, context)
    )
    if not (
        isinstance(security, dict)
        and security.get("transport_proof_id") == context["proof"].get("proof_id")
        and binding_complete
        and records_complete
    ):
        return (
            _blocked_admission(
                context["mutation_id"],
                "classification",
                ["classification_incomplete"],
                context["target_ids"],
            ),
            {},
        )
    if context["blocked_items"] and not _partitionable(security):
        return (
            _blocked_admission(
                context["mutation_id"],
                "classification",
                ["partition_not_proved"],
                context["target_ids"],
            ),
            {},
        )
    return (
        None,
        {
            "security": security,
            "item_records": item_records,
            "action_record": action_record,
        },
    )


def _partitionable(security: dict) -> bool:
    return (
        security.get("item_level_execution") is True
        and security.get("uncoupled") is True
    )


def _authorization_gate(
    admission: dict, context: dict, classification: dict, queue_revision: object
) -> dict:
    item_records = classification["item_records"]
    action_record = classification["action_record"]
    protected_items = [
        item["item_id"]
        for item in item_records
        if item["item_id"] in context["candidate_ids"]
        and item["result"] != "unprotected"
    ]
    if action_record["result"] != "unprotected":
        protected_items = context["candidate_ids"]

    authorization = classification["security"].get("authorization")
    decision = (
        authorization.get("normalized_decision")
        if isinstance(authorization, dict)
        else None
    )
    parent_receipt = (
        authorization.get("parent_receipt")
        if isinstance(authorization, dict)
        else None
    )
    current_revision = (
        isinstance(queue_revision, int) and not isinstance(queue_revision, bool)
    )
    authorization_valid = (
        isinstance(authorization, dict)
        and isinstance(authorization.get("receipt_id"), str)
        and bool(authorization["receipt_id"])
        and isinstance(authorization.get("decision_identity"), str)
        and bool(authorization["decision_identity"])
        and isinstance(parent_receipt, dict)
        and isinstance(parent_receipt.get("reference"), str)
        and bool(parent_receipt["reference"])
        and parent_receipt.get("validator") == "root_parent"
        and parent_receipt.get("validated_decision_identity")
        == authorization["decision_identity"]
        and isinstance(decision, dict)
        and decision.get("identity") == authorization["decision_identity"]
        and decision.get("choice") == "authorize_exact_mutation"
        and current_revision
        and decision.get("queue_revision") == queue_revision
        and decision.get("mutation_id") == context["mutation_id"]
        and decision.get("action") == admission.get("action")
        and decision.get("target_state") == admission.get("target_state")
        and _string_list(decision.get("item_ids"))
        and bool(decision["item_ids"])
        and len(decision["item_ids"]) == len(set(decision["item_ids"]))
        and set(decision["item_ids"]) <= set(context["target_ids"])
    )
    authorized_items = set(decision["item_ids"]) if authorization_valid else set()
    authorization_blocked = [
        target_id
        for target_id in protected_items
        if target_id not in authorized_items
    ]
    if authorization is not None and not authorization_valid:
        authorization_blocked = context["candidate_ids"]

    blocked_items = [
        target_id
        for target_id in context["target_ids"]
        if target_id in context["blocked_items"]
        or target_id in authorization_blocked
    ]
    allowed_items = [
        target_id
        for target_id in context["candidate_ids"]
        if target_id not in blocked_items
    ]
    if (
        blocked_items
        and isinstance(context.get("predicate"), dict)
        and isinstance(context["predicate"].get("aggregate_scope"), dict)
        and context["predicate"]["aggregate_scope"].get("requires_complete_set") is True
    ):
        blocked_items = context["target_ids"]
        allowed_items = []
    if blocked_items and (
        not allowed_items or not _partitionable(classification["security"])
    ):
        return _blocked_admission(
            context["mutation_id"],
            "authorization",
            ["exact_authorization_required"],
            context["target_ids"],
        )
    return {
        "mutation_id": context["mutation_id"],
        "status": "allow",
        "evaluated_gates": [
            "transport",
            "classification",
            "authorization",
            "mutation",
        ],
        "allowed_items": allowed_items,
        "blocked_items": blocked_items,
        "reasons": [],
    }


def _evaluate_mutation_admission(
    admission: object,
    queue_revision: object,
    reachable_mutation_ids: set[str],
) -> dict | None:
    if admission is None:
        return None
    if not isinstance(admission, dict):
        return _blocked_admission(
            None, "transport", ["malformed_mutation_admission"]
        )

    blocked, context = _transport_gate(admission, reachable_mutation_ids)
    if blocked:
        return blocked
    blocked, classification = _classification_gate(admission, context)
    if blocked:
        return blocked
    return _authorization_gate(admission, context, classification, queue_revision)


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

_MAX_TARGET_NESTING_DEPTH = 100

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
_REPAIR_ALLOWED = {
    "narrow_read",
    "continue_complete_cursor_or_range",
    "authoritative_alias_lookup",
    "normalize_and_reconcile",
}
_MUTATING_REPAIR = {
    "mutation_retry",
    "corrective_mutation",
    "expanded_authority",
    "undo",
    "compensate",
}
_FAMILY_MATRIX = {
    "record_state": {
        "action": "set_state",
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
        "action": "add_edge",
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
        "action": "append",
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
        "action": "soft_delete",
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
        "action": "replace_content",
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
        "action": "run_operation",
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
_EVIDENCE_FIELDS = [
    "kind",
    "owner",
    "authoritative",
    "alias",
    "canonical_target_ids",
    "mutation_id",
    "target_ids",
    "aggregate_scope",
    "fixed_predicate",
    "required_fields",
    "capability",
    "read_locator",
    "requested_scope",
    "returned_scope",
    "relevant_versions",
    "signals",
    "recovery_attempts",
    "no_progress_stop",
    "outcome",
    "target_id",
    "transport_ref",
    "action",
    "status",
    "item_id",
    "batch_id",
    "target_state",
    "transport_proof_ref",
    "item_axis",
    "action_axis",
    "categories",
    "deterministic_markers",
    "evidence_locators",
    "classification_reasons",
    "uncertainty",
    "authorization_ref",
    "authorization_scope_id",
    "authorization_current",
    "client_mutation_key",
    "result_resource_id",
    "request_id",
    "scope_before",
    "scope_after",
    "progress",
    "coverage_before",
    "coverage_after",
    "eligible",
    "reason_code",
    "pre_ref",
]
for _family_row in _FAMILY_MATRIX.values():
    _EVIDENCE_FIELDS.extend(_family_row["pre"])
    _EVIDENCE_FIELDS.extend(_family_row["receipt"])
    _EVIDENCE_FIELDS.extend(_family_row["post"])
_EVIDENCE_FIELDS = list(dict.fromkeys(_EVIDENCE_FIELDS))


def _present_field(record: object, field: str) -> bool:
    if not isinstance(record, dict) or field not in record:
        return False
    value = record[field]
    if value is None:
        return False
    if isinstance(value, bool):
        return value is True
    if isinstance(value, (str, list, dict, tuple, set)):
        if field == "ranges":
            return True
        return bool(value)
    if field == "length":
        return True
    return bool(value)


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
    expected_mutation: object = None,
    expected_scope: object = None,
    expected_predicate: object = None,
) -> bool:
    record = records.get(ref) if isinstance(ref, str) else None
    if (
        ref not in linked["transport_proofs"]
        or not isinstance(record, dict)
        or record.get("kind") != "transport_proof"
        or record.get("outcome") != "complete"
        or not _present_field(record, "mutation_id")
        or (
            expected_mutation is not None
            and record.get("mutation_id") != expected_mutation
        )
        or not _valid_string_set(expected_targets)
        or not _valid_string_set(record.get("target_ids"))
        or set(record["target_ids"]) != set(expected_targets)
        or not _present_field(record, "aggregate_scope")
        or not _present_field(record, "fixed_predicate")
        or (
            expected_scope is not None
            and record.get("aggregate_scope") != expected_scope
        )
        or not _valid_string_set(record.get("required_fields"))
        or (
            expected_predicate is not None
            and record.get("fixed_predicate") != expected_predicate
        )
        or not record["required_fields"]
        or not _present_field(record, "read_locator")
        or not _valid_string_set(record.get("requested_scope"))
        or set(record["requested_scope"]) != set(expected_targets)
        or not _valid_string_set(record.get("returned_scope"))
        or set(record["returned_scope"]) != set(expected_targets)
        or not isinstance(record.get("relevant_versions"), dict)
        or record.get("signals") != []
        or not isinstance(record.get("recovery_attempts"), list)
        or not _present_field(record, "no_progress_stop")
    ):
        return False

    witness = record.get("witness")
    capability = record.get("capability")
    if capability == "bounded_list":
        if not isinstance(witness, dict):
            return False
        unique_count = witness.get("unique_count")
        return (
            isinstance(witness.get("authoritative_total"), int)
            and not isinstance(witness["authoritative_total"], bool)
            and witness["authoritative_total"] == len(record["target_ids"])
            and isinstance(unique_count, int)
            and not isinstance(unique_count, bool)
            and unique_count == len(record["target_ids"])
        )
    if capability == "cursor_page":
        return isinstance(witness, dict) and _present_field(
            witness, "terminal_condition"
        )
    if capability == "single_object_blob":
        return (
            len(record["target_ids"]) == 1
            and isinstance(witness, dict)
            and isinstance(witness.get("kind"), str)
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

def _security_gate_allows(
    security: object,
    target_id: object,
    mutation_id: object,
    action: object,
    pre_transport_ref: object,
    decision_ref: object,
    scope_id: object,
) -> bool:
    if not isinstance(security, dict):
        return False
    item_axis = security.get("item_axis")
    action_axis = security.get("action_axis")
    categories = security.get("categories")
    partitions = security.get("partition_sets")
    expiry = security.get("expiry")
    return (
        security.get("kind") == "security_gate"
        and security.get("owner") == "root"
        and security.get("authoritative") is True
        and security.get("verdict") == "allow"
        and all(
            _present_field(security, field)
            for field in ("item_id", "batch_id", "target_state")
        )
        and security.get("target_id") == target_id
        and security.get("mutation_id") == mutation_id
        and security.get("action") == action
        and security.get("transport_proof_ref") == pre_transport_ref
        and isinstance(item_axis, str)
        and item_axis in _CLASSIFICATION_RESULTS
        and isinstance(action_axis, str)
        and action_axis in _CLASSIFICATION_RESULTS
        and item_axis != "uncertain"
        and action_axis != "uncertain"
        and _valid_string_set(categories)
        and set(categories).issubset(_PROTECTED_CATEGORIES)
        and (
            (item_axis == action_axis == "unprotected" and not categories)
            or (
                "protected" in {item_axis, action_axis}
                and bool(categories)
            )
        )
        and _valid_string_set(security.get("deterministic_markers"))
        and _valid_string_set(security.get("evidence_locators"))
        and bool(security["evidence_locators"])
        and _valid_string_set(security.get("classification_reasons"))
        and bool(security["classification_reasons"])
        and security.get("uncertainty") is False
        and isinstance(expiry, dict)
        and expiry.get("expired") is False
        and expiry.get("classification_preserved") is True
        and expiry.get("material_usable") is True
        and security.get("authorization_current") is True
        and security.get("authorization_ref") == decision_ref
        and security.get("authorization_scope_id") == scope_id
        and isinstance(partitions, dict)
        and _valid_string_set(partitions.get("allowed"))
        and partitions["allowed"] == [target_id]
        and partitions.get("blocked") == []
    )


def _repair_valid(
    repair: object, linked: dict[str, list[str]], records: dict
) -> bool:
    if not isinstance(repair, dict):
        return False
    allowed = repair.get("allowed")
    forbidden = repair.get("forbidden")
    attempts = repair.get("attempts")
    if (
        not _valid_string_set(allowed)
        or not set(allowed).issubset(_REPAIR_ALLOWED)
        or set(allowed) & _MUTATING_REPAIR
        or not _valid_string_set(forbidden)
        or not {"mutation_retry", "corrective_mutation"}.issubset(forbidden)
        or not isinstance(attempts, list)
    ):
        return False
    request_ids = set()
    requests = set()
    evidence_refs = set()
    previous_coverage = None
    for attempt in attempts:
        coverage_before = (
            attempt.get("coverage_before") if isinstance(attempt, dict) else None
        )
        coverage_after = (
            attempt.get("coverage_after") if isinstance(attempt, dict) else None
        )
        request_id = attempt.get("request_id") if isinstance(attempt, dict) else None
        evidence_ref = (
            attempt.get("evidence_ref") if isinstance(attempt, dict) else None
        )
        if (
            not isinstance(attempt, dict)
            or attempt.get("action") not in allowed
            or not _valid_string_set(attempt.get("scope_before"))
            or not _valid_string_set(attempt.get("scope_after"))
            or not isinstance(request_id, str)
            or not request_id
            or request_id in request_ids
            or not isinstance(evidence_ref, str)
            or not any(evidence_ref in refs for refs in linked.values())
            or not isinstance(records.get(evidence_ref), dict)
            or records[evidence_ref].get("owner") != "root"
            or not (
                records[evidence_ref].get("authoritative") is True
                or records[evidence_ref].get("kind") == "transport_proof"
            )
            or not evidence_ref
            or evidence_ref in evidence_refs
            or not isinstance(coverage_before, int)
            or isinstance(coverage_before, bool)
            or not isinstance(coverage_after, int)
            or isinstance(coverage_after, bool)
            or coverage_before < 0
            or coverage_after <= coverage_before
            or records[evidence_ref].get("request_id") != request_id
            or records[evidence_ref].get("action") != attempt.get("action")
            or records[evidence_ref].get("scope_before")
            != attempt.get("scope_before")
            or records[evidence_ref].get("scope_after") != attempt.get("scope_after")
            or records[evidence_ref].get("progress") != attempt.get("progress")
            or records[evidence_ref].get("coverage_before") != coverage_before
            or records[evidence_ref].get("coverage_after") != coverage_after
            or (
                previous_coverage is not None
                and coverage_before != previous_coverage
            )
        ):
            return False
        before = set(attempt["scope_before"])
        after = set(attempt["scope_after"])
        request = (attempt["action"], tuple(attempt["scope_after"]))
        if request in requests:
            return False
        if attempt.get("progress") == "scope_narrowed":
            if not after < before:
                return False
        elif attempt.get("progress") == "coverage_advanced":
            if not after.issubset(before):
                return False
        else:
            return False
        request_ids.add(request_id)
        requests.add(request)
        evidence_refs.add(evidence_ref)
        previous_coverage = coverage_after
    return True


def _sanitize_attempts(attempts: object) -> list[dict]:
    if not isinstance(attempts, list):
        return []
    return [
        {
            field: attempt[field]
            for field in (
                "action",
                "scope_before",
                "scope_after",
                "progress",
                "evidence_ref",
                "request_id",
                "coverage_before",
                "coverage_after",
            )
            if isinstance(attempt, dict) and field in attempt
        }
        for attempt in attempts
        if isinstance(attempt, dict)
    ]


def _sanitize_evidence_summaries(
    records: dict, linked: dict[str, list[str]]
) -> dict[str, dict]:
    refs = []
    for category_refs in linked.values():
        for ref in category_refs:
            if ref not in refs:
                refs.append(ref)
    summaries = {}
    for ref in refs:
        record = records.get(ref)
        if not isinstance(record, dict):
            continue
        summary = {
            field: record[field]
            for field in _EVIDENCE_FIELDS
            if field in record
        }
        witness = record.get("witness")
        if isinstance(witness, dict):
            summary["witness"] = _copy_fields(
                witness,
                (
                    "kind",
                    "value",
                    "authoritative_total",
                    "unique_count",
                    "terminal_condition",
                ),
            )
        expiry = record.get("expiry")
        if isinstance(expiry, dict):
            summary["expiry"] = _copy_fields(
                expiry,
                ("expired", "classification_preserved", "material_usable"),
            )
        partitions = record.get("partition_sets")
        if isinstance(partitions, dict):
            summary["partition_sets"] = _copy_fields(
                partitions, ("allowed", "blocked")
            )
        if "recovery_attempts" in summary:
            summary["recovery_attempts"] = _sanitize_attempts(
                summary["recovery_attempts"]
            )
        summaries[ref] = summary
    return summaries


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
    decision_ref: object,
    scope_id: object,
    tool_contract_digest: object,
    linked: dict[str, list[str]],
    records: dict,
    sets: dict[str, list[str]],
    authorized_mutation_id: object = None,
    depth: int = 0,
) -> tuple[str, bool, bool, bool, list[str], list[str]]:
    if depth > _MAX_TARGET_NESTING_DEPTH:
        return "failed", False, False, False, ["excessive_target_nesting"], []
    if (
        not isinstance(target, dict)
        or not isinstance(family, str)
        or family not in _FAMILY_MATRIX
    ):
        return "failed", False, False, False, ["malformed_target"], []

    row = _FAMILY_MATRIX[family]
    target_id = target.get("canonical_target_id")
    action_started = _target_action_started(
        target, target_id, linked, records, sets
    )
    expected_action = exact_action if isinstance(exact_action, str) else row.get("action")
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
    intent_mutation = intent.get("mutation_id") if isinstance(intent, dict) else None
    action = intent.get("action") if isinstance(intent, dict) else None
    if (
        not isinstance(intent, dict)
        or not isinstance(intent_mutation, str)
        or not intent_mutation
        or (
            isinstance(authorized_mutation_id, str)
            and intent_mutation != authorized_mutation_id
        )
        or not isinstance(action, str)
        or not action
        or action != expected_action
    ):
        pre_issues.append("malformed_exact_intent")
    expected_mutation = (
        authorized_mutation_id
        if isinstance(authorized_mutation_id, str)
        else intent_mutation
    )

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
            pre_transport_ref,
            [target_id],
            linked,
            records,
            expected_mutation=expected_mutation,
        )
    )
    pre_transport = (
        records.get(pre_transport_ref)
        if isinstance(pre_transport_ref, str)
        else None
    )
    if (
        isinstance(pre_transport, dict)
        and _string_list(pre_transport.get("required_fields"))
        and not {"canonical_target_id", *row["pre"]}.issubset(
            pre_transport["required_fields"]
        )
    ):
        pre_valid = False
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
        or not _security_gate_allows(
            security,
            target_id,
            expected_mutation,
            action,
            pre_transport_ref,
            decision_ref,
            scope_id,
        )
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
        or receipt.get("mutation_id") != expected_mutation
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
        and post_transport_ref != pre_transport_ref
        and _transport_complete(
            post_transport_ref,
            [target_id],
            linked,
            records,
            expected_mutation=expected_mutation,
        )
    )
    post_transport = (
        records.get(post_transport_ref)
        if isinstance(post_transport_ref, str)
        else None
    )
    if (
        isinstance(post_transport, dict)
        and _string_list(post_transport.get("required_fields"))
        and not {"canonical_target_id", *row["post"]}.issubset(
            post_transport["required_fields"]
        )
    ):
        post_verified = False
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
        and isinstance(ordering_kind, str)
        and ordering_kind in _ORDERING_KINDS
        and (ordering_kind == expected_kind or timestamp_is_bound)
    )
    if not ordering_is_admissible:
        failures.append("inadmissible_ordering")
    else:
        pre_order_values = tuple(
            value
            for (source, _), value in zip(order_sources, expected_values)
            if source == "pre"
        )
        post_order_values = tuple(
            value
            for (source, _), value in zip(order_sources, expected_values)
            if source == "post"
        )
        if (
            pre_order_values
            and post_order_values
            and pre_order_values == post_order_values
        ):
            failures.append("ordering_process_no_advancement")
        elif ordering.get("values") != expected_values:
            if pre_valid and receipt_core and post_verified:
                failures.append("ordering_process_violation")
            else:
                post_issues.append("unresolved_ordering")

    if family == "create_append":
        key_state = pre.get("key_state") if isinstance(pre, dict) else None
        if not isinstance(key_state, str) or key_state not in {
            "unused",
            "preallocated",
        }:
            pre_issues.append("replayed_create_identity")
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
        elif not all(
            isinstance(value, str) and bool(value)
            for value in (
                pre.get("client_mutation_key"),
                receipt.get("result_resource_id"),
                binding.get("client_mutation_key"),
                binding.get("result_resource_id"),
            )
        ):
            failures.append("malformed_create_identity_binding")
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
        elif not isinstance(witness, str) or witness not in {
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
            leaf_family = leaf.get("family") if isinstance(leaf, dict) else None
            leaf_action = (
                _FAMILY_MATRIX[leaf_family].get("action")
                if isinstance(leaf_family, str) and leaf_family in _FAMILY_MATRIX
                else None
            )
            leaf_result = _evaluate_target(
                leaf,
                leaf_family,
                leaf_action,
                decision_ref,
                scope_id,
                tool_contract_digest,
                linked,
                records,
                leaf_sets,
                authorized_mutation_id=expected_mutation,
                depth=depth + 1,
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
        list(dict.fromkeys(d for d in duplicates if isinstance(d, str))),
    )

def _zero_mutation_proved(
    manifest: dict,
    sets: dict[str, list[str]],
    linked: dict[str, list[str]],
    records: dict,
    expected_mutation: object,
    expected_scope: object,
    expected_predicate: object,
) -> bool:
    proof = manifest.get("zero_mutation_proof")
    skipped_set = set(sets["skipped"])
    if (
        not isinstance(proof, dict)
        or not _valid_string_set(proof.get("candidate_ids"))
        or set(proof["candidate_ids"]) != skipped_set
        or not skipped_set.issubset(set(sets["inspected"]))
        or not skipped_set.isdisjoint(
            set(sets["intended"]) | set(sets["attempted"])
        )
        or not _transport_complete(
            proof.get("transport_proof_ref"),
            proof["candidate_ids"],
            linked,
            records,
            expected_mutation=expected_mutation,
            expected_scope=expected_scope,
            expected_predicate=expected_predicate,
        )
    ):
        return False
    if proof.get("kind") == "complete_empty_set":
        return (
            not proof["candidate_ids"]
            and not sets["skipped"]
            and not sets["attempted"]
            and not linked["actions"]
        )
    if proof.get("kind") != "complete_exclusions":
        return False

    exclusions = proof.get("exclusions")
    if (
        not isinstance(exclusions, dict)
        or set(exclusions) != set(proof["candidate_ids"])
        or set(sets["skipped"]) != set(proof["candidate_ids"])
    ):
        return False
    for target_id, exclusion in exclusions.items():
        if not isinstance(exclusion, dict):
            return False
        pre_ref = exclusion.get("pre_ref")
        predicate_ref = exclusion.get("predicate_evidence_ref")
        pre = records.get(pre_ref) if isinstance(pre_ref, str) else None
        predicate = (
            records.get(predicate_ref) if isinstance(predicate_ref, str) else None
        )
        transport_ref = pre.get("transport_ref") if isinstance(pre, dict) else None
        transport = (
            records.get(transport_ref) if isinstance(transport_ref, str) else None
        )
        if (
            not _present_field(exclusion, "reason_code")
            or not _present_field(predicate, "reason_code")
            or pre_ref not in linked["pre"]
            or predicate_ref not in linked["pre"]
            or not isinstance(pre, dict)
            or pre.get("kind") != "pre_state"
            or pre.get("owner") != "root"
            or pre.get("authoritative") is not True
            or pre.get("target_id") != target_id
            or not _transport_complete(
                transport_ref,
                [target_id],
                linked,
                records,
                expected_mutation=expected_mutation,
            )
            or not isinstance(predicate, dict)
            or predicate.get("kind") != "exclusion"
            or predicate.get("owner") != "root"
            or predicate.get("authoritative") is not True
            or predicate.get("target_id") != target_id
            or predicate.get("eligible") is not False
            or predicate.get("pre_ref") != pre_ref
            or predicate.get("reason_code") != exclusion.get("reason_code")
            or predicate.get("fixed_predicate")
            != (
                transport.get("fixed_predicate")
                if isinstance(transport, dict)
                else None
            )
        ):
            return False
    return True


def _sanitize_target(target: object, depth: int = 0) -> dict:
    if depth > _MAX_TARGET_NESTING_DEPTH:
        return {"depth_exceeded": True}
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
    aliases = target.get("aliases")
    sanitized["aliases"] = [
        {"alias": alias.get("alias"), "proof_ref": alias.get("proof_ref")}
        for alias in (aliases if isinstance(aliases, list) else [])
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
    leaf_entries = target.get("leaf_entries")
    if isinstance(leaf_entries, list):
        sanitized["leaf_entries"] = [
            _sanitize_target(leaf, depth=depth + 1) for leaf in leaf_entries
        ]
    return sanitized


def _copy_fields(value: object, fields: tuple[str, ...]) -> dict:
    return {
        field: value[field]
        for field in fields
        if isinstance(value, dict) and field in value
    }


def _evaluate_acceptance_manifest(
    manifest: object,
    revision: object,
    authorized_mutation_id: object = None,
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
        not isinstance(adapter, dict)
        or not isinstance(family, str)
        or family not in _FAMILY_MATRIX
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
            for field in (
                "scope_id",
                "decision_ref",
                "mutation_id",
                "exact_action",
                "set_proof_ref",
            )
        )
        or not _valid_string_set(authorized_ids)
        or set(authorized_ids) != set(sets["authorized"])
        or (
            isinstance(authorized_mutation_id, str)
            and authorization.get("mutation_id") != authorized_mutation_id
        )
        or (
            isinstance(family, str)
            and family in _FAMILY_MATRIX
            and exact_action != _FAMILY_MATRIX[family]["action"]
        )
    ):
        shape_reasons.append("malformed_acceptance_authorization")
    effective_mutation_id = (
        authorized_mutation_id
        if isinstance(authorized_mutation_id, str)
        else authorization.get("mutation_id")
        if isinstance(authorization, dict)
        else None
    )

    repair = manifest.get("repair")
    if not _repair_valid(repair, linked, records):
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
    if not set(sets["authorized"]).issubset(
        set(sets["intended"])
        | set(sets["skipped"])
        | set(sets["unauthorized"])
        | set(sets["duplicates"])
    ):
        shape_reasons.append("authorized_target_uncovered")

    zero_proof = manifest.get("zero_mutation_proof")
    authorized_scope = set(sets["authorized"])
    if (
        not sets["intended"]
        and isinstance(zero_proof, dict)
        and _valid_string_set(zero_proof.get("candidate_ids"))
    ):
        authorized_scope |= set(zero_proof["candidate_ids"])
    if not set(sets["skipped"]).issubset(authorized_scope):
        shape_reasons.append("unauthorized_skipped")
    if not set(sets["skipped"]).isdisjoint(set(sets["intended"])):
        shape_reasons.append("conflicting_intent_skipped")
    if not set(sets["skipped"]).issubset(set(sets["inspected"])):
        shape_reasons.append("uninspected_skipped")

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
        expected_mutation=effective_mutation_id,
        expected_scope=authorization.get("scope_id")
        if isinstance(authorization, dict)
        else None,
        expected_predicate=exact_action,
    ):
        shape_reasons.append("unproved_authorized_set")

    alias_targets: dict[str, set[str]] = {}
    for target in targets:
        if not isinstance(target, dict):
            continue
        target_id = target.get("canonical_target_id")
        aliases = target.get("aliases")
        for alias in aliases if isinstance(aliases, list) else []:
            if (
                isinstance(target_id, str)
                and isinstance(alias, dict)
                and isinstance(alias.get("alias"), str)
            ):
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
            authorization.get("decision_ref")
            if isinstance(authorization, dict)
            else None,
            authorization.get("scope_id")
            if isinstance(authorization, dict)
            else None,
            adapter.get("tool_contract_digest")
            if isinstance(adapter, dict)
            else None,
            linked,
            records,
            sets,
            authorized_mutation_id=effective_mutation_id,
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
        else:
            shape_reasons.append("malformed_target_entry")
        target_reasons.extend(result[4])
        detected_duplicates.extend(result[5])

    create_keys = []
    create_results = []
    all_target_ids: set[str] = set()
    pending_targets = [(target, family) for target in targets]
    while pending_targets:
        candidate, candidate_family = pending_targets.pop()
        if not isinstance(candidate, dict):
            continue
        candidate_id = candidate.get("canonical_target_id")
        if isinstance(candidate_id, str) and candidate_id:
            all_target_ids.add(candidate_id)
        if candidate_family == "create_append":
            pre_ref = candidate.get("pre_ref")
            receipt_ref = candidate.get("receipt_ref")
            pre = records.get(pre_ref) if isinstance(pre_ref, str) else None
            receipt = records.get(receipt_ref) if isinstance(receipt_ref, str) else None
            if isinstance(pre, dict) and isinstance(
                pre.get("client_mutation_key"), str
            ):
                create_keys.append(pre["client_mutation_key"])
            if isinstance(receipt, dict) and isinstance(
                receipt.get("result_resource_id"), str
            ):
                create_results.append(receipt["result_resource_id"])
        leaf_entries = candidate.get("leaf_entries")
        if candidate_family == "operation_composite" and isinstance(
            leaf_entries, list
        ):
            pending_targets.extend(
                (
                    leaf,
                    leaf.get("family") if isinstance(leaf, dict) else None,
                )
                for leaf in leaf_entries
            )
    if len(create_keys) != len(set(create_keys)):
        shape_reasons.append("duplicate_create_mutation_key")
    if len(create_results) != len(set(create_results)):
        shape_reasons.append("duplicate_create_result_identity")

    verified_target_ids = all_target_ids | set(sets["skipped"])

    for receipt_ref in linked["actions"]:
        receipt = records.get(receipt_ref)
        receipt_target_id = (
            receipt.get("target_id") if isinstance(receipt, dict) else None
        )
        if (
            not isinstance(receipt, dict)
            or receipt.get("kind") != "receipt"
            or receipt.get("authoritative") is not True
            or not isinstance(receipt_target_id, str)
            or receipt_target_id not in all_target_ids
        ):
            shape_reasons.append("out_of_scope_action_receipt")

    any_action = bool(replay_prohibited or linked["actions"])
    if any_action:
        for target_id, target_status in statuses.items():
            if target_status == "blocked":
                statuses[target_id] = "failed"
                target_reasons.append("mutation_started_before_pre_action_gate")

    outcome_rank = {
        "skipped": 0,
        "accepted": 1,
        "unknown": 2,
        "failed": 3,
        "unauthorized": 4,
        "duplicates": 5,
    }
    computed_status = {
        "accepted": "accepted",
        "indeterminate": "unknown",
        "failed": "failed",
        "blocked": "skipped",
    }
    computed_rank = {
        "accepted": 1,
        "unknown": 2,
        "failed": 3,
        "blocked": 4,
    }
    outcome_priority = {}
    for name in (
        "skipped",
        "accepted",
        "unknown",
        "failed",
        "unauthorized",
        "duplicates",
    ):
        for target_id in sets[name]:
            previous = outcome_priority.get(target_id)
            if previous is None or outcome_rank[name] > outcome_rank[previous]:
                outcome_priority[target_id] = name
    for target_id, target_status in statuses.items():
        computed = computed_status.get(target_status, "skipped")
        previous = outcome_priority.get(target_id)
        if target_status == "blocked":
            if previous == "accepted":
                outcome_priority[target_id] = "skipped"
            elif previous is None:
                outcome_priority[target_id] = "skipped"
            continue
        rank = computed_rank.get(target_status, outcome_rank.get(computed, 0))
        if previous is None or rank > outcome_rank[previous]:
            outcome_priority[target_id] = computed
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
                and (
                    name in ("unauthorized", "duplicates")
                    or target_id in verified_target_ids
                )
            ]
            for name in _OUTCOME_SETS
        },
    }
    normalized_sets["derived_counts"] = {
        name: len(normalized_sets[name]) for name in _RECONCILIATION_SETS
    }

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
    zero_mutation_proved = (
        not sets["intended"] or sets["skipped"]
    ) and _zero_mutation_proved(
        manifest,
        sets,
        linked,
        records,
        effective_mutation_id,
        authorization.get("scope_id")
        if isinstance(authorization, dict)
        else None,
        exact_action,
    )
    terminal_ids = set()
    for name in ("accepted", "failed", "unknown"):
        terminal_ids.update(normalized_sets[name])
    blocked = bool(
        shape_reasons
        or any(status == "blocked" for status in statuses.values())
        or len(sets["intended"]) != len(terminal_ids)
        or any(target_id not in terminal_ids for target_id in sets["intended"])
        or (sets["skipped"] and not zero_mutation_proved)
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
                "mutation_id",
                "exact_action",
                "canonical_target_ids",
                "set_proof_ref",
            ),
        ),
        "evidence": linked,
        "evidence_summaries": _sanitize_evidence_summaries(records, linked),
        "targets": [_sanitize_target(target) for target in targets],
        "reconciliation": normalized_sets,
        "repair": {
            **_copy_fields(repair, ("allowed", "forbidden")),
            "attempts": _sanitize_attempts(
                repair.get("attempts") if isinstance(repair, dict) else None
            ),
        },
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


def _finding_reasons(
    finding: object,
    design_revision: object,
    design_digest: object,
    review_identity: object,
    allow_unresolved: bool,
) -> list[str]:
    if not isinstance(finding, dict):
        return ["malformed_review_finding"]

    identity = finding.get("identity")
    classification = finding.get("classification")
    required_text = (
        identity,
        finding.get("criterion"),
        finding.get("sanitized_evidence"),
        finding.get("rationale"),
        finding.get("clearance_condition"),
    )
    if (
        not all(isinstance(value, str) and value for value in required_text)
        or classification not in {"must-fix", "advisory"}
        or not _string_list(finding.get("affected_nodes"))
        or not finding["affected_nodes"]
        or finding.get("waiver_policy")
        not in {"unwaivable", "human-authorized"}
    ):
        return ["malformed_review_finding"]

    if classification == "advisory":
        return []

    disposition = finding.get("disposition")
    if disposition not in {
        "repaired",
        "human-authorized-deviation",
        "unresolved",
    }:
        return ["malformed_review_disposition"]
    if disposition == "unresolved":
        return [] if allow_unresolved else ["unresolved_must_fix"]

    clearance = finding.get("clearance")
    if disposition == "repaired":
        if (
            not isinstance(clearance, dict)
            or clearance.get("finding_identity") != identity
            or clearance.get("review_identity") != review_identity
            or clearance.get("design_digest") != design_digest
        ):
            return ["missing_independent_clearance"]
        return []

    if finding["waiver_policy"] != "human-authorized":
        return ["unwaivable_finding"]
    if (
        not isinstance(clearance, dict)
        or clearance.get("finding_identity") != identity
        or clearance.get("design_revision") != design_revision
        or not isinstance(clearance.get("decision_receipt"), str)
        or not clearance["decision_receipt"]
    ):
        return ["inexact_human_deviation"]
    return []


def _review_gate(
    design_review: object,
    revision: object,
    frozen_design_digest: object,
    allow_previous: bool,
) -> dict:
    reasons: list[str] = []
    if design_review is None:
        return {"status": "block", "reasons": ["missing_design_review"]}
    if not isinstance(design_review, dict):
        return {"status": "block", "reasons": ["malformed_design_review"]}

    design_revision = design_review.get("design_revision")
    if not isinstance(design_revision, int) or isinstance(design_revision, bool):
        reasons.append("malformed_design_revision")
    elif design_revision != revision:
        reasons.append("stale_design_review")

    design_digest = design_review.get("design_digest")
    if not isinstance(design_digest, str) or not design_digest:
        reasons.append("malformed_design_digest")
    if not isinstance(frozen_design_digest, str) or not frozen_design_digest:
        reasons.append("missing_frozen_design_digest")
    elif design_digest != frozen_design_digest:
        reasons.append("frozen_design_digest_mismatch")

    repair_count = design_review.get("repair_count")
    if (
        not isinstance(repair_count, int)
        or isinstance(repair_count, bool)
        or repair_count < 0
    ):
        reasons.append("malformed_repair_count")
    elif repair_count > 1:
        reasons.append("repair_limit_exceeded")

    self_check = design_review.get("self_check")
    if not isinstance(self_check, dict):
        reasons.append("missing_self_check")
    else:
        if self_check.get("design_digest") != design_digest:
            reasons.append("self_check_digest_mismatch")
        if self_check.get("verdict") != "pass":
            reasons.append("self_check_not_passed")
        self_check_evidence = self_check.get("evidence_locators")
        if not _string_list(self_check_evidence) or not self_check_evidence:
            reasons.append("malformed_self_check_evidence")

    independent_review = design_review.get("independent_review")
    if not isinstance(independent_review, dict):
        reasons.append("missing_independent_review")
        independent_review = {}
    elif independent_review.get("status") == "timed_out":
        reasons.append("independent_review_timed_out")
    elif independent_review.get("status") != "complete":
        reasons.append("malformed_independent_review_status")

    review_identity = independent_review.get("identity")
    if not isinstance(review_identity, str) or not review_identity:
        reasons.append("malformed_review_identity")
    if independent_review.get("design_digest") != design_digest:
        reasons.append("review_digest_mismatch")

    verdict = independent_review.get("verdict")
    if verdict not in {"pass", "repair", "block"}:
        reasons.append("malformed_review_verdict")
    if verdict == "block":
        reasons.append("independent_review_blocked")
    elif verdict == "repair" and repair_count != 0:
        reasons.append("repair_limit_exceeded")

    independence = independent_review.get("independence")
    if (
        not isinstance(independence, dict)
        or independence.get("separate_context") is not True
        or independence.get("read_only") is not True
        or independence.get("design_authority") is not False
        or independence.get("mutation_authority") is not False
    ):
        reasons.append("unproved_reviewer_independence")

    findings = independent_review.get("findings")
    if not isinstance(findings, list):
        reasons.append("malformed_review_findings")
        findings = []
    finding_identities = []
    for finding in findings:
        reasons.extend(
            _finding_reasons(
                finding,
                design_revision,
                design_digest,
                review_identity,
                allow_unresolved=verdict == "repair" and repair_count == 0,
            )
        )
        if (
            isinstance(finding, dict)
            and isinstance(finding.get("identity"), str)
            and finding["identity"]
        ):
            finding_identities.append(finding["identity"])
    if len(finding_identities) != len(set(finding_identities)):
        reasons.append("duplicate_finding_identity")

    if verdict == "repair" and not any(
        isinstance(finding, dict)
        and finding.get("classification") == "must-fix"
        and finding.get("disposition") == "unresolved"
        for finding in findings
    ):
        reasons.append("repair_without_must_fix")

    current_findings = {
        finding["identity"]: finding
        for finding in findings
        if isinstance(finding, dict)
        and isinstance(finding.get("identity"), str)
        and finding["identity"]
    }
    previous_review = design_review.get("previous_review")
    if repair_count == 0:
        if previous_review is not None:
            reasons.append("unexpected_previous_review")
        if any(
            isinstance(finding, dict)
            and finding.get("classification") == "must-fix"
            and finding.get("disposition") == "repaired"
            for finding in findings
        ):
            reasons.append("repair_count_mismatch")
    elif repair_count == 1:
        if not allow_previous:
            reasons.append("invalid_previous_review")
        elif not isinstance(previous_review, dict):
            reasons.append("missing_previous_review")
        else:
            previous_revision = previous_review.get("design_revision")
            previous_digest = previous_review.get("design_digest")
            previous_gate = _review_gate(
                previous_review,
                previous_revision,
                previous_digest,
                allow_previous=False,
            )
            if previous_gate["status"] != "repair_required":
                reasons.append("invalid_previous_review")
            else:
                if (
                    not isinstance(previous_revision, int)
                    or isinstance(previous_revision, bool)
                    or not isinstance(design_revision, int)
                    or isinstance(design_revision, bool)
                    or design_revision <= previous_revision
                    or previous_digest == design_digest
                ):
                    reasons.append("repair_did_not_create_new_revision")

                immutable_fields = (
                    "identity",
                    "classification",
                    "criterion",
                    "affected_nodes",
                    "sanitized_evidence",
                    "rationale",
                    "clearance_condition",
                    "waiver_policy",
                )
                previous_must_fix = {
                    finding["identity"]: finding
                    for finding in previous_gate["independent_review"]["findings"]
                    if isinstance(finding, dict)
                    and finding.get("classification") == "must-fix"
                    and isinstance(finding.get("identity"), str)
                    and finding["identity"]
                }
                for identity, previous_finding in previous_must_fix.items():
                    current_finding = current_findings.get(identity)
                    if current_finding is None:
                        reasons.append("missing_prior_finding")
                    elif any(
                        current_finding.get(field) != previous_finding.get(field)
                        for field in immutable_fields
                    ):
                        reasons.append("altered_prior_finding")
                if any(
                    finding.get("classification") == "must-fix"
                    and finding.get("disposition") == "repaired"
                    and identity not in previous_must_fix
                    for identity, finding in current_findings.items()
                ):
                    reasons.append("unexpected_repaired_finding")

    review_evidence = independent_review.get("evidence_locators")
    if not _string_list(review_evidence) or not review_evidence:
        reasons.append("malformed_review_evidence")

    status = "block" if reasons else "pass"
    if not reasons and verdict == "repair":
        status = "repair_required"
    gate = {
        "status": status,
        "reasons": list(dict.fromkeys(reasons)),
        "design_revision": design_revision,
        "design_digest": design_digest,
        "frozen_design_digest": frozen_design_digest,
        "repair_count": repair_count,
        "previous_review": previous_review,
        "self_check": self_check,
        "independent_review": {
            **independent_review,
            "findings": findings,
        },
    }
    if status == "repair_required":
        gate["required_action"] = "repair_design"
    return gate


def _blocked_result(
    reasons: list[str],
    retained_evidence: list[str],
    observed_effects: list[str],
    stopped_workers: list[str],
    revision: object = None,
    review_gate: dict | None = None,
    review_checkpoint: object = None,
    mutation_admission: dict | None = None,
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
        "mutation_admission": mutation_admission,
        "workflow_state": {"state": "blocked", "final": True},
        "review_gate": review_gate or {"status": "not_evaluated", "reasons": []},
        "review_checkpoint": review_checkpoint,
    }


def evaluate_root_workflow(
    metadata: object,
    events: object = (),
    review_checkpoint: object = None,
) -> dict:
    """Evaluate authority admission without performing or accepting any work."""
    if not isinstance(metadata, dict):
        return _blocked_result(
            ["malformed_workflow_metadata"],
            [],
            [],
            [],
            revision=None,
            review_checkpoint=review_checkpoint,
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
            review_checkpoint=review_checkpoint,
        )
    if not isinstance(preflight, dict):
        return _blocked_result(
            ["malformed_authority_preflight"],
            retained_evidence,
            observed_effects,
            [],
            revision=metadata.get("revision"),
            review_checkpoint=review_checkpoint,
        )

    reasons: list[str] = []
    revision = preflight.get("revision")
    preflight_revision = revision
    if not isinstance(revision, int) or isinstance(revision, bool):
        reasons.append("malformed_authority_preflight_revision")
    elif revision != metadata.get("revision"):
        reasons.append("stale_authority_preflight")

    checkpoint_valid = review_checkpoint is None
    prior_repair_used = False
    checkpoint_state_reasons: list[str] = []
    if review_checkpoint is not None:
        if (
            not isinstance(review_checkpoint, dict)
            or not isinstance(review_checkpoint.get("design_revision"), int)
            or isinstance(review_checkpoint.get("design_revision"), bool)
            or not isinstance(review_checkpoint.get("design_digest"), str)
            or not review_checkpoint["design_digest"]
            or not isinstance(
                review_checkpoint.get("automatic_repair_used"), bool
            )
        ):
            checkpoint_state_reasons.append("malformed_review_checkpoint")
            reasons.append("malformed_review_checkpoint")
        else:
            checkpoint_valid = True
            prior_repair_used = review_checkpoint["automatic_repair_used"]
            if (
                isinstance(revision, int)
                and not isinstance(revision, bool)
                and review_checkpoint["design_revision"] > revision
            ):
                checkpoint_state_reasons.append("stale_review_checkpoint")
                reasons.append("stale_review_checkpoint")

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
    current_design_review = metadata.get("design_review")
    current_design_digest = metadata.get("design_digest")
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
            if "design_review" in event:
                current_design_review = event["design_review"]
            if "design_digest" in event:
                current_design_digest = event["design_digest"]
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
                mutation_owners.setdefault(mutation["identity"], set()).add("root")

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

    review_gate = {"status": "not_applicable", "reasons": []}
    if any(
        isinstance(mutation, dict)
        and isinstance(mutation.get("identity"), str)
        and mutation["identity"]
        and mutation.get("owner") == "root"
        for mutation in mutations
    ):
        review_gate = _review_gate(
            current_design_review,
            revision,
            current_design_digest,
            allow_previous=True,
        )
        if checkpoint_state_reasons:
            review_gate["reasons"] = list(
                dict.fromkeys(review_gate["reasons"] + checkpoint_state_reasons)
            )
            review_gate["status"] = "block"
            review_gate.pop("required_action", None)
        if checkpoint_valid:
            repair_count = review_gate.get("repair_count")
            verdict = review_gate.get("independent_review", {}).get("verdict")
            checkpoint_reasons = []
            if prior_repair_used:
                if repair_count != 1:
                    checkpoint_reasons.append("repair_count_mismatch")
                else:
                    previous_review = review_gate.get("previous_review")
                    if (
                        not isinstance(previous_review, dict)
                        or previous_review.get("design_revision")
                        != review_checkpoint["design_revision"]
                        or previous_review.get("design_digest")
                        != review_checkpoint["design_digest"]
                    ):
                        checkpoint_reasons.append("review_checkpoint_mismatch")
                if verdict == "repair":
                    checkpoint_reasons.append("repair_limit_exceeded")
            elif repair_count == 1:
                checkpoint_reasons.append("unproved_repair_transition")
            if checkpoint_reasons:
                review_gate["reasons"] = list(
                    dict.fromkeys(review_gate["reasons"] + checkpoint_reasons)
                )
                review_gate["status"] = "block"
                review_gate.pop("required_action", None)
        reasons.extend(review_gate["reasons"])

    next_review_checkpoint = (
        review_checkpoint if isinstance(review_checkpoint, dict) else None
    )
    if review_checkpoint is not None and not checkpoint_valid:
        origin_revision = (
            review_checkpoint.get("design_revision")
            if isinstance(review_checkpoint, dict)
            else None
        )
        origin_digest = (
            review_checkpoint.get("design_digest")
            if isinstance(review_checkpoint, dict)
            else None
        )
        if (
            not isinstance(origin_revision, int)
            or isinstance(origin_revision, bool)
            or not isinstance(origin_digest, str)
            or not origin_digest
        ):
            previous_review = review_gate.get("previous_review")
            if isinstance(previous_review, dict):
                origin_revision = previous_review.get("design_revision")
                origin_digest = previous_review.get("design_digest")
            else:
                origin_revision = review_gate.get("design_revision")
                origin_digest = review_gate.get("design_digest")
        if (
            isinstance(origin_revision, int)
            and not isinstance(origin_revision, bool)
            and isinstance(origin_digest, str)
            and origin_digest
        ):
            next_review_checkpoint = {
                "design_revision": origin_revision,
                "design_digest": origin_digest,
                "automatic_repair_used": True,
            }
        else:
            next_review_checkpoint = {
                "state": "unknown",
                "automatic_repair_used": True,
            }
    if (
        review_gate["status"] == "repair_required"
        and isinstance(review_gate.get("design_revision"), int)
        and not isinstance(review_gate["design_revision"], bool)
        and isinstance(review_gate.get("design_digest"), str)
        and review_gate["design_digest"]
    ):
        next_review_checkpoint = {
            "design_revision": review_gate["design_revision"],
            "design_digest": review_gate["design_digest"],
            "automatic_repair_used": (
                prior_repair_used or review_gate["status"] == "repair_required"
            ),
        }


    if reasons:
        return _blocked_result(
            list(dict.fromkeys(reasons)),
            retained_evidence,
            observed_effects,
            stopped_workers,
            revision=revision,
            review_gate=review_gate,
            review_checkpoint=next_review_checkpoint,
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

    mutation_admission = _evaluate_mutation_admission(
        metadata.get("mutation_admission"),
        metadata.get("queue_revision"),
        set(mutation_owners),
    )

    review_may_execute = (
        not runtime_decision
        and not human_decision_required
        and review_gate["status"] in {"pass", "not_applicable"}
    )
    root_may_execute = (
        review_may_execute
        and mutation_admission is not None
        and mutation_admission["status"] == "allow"
    )
    delegated_work = review_may_execute and selected_topology != "L0"
    mutation_blocked = (
        mutation_admission is not None
        and mutation_admission["status"] == "blocked"
    )
    workflow_state = (
        "human_decision_required" if human_decision_required else "continue"
    )
    result = {
        "authority_preflight": authority_preflight,
        "selected_topology": selected_topology,
        "execution_permission": {
            "root_mutation": root_may_execute and bool(mutations),
            "delegated_work": delegated_work,
            "delegated_mutation": False,
            "stopped_workers": stopped_workers,
        },
        "retained_evidence": retained_evidence,
        "observed_effects": observed_effects,
        "mutation_admission": mutation_admission,
        "review_gate": review_gate,
        "review_checkpoint": next_review_checkpoint,
        "workflow_state": {
            "state": workflow_state,
            "final": workflow_state == "blocked",
        },
    }
    authorized_mutation_id = (
        mutation_admission["mutation_id"]
        if mutation_admission is not None
        and isinstance(mutation_admission.get("mutation_id"), str)
        else None
    )
    if "acceptance_manifest" in metadata and review_may_execute:
        manifest, terminal = _evaluate_acceptance_manifest(
            metadata["acceptance_manifest"], revision, authorized_mutation_id
        )
        if terminal == "accepted" and not root_may_execute:
            terminal = "blocked"
            manifest["terminal"] = {
                "status": terminal,
                "reason_code": "pre_action_evidence_gap",
            }
        result["acceptance_manifest"] = manifest
        result["workflow_state"] = {"state": terminal, "final": True}
        result["execution_permission"] = {
            "root_mutation": False,
            "delegated_work": False,
            "delegated_mutation": False,
            "stopped_workers": stopped_workers,
        }
    return result
