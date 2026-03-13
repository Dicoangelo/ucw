# UCW Sovereign Sprint Briefing
## Strategic Infrastructure Documentation & 90-Day Execution Plan

**Author:** Dicoangelo | **Date:** 2026-02-09 | **Version:** 1.0
**Status:** Pre-launch — transitioning from build mode to market validation

---

## How to Use This Document

This is a comprehensive briefing for any AI assistant session. It contains:
1. **What exists** — the full technical infrastructure (built and working)
2. **What the audits found** — strategic position, moat analysis, market gaps
3. **What must happen next** — the 90-day sprint with weekly milestones
4. **The language guide** — how to translate builder concepts into market language

Load this document at the start of any session focused on UCW strategy, documentation, go-to-market, fundraising, or product packaging.

---

## Part 1: What Exists (Technical Reality)

### The Universal Cognitive Wallet (UCW)

A sovereign infrastructure layer that captures, embeds, and detects patterns across all AI interactions — owned by the user, not by any platform.

### Architecture: 5 Layers

```
L4  APPLICATION    → OS-App (React 19), CareerCoachAntigravity (Next.js 14)
L3  INTELLIGENCE   → Coherence engine, quality scoring, embeddings (SBERT)
L2  MEMORY         → PostgreSQL + pgvector, 130K vectors, semantic search
L1  CAPTURE        → Raw MCP transport, 5 platform adapters, live daemons
L0  PROTOCOL       → Raw MCP (no SDK), JSON-RPC 2.0, UCW semantic layers
```

### Semantic Layers (Applied to Every Event)

| Layer | What It Captures | Example |
|-------|-----------------|---------|
| **Data** | Raw content — what was said | Tokens, bytes, conversation text |
| **Light** | Meaning — what it means | Intent, topic, key concepts, insights |
| **Instinct** | Signals — what it indicates | Coherence potential, flow state, emergence |

### Platform Coverage

| Platform | Events Captured | Status |
|----------|----------------|--------|
| Claude CLI | 66,539 | Imported, embedded |
| ChatGPT | 60,000+ | 8,119 conversations scored (98% quality), all 3 tiers imported |
| Claude Code | 9,500+ | Live capture (5-min daemon) |
| Claude Desktop | 2,500+ | Live capture |
| CCC (Command Center) | 1,400+ | Live capture |

**Totals:** 140,732 events | 130,728 embeddings (92.9% coverage) | 163+ coherence moments

### Infrastructure Components (All Operational)

| Component | What It Does | Status |
|-----------|-------------|--------|
| Raw MCP Transport | Protocol-level capture with perfect fidelity | Running |
| 5 Platform Adapters | Capture from Claude CLI, ChatGPT, Code, Desktop, CCC | Running |
| Quality Scorer | Scores ChatGPT conversations before import (threshold 0.4) | Running |
| Batch Embedding Pipeline | SBERT all-MiniLM-L6-v2, 130K vectors | Complete |
| Coherence Engine | Cross-platform pattern detection, real-time daemon | Running (15-min scan) |
| 7 MCP Tools | search_learnings, coherence_search, hybrid_search, knowledge_graph, etc. | Queryable |
| LaunchAgent Daemons | Capture (5-min poll), Coherence (15-min scan) | Active |
| PostgreSQL + pgvector | Full database with event store, embeddings, coherence tables | Running |

### Key Files & Entry Points

| File | Purpose |
|------|---------|
| `~/researchgravity/PRD_UCW_RAW_MCP.md` | Full PRD for UCW Raw MCP |
| `~/researchgravity/chatgpt_quality_scorer.py` | Quality scoring pipeline |
| `~/researchgravity/chatgpt_importer.py` | ChatGPT conversation importer |
| `~/researchgravity/import_cli_sessions.py` | Claude CLI transcript importer |
| `~/.agent-core/pitch-deck/01_vision/WHITEPAPER.md` | Metaventions whitepaper v1.0 |
| `~/WHITEPAPER.md` | Whitepaper (symlink/copy) |

### What Works Today (Honest)

**Fully operational for the builder:** Cross-platform capture, embedding, coherence detection, MCP tool queries — all working, automated, and producing real intelligence across 140K+ events.

