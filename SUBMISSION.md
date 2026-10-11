# AgentSLA – GenLayer Intelligent Contract Submission

## One-Sentence Summary
AgentSLA is a reusable GenLayer Intelligent Contract primitive that provides verifiable, decentralized Service Level Agreements (SLAs) for AI agents through multi-validator LLM consensus over external web evidence.

---

## Purpose
In the emerging agentic economy, autonomous agents require verifiable contracts to buy, sell, and coordinate services. However, performance criteria (e.g., uptime, p95 latency, output format schemas, response quality) are fundamentally subjective and cannot be evaluated by deterministic smart contracts.

AgentSLA solves this by allowing providers and consumers to define natural-language SLAs, lock stakes, and submit web-verifiable claims that are settled permissionlessly via decentralized AI validators.

---

## How Consensus is Used
AgentSLA demonstrates production-grade GenLayer consensus patterns:
1. **Bounded Web I/O**: The leader fetches external evidence (logs, status dashboards, telemetry) with strict URL counts ($\le 5$) and content truncation ($\le 3,000$ characters).
2. **Missing Evidence Safety Guard**: If no evidence is obtainable, the contract deterministically forces `verdict = "insufficient_evidence"`, preventing ungrounded LLM hallucinations.
3. **Structured Non-Deterministic Prompting**: `gl.nondet.exec_prompt` produces a structured JSON decision (`verdict`, `score`, `summary`).
4. **Independent Comparative Validator**: The validator independently re-fetches the evidence and evaluates the prompt. Consensus requires:
   - **Exact verdict match** (`met`, `breached`, `insufficient_evidence`).
   - **Confidence score tolerance** ($\pm 15$ points).
   - **Substantive explanation** ($\ge 10$ characters).
5. **Checks-Effects-Interactions & Lifecycle Protection**: All storage modifications occur after consensus succeeds, before any stake payouts. Collateral is strictly locked and cannot be withdrawn or closed via `close_sla` while any claims remain pending (`pending_claims_count > 0`), preventing premature collateral drains before breach adjudication.

---

## Why It Is Strong / Not a Demo
- **True Infrastructure Primitive**: Designed as a generic layer that autonomous agent marketplaces, freelance agent pools, or DeFi agent protocols can integrate.
- **Collateral Lifecycle Integrity**: Fully guards against frontrunning and premature withdrawals by tracking unresolved claims per SLA, guaranteeing collateral is preserved until all claims are settled.
- **Robust Equivalence Principle**: Does not rubber-stamp the leader. Enforces independent evaluation with discrete verdict matching and bounded numerical tolerance.
- **Production Safety Standards**: Pinned GenVM runner hash (`py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`), validated with `genvm-lint`, zero storage writes inside non-deterministic blocks, and complete test suite passing in direct mode.

---

## On-Chain Deployment & Verification
- **Network**: GenLayer Testnet Bradbury (Chain ID `4221`)
- **RPC URL**: `https://rpc-bradbury.genlayer.com`
- **Contract Address**: [`0xa36e8fbc78b602722a766dfb69d4857c1670b449`](https://scan-bradbury.genlayer.com/address/0xa36e8fbc78b602722a766dfb69d4857c1670b449)
- **Deployer (`ace-deployer`)**: `0xE4220c4b71877bb94EB173f467ef5c5557017085`
- **Deployment Transaction Hash**: `0x901f2c16ccfc6351869cdb1f6d60a9c58f327eab554bdf935e630919cdd0beee` (Status: `FINALIZED`, Result: `SUCCESS`)
- **Initial Deployment (v1)**: `0xB0fe13b5A5FEa9b39D217184606430d8d9bB11ee` (Tx: `0x1df9694b26bba8539cab8e9b0c9eb5bad327c537bfa466edc38d87147f5020ff`)

---

## Files Included

- [`contracts/agent_sla.py`](file:///C:/Users/NO%20GO%20NO/AgentSLA/contracts/agent_sla.py): Core Intelligent Contract implementation.
- [`tests/test_agent_sla.py`](file:///C:/Users/NO%20GO%20NO/AgentSLA/tests/test_agent_sla.py): Direct mode test suite covering SLA lifecycle, input validation, web mocks, LLM mocks, failed evidence handling, and the Equivalence Principle.
- [`README.md`](file:///C:/Users/NO%20GO%20NO/AgentSLA/README.md): Complete architecture documentation, interface reference, and extension guide.
- [`SUBMISSION.md`](file:///C:/Users/NO%20GO%20NO/AgentSLA/SUBMISSION.md): Submission overview.

