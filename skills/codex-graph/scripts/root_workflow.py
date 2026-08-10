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
                pages[index]["cursor"] == pages[index - 1]["next_cursor"]
                for index in range(1, len(pages))
            )
            and returned_ids == target_ids
            and pages[-1]["next_cursor"] is None
        )
    if capability == "bounded_list":
        return returned_ids == target_ids and (
            terminal.get("kind") == "authoritative_total"
            and terminal.get("total") == len(set(returned_ids))
            or terminal.get("kind") == "documented_short_page_terminal"
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

    total = terminal.get("total_length")
    ranges = terminal.get("ranges")
    if (
        len(target_ids) != 1
        or terminal.get("kind") != "gap_free_ranges"
        or not isinstance(total, int)
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

    seen_inputs = set()
    prior_completed = None
    prior_remaining = None
    for index, attempt in enumerate(attempts):
        if (
            not isinstance(attempt, dict)
            or not isinstance(attempt.get("input"), str)
            or not attempt["input"]
            or not isinstance(attempt.get("completed_units"), int)
            or isinstance(attempt["completed_units"], bool)
            or attempt["completed_units"] < 0
            or not isinstance(attempt.get("remaining_units"), int)
            or isinstance(attempt["remaining_units"], bool)
            or attempt["remaining_units"] < 0
        ):
            reasons.append("malformed_recovery_attempt")
            continue
        if attempt["input"] in seen_inputs:
            reasons.append("repeated_incomplete_input")
        seen_inputs.add(attempt["input"])

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


def _acceptance_path_complete(path: object, target_ids: list[str]) -> bool:
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
        if (
            not isinstance(capability, dict)
            or not isinstance(capability.get("locator"), str)
            or not capability["locator"]
            or capability.get("target_ids") != target_ids
        ):
            return False
        capabilities.append(capability)
    return (
        capabilities[3].get("actor") == "root"
        and capabilities[2]["locator"] != capabilities[3]["locator"]
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
        and _acceptance_path_complete(admission.get("acceptance_path"), target_ids)
        and isinstance(proof, dict)
        and proof.get("mutation_id") == mutation_id
        and proof.get("action") == admission["action"]
        and proof.get("target_state") == admission["target_state"]
        and proof.get("predicate_identity") == predicate.get("identity")
        and proof.get("target_bindings") == targets
        and proof.get("requested_scope") == target_ids
        and proof.get("returned_scope") == target_ids
        and proof.get("required_fields") == required_fields
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
            and signal.get("scope") in {*target_ids, "call"}
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
    if proof.get("aggregate_required") is True and blocked_items:
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
        and record.get("result") in _CLASSIFICATION_RESULTS
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
    binding_complete = (
        isinstance(binding, dict)
        and binding.get("mutation_id") == context["mutation_id"]
        and binding.get("action") == admission.get("action")
        and binding.get("target_state") == admission.get("target_state")
        and binding.get("predicate_identity") == context["predicate"].get("identity")
        and binding.get("target_bindings") == context["targets"]
    )
    records_complete = (
        isinstance(item_records, list)
        and len(item_records) == len(context["target_ids"])
        and [
            item.get("item_id") for item in item_records if isinstance(item, dict)
        ]
        == context["target_ids"]
        and all(_classification_record_complete(item) for item in item_records)
        and _classification_record_complete(action_record)
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
                "transport",
                ["partition_not_proved"],
                context["target_ids"],
                context["proof"],
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
    current_revision = (
        isinstance(queue_revision, int) and not isinstance(queue_revision, bool)
    )
    authorization_valid = (
        isinstance(authorization, dict)
        and isinstance(authorization.get("receipt_id"), str)
        and bool(authorization["receipt_id"])
        and current_revision
        and authorization.get("queue_revision") == queue_revision
        and authorization.get("mutation_id") == context["mutation_id"]
        and authorization.get("action") == admission.get("action")
        and authorization.get("target_state") == admission.get("target_state")
        and _string_list(authorization.get("item_ids"))
        and bool(authorization["item_ids"])
        and len(authorization["item_ids"]) == len(set(authorization["item_ids"]))
        and set(authorization["item_ids"]) <= set(context["target_ids"])
    )
    authorized_items = (
        set(authorization["item_ids"]) if authorization_valid else set()
    )
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

    mutation_admission = _evaluate_mutation_admission(
        metadata.get("mutation_admission"),
        metadata.get("queue_revision"),
        set(mutation_owners),
    )

    root_may_execute = (
        not runtime_decision
        and not human_decision_required
        and mutation_admission is not None
        and mutation_admission["status"] == "allow"
    )
    delegation_may_continue = not runtime_decision and not human_decision_required
    return {
        "authority_preflight": authority_preflight,
        "selected_topology": selected_topology,
        "execution_permission": {
            "root_mutation": root_may_execute and bool(mutations),
            "delegated_work": (
                delegation_may_continue and selected_topology != "L0"
            ),
            "delegated_mutation": False,
            "stopped_workers": stopped_workers,
        },
        "retained_evidence": retained_evidence,
        "observed_effects": observed_effects,
        "mutation_admission": mutation_admission,
        "workflow_state": {
            "state": (
                "blocked"
                if mutation_admission is not None
                and mutation_admission["status"] == "blocked"
                else "human_decision_required"
                if human_decision_required
                else "continue"
            ),
            "final": (
                mutation_admission is not None
                and mutation_admission["status"] == "blocked"
            ),
        },
    }