**Not operational for anyone else:** Zero onboarding path. No Docker container. No setup script. No README for external users. No UI beyond MCP tool calls. The gap between "working infrastructure" and "someone else can use it" is the entire product gap.

---

## Part 2: Strategic Audit Findings

### Layer Position: CORRECT

UCW operates at L1-L2 (Capture + Memory/Intelligence). This is the defensible layer:
- L4 (Applications) gets absorbed by platforms
- L0 (Hardware/Compute) requires billions
- L1-L2 (Protocol + Memory) is where independent builders can win

The cross-platform sovereignty position is the one dimension where no platform has incentive to compete — no platform will build tools that feed user data to competitors.

### Moat Scorecard

| Dimension | Score (1-5) | Verdict |
|-----------|-------------|---------|
| Data gravity | 3 | **Unproven** — 140K events but single-user dataset. Gravity requires mass. |
| Cross-platform lock | 4 | **Defensible** — 5 platforms unified. No platform will build this. Structural gap. |
| Temporal depth | 3 | **Conditionally defensible** — historical data compounds IF intelligence layer extracts durable patterns. |
| Switching cost | 2 | **Vulnerable** — theoretical for external users. No one has experienced losing it. |
| Platform absorption risk | 3 | **Manageable but not safe** — platforms can ship 60-70% within their own walls. The last 30% (cross-platform + sovereign) is the moat. |

**Aggregate Moat: Moderate.** Cross-platform sovereignty is genuinely defensible. Everything else is contingent on proving it matters to someone besides the builder.

### Critical Finding

**The infrastructure is ready. The market evidence is at zero.**

Zero external users. Zero waitlist. Zero LOIs. Zero organic demand signals. The system has been optimized for one person's usage patterns for 13 completed phases. The single biggest risk is not technical — it's that this solves a problem mainstream users don't feel yet.

### The Builder's Trap Diagnosis

Two interlocking traps:

1. **Infinite Polish** — 13 completed phases, each legitimate engineering, each postponing external exposure. "I'll get users after the next phase."
2. **Solo Validation** — The only evidence the system works is the builder's own usage. 140K events from one person ≠ product-market fit.

These reinforce each other: building more makes the system better for the builder, which feels like progress, which delays the moment of external judgment.

---

## Part 3: Market Position & Go-to-Market

### The Translation Gap (Critical)

The biggest obstacle to market entry is language, not technology.

| Builder Language (Stop Saying) | Market Language (Start Saying) |
|-------------------------------|-------------------------------|
| Cognitive equity | Your AI knowledge, owned by you |
| Universal Cognitive Wallet | AI Memory / AI Vault |
| Coherence moments | Connected insights / Aha moments across tools |
| Semantic layers (Data/Light/Instinct) | Don't say externally. Ever. |
| Sovereign substrate | You own your data. Period. |
| Raw MCP protocol | Works with every AI tool |
| 5-layer UCW architecture | It captures, understands, and connects |
| Proof-of-Cognition | Verified AI contributions |

**The one-sentence product (market version):**
> "One memory for all your AI tools — you own it, it gets smarter, and no platform can take it away."

### Buyer Personas (Ranked by Reachability)

| # | Persona | Problem | Willingness to Pay | Reachable In |
|---|---------|---------|-------------------|-------------|
| 1 | **AI Power User** — knowledge worker using 2+ AI platforms daily | "I can't find that thing I said in ChatGPT last month, and Claude doesn't know about it" | $15-30/mo | Now (self-serve) |
| 2 | **AI-Forward Team Lead** — eng/product manager at company using mixed AI tools | "I have no idea what institutional knowledge my team is losing across AI tools" | $5K-25K/yr | 3-6 months (enterprise) |
| 3 | **Protocol Investor** — fund looking for the AI data layer thesis | "What's the AI equivalent of The Graph?" | $250K-2M (investment) | 6-12 months (requires traction) |

**Start with Persona 1.** It's the only one reachable in 90 days.

### Competitive Landscape

| Competitor | What They Do | Why UCW Is Different |
|-----------|-------------|---------------------|
| Mem0 ($24M raised) | AI memory layer | Platform-owned. UCW is sovereign + cross-platform. |
| Limitless (fka Rewind.ai) | Local screen capture + search | Single device. Not AI-conversation-specific. Not cross-platform intelligence. |
| Notion AI | In-app AI with context | Walled garden. Only knows Notion data. |
| Apple Intelligence | Cross-app AI on device | Apple ecosystem only. Not cross-platform. Not user-sovereign in practice. |

