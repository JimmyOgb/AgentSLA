import json
import pytest


def test_sla_creation_and_view(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Test valid SLA creation and reading back terms and metadata."""
    contract = direct_deploy("contracts/agent_sla.py")
    direct_vm.sender = direct_alice

    terms = "Service Guarantee: 99.9% API uptime with response latency < 200ms."
    sla_id = contract.create_sla(terms)
    assert sla_id == 1

    sla_data = contract.get_sla(1)
    assert sla_data["id"] == 1
    alice_hex = "0x" + direct_alice.hex() if isinstance(direct_alice, bytes) else direct_alice.as_hex
    assert sla_data["provider"].lower() == alice_hex.lower()
    assert sla_data["terms"] == terms
    assert sla_data["status"] == "active"
    assert sla_data["stake"] == 0

    stats = contract.get_stats()
    assert stats["total_slas"] == 1
    assert stats["total_active_slas"] == 1
    assert stats["total_pending_claims"] == 0


def test_sla_terms_validation_reverts(direct_vm, direct_deploy, direct_alice):
    """Test that SLA terms with insufficient length revert."""
    contract = direct_deploy("contracts/agent_sla.py")
    direct_vm.sender = direct_alice

    # Minimum terms length is 20 chars
    with direct_vm.expect_revert("SLA terms too short"):
        contract.create_sla("Too short")


def test_submit_claim_validations(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Test claim submission requirements and input validations."""
    contract = direct_deploy("contracts/agent_sla.py")
    direct_vm.sender = direct_alice

    terms = "Service Guarantee: 99.9% API uptime with response latency < 200ms."
    sla_id = contract.create_sla(terms)

    direct_vm.sender = direct_bob

    # 1. Non-existent SLA reverts
    with direct_vm.expect_revert("SLA 99 does not exist"):
        contract.submit_claim(99, ["https://status.agent.network/log1"], "Downtime observed")

    # 2. Empty evidence URLs reverts
    with direct_vm.expect_revert("Evidence URLs required"):
        contract.submit_claim(sla_id, [], "Downtime observed")

    # 3. Invalid URL scheme reverts
    with direct_vm.expect_revert("Invalid evidence URL scheme"):
        contract.submit_claim(sla_id, ["ftp://invalid-url.com/log"], "Downtime observed")

    # 4. Valid claim submission
    claim_id = contract.submit_claim(
        sla_id,
        ["https://status.agent.network/incident-101", "https://metrics.agent.network/latency"],
        "Observed 45 minutes of complete downtime on 2026-10-09."
    )
    assert claim_id == 1

    claim = contract.get_claim(claim_id)
    assert claim["id"] == 1
    assert claim["sla_id"] == sla_id
    bob_hex = "0x" + direct_bob.hex() if isinstance(direct_bob, bytes) else direct_bob.as_hex
    assert claim["claimant"].lower() == bob_hex.lower()
    assert len(claim["evidence_urls"]) == 2
    assert claim["status"] == "pending"
    assert claim["verdict"] == "none"

    pending = contract.get_pending_claims()
    assert len(pending) == 1
    assert pending[0]["id"] == 1


def test_adjudication_breach_with_evidence(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Test adjudication consensus when web evidence demonstrates breach."""
    contract = direct_deploy("contracts/agent_sla.py")
    
    # Alice creates SLA
    direct_vm.sender = direct_alice
    sla_id = contract.create_sla("Guaranteed uptime >= 99.9% over rolling 30 days.")

    # Bob submits claim
    direct_vm.sender = direct_bob
    evidence_url = "https://status.agent.network/incidents/oct9"
    claim_id = contract.submit_claim(
        sla_id,
        [evidence_url],
        "Provider experienced 8 hours outage violating the 99.9% monthly uptime guarantee."
    )

    # Mock web fetch
    direct_vm.mock_web(
        r".*status\.agent\.network/incidents/oct9.*",
        {
            "status": 200,
            "body": "Incident Report: Complete outage on October 9 lasting 480 minutes (8.0 hours). Total uptime degraded to 98.8%."
        }
    )

    # Mock LLM evaluation
    direct_vm.mock_llm(
        r".*Service Level Agreement.*",
        json.dumps({
            "verdict": "breached",
            "score": 95,
            "summary": "The incident report confirms 8 hours of downtime degrading uptime to 98.8%, breaching the 99.9% SLA."
        })
    )

    # Anyone can trigger adjudication
    direct_vm.sender = direct_bob
    result = contract.adjudicate(claim_id)

    assert result["verdict"] == "breached"
    assert result["score"] == 95
    assert "breaching the 99.9% SLA" in result["summary"]

    claim = contract.get_claim(claim_id)
    assert claim["status"] == "adjudicated"
    assert claim["verdict"] == "breached"
    assert claim["score"] == 95

    stats = contract.get_stats()
    assert stats["total_pending_claims"] == 0
    assert stats["total_adjudicated_claims"] == 1


def test_adjudication_met_verdict(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Test adjudication consensus when evidence confirms terms were met."""
    contract = direct_deploy("contracts/agent_sla.py")
    
    direct_vm.sender = direct_alice
    sla_id = contract.create_sla("Response latency guarantee: p95 latency must remain strictly below 250ms.")

    direct_vm.sender = direct_bob
    evidence_url = "https://metrics.agent.network/summary"
    claim_id = contract.submit_claim(
        sla_id,
        [evidence_url],
        "Verify monthly p95 latency compliance for billing cycle."
    )

    direct_vm.mock_web(
        r".*metrics\.agent\.network/summary.*",
        {
            "status": 200,
            "body": "Official telemetry report: P95 latency is 142ms across 2,400,000 requests during the period."
        }
    )

    direct_vm.mock_llm(
        r".*Service Level Agreement.*",
        json.dumps({
            "verdict": "met",
            "score": 92,
            "summary": "Telemetry data confirms p95 latency was 142ms, well within the guaranteed 250ms threshold."
        })
    )

    res = contract.adjudicate(claim_id)
    assert res["verdict"] == "met"
    assert res["score"] == 92
    assert contract.get_claim(claim_id)["verdict"] == "met"


def test_insufficient_evidence_when_fetch_fails(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Test that when evidence cannot be fetched, contract forces insufficient_evidence without hallucinating."""
    contract = direct_deploy("contracts/agent_sla.py")
    
    direct_vm.sender = direct_alice
    sla_id = contract.create_sla("Uptime guarantee of 99.95% on primary WebSocket gateway.")

    direct_vm.sender = direct_bob
    dead_url = "https://broken-domain-unreachable.io/log"
    claim_id = contract.submit_claim(
        sla_id,
        [dead_url],
        "Alleged outage at 04:00 UTC."
    )

    # Mock 404 or connection error
    direct_vm.mock_web(
        r".*broken-domain-unreachable\.io.*",
        {"status": 404, "body": "Not Found"}
    )

    # Note: no LLM mock needed because evaluate_evidence detects empty usable evidence and returns deterministic fallback!
    res = contract.adjudicate(claim_id)
    assert res["verdict"] == "insufficient_evidence"
    assert res["score"] <= 30
    assert "No usable evidence" in res["summary"]

    claim = contract.get_claim(claim_id)
    assert claim["verdict"] == "insufficient_evidence"


def test_cannot_re_adjudicate_claim(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Test that an already adjudicated claim cannot be evaluated twice."""
    contract = direct_deploy("contracts/agent_sla.py")
    direct_vm.sender = direct_alice
    sla_id = contract.create_sla("Uptime guarantee of 99.95% on primary WebSocket gateway.")

    direct_vm.sender = direct_bob
    claim_id = contract.submit_claim(
        sla_id,
        ["https://status.io/log"],
        "Outage reported."
    )

    direct_vm.mock_web(r".*status\.io/log.*", {"status": 500, "body": "Server Error"})
    contract.adjudicate(claim_id)

    with direct_vm.expect_revert("already adjudicated"):
        contract.adjudicate(claim_id)


def test_close_sla_by_provider(direct_vm, direct_deploy, direct_alice, direct_bob):
    """Test closing an SLA and authorization checks."""
    contract = direct_deploy("contracts/agent_sla.py")
    direct_vm.sender = direct_alice
    sla_id = contract.create_sla("Guaranteed response format: valid JSON-RPC 2.0 matching schema.")

    # Bob cannot close Alice's SLA
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Only provider can close SLA"):
        contract.close_sla(sla_id)

    # Alice closes SLA
    direct_vm.sender = direct_alice
    contract.close_sla(sla_id)

    sla = contract.get_sla(sla_id)
    assert sla["status"] == "closed"

    # Cannot submit claims against closed SLA
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("Cannot submit claim against non-active SLA"):
        contract.submit_claim(sla_id, ["https://test.com/log"], "test")


def test_equivalence_principle_rules(direct_vm, direct_deploy, direct_alice):
    """Test that the Equivalence Principle strictly enforces agreement and rejects divergences."""
    contract = direct_deploy("contracts/agent_sla.py")

    leader_valid = {
        "verdict": "breached",
        "score": 90,
        "summary": "Evidence proves uptime dropped to 95%, breaching the SLA.",
    }

    # 1. Matching validator output -> Accepted
    validator_matching = {
        "verdict": "breached",
        "score": 85,  # within ±15
        "summary": "Confirmed breach based on incident timeline showing 5% drop.",
    }
    assert contract.validate_equivalence(leader_valid, validator_matching) is True

    # 2. Conflicting verdict -> Rejected
    validator_wrong_verdict = {
        "verdict": "met",
        "score": 90,
        "summary": "Confirmed uptime was actually within limits.",
    }
    assert contract.validate_equivalence(leader_valid, validator_wrong_verdict) is False

    # 3. Score deviation exceeds tolerance (90 vs 70 -> diff 20 > 15) -> Rejected
    validator_diff_score = {
        "verdict": "breached",
        "score": 70,
        "summary": "Evidence proves uptime dropped to 95%, breaching the SLA.",
    }
    assert contract.validate_equivalence(leader_valid, validator_diff_score) is False

    # 4. Empty or trivial summary (< 10 chars) -> Rejected
    validator_short_summary = {
        "verdict": "breached",
        "score": 90,
        "summary": "Bad",
    }
    assert contract.validate_equivalence(leader_valid, validator_short_summary) is False
