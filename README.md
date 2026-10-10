# Agentic Knowledge Worker Automation

An agentic AI system for automating knowledge-worker review processes using natural-language business rules, desktop interaction, human-in-the-loop decision making, and adaptive policy updates.

## Branch Versions

This repository contains multiple implementations of the Agentic AI Knowledge Workers project. Each branch represents a different version or architectural approach to the system.

### Version Overview

| Branch                            | Environment | Data Extraction              | Session Logs | Context Engineering | Description                                                        |
| --------------------------------- | ----------- | ---------------------------- | ------------ | ------------------- | ------------------------------------------------------------------ |
| `main` / `version_1_local`        | Local       | Programmatic                 | ✅            | ✅                   | Full-featured local implementation                                 |
| `version_1_screenenv`             | ScreenEnv   | Programmatic                 | ✅            | ✅                   | Full-featured implementation running inside ScreenEnv              |
| `version_2_screenenv`             | ScreenEnv   | Clicks + Screenshot Analysis | ✅            | ✅                   | Full-featured ScreenEnv implementation with visual data extraction |
| `version_1_screenenv_alternative` | ScreenEnv   | Programmatic                 | ❌            | ❌                   | Independent alternative implementation                             |
| `version_2_screenenv_alternative` | ScreenEnv   | Clicks + Screenshot Analysis | ❌            | ❌                   | Alternative implementation with Clicks + Screenshot Analysis       |

### Branch Descriptions

#### `main` / `version_1_local`

The original **local implementation** of the Knowledge Workers system.

It provides the complete set of core features, including:

* Session logs
* Context engineering
* Agentic AI workflow
* Programmatic data extraction

This version runs locally and does not depend on ScreenEnv.

#### `version_1_screenenv`

The ScreenEnv adaptation of the full-featured local implementation.

It retains the complete functionality of `version_1_local`, including:

* Session logs
* Context engineering
* Agentic AI workflow
* Programmatic data extraction

The main difference is that the system is adapted to run within the ScreenEnv environment.

#### `version_2_screenenv`

An evolution of `version_1_screenenv` that changes the data extraction approach.

Instead of extracting data purely programmatically, this version uses:

* Mouse and keyboard interactions / clicks
* Screenshot capture
* Screenshot analysis using a vision-capable model

The **session logs and context engineering features are still preserved** from the previous full-featured implementation.

#### `version_1_screenenv_alternative`

A **separate alternative implementation** of the ScreenEnv Knowledge Workers system.

This implementation has a different architecture and approach from the main development line. It does **not** include:

* Session logs
* Context engineering

It should therefore be considered an independent implementation rather than a continuation of `version_1_screenenv`. Data extraction is programmatic/tool_based.

#### `version_2_screenenv_alternative`

A second iteration of the alternative implementation.

It retains the alternative architecture of `version_1_screenenv_alternative` and focuses on improving the data extraction approach through clicks and screenshot analysis rather than relying on programmatic/tool-based extraction.

Like the previous alternative implementation, it does **not** include:

* Session logs
* Context engineering

### Implementation Families

The branches can therefore be viewed as two main implementation families:

**Full-featured implementation**

```text
version_1_local
      │
      ▼
version_1_screenenv
      │
      ▼
version_2_screenenv
```

These versions share the core architecture and include **session logs and context engineering**.

**Alternative implementation**

```text
version_1_screenenv_alternative
      │
      ▼
version_2_screenenv_alternative
```

These versions use a **different architecture** and intentionally omit **session logs and context engineering**.

> **Note:** The alternative branches are not incremental replacements for the full-featured implementation. They represent a separate implementation approach that was developed and evaluated independently.


## Development Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Create a Virtual Environment

Create an isolated Python environment for the project:

**Windows:**

```bash
python -m venv .venv
```

**Linux / macOS:**

```bash
python3 -m venv .venv
```

### 3. Activate the Virtual Environment

**Windows — Command Prompt:**

```bash
.venv\Scripts\activate
```

**Windows — PowerShell:**

```powershell
.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
source .venv/bin/activate
```

Once activated, your terminal should indicate that the `.venv` environment is active.

### 4. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 5. Install Dependencies

Install the project's required Python packages:

```bash
pip install -r requirements.txt
```

### 6. Configure Environment Variables

Create a local `.env` file based on the project's environment configuration template:

```bash
cp .env.example .env
```

On Windows, you can alternatively create the file manually:

```powershell
Copy-Item .env.example .env
```

Update the `.env` file with the required local configuration and credentials.

> **Never commit `.env` or other files containing secrets to the repository.**

### 7. Run the Application

