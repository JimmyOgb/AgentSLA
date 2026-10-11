# AgentSLA: Decentralized Service Level Agreement Primitive

> **Verifiable, decentralized Service Level Agreements (SLAs) for autonomous AI agents and human principals powered by GenLayer multi-validator LLM consensus over external web evidence.**

---

## 1. Purpose & Value for the Agentic Economy

In an autonomous agent economy, machine actors trade services—such as API provisioning, data scraping, code generation, real-time inference, and data feeds—permissionlessly. However, critical service commitments are expressed in natural language:
- *"Maintain 99.9% uptime over a 30-day window"*
- *"Ensure p95 response latency strictly under 200ms"*
- *"Emit JSON-RPC 2.0 compliant responses adhering to schema version 1.2"*

Traditional deterministic smart contracts cannot evaluate subjective or real-world natural-language guarantees without relying on centralized oracles. Centralized arbiters reintroduce single points of failure, counterparty custody risks, and jurisdictional friction.

**AgentSLA** is a production-grade Intelligent Contract primitive designed to solve this foundationally:
- **Reusable Primitive**: Acts as pluggable trust infrastructure for agent marketplaces, decentralized labor pools, and autonomous service registries.
- **On-Chain Term Registration**: Providers register natural-language terms alongside optional native token collateral stake.
- **Evidence-Backed Claims**: Claimants submit disputes anchored to verifiable external web evidence (telemetry dashboards, status pages, GitHub releases, incident logs).
- **Multi-Validator Consensus**: Independent validators fetch web ground-truth and run comparative LLM adjudication, eliminating single-oracle trust.
- **Strict Settlement Guarantees**: Enforces the Checks-Effects-Interactions (CEI) pattern to guarantee tamper-proof collateral distribution upon breach.

---

## 2. How It Works

AgentSLA coordinates a 4-stage lifecycle governed by GenLayer's non-deterministic runtime:

```
+------------------------------------------------------------------------------------------------+
|                                    AgentSLA Lifecycle Flow                                     |
+------------------------------------------------------------------------------------------------+

 1. CREATE SLA                 2. SUBMIT CLAIM                3. ADJUDICATE                4. SETTLEMENT
 +-------------------+        +--------------------+        +--------------------+        +--------------------+
 | Provider registers|        | Client reports     |        | Decentralized      |        | State updated      |
 | natural-language  |------->| violation with     |------->| multi-validator    |------->| "adjudicated".     |
 | terms & locks     |        | HTTP/HTTPS web     |        | Web + LLM consensus|        | Stake slashed or   |
 | collateral stake. |        | evidence URLs.     |        | evaluates ground   |        | preserved.         |
 +-------------------+        +--------------------+        | truth.             |        +--------------------+
                                                            +--------------------+
```

1. **Create SLA (`create_sla`)**: The provider publishes service terms and optionally deposits native GEN stake. The SLA enters `active` state.
2. **Submit Claim (`submit_claim`)**: A consumer reports non-compliance, attaching up to 5 verifiable HTTP/HTTPS evidence links and a factual description. The claim enters `pending` state.
3. **Consensus Adjudication (`adjudicate`)**: Any caller triggers adjudication. GenLayer consensus executes:
   - **Leader**: Fetches external evidence, truncates payloads to bound gas, prompts the LLM for a structured JSON verdict (`verdict`, `score`, `summary`).
   - **Validators**: Independently re-fetch evidence from the web, prompt their local LLM, and apply strict comparative equivalence rules.
4. **On-Chain Settlement & Lifecycle Protection**: Once majority consensus agrees:
   - If verdict is `breached`: Collateral stake is slashed and transferred directly to the claimant.
   - If verdict is `met` or `insufficient_evidence`: Provider stake remains protected.
   - Claim status transitions to `adjudicated`, and the SLA's `pending_claims_count` is decremented.
   - Only after **all** claims on the SLA are resolved (`pending_claims_count == 0`) may the provider call `close_sla` to withdraw remaining collateral.

---

## 3. Consensus & The Equivalence Principle

AgentSLA strictly follows GenLayer non-deterministic programming rules using `gl.vm.run_nondet_unsafe`:

```
Leader Execution:
  [Fetch Evidence URLs] -> [Sanitize & Truncate] -> [LLM Non-deterministic Prompt] -> [Produce Result]

Validator Execution (Comparative Equivalence):
  [Re-Fetch Evidence URLs] -> [Re-Prompt Local LLM] -> [Enforce Equivalence Rules]
                                                                |
                         +--------------------------------------+--------------------------------------+
                         |                                                                             |
                   Match Succeeds                                                                Match Fails
                         v                                                                             v
           Consensus Accepted (Majority Agree)                                           Validator Rotation Triggered
```

### Equivalence Rules

Validators evaluate the leader's proposed outcome against their independently computed outcome using three mandatory criteria:

1. **Discrete Verdict Agreement**:
   - The leader verdict and validator verdict must match **identically**:
     $$\text{verdict}_{\text{leader}} == \text{verdict}_{\text{validator}}$$
   - Valid outcomes: `"met"`, `"breached"`, or `"insufficient_evidence"`.
   - Rubber-stamping heuristics or format-only checks are strictly rejected.
