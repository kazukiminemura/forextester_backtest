# AI Agentの次に来るAIサービス

- Audience: 事業・プロダクト企画者
- Date: 2026-09-03
- Scope: 世界市場、2026-2035年。デジタルサービスを主軸に、身体性AIまで比較。
- Assumption: 「次」はモデル名称ではなく、顧客が認識し対価を払うサービス形態を指す。

## Executive answer

最有力は「委任型AI OS / Autonomous Outcome Service」。単発指示に応答する一体のAgentではなく、ユーザーや企業の目標、長期文脈、権限、予算、制約を保持し、複数の専門Agent・人・アプリ・将来的にはロボットを編成して、継続的な成果に責任を持つサービスである。消費者向けにはPersonal AI / Life OS、企業向けにはAI-operated functionまたはDigital Workforceとして現れる。課金単位は席数やトークンから、解決・予約・回収・売上など検証可能な成果へ移る。

## Why this is the leading hypothesis

1. Autonomy is lengthening but still supervised. Anthropic observed longest Claude Code turns rising from under 25 to over 45 minutes in three months; experienced users auto-approve more but also interrupt more. This favors risk-tiered supervision over unconditional autonomy.
2. Interoperability rails are converging. MCP connects models to tools/data; A2A connects agents; UCP/AP2 add commerce and cryptographic authorization. This enables an orchestration layer above individual agents.
3. Persistent personal context is becoming product infrastructure. OpenAI describes memory synthesis over multi-year histories; Google and Apple describe assistants using screen, camera, messages, email, and cross-app actions.
4. Commercial units are shifting from software access to completed work. Intercom charges only for defined outcomes and Zendesk announced verified outcome pricing; Salesforce charges per action. This is direct evidence of movement toward outcome-as-a-service.
5. Trust infrastructure is becoming a separate layer. NIST is developing an agent identity/authorization project; Visa specifies signed agent intent; W3C Verifiable Credentials 2.0 standardizes machine-verifiable credentials.
6. Commercial traction exists but broad scaling lags intent. Salesforce reported Agentforce ARR of $800 million and more than 29,000 deals in its FY2026 proxy, while McKinsey's 2025 survey found only 23% of respondents were scaling an agentic system anywhere in their enterprise.

## Ranked forecast

### 1. 2026-2028: Supervised AI delegation layer

Persistent memory, cross-app action, recurring work, specialist-agent orchestration, and approvals at consequential steps. The dominant product promise changes from “use this agent” to “delegate this responsibility.”

### 2. 2027-2030: Outcome-as-a-Service / AI-operated functions

Vendors assume bounded operational responsibility for customer support, finance operations, sales qualification, procurement, compliance preparation, and software maintenance. Contracts and pricing depend on verified results, with exceptions and human escalation explicitly defined.

### 3. 2028-2032: Personal AI OS / fiduciary-like delegate

A user-controlled layer manages identity, preferences, credentials, calendars, communications, purchases, and negotiations across providers. It is proactive but interruptible, with revocable scopes, spending limits, audit logs, and selective disclosure.

### 4. 2030-2035: Embodied service networks

The same delegation layer dispatches robots for logistics, inspection, cleaning, care support, and field work. Robotics is later because hardware cost, maintenance, physical safety, insurance, and dexterity reliability make deployment slower than digital services.

## Disconfirming evidence and limits

- Consumer Claude use in late 2025 was still more augmentation (52%) than automation (45%), so people may prefer collaboration to full delegation.
- A 2025 METR RCT found early-2025 AI tools made experienced open-source developers 19% slower in the studied setting, despite perceived speedups.
- OpenAI's early CUA scored 38.1% on OSWorld; prompt injection remains an unsolved system problem whose damage must be constrained even when attacks succeed.
- Multi-agent systems may improve quality but Anthropic reports roughly 15x chat token use, limiting economics outside high-value tasks.
- World models and robotics remain capability enablers rather than proof of mass-market services; several robot dexterity tasks remain below 50% success.

## Falsification tests

By 2028-2030, lower confidence materially if: interoperable revocable delegation credentials are not adopted by major OS/payment ecosystems; agent fraud/chargeback remains materially worse than human commerce; outcome-based contracts retreat to seat/token pricing; proactive assistants show high disablement/churn; or high-value agents cannot achieve auditable success under bounded permissions.

## Claim-to-source ledger

