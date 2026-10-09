# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from dataclasses import dataclass
from genlayer import *

ERROR_EXPECTED = "[EXPECTED]"
ERROR_LLM = "[LLM_ERROR]"

MAX_EVIDENCE_URLS = 5
MAX_PAGE_CHARS = 3000
MIN_TERMS_LEN = 20
MIN_SUMMARY_LEN = 10
SCORE_TOLERANCE = 15
VALID_VERDICTS = {"met", "breached", "insufficient_evidence"}


@allow_storage
@dataclass
class SLA:
    provider: Address
    terms: str
    stake: u256
    status: str
    created_at_block: u256


@allow_storage
@dataclass
class Claim:
    sla_id: u256
    claimant: Address
    evidence_urls_json: str
    description: str
    status: str
    verdict: str
    score: u256
    summary: str
    adjudicated_by: Address


class AgentSLA(gl.Contract):
    next_sla_id: u256
    next_claim_id: u256
    slas: TreeMap[u256, SLA]
    claims: TreeMap[u256, Claim]
    total_active_slas: u256
    total_pending_claims: u256
    total_adjudicated_claims: u256

    def __init__(self):
        self.next_sla_id = u256(1)
        self.next_claim_id = u256(1)
        self.total_active_slas = u256(0)
        self.total_pending_claims = u256(0)
        self.total_adjudicated_claims = u256(0)

    @gl.public.write
    def create_sla(self, terms: str) -> u256:
        trimmed = terms.strip()
        if len(trimmed) < MIN_TERMS_LEN:
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} SLA terms too short: minimum {MIN_TERMS_LEN} characters required"
            )
        sla_id = self.next_sla_id
        self.next_sla_id = sla_id + u256(1)
        self.slas[sla_id] = SLA(
            provider=gl.message.sender_address,
            terms=trimmed,
            stake=gl.message.value,
            status="active",
            created_at_block=u256(0),
        )
        self.total_active_slas = self.total_active_slas + u256(1)
        return sla_id

    @gl.public.write
    def close_sla(self, sla_id: u256) -> None:
        if sla_id not in self.slas:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} SLA {sla_id} does not exist")
        sla = self.slas[sla_id]
        if gl.message.sender_address != sla.provider:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only provider can close SLA")
        if sla.status != "active":
            raise gl.vm.UserError(f"{ERROR_EXPECTED} SLA is not active")

        sla.status = "closed"
        refund = sla.stake
        sla.stake = u256(0)
        self.slas[sla_id] = sla
        if self.total_active_slas > u256(0):
            self.total_active_slas = self.total_active_slas - u256(1)
        if refund > u256(0):
            gl.chain.Account(gl.message.sender_address).emit_transfer(refund)

    @gl.public.write
    def submit_claim(
        self, sla_id: u256, evidence_urls: list[str], description: str
    ) -> u256:
        if sla_id not in self.slas:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} SLA {sla_id} does not exist")
        if self.slas[sla_id].status != "active":
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Cannot submit claim against non-active SLA"
            )
        if not evidence_urls or len(evidence_urls) == 0:
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Evidence URLs required: at least one URL must be provided"
            )

        validated_urls: list[str] = []
        for url in evidence_urls[:MAX_EVIDENCE_URLS]:
            trimmed = url.strip()
            if not (trimmed.startswith("http://") or trimmed.startswith("https://")):
                raise gl.vm.UserError(
                    f"{ERROR_EXPECTED} Invalid evidence URL scheme: {trimmed}"
                )
            validated_urls.append(trimmed)

        if len(validated_urls) == 0:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} No valid http/https URLs provided")

        claim_id = self.next_claim_id
        self.next_claim_id = claim_id + u256(1)
        self.claims[claim_id] = Claim(
            sla_id=sla_id,
            claimant=gl.message.sender_address,
            evidence_urls_json=json.dumps(validated_urls),
            description=description.strip(),
            status="pending",
            verdict="none",
            score=u256(0),
            summary="",
            adjudicated_by=Address("0x0000000000000000000000000000000000000000"),
        )
        self.total_pending_claims = self.total_pending_claims + u256(1)
        return claim_id

    @gl.public.write
    def adjudicate(self, claim_id: u256) -> dict:
        if claim_id not in self.claims:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Claim {claim_id} does not exist")
        claim = self.claims[claim_id]
        if claim.status != "pending":
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Claim {claim_id} is already adjudicated"
            )
        sla_id = claim.sla_id
        if sla_id not in self.slas:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Target SLA does not exist")
        sla = self.slas[sla_id]

        sla_terms = sla.terms
        claim_desc = claim.description
        try:
            urls_to_fetch: list[str] = json.loads(claim.evidence_urls_json)
        except Exception:
            urls_to_fetch = []

        def evaluate_evidence() -> dict:
            fetched_evidence: list[str] = []
            for u in urls_to_fetch[:MAX_EVIDENCE_URLS]:
                try:
                    res = gl.nondet.web.get(u)
                    if res.status == 200:
                        body = " ".join(
                            res.body.decode("utf-8", errors="replace").split()
                        )
                        if len(body) > MAX_PAGE_CHARS:
                            body = body[:MAX_PAGE_CHARS] + "... [truncated]"
                        if len(body.strip()) > 0:
                            fetched_evidence.append(f"Source ({u}):\n{body}")
                except Exception:
                    pass

            if not fetched_evidence:
                return {
                    "verdict": "insufficient_evidence",
                    "score": 10,
                    "summary": "No usable evidence could be retrieved from the provided URLs.",
                }

            combined_evidence = "\n\n".join(fetched_evidence)
            prompt = f"""You are a Service Level Agreement Adjudicator.
Evaluate if terms were met or breached based on evidence.
SLA TERMS: {sla_terms}
CLAIM: {claim_desc}
EVIDENCE: {combined_evidence}
CRITERIA: "met", "breached", or "insufficient_evidence".
Respond ONLY with JSON: {{"verdict": "met"|"breached"|"insufficient_evidence", "score": 0-100, "summary": "<1-2 sentences>"}}"""

            raw_resp = gl.nondet.exec_prompt(prompt, response_format="json")
            return _parse_and_validate_verdict(raw_resp)

        def validator_fn(leaders_res: gl.vm.Result) -> bool:
            if not isinstance(leaders_res, gl.vm.Return):
                return False
            leader_data = leaders_res.calldata
            if not isinstance(leader_data, dict):
                return False
            try:
                validator_data = evaluate_evidence()
            except Exception:
                return False
            return _validate_equivalence_logic(leader_data, validator_data)

        adjudication = gl.vm.run_nondet_unsafe(evaluate_evidence, validator_fn)

        final_verdict = str(adjudication["verdict"])
        final_score = u256(int(adjudication["score"]))
        final_summary = str(adjudication["summary"])

        claim.status = "adjudicated"
        claim.verdict = final_verdict
        claim.score = final_score
        claim.summary = final_summary
        claim.adjudicated_by = gl.message.sender_address
        self.claims[claim_id] = claim

        if self.total_pending_claims > u256(0):
            self.total_pending_claims = self.total_pending_claims - u256(1)
        self.total_adjudicated_claims = self.total_adjudicated_claims + u256(1)

        payout_recipient: Address | None = None
        payout_amount = u256(0)
        if final_verdict == "breached" and sla.stake > u256(0):
            payout_recipient = claim.claimant
            payout_amount = sla.stake
            sla.stake = u256(0)
            self.slas[sla_id] = sla

        if payout_recipient is not None and payout_amount > u256(0):
            gl.chain.Account(payout_recipient).emit_transfer(payout_amount)

        return {
            "claim_id": int(claim_id),
            "sla_id": int(sla_id),
            "verdict": final_verdict,
            "score": int(final_score),
            "summary": final_summary,
            "settled_payout": int(payout_amount),
        }

    @gl.public.view
    def get_sla(self, sla_id: u256) -> dict:
        if sla_id not in self.slas:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} SLA {sla_id} does not exist")
        sla = self.slas[sla_id]
        p_hex = (
            sla.provider.as_hex
            if hasattr(sla.provider, "as_hex")
            else (
                "0x" + sla.provider.hex()
                if isinstance(sla.provider, bytes)
                else str(sla.provider)
            )
        )
        return {
            "id": int(sla_id),
            "provider": p_hex,
            "terms": sla.terms,
            "stake": int(sla.stake),
            "status": sla.status,
            "created_at_block": int(sla.created_at_block),
        }

    @gl.public.view
    def get_claim(self, claim_id: u256) -> dict:
        if claim_id not in self.claims:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Claim {claim_id} does not exist")
        claim = self.claims[claim_id]
        try:
            urls = json.loads(claim.evidence_urls_json)
        except Exception:
            urls = []
        c_hex = (
            claim.claimant.as_hex
            if hasattr(claim.claimant, "as_hex")
            else (
                "0x" + claim.claimant.hex()
                if isinstance(claim.claimant, bytes)
                else str(claim.claimant)
            )
        )
        a_hex = (
            claim.adjudicated_by.as_hex
            if hasattr(claim.adjudicated_by, "as_hex")
            else (
                "0x" + claim.adjudicated_by.hex()
                if isinstance(claim.adjudicated_by, bytes)
                else str(claim.adjudicated_by)
            )
        )
        return {
            "id": int(claim_id),
            "sla_id": int(claim.sla_id),
            "claimant": c_hex,
            "evidence_urls": urls,
            "description": claim.description,
            "status": claim.status,
            "verdict": claim.verdict,
            "score": int(claim.score),
            "summary": claim.summary,
            "adjudicated_by": a_hex,
        }

    @gl.public.view
    def get_active_slas(self) -> list[dict]:
        result: list[dict] = []
        curr = u256(1)
        while curr < self.next_sla_id:
            if curr in self.slas and self.slas[curr].status == "active":
                s = self.slas[curr]
                p_hex = (
                    s.provider.as_hex
                    if hasattr(s.provider, "as_hex")
                    else (
                        "0x" + s.provider.hex()
                        if isinstance(s.provider, bytes)
                        else str(s.provider)
                    )
                )
                result.append(
                    {
                        "id": int(curr),
                        "provider": p_hex,
                        "terms": s.terms,
                        "stake": int(s.stake),
                        "status": s.status,
                    }
                )
            curr = curr + u256(1)
        return result

    @gl.public.view
    def get_pending_claims(self) -> list[dict]:
        result: list[dict] = []
        curr = u256(1)
        while curr < self.next_claim_id:
            if curr in self.claims and self.claims[curr].status == "pending":
                c = self.claims[curr]
                c_hex = (
                    c.claimant.as_hex
                    if hasattr(c.claimant, "as_hex")
                    else (
                        "0x" + c.claimant.hex()
                        if isinstance(c.claimant, bytes)
                        else str(c.claimant)
                    )
                )
                result.append(
                    {
                        "id": int(curr),
                        "sla_id": int(c.sla_id),
                        "claimant": c_hex,
                        "description": c.description,
                        "status": c.status,
                    }
                )
            curr = curr + u256(1)
        return result

    @gl.public.view
    def get_stats(self) -> dict:
        return {
            "total_slas": int(self.next_sla_id) - 1,
            "total_claims": int(self.next_claim_id) - 1,
            "total_active_slas": int(self.total_active_slas),
            "total_pending_claims": int(self.total_pending_claims),
            "total_adjudicated_claims": int(self.total_adjudicated_claims),
        }

    @gl.public.view
    def validate_equivalence(self, leader_data: dict, validator_data: dict) -> bool:
        return _validate_equivalence_logic(leader_data, validator_data)