After completing the setup, run the application using the project's entry point:

```bash
python <entry-point>.py
```

> The exact command may change as the project architecture develops. Refer to the relevant project documentation for the current execution command.

### 8. Deactivate the Virtual Environment

When finished working on the project:

```bash
deactivate
```

### Development Workflow

A typical development session looks like:

```bash
# Activate environment
.venv\Scripts\activate

# Install/update dependencies
pip install -r requirements.txt

# Run the application
python <entry-point>.py
```

If new dependencies are added during development, update `requirements.txt` accordingly:

```bash
pip freeze > requirements.txt
```


## Overview

Knowledge workers routinely perform repetitive review tasks across documents, spreadsheets, and desktop applications: checking invoices against purchase orders, reconciling inventory records, validating compliance information, and investigating inconsistencies.

This project aims to automate these workflows without relying on fragile, hardcoded rules.

Instead, the system allows humans to describe a **review process** and its **business policies in natural language**. An agent interprets those instructions, creates an execution plan, interacts with workplace artifacts, evaluates records against the active policy, escalates ambiguous cases to a human, and produces an auditable report.

The system is intentionally **use-case agnostic**. The same agentic workflow can support different knowledge-worker tasks by changing the process and policy provided as input.

## Core Idea

```text
                 ┌──────────────────────┐
                 │   Review Process     │
                 │   + Review Policy    │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │   Create Review Plan │
                 │        (LLM)         │
                 └──────────┬───────────┘
                            │
                       Human Sign-off
                            │
                            ▼
                 ┌──────────────────────┐
                 │    Extract Data      │◄──────┐
                 │  ReAct + ScreenEnv   │       │
                 └──────────┬───────────┘       │
                            │                    │
                            ▼                    │
                 ┌──────────────────────┐       │
                 │   Evaluate Record    │       │
                 └──────────┬───────────┘       │
                            │                    │
                  ┌─────────┼─────────┐          │
                  ▼         ▼         ▼          │
                VALID     INVALID   AMBIGUOUS    │
                  │         │         │           │
                  │         │         ▼           │
                  │         │   ┌─────────────┐  │
                  │         │   │ Human Review│  │
                  │         │   └──────┬──────┘  │
                  │         │          │         │
                  │         │    Policy Update? │
                  │         │          │         │
                  └─────────┴──────────┴─────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │    Audit Logging     │
                 └──────────┬───────────┘
                            │
                      More records?
                            │
                            ▼
                 ┌──────────────────────┐
                 │   Generate Report    │
                 └──────────────────────┘
```

## Key Features

### Natural-Language Policy Processing

Business rules are provided as human-readable policies rather than being encoded as application-specific conditional logic.

The agent interprets these policies and applies them during record evaluation.

### Dynamic Review Planning

The system converts a natural-language review process into an ordered set of structured execution steps.

This allows the same workflow architecture to support different domains without hardcoding the process itself.

### Human-in-the-Loop

Human intervention is a core part of the system rather than an afterthought.

A human reviews the generated execution plan before the agent interacts with the target data. During execution, ambiguous cases can also be escalated to a human operator for a decision.

### Desktop & Document Interaction

Data extraction is performed through a ReAct-style agent operating inside **ScreenEnv**, allowing the system to interact with workplace artifacts such as spreadsheets and documents.

The agent can determine the sequence of actions required to locate and extract the relevant information rather than assuming a fixed file layout.

### Adaptive Policy Updates

When a human resolves an ambiguous case and their decision represents a durable business rule, the system can update its active policy.

This allows future records to benefit from previously resolved edge cases without repeatedly escalating the same ambiguity.

### Auditable Decisions

Every evaluated record contributes to an audit trail containing:

* Decision status
* Reasoning
* Supporting evidence
* Record identifier
* Timestamp

The accumulated audit trail is then used to generate the final report.

## Example Use Cases

### Restaurant Invoice Review

A restaurant receives an invoice from a supplier and needs to verify it against the original purchase order.

The system can review:

* Ordered quantities
* Delivered quantities
* Prices
* Calculated totals
* Applicable sales taxes
* Potential discrepancies

Valid records can be approved automatically, while ambiguous cases can be escalated to a human reviewer.

### Factory Inventory Audit

A factory maintains inventory through multiple records:

* Previous inventory
* Sales or dispatch records
* Current inventory

The agent can verify whether:

```text
Current Inventory = Last Inventory - Sales
```

and identify discrepancies caused by missing stock, unrecorded damage, or data-entry errors.

## Architecture

The workflow is orchestrated using **LangGraph** and maintains a structured state throughout execution.