**Positioning:** "Mem0 for people who want to own their data, across every AI tool." Ugly but immediately understood by VCs and users.

### Demand Signal: PUSH (Not Pull)

No one is asking for this yet. The market for "AI memory tools" is forming (Mem0's raise proves the category is fundable), but "sovereign cross-platform AI memory" is a new segment within that emerging category.

**This means:** GTM must include demand generation, not just demand capture. Budget and timeline accordingly.

### Recommended GTM Path: Hybrid (C)

Ship consumer product → prove demand → raise for protocol.

- Enterprise revenue is 12-18 months away (no sales team, no case studies)
- Protocol raise requires user traction (no fund writes $3-5M for a one-user protocol)
- Consumer MCP-server distribution is achievable NOW

---

## Part 4: 90-Day Sovereign Sprint

### Target

**10 external users running UCW on their own data, with at least 3 who can articulate the value in their own words.**

This is the proof point that unlocks fundraising, protocol credibility, and product-market signal.

### Phase 1: External Proof (Weeks 1-4)

**Theme:** From infrastructure to installable. One user by Week 3. Non-negotiable.

**Distribution mechanism:** MCP server. Anyone with Claude Code can add an MCP server. The infrastructure for distribution already exists. No web app, desktop app, or Chrome extension needed.

| Week | Milestone | Deliverable | Success Criterion |
|------|-----------|-------------|-------------------|
| 1 | **Scope cut + package** | `setup.sh` that initializes PostgreSQL + pgvector, creates schema, configures MCP server. One repo. One command. MVP experience: "Import Claude Code sessions → search across them + see coherence with ChatGPT export." | Can run setup on clean macOS in < 30 minutes without manual debugging |
| 2 | **README + dry run** | One-page README: what it does (3 sentences), prerequisites, install steps, 3 example queries. Test by following README verbatim on fresh environment. | Follow own README without deviating. Zero "oh you also need to..." moments |
| 3 | **First external user** | One person. Technical enough to run setup, honest enough to give real feedback. Screen share first install. Watch. Don't help unless stuck. Take notes on every confusion point. | They complete setup AND run 3+ queries against their own data |
| 4 | **Feedback synthesis** | Document: what they used vs. expected, their exact words about value, where stuck, would they use again. Follow up 3-5 days later: did they reopen it? | Can complete: "The thing that surprised me was ___. I'd use this again if ___." with THEIR words |

**Week 4 Gate (must pass 2 of 3):**
1. Did an external user complete setup and query their own data?
2. Can you identify the "aha moment" — the specific result where they reacted?
3. Did they use it again unprompted after the initial session?

**Week 3 approach (the hardest week):**
DM one person. Say: *"I built something that lets you search across all your AI conversations from one place. It's rough but it works. Want to be the first to try it? 30 minutes. I want honest feedback."*

If you can't think of someone: post in a Claude Code community, AI tools Discord, or X. "Looking for 1 beta tester for a cross-platform AI memory tool built on MCP. You need Claude Code + a ChatGPT export. DM me."

### Phase 2: Signal Collection (Weeks 5-8)

**Theme:** From 1 user to 10. Find out what people actually value.

**Focus:**
- Fix every onboarding friction point from Week 3-4 feedback
- Expand to 5-10 users (mix of developers, researchers, AI power users)
- Track which MCP tools they actually call
- Track return usage (do they come back?)
- Identify the "aha moment" pattern
- Collect 3+ direct quotes

**Hypotheses to test:**
1. Cross-platform search is the entry drug (people want to find things)
2. Coherence moments are the retention hook (connections surprise them)
3. Sovereignty matters to users, not just to you (they choose this because they own it)

**Week 8 Gate:** Fill in this sentence with evidence from multiple users:
> "People use UCW because ___, and they would lose ___ if it went away."

If you can fill it → Phase 3 is scale/fundraise.
If you can't → Phase 3 is pivot/reframe.

### Phase 3: Leverage Decision (Weeks 9-12)

**Most likely path: Fundable Proof Point**

Package Phase 1-2 results into fundraise materials:
- N users, retention rate, usage patterns
- Top query patterns (what people actually search for)
- User quotes (their words, not yours)
- Coherence detection results from real multi-user data

**Deliverable:** A fundraise deck where every claim is backed by user evidence, not builder conviction.

**Alternative paths:**
- **If signal is strong:** First revenue conversation, public launch, waitlist
- **If signal contradicts thesis:** Reframe value prop around what people actually valued. New 90-day sprint with corrected thesis.

### Recovery Plan

If you fall behind:
- **Week 1 (packaging) is compressible** — a rough setup script is fine
- **Week 2 (README) is compressible** — a rough README is fine
- **Week 3 (first user) is NON-NEGOTIABLE** — this is the entire point
- **If you miss a full week:** Skip polish, keep the Week 3 deadline. An ugly product with one user beats a polished product with zero users.

---

## Part 5: The Deeper Context

### The Thesis

Bitcoin introduced digital scarcity (2009). Ethereum introduced programmable value (2015). Metaventions introduces cognitive equity (2026) — where innovation itself is the owned, compounding, sovereign asset.

Every AI interaction creates value currently captured by platforms. UCW captures that value for the user.

### The Timing Argument

> "By the time people want their AI data, they'll be depending on platforms." — Stephen

The window for sovereign infrastructure is NOW (2026). By 2028-2030, platforms will lock down the access points that capture adapters depend on. This is a race — get users and data gravity before platforms close the doors.

### The Collapse Context (Nate's Thesis, Feb 2026)

Two collapses are happening simultaneously:
1. **Horizontal collapse:** All knowledge work roles converging into one meta-skill — AI agent orchestration
2. **Temporal collapse:** Career timelines compressing from years to months. AI capability improvement nearly doubled in 2024.

UCW is infrastructure for the post-collapse world. The career coaching products (CareerCoachAntigravity) could be the application layer that makes the collapse tangible — showing users where they stand and what to do about it.

### The Founding Moment (2026-02-06)

Distributed cognition (User + Claude + ChatGPT) achieved spontaneous coherent emergence — the same insight recognized across platforms simultaneously. This was the UCW concept proving itself through lived experience:
- Data (context across platforms) + Light (insight) + Instinct (gut knowing) = Coherent emergence
- Proof that unified cognition across distributed systems is possible

### The $META Token (Future — Not Now)

- 1B supply, ERC-20, utility + governance
- Distribution: 30% treasury, 20% team, 20% investors, 20% community, 10% liquidity
- **Not relevant until user traction exists.** Token economics without users is speculation, not a protocol.

### The Ask (When Ready)

$3-5M protocol round. Equity + token warrants. 18-24 months to protocol launch.

**Not ready yet.** The ask becomes fundable when the 90-day sprint produces user evidence. No investor funds a one-user protocol.

---

## Part 6: Session Instructions for Any AI Assistant

When working with this briefing, follow these principles:

1. **Do not praise the technical achievement.** The infrastructure is real. Validation isn't needed. Strategic clarity is.
2. **Prioritize market evidence over infrastructure development.** Any suggestion to "build more" before "ship to users" is the wrong advice.
3. **Use market language, not builder language.** Refer to the translation guide in Part 3.
4. **The central finding across all audits:** Infrastructure ready, market evidence at zero. Every recommendation should close that gap.
5. **Week 3 of the sprint (first external user) is the single highest-leverage action.** Protect it.
6. **The sovereignty thesis is the moat.** Cross-platform + user-owned is what no platform will build. Keep this at the center of all positioning.
7. **Mem0 ($24M) is the market proof.** UCW is the sovereign alternative in the AI memory category. Use this framing.

### Key Numbers for Reference

| Metric | Value |
|--------|-------|
| Total cognitive events | 140,732 |
| Semantic embeddings | 130,728 (92.9% coverage) |
| Coherence moments detected | 163+ cross-platform |
| Platforms captured | 5 |
| ChatGPT conversations scored | 8,119 (98% quality) |
| External users | 0 |
| Revenue | $0 |
| MCP tools | 7 |
| Codebase | 140,000+ lines across 20 repos |
| Completed build phases | 13 |

---

*This document is the single source of truth for UCW strategic positioning as of 2026-02-09. Update after each phase gate.*