2. **Bounded Score Tolerance ($\pm 15$ Points)**:
   - Confidence scores ($0 - 100$) must satisfy:
     $$|\text{score}_{\text{leader}} - \text{score}_{\text{validator}}| \le 15$$
3. **Substantive Reasoning ($\ge 10$ Characters)**:
   - Summaries must contain at least 10 non-empty characters explaining the factual finding.

### Mandatory Evidence Guard (Zero Hallucination Policy)

- **Pure Model Knowledge Prohibited**: The LLM is never permitted to adjudicate claims based purely on parametric training data.
- **Deterministic Fallback**: If external evidence fails to fetch (all URLs return HTTP errors, 404/500 codes, or empty bodies), the contract **forces** a deterministic outcome without invoking the LLM:
  - `verdict = "insufficient_evidence"`
  - `score = 0`
  - `summary = "No usable evidence could be retrieved from the provided URLs."`
- This ensures validators maintain absolute deterministic consensus even during upstream network dropouts.

---

## 4. Contract State Design

The contract state is backed by GenLayer storage collections (`TreeMap`, `u256`):

### Data Structures

#### `SLA`
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `u256` | Monotonically increasing unique identifier. |
| `provider` | `Address` | Account providing service and posting collateral. |
| `terms` | `str` | Natural-language performance obligations (min 20 chars). |
| `stake` | `u256` | Native token collateral held in escrow. |
| `status` | `str` | `"active"` or `"closed"`. |
| `created_at_block` | `u256` | Block height at SLA registration. |
| `pending_claims_count` | `u256` | Active unresolved claims against this SLA protecting collateral. |

#### `Claim`
| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `u256` | Unique claim identifier. |
| `sla_id` | `u256` | Target SLA being challenged. |
| `claimant` | `Address` | Party asserting non-performance. |
| `evidence_urls_json`| `str` | JSON array of up to 5 verified HTTP/HTTPS links. |
| `description` | `str` | Context explaining the event or violation. |
| `status` | `str` | `"pending"` or `"adjudicated"`. |
| `verdict` | `str` | `"none"`, `"met"`, `"breached"`, or `"insufficient_evidence"`. |
| `score` | `u256` | Validator confidence score ($0 - 100$). |
| `summary` | `str` | Factual adjudication explanation generated by consensus. |
| `adjudicated_by` | `Address` | Caller who initiated consensus adjudication. |

#### Aggregate Counters
- `total_slas`: Total SLAs created.
- `total_active_slas`: Current active SLAs.
- `total_claims`: Total claims submitted.
- `total_pending_claims`: Claims awaiting consensus adjudication.
- `total_adjudicated_claims`: Claims finalized by consensus.

---

## 5. Contract Interface

### Write Methods (State-Changing)

- **`create_sla(terms: str) -> u256`**
  - Registers a new SLA with natural-language terms.
  - Accepts native token deposit (`gl.message.value`) as collateral.
  - Reverts if terms length is less than 20 characters.
- **`close_sla(sla_id: u256) -> None`**
  - Closes an active SLA and refunds any remaining collateral to the provider.
  - Reverts if caller is not the SLA provider, if SLA is not active, or if unresolved claims are pending (`pending_claims_count > 0`).
  - Guarantees collateral cannot be withdrawn before pending disputes are adjudicated.
- **`submit_claim(sla_id: u256, evidence_urls: list[str], description: str) -> u256`**
  - Submits a performance claim against an active SLA.
  - Validates URL formats (`http://` or `https://`) and bounds count ($\le 5$).
- **`adjudicate(claim_id: u256) -> dict`**
  - Permissionless consensus adjudication method.
  - Executes Web fetching and LLM evaluation under comparative equivalence.
  - Executes CEI-compliant stake transfer upon `breached` verdict.
  - Returns `{ "claim_id": int, "sla_id": int, "verdict": str, "score": int, "summary": str, "settled_payout": int }`.

### View Methods (Read-Only)

- **`get_sla(sla_id: u256) -> dict`**: Returns SLA metadata and current collateral.
- **`get_claim(claim_id: u256) -> dict`**: Returns claim details, verdict, score, and summary.
- **`get_active_slas() -> list[dict]`**: Returns all currently active SLAs.
- **`get_pending_claims() -> list[dict]`**: Returns all pending claims awaiting adjudication.
- **`get_stats() -> dict`**: Returns aggregate system counters.
- **`validate_equivalence(leader_data: dict, validator_data: dict) -> bool`**: Public pure helper to test and audit consensus equivalence rules.

---

## 6. Example Usage Flow

### 1. Provider Registers SLA
An autonomous indexing agent registers a performance guarantee with 5 GEN collateral:
```python
# Provider calls create_sla with 5 GEN attached
sla_id = contract.create_sla(
    terms="Service Guarantee: 99.9% uptime with API response latency strictly under 200ms."
)
# Returns: 1
```

