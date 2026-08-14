"""Deterministic root-owned authority admission for sanitized workflow facts."""

from __future__ import annotations


_TOPOLOGIES = {"L0", "L1", "L2", "L3", "L4"}
_TRIGGER_STATES = {"fired", "not_fired", "not_evaluated", "not_applicable"}
_PROCESS_FACTS = {"process_exit", "generated_output", "attempt_pass"}

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
    forensics_valid = (
        isinstance(supplied, dict)
        and isinstance(supplied.get("cap_bytes"), int)
        and not isinstance(supplied["cap_bytes"], bool)
        and supplied["cap_bytes"] >= 0
        and isinstance(supplied.get("last_raw"), str)
        and len(supplied["last_raw"].encode()) <= supplied["cap_bytes"]
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

    capability = proof.get("capability") if isinstance(proof, dict) else "transport"
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
    return {
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
            "state": (
                "human_decision_required"
                if human_decision_required
                else "continue"
                if not mutation_blocked or delegated_work
                else "blocked"
            ),
            "final": (
                mutation_blocked
                and not delegated_work
                and not human_decision_required
                and not runtime_decision
                and selected_topology != "L0"
            ),
        },
    }