The major workflow components are:

1. **Parse Review Docs**
   Loads the review process and policy.

2. **Create Review Plan**
   Uses an LLM to transform the natural-language process into structured execution steps.

3. **Confirm Plan**
   Human checkpoint where the generated plan can be accepted or sent back for revision.

4. **Extract Data**
   A ReAct agent interacts with the target application or document through ScreenEnv.

5. **Tool**
   Executes concrete desktop actions requested by the extraction agent.

6. **Evaluate Record**
   Evaluates each extracted record against the active policy.

7. **Human Review**
   Handles cases where the agent cannot confidently determine the correct outcome.

8. **Update Policy**
   Incorporates approved durable rules derived from human decisions.

9. **Log Audit Entry**
   Records the decision, reasoning, and evidence.

10. **Generate Report**
    Produces the final audit report after all records have been processed.

## State Management

The LangGraph state tracks the complete execution lifecycle, including:

* Review process and policy
* Active policy
* Target file
* Use-case context
* Generated process steps
* Current execution step
* Evaluation status
* Reasoning and evidence
* Human intervention context
* Audit entries
* Report location
* Execution status
* Errors and completion state

This provides a traceable representation of what the agent has done and why.

## Design Principles

### General-Purpose Workflow

The graph should not contain domain-specific logic for individual use cases.

The process and policy supplied by the user determine what the agent needs to do.

### Human Control

Humans remain in control at critical decision points, particularly before execution and whenever the agent encounters ambiguity.

### Semantic Automation

Instead of relying exclusively on hardcoded UI scripts and conditional rules, the system uses language models to interpret processes, policies, and workplace data.

### Traceability

Agent decisions should be backed by recorded evidence and reasoning so that the resulting audit can be inspected.

### Adaptive Behavior

Human corrections should have the potential to improve subsequent decisions by updating the active operational policy.

## Technology Direction

The blueprint is centered around:

* **Python**
* **LangGraph** — stateful workflow orchestration
* **Local 3B–8B multimodal LLMs** — reasoning and structured outputs
* **ScreenEnv** — containerized desktop execution environment
* **ReAct agents** — dynamic data extraction and tool interaction

The architecture is designed around small local models capable of structured JSON output and fast inference.

## Project Status

> 🚧 **Early Development**

The project is currently in the architecture and implementation phase.

The initial development focus is on establishing the core LangGraph workflow, state management, process/policy interpretation, ScreenEnv interaction, human-in-the-loop checkpoints, and audit reporting.

## Roadmap

* [ ] Establish project structure and development environment
* [ ] Implement LangGraph state
* [ ] Implement review-document parsing
* [ ] Implement review-plan generation
* [ ] Implement human plan confirmation
* [ ] Integrate ScreenEnv
* [ ] Implement ReAct-based data extraction
* [ ] Implement record evaluation
* [ ] Implement human escalation
* [ ] Implement dynamic policy updates
* [ ] Implement audit logging
* [ ] Implement report generation
* [ ] Validate the architecture on multiple use cases
* [ ] Evaluate reliability, traceability, and automation effectiveness

## Project Vision

The long-term goal is to build a general-purpose **agentic knowledge-worker automation engine** capable of taking human-defined workplace processes and turning them into executable, auditable workflows.

Rather than replacing human judgment entirely, the system is designed around a collaborative model:

**Human defines → Agent plans → Human confirms → Agent executes → Human resolves ambiguity → Agent learns → System reports**

---

## License & Confidentiality

This project is developed under the **Software Engineering Competence Center (SECC)**, a center of the **Information Technology Industry Development Agency (ITIDA)**.

### Proprietary & Confidential

**Copyright © 2026 Software Engineering Competence Center (SECC). All rights reserved.**

This project and its associated source code, documentation, designs, materials, and related artifacts are proprietary and confidential.

No part of this project may be:

* Published, publicly distributed, or made available online
* Reproduced, copied, or transmitted in any form
* Shared with or disclosed to unauthorized individuals or organizations
* Presented, demonstrated, or exhibited to external parties
* Used for commercial, academic, educational, or other purposes outside the scope authorized by SECC

These restrictions apply **during and after the completion of the internship** and remain in effect unless explicit written permission is granted by SECC.

Any request to reproduce, distribute, disclose, publish, or otherwise use any part of this project must be directed to and approved in writing by the **Software Engineering Competence Center (SECC)**.

> **This repository is private and is not intended for public release.**

**Software Engineering Competence Center (SECC)**
**Information Technology Industry Development Agency (ITIDA)**
**Copyright © 2026 SECC. All rights reserved.**
