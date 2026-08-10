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
        "review_gate": review_gate or {"status": "not_evaluated", "reasons": []},
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
        reasons.extend(review_gate["reasons"])


    if reasons:
        return _blocked_result(
            list(dict.fromkeys(reasons)),
            retained_evidence,
            observed_effects,
            stopped_workers,
            revision=revision,
            review_gate=review_gate,
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

    may_execute = (
        not runtime_decision
        and not human_decision_required
        and review_gate["status"] in {"pass", "not_applicable"}
    )
    return {
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
        "review_gate": review_gate,
        "workflow_state": {
            "state": "human_decision_required"
            if human_decision_required
            else "continue",
            "final": False,
        },
    }