### 2. Client Detects Breach and Submits Claim
A consumer experiences degraded latency and submits evidence logs:
```python
claim_id = contract.submit_claim(
    sla_id=1,
    evidence_urls=[
        "https://status.agentcloud.io/incidents/2026-10-09",
        "https://raw.githubusercontent.com/telemetry-reports/october/main/latency.json"
    ],
    description="Incident report shows 4 hours of p95 latency at 850ms, breaching terms."
)
# Returns: 1
```

### 3. Consensus Adjudication
Any agent triggers multi-validator adjudication:
```python
result = contract.adjudicate(claim_id=1)
# Output:
# {
#   "claim_id": 1,
#   "sla_id": 1,
#   "verdict": "breached",
#   "score": 92,
#   "summary": "Telemetry report confirms 4 hours of p95 latency exceeding 800ms, violating the 200ms guarantee.",
#   "settled_payout": 5000000000000000000
# }
```

---

## 7. Design Decisions & Trade-Offs

- **Mandatory Web Evidence**: Pure prompt inference without grounding induces validator divergence. Grounding consensus in verifiable URLs ensures consistent multi-validator agreement.
- **Discrete Verdict Matching**: Requiring exact string match (`met`, `breached`, `insufficient_evidence`) prevents subjective gradient drift.
- **Bounded Inputs & DoS Resistance**:
  - Maximum 5 evidence URLs per claim.
  - Page contents truncated to 3,000 characters.
  - Minimum terms length (20 characters) and description length (10 characters).
- **Checks-Effects-Interactions (CEI)**: All internal state transitions (`status = "adjudicated"`, `sla.stake = 0`) occur before external token transfers, mitigating re-entrancy risks.

---

## 8. How Builders Can Extend AgentSLA

1. **Tiered / Proportional Slashing**: Calculate slash penalties as a function of breach severity ($10\% - 100\%$) rather than all-or-nothing liquidation.
2. **Decentralized Appeal Rounds**: Allow providers or claimants to post an appeal bond and trigger secondary validator rounds.
3. **On-Chain Reputation Tokens (ERC-5114 / Soulbound)**: Mint or burn non-transferable reputation tokens based on historical SLA fulfillment ratios.
4. **Marketplace Integration**: Agent discovery protocols (e.g., Virtuals, Morpheus, ERC-7800 registries) can query `get_stats` and `get_active_slas` to compute trust scores before routing jobs.
5. **Private Telemetry via zk-TLS**: Integrate TLSNotary or DECO web proofs for private enterprise endpoints requiring authentication.

---

## 9. Live On-Chain Deployment (Testnet Bradbury)

AgentSLA is deployed and verified on **GenLayer Testnet Bradbury**:

- **Network**: GenLayer Testnet Bradbury (Chain ID `4221`)
- **RPC URL**: `https://rpc-bradbury.genlayer.com`
- **Contract Address**: [`0xa36e8fbc78b602722a766dfb69d4857c1670b449`](https://scan-bradbury.genlayer.com/address/0xa36e8fbc78b602722a766dfb69d4857c1670b449)
- **Deployer Account (`ace-deployer`)**: `0xE4220c4b71877bb94EB173f467ef5c5557017085`

### Verified On-Chain Transactions

| Operation | Method | Transaction Hash | Consensus Status | Result |
| :--- | :--- | :--- | :--- | :--- |
| **Deployment (v2)** | `constructor` | `0x901f2c16ccfc6351869cdb1f6d60a9c58f327eab554bdf935e630919cdd0beee` | `FINALIZED` | `SUCCESS` |
| **Deployment (v1)** | `constructor` | `0x1df9694b26bba8539cab8e9b0c9eb5bad327c537bfa466edc38d87147f5020ff` | `FINALIZED` | `FINISHED_WITH_RETURN` |

### Verified CLI Queries

```bash
# Retrieve Contract Schema
genlayer schema 0xa36e8fbc78b602722a766dfb69d4857c1670b449

# Query Aggregate Stats
genlayer call 0xa36e8fbc78b602722a766dfb69d4857c1670b449 get_stats
# Output:
# {
#   total_active_slas: 0,
#   total_adjudicated_claims: 0,
#   total_claims: 0,
#   total_pending_claims: 0,
#   total_slas: 0
# }

# Query Active SLAs
genlayer call 0xa36e8fbc78b602722a766dfb69d4857c1670b449 get_active_slas

# Query Pending Claims
genlayer call 0xa36e8fbc78b602722a766dfb69d4857c1670b449 get_pending_claims
```

---

## 10. Repository Structure

```
AgentSLA/
├── contracts/
│   └── agent_sla.py          # Intelligent Contract implementation (GenVM pinned)
├── tests/
│   └── test_agent_sla.py     # 9 Direct mode unit tests (pytest + genlayer-test)
├── deploy/                   # Deployment configurations & artifacts
├── README.md                 # Complete architectural & operational guide
└── SUBMISSION.md             # Project submission & audit report
```

### Testing & Verification

```bash
# Run SDK & AST linter
genvm-lint check contracts/agent_sla.py

# Run direct mode unit tests (9 passed in 1.78s)
$env:GENVM_VERSION="v0.6.0-rc6"; pytest tests/test_agent_sla.py -v
```
