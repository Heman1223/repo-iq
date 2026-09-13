# Pending Improvements & Additions

This document outlines the pending items, planned features, and areas for improvement for the **GitHub Repository AI Assistant** project. These have been identified primarily from the project documentation.

## 1. Authentication & Access
* **Private Repository Support:** Currently, only public repositories are supported (attempts to index private repos result in a `private_repository` error). Implementing GitHub OAuth is needed to allow cloning and indexing of private user/org repositories securely.

## 2. Advanced Retrieval & Indexing
* **Multi-Repository Operations:** The current system isolates one Chroma collection per repository. A planned improvement is indexing and querying **multiple repositories** simultaneously, enabling cross-repo semantic search and architectural comparisons.
* **Hybrid Search (BM25 + Vector):** Pure cosine similarity vector search is currently implemented. Adding BM25 keyword matching with a re-ranking stage (e.g., Cohere Rerank or Cross-Encoder) will significantly improve the accuracy of finding specific variables, exact match functions, and short queries.
* **Code Graph Awareness:** Implement code graph visualization to understand imports, call paths, and module boundaries natively rather than purely text-chunking. 

## 3. Architecture & Workflows
* **Multi-Agent Architecture:** Transition from a single LLM generation call to a multi-agent workflow (e.g., via LangGraph) consisting of:
  * *Planner:* Plans how to answer complex queries.
  * *Retriever:* Gathers relevant files and chunks.
  * *Verifier:* Checks if the generated answer is fully grounded in the retrieved code.
* **Pull Request & Issue Analysis:** Expand scope beyond static code to analyze and summarize pull requests, issues, and commit histories.
* **MCP Integration:** Implement a Model Context Protocol (MCP) server so that the repository index is queryable from any MCP-capable client or IDE directly.

## 4. UI/UX & Real-time Feedback
* **Streaming Responses (SSE):** Currently, the user waits for the entire LLM generation to finish. Implement Server-Sent Events (SSE) to stream answers to the frontend.
* **Real-time Indexing WebSocket:** Replace the current HTTP polling mechanism (`GET /status`) with WebSockets for instantaneous pipeline progress updates.
* **Codebase Comparison (Diffing):** Add features to visually or architecturally diff two codebases and generate AI summaries of the differences.

## 5. Deployment & CI/CD
* **Dockerization:** Add a `docker-compose.yml` to simplify deployment, bundling the FastAPI backend, React frontend, and ChromaDB into isolated containers.
* **Continuous Integration:** Configure automated CI workflows (e.g., GitHub Actions) to run the existing `pytest` backend suite and `Playwright` UI tests on every commit/PR.
