# The Self-Healing DOM Scraper (Agentic RAG)

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Model](https://img.shields.io/badge/Model-Qwen2.5--Coder--1.5B-violet)
![Stack](https://img.shields.io/badge/Stack-Unsloth%20%7C%20Llama.cpp%20%7C%20Crawl4AI-green)
[![License](https://img.shields.io/badge/License-MIT-yellow)](./LICENSE)

> **"Scrapers shouldn't break just because a `<div>` changed."**

## Visual Demo

<div align="center">
  <table>
    <tr>
      <td align="center" width="50%" style="height:420px; overflow:hidden; vertical-align:middle;">
        <img src="assets/ui_screenshot.png" alt="Domfie UI" style="height:420px; width:auto; object-fit:cover;">
        <br><b>UI Interface</b>
      </td>
      <td align="center" width="50%" style="height:420px; overflow:hidden; vertical-align:middle;">
        <img src="assets/demo.gif" alt="Self-Healing Demo" style="height:420px; width:auto; object-fit:cover;">
        <br><b>Self-Healing in Action</b>
      </td>
    </tr>
  </table>
  <p><em>Note: The version label 'V4' in the live demo is a typo.</em></p>
</div>

## Table of Contents

1. [Project Manifesto](#project-manifesto)
2. [System Architecture](#system-architecture)
3. [Quick Start Guide](#quick-start-guide)
4. [The Engineering Journey](#the-engineering-journey)
    - [1.0 Data Engineering](#10-data-engineering-the-universal-dataset)
    - [2.0 Fine-Tuning](#20-fine-tuning-the-skill-layer)
    - [3.0 RAG Pipeline](#30-rag-pipeline-the-spotter-engine)
    - [4.0 Context Engineering](#40-context-engineering-html-aware-rag)
    - [5.0 MLOps](#50-mlops-quantization--export)
    - [6.0 Agent Logic](#60-the-autonomous-agent-loop)
5. [Reliability Engineering](#reliability-engineering-qa--debugging-protocols)
6. [Disclaimer & Research Mode](#disclaimer--research-mode)
7. [Repository Structure](#repository-structure)

---

## Project Manifesto

I engineered this system to solve the "Brittle Scraper" problem. In traditional data engineering, pipelines fail constantly because frontend developers rename CSS classes (e.g., changing `.price` to `.p-val-2`).

Instead of maintaining fragile Regex or hardcoded selectors, I built an **Autonomous AI Agent** capable of:
1.  **Browsing** the web via a headless browser.
2.  **Detecting** when extraction fails.
3.  **Reading** the raw HTML structure.
4.  **"Healing"** itself by generating a new, correct CSS selector in real-time.

This repository documents the full **End-to-End LLM Pipeline**: from synthetic data generation to fine-tuning, quantization, and agentic deployment.

---

## System Architecture

To make this run on consumer hardware (local MacBook/Consumer GPU), I architected a "Bifurcated Brain" system that separates context retrieval from reasoning.

| Component | Tech Stack | Responsibility |
| :--- | :--- | :--- |
| **The Body** | `Crawl4AI` (Playwright) | Handles browsing, JS rendering, and caching successful selectors. |
| **The Spotter** | `Heuristic NLP` | Extracts the subject (e.g., "Director") and focuses the HTML window to prevent token overflow. |
| **The Brain** | `Qwen2.5-1.5B (GGUF)` | A fine-tuned model that translates `Raw HTML + User Intent` $\rightarrow$ `CSS Selector`. |
| **The Fallback** | `Direct Extraction` | If code generation fails (e.g., obfuscated React apps), the agent switches strategies to read text directly. |

```mermaid
graph TD;
    User[User / Client] -->|Intent + URL| UI[Streamlit UI / API];
    UI --> Body[Crawl4AI Browser];
    
    subgraph "The Autonomous Loop"
        Body -->|Raw HTML| Check{Selector Works?};
        Check -->|Yes| Cache[Return Data];
        Check -->|No| Healer[AI Healer];
        
        Healer -->|1. Extract Subject| NLP[Heuristic NLP];
        NLP -->|2. Focus Context| CleanHTML[HTML Chunking];
        CleanHTML -->|3. Generate Selector| Brain[Qwen 2.5-1.5B];
        
        Brain -->|New Selector| Verify{Verify Fix};
        Verify -->|Success| Cache;
        Verify -->|Fail| Fallback[Direct Text Extraction];
    end
    
    Fallback --> Result[Final Data];
    Cache --> Result;
```

---

## Quick Start Guide

### Step 1: Train & Export (Cloud)
1.  Open `domfie.ipynb` in Google Colab (T4 GPU).
2.  Run Phases 1–5 to fine-tune and export the model.
3.  Download `dom_specialist.Q4_K_M.gguf` to your local machine.

### Step 2: Deploy Locally (Ollama)
Move the `.gguf` file into a folder with the `Modelfile` from this repo.

1.  **Install Ollama:** Download from [ollama.com](https://ollama.com).
2.  **Create the Model:**
    ```bash
    ollama create dom-specialist -f Modelfile
    ```
3.  **Verify it Works:** (Crucial Step)
    Run this command to check if the model is registered:
    ```bash
    ollama list
    ```
    *You should see `dom-specialist` in the list.*
    
    Now, do a quick "Smoke Test" to ensure it loads:
    ```bash
    ollama run dom-specialist "Extract price from <div>$10</div>"
    ```
    *If it replies with `$10` or a selector, you are ready.*

### Step 3: Launch the Agent
1.  **Start the Ollama Server:** (Keep this terminal open)
    ```bash
    ollama serve
    ```
2.  **Run the UI:** (In a new terminal)
    ```bash
    pip install -r requirements.txt # review the text file first
    streamlit run app.py
    `````

---

## The Engineering Journey

This codebase was built in 7 distinct engineering phases.

### 1.0 Data Engineering: The "Universal" Dataset
**Objective:** Create a diverse training corpus to force generalization across DOM structures.
* **Strategy:** I wrote a harvester script targeting 4 distinct web architectures:
    * **Static Grids:** `books.toscrape.com` (Standard E-commerce)
    * **Data Tables:** `scrapethissite.com` (Row/Col logic)
    * **Dynamic/AJAX:** `quotes.toscrape.com` (Latency handling)
    * **Complex Nested Divs:** `webscraper.io` (Modern React-style nesting)
* **Output:** ~600+ high-quality training pairs.

### 2.0 Fine-Tuning: The "Skill" Layer
**Objective:** Specialize `Qwen2.5-Coder-1.5B` to speak "DOM Selector" fluently.
* **Configuration:** Used **Unsloth** for QLoRA (4-bit) training on a single T4 GPU.
* **Result:** Training Loss dropped from **1.89** (Guessing) to **0.29** (Mastery). The model learned to ignore noise (`<nav>`, `<footer>`) and pinpoint semantic targets.

### 3.0 RAG Pipeline: The "Spotter" Engine
**Problem:** Large pages (Wikipedia/IMDb) exceed the token window of small models.
**Solution:** Implemented a **DOM-Aware RAG** system using `LlamaIndex` to ingest raw HTML, vectorize it using `BAAI/bge-small`, and retrieve only the relevant `<div>` blocks for the agent.

### 4.0 Context Engineering: HTML-Aware RAG
**Critical Pivot:** Standard RAG pipelines strip HTML tags to save tokens, which destroys structural cues.
* **The Fix:** I re-engineered the pipeline to index **Raw HTML Chunks** (preserving tags like `<span class="price">`).
* **Verification:** The model successfully identified pricing tables embedded in "Massive HTML" test cases where standard text-RAG failed.

### 5.0 MLOps: Quantization & Export
**Objective:** Compress the 3GB FP16 model into a ~1GB GGUF binary for local deployment.
* **Challenge:** Google Colab OOM (Out of Memory) crashes during the merge.
* **Solution:**
    1.  Performed a manual off-line conversion (saving weights to disk first).
    2.  Patched `transformers` library compatibility issues.
    3.  Manually compiled `llama.cpp` using CMake to finalize the quantization (`Q4_K_M`).

### 6.0 The Autonomous Agent Loop
**Logic Flow:** The `SelfHealingAgent` class implements a state machine:
1.  **Fast Path:** Attempt cached selector.
2.  **Detection:** If `data == null`, trigger AI.
3.  **Healing (Slow Path):** Load GGUF $\rightarrow$ Analyze DOM $\rightarrow$ Generate Fix.
4.  **Fallback:** If code generation fails, trigger **Direct Text Extraction**.

### 7.0 Deployment Strategy
* **The Visualization Layer:** A Streamlit UI for real-time monitoring of the "Healing" process.
* **The Headless Layer:** The logic is decoupled into a pure Python class, ready for integration into Airflow or FastAPI pipelines.

---

## Reliability Engineering: QA & Debugging Protocols

* **Logic Debugging:** The agent includes a "Verbose Mode" that dumps the specific HTML context window. This was crucial for solving the "Tim Robbins Bug" (where the AI extracted the Actor instead of the Director because the context window was too wide).
* **Tokenizer Compatibility:** The `Modelfile` explicitly sets `temperature 0.1` and `stop` tokens to prevent the model from hallucinating conversational filler.
* **Infrastructure Validation:** The setup script automatically detects if `undetected-chromedriver` is required for anti-bot sites (StockX/Nike).

---

## Disclaimer & Research Mode

> **Note:** The training notebook and local script run in **'Research Mode'** (bypassing restrictions) to generate synthetic training data and test out the fine-tuned model.

* This tool is a Proof of Concept (PoC) for autonomous software architecture.
* It utilizes `undetected-chromedriver` to test capabilities against anti-bot systems (like StockX).
* Users are solely responsible for ensuring their scraping activities comply with local laws and the Terms of Service of target websites.

---

## Repository Structure

```text
/
├── domfie.ipynb                    # The Master Notebook (Phases 1-9)
├── Modelfile                       # Ollama Configuration for the GGUF model
├── dom_specialist.Q4_K_M.gguf      # The model (Not committed)
├── app.py                          # Local Testing of Agent Logic and UI (No ngrok needed)
├── dom_specialist_dataset.jsonl    # The Synthetic Training Data
├── requirements.txt                # Kindly check this out
├── LICENSE                         # Kindly check this out too
└── README.md                       # You are here