def _validate_equivalence_logic(leader_data: dict, validator_data: dict) -> bool:
    if not isinstance(leader_data, dict) or not isinstance(validator_data, dict):
        return False
    if leader_data.get("verdict") != validator_data.get("verdict"):
        return False
    try:
        l_score = int(leader_data.get("score", -1))
        v_score = int(validator_data.get("score", -1))
    except Exception:
        return False
    if abs(l_score - v_score) > SCORE_TOLERANCE:
        return False
    l_sum = str(leader_data.get("summary", "")).strip()
    v_sum = str(validator_data.get("summary", "")).strip()
    return len(l_sum) >= MIN_SUMMARY_LEN and len(v_sum) >= MIN_SUMMARY_LEN


def _parse_and_validate_verdict(raw: dict | str) -> dict:
    parsed: dict
    if isinstance(raw, str):
        try:
            first = raw.find("{")
            last = raw.rfind("}")
            if first != -1 and last != -1:
                raw = raw[first : last + 1]
            parsed = json.loads(raw)
        except Exception as e:
            raise gl.vm.UserError(f"{ERROR_LLM} Invalid JSON from LLM: {e}")
    elif isinstance(raw, dict):
        parsed = raw
    else:
        raise gl.vm.UserError(
            f"{ERROR_LLM} Expected dict or json string, got {type(raw)}"
        )

    verdict = str(parsed.get("verdict", "")).strip().lower()
    if verdict not in VALID_VERDICTS:
        raise gl.vm.UserError(
            f"{ERROR_LLM} Invalid verdict '{verdict}'. Allowed: {VALID_VERDICTS}"
        )

    raw_score = parsed.get("score")
    if raw_score is None:
        raw_score = parsed.get("confidence", 50)
    try:
        score_val = max(0, min(100, int(round(float(str(raw_score).strip())))))
    except Exception:
        raise gl.vm.UserError(f"{ERROR_LLM} Non-numeric score: {raw_score}")

    summary = str(parsed.get("summary", "")).strip()
    if len(summary) < MIN_SUMMARY_LEN:
        raise gl.vm.UserError(
            f"{ERROR_LLM} Summary too short or missing ({len(summary)} chars)"
        )

    return {
        "verdict": verdict,
        "score": score_val,
        "summary": summary,
    }