- Anthropic, “Measuring AI agent autonomy in practice,” 2026-02-18. https://www.anthropic.com/news/measuring-agent-autonomy
- Anthropic, “Anthropic Economic Index: New building blocks for understanding AI use,” 2026-01-15. https://www.anthropic.com/research/economic-index-primitives
- METR, “Time Horizon 1.1,” 2026-01-29. https://metr.org/blog/2026-1-29-time-horizon-1-1/
- METR, “Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity,” 2025. https://metr.org/Early_2025_AI_Experienced_OS_Devs_Study-paper.pdf
- Linux Foundation, “Launches the Agent2Agent Protocol Project,” 2025-06-23. https://www.linuxfoundation.org/press/linux-foundation-launches-the-agent2agent-protocol-project-to-enable-secure-intelligent-communication-between-ai-agents
- Anthropic, “Donating the Model Context Protocol and establishing the Agentic AI Foundation,” 2025-12-09. https://www.anthropic.com/news/donating-the-model-context-protocol-and-establishing-of-the-agentic-ai-foundation
- Google Developers Blog, “Developer’s Guide to AI Agent Protocols,” accessed 2026-09-03. https://developers.googleblog.com/developers-guide-to-ai-agent-protocols/
- OpenAI, “Dreaming: Better memory for a more helpful ChatGPT,” 2026-06-04. https://openai.com/index/chatgpt-memory-dreaming/
- Google, “Our vision for building a universal AI assistant,” 2025-05-20. https://blog.google/innovation-and-ai/models-and-research/google-deepmind/gemini-universal-ai-assistant/
- Apple, “Apple unveils next generation of Apple Intelligence,” 2026-06-08. https://www.apple.com/newsroom/2026/06/apple-unveils-next-generation-of-apple-intelligence-siri-ai-and-more/
- Intercom, “Fin AI Agent outcomes,” 2026-07-30. https://www.intercom.com/help/en/articles/8205718-fin-ai-agent-outcomes
- Zendesk, “Autonomous Service Workforce,” 2026-05-19. https://www.zendesk.com/newsroom/articles/relate-2026/
- Salesforce, “New Ways to Pay for Agentforce,” 2025-08-19. https://www.salesforce.com/news/stories/new-agentforce-payment-options/
- NIST NCCoE, “Software and AI Agent Identity and Authorization,” 2026. https://www.nccoe.nist.gov/projects/software-and-ai-agent-identity-and-authorization
- Visa, “Trusted Agent Protocol Specifications,” 2025-10. https://developer.visa.com/capabilities/trusted-agent-protocol/trusted-agent-protocol-specifications/
- W3C, “Verifiable Credentials 2.0 family is now a Recommendation,” 2025-05-15. https://www.w3.org/news/2025/the-verifiable-credentials-2-0-family-of-specifications-is-now-a-w3c-recommendation/
- European Union, Regulation (EU) 2024/1689, Article 14. https://eur-lex.europa.eu/eli/reg/2024/1689/oj?locale=en
- OpenAI, “Designing AI agents to resist prompt injection,” 2026-03-11. https://openai.com/index/designing-agents-to-resist-prompt-injection/
- Google DeepMind, “Genie 3: A new frontier for world models,” 2025-08-05. https://deepmind.google/blog/genie-3-a-new-frontier-for-world-models/
- Google DeepMind, “Gemini Robotics 2 brings whole body intelligence to robots,” 2026-07-30. https://deepmind.google/blog/gemini-robotics-2-brings-whole-body-intelligence-to-robots/
- Anthropic, “How we built our multi-agent research system,” 2025-06-13. https://www.anthropic.com/engineering/multi-agent-research-system
- Salesforce, “2026 Proxy Statement,” filed 2026-04-16. https://www.sec.gov/Archives/edgar/data/1108524/000110852426000085/crm-20260416.htm
- Klarna Group plc, “2025 Form 20-F,” filed 2026. https://www.sec.gov/Archives/edgar/data/2003292/000200329226000007/klar-20251231.htm
- McKinsey, “The State of AI: Global Survey 2025,” 2025-11. https://www.mckinsey.com/capabilities/quantumblack/our-insights/the-state-of-ai
- Microsoft, “2025: The year the Frontier Firm is born,” 2025-04-23. https://www.microsoft.com/en-us/worklab/work-trend-index/2025-the-year-the-frontier-firm-is-born

## Research stop note

Discovery covered capability, adoption/economics, identity/authorization, regulation/HCI, and embodiment. Follow-up prioritized counterevidence and current primary sources. Remaining uncertainty is mainly timing, economics at scale, and external validation; additional broad search is unlikely to change the category ranking.
