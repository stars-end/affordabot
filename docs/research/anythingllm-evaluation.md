# Research Report: AnythingLLM for Legislation Analysis

**Date:** 2025-12-08
**Context:** Affordabot Migration to Postgres/pgvector
**Subject:** Evaluation of AnythingLLM (Railway Template)

## Executive Summary

AnythingLLM is a strong candidate for the **User Interface (UI)** and **Agentic Interaction** layer of Affordabot, but it should **not** replace the core ingestion pipeline.

Its primary value proposition for Affordabot is providing an immediate, multi-user Chat UI that can interact with your data via **MCP (Model Context Protocol)**. It supports `pgvector`, making it compatible with your new infrastructure strategy. However, its native metadata filtering capabilities are currently immature, limiting its use as a primary search engine for complex legislative queries without custom agent skills.

## Scorecard

| Dimension | Score | Notes |
|-----------|-------|-------|
| **Document Ingestion** | **3/5** | Good format support (PDF, HTML), but metadata extraction/tagging is manual/basic compared to your custom pipeline. |
| **Search Quality** | **3/5** | Supports `pgvector`, but lacks robust native metadata filtering (e.g., "Session 2024 only") or hybrid search out-of-the-box. |
| **Agent Capabilities** | **5/5** | **Excellent.** Full MCP support means it can call your existing Affordabot API tools. Custom Node.js skills supported. |
| **Multi-user/Auth** | **5/5** | Built-in RBAC (Admin/Manager/Default), workspaces, and simple SSO links. Perfect for internal team use. |
| **Integration** | **4/5** | API-first design. Can use external Postgres/Postgres as its backend. |
| **Deployment** | **5/5** | Verified Railway template. Lightweight (runs on 2GB RAM node if using Cloud LLMs). |
| **Total** | **25/30** | **RECOMMEND: PILOT** |

---

## Detailed Findings

### 1. Document Ingestion Fit
*   **Formats:** Supports PDF, DOCX, TXT, HTML, and Markdown natively.
*   **Chunking:** Configurable chunk sizes (default 384-512 tokens) with overlap. Good for general text, but legislative text often requires semantic chunking (by section/clause) which generic splitters miss.
*   **Metadata:** Weakness. While it ingests documents, assigning structured metadata (Bill ID, Sponsor, Year) for precise filtering is not a first-class citizen in the UI flow compared to a dedicated CMS.

### 2. Search & Retrieval Quality
*   **Backend:** **Crucially, it supports `pgvector`.** This allows it to coexist with your Prime Radiant/Postgres infrastructure.
*   **Limitation:** It primarily relies on semantic similarity. Use cases like "Find all housing bills from 2024" are difficult without agentic intervention because strict metadata filtering is not exposed in the simple chat UI.
*   **Hybrid Search:** Not natively supported in the core distribution yet; relies on the vector DB's capabilities which aren't always fully exposed.

### 3. Agent Capabilities (The "Killer Feature")
*   **MCP Support:** AnythingLLM has full support for **Model Context Protocol**.
    *   *Strategy:* You can wrap your `daily_scrape.py` or `legislation` lookup endpoints as an MCP Server. AnythingLLM becomes the UI that "calls" your backend tools.
*   **Custom Skills:** You can write Node.js scripts effectively acting as "Tools" for the agent (e.g., `lookup_bill_status(bill_id)`).

### 4. Multi-User & Auth
*   **Workspaces:** You can create specific workspaces (e.g., "San Jose Housing", "State Senate").
*   **RBAC:** "Multi-user mode" allows you to invite stakeholders (analysts, partners) with read-only access to specific workspaces.
*   **Auth:** Simple password management or "Magic Link" SSO.

### 5. Deployment & Integration
*   **Railway:** The template `HNSCS1` creates a Docker container.
*   **Database:** It typically spawns its own DB, but you **can** configure it to point to your existing Postgres Postgres by setting `DATABASE_URL` and `VECTOR_DB` environment variables.
*   **API:** It exposes a full API, allowing your backend to programmatically create workspaces or upload documents if you choose to sync them.

### 6. Cost & Scaling
*   **Compute:** Very low (<$10/mo on Railway) if using Z.ai or OpenAI for inference. High if running local LLMs (Ollama).
*   **Storage:** Vectors stored in Postgres. Negligible cost for text vectors.

---

## Recommendation: Proceed with "Hybrid Pilot"

Do not use AnythingLLM as your *Database*. Use it as your *Interface*.

**Proposed Architecture:**
1.  **Ingestion (Keep Existing):** Continue using `daily_scrape.py` and `run_universal_harvester.py` to fetch and process data into Postgres `legislation` and `documents` tables.
2.  **Integration (The Glue):**
    *   Deploy AnythingLLM on Railway.
    *   Point it to your Postgres Postgres (carefully, ensuring table namespaces don't collide).
    *   *Alternatively (Safer):* Use AnythingLLM's API to "push" final summaries from your pipeline into AnythingLLM Workspaces for viewing.
3.  **Agents:** Configure AnythingLLM to use an **MCP Server** that exposes your `legislation` SQL table. This gives the Chatbot "Perfect Memory" of the structured data your scrapers found.

### Next Steps
1.  **Deploy Template:** `railway.com/deploy/HNSCS1`
2.  **Config:** Connect to Z.ai (GLM-4.6) via OpenAI-compatible endpoint settings.
3.  **Test:** Upload the `San Jose ADU Guide` and test the chat experience.
