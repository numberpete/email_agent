# EMaiL Assist

![MIT License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.12%2B-blue.svg)

Email Assist is a multi-agent, LangGraph-powered AI email assistant that parses intent,
applies tone, drafts emails using templates, validates output, and maintains lightweight
memory across interactions.

This was done as a capstone project for the Interview Kickstart Agentic AI course.

## Quickstart

### Requirements
- Python 3.12+
- OPENAI_API_KEY
- ANTHROPIC_API_KEY (optional fallback)
- SECRET_SALT

### Run locally
```bash
./start.sh
```

### Run with Docker
```bash
docker compose up --build
```

### Test
```bash
pytest -v
```

## Architecture

### System Architecture

```mermaid
flowchart TB
    subgraph UI["🖥️ UI Layer"]
        ST[Streamlit App<br/>src/ui/app.py]
    end

    subgraph WF["⚙️ Workflow Layer"]
        direction TB
        WE[LangGraph Workflow Engine<br/>src/workflow/workflow.py]
        RT[LiteLLM Router<br/>src/workflow/router.py]
    end

    subgraph AGENTS["🤖 Agent Layer"]
        direction LR
        subgraph Processing["Input Processing"]
            IP[InputParser<br/>Agent]
            ID[IntentDetection<br/>Agent]
            TS[ToneStylist<br/>Agent]
        end
        subgraph Generation["Content Generation"]
            DW[DraftWriter<br/>Agent]
            PS[Personalization<br/>Agent]
        end
        subgraph Validation["Validation & Memory"]
            RV[ReviewValidator<br/>Agent]
            MA[Memory<br/>Agent]
        end
    end

    subgraph DATA["💾 Data Layer"]
        direction LR
        DB[(SQLite Database<br/>email_assist.db)]
        TMP[Templates<br/>Store]
        PRF[Profiles<br/>Store]
        MEM[Memory<br/>Store]
    end

    subgraph EXTERNAL["☁️ External Services"]
        OAI[OpenAI API]
        ANT[Anthropic API]
    end

    ST <-->|User Input/Output| WE
    WE <--> RT
    RT <--> OAI
    RT <--> ANT
    WE <--> AGENTS
    
    IP --> ID --> TS --> DW --> PS --> RV
    RV -->|PASS| MA
    RV -->|FAIL| DW
    
    MA <--> MEM
    DW <--> TMP
    PS <--> PRF
    
    MEM --- DB
    TMP --- DB
    PRF --- DB

    style UI fill:#FAF0F3,stroke:#8B4557,stroke-width:2px
    style WF fill:#F0E4E8,stroke:#6B3A4A,stroke-width:2px
    style AGENTS fill:#FDF9FA,stroke:#8B4557,stroke-width:2px
    style DATA fill:#E8D8DD,stroke:#5D2E3D,stroke-width:2px
    style EXTERNAL fill:#f5f5f5,stroke:#666,stroke-width:1px
```

### Agent Workflow (StateGraph)

Built with LangGraph.

```mermaid
flowchart LR
    UI[/"User Input"/] --> InputParser
    InputParser --> IntentDetection
    InputParser --> END
    IntentDetection --> ToneStylist
    ToneStylist --> DraftWriter
    DraftWriter --> Personalization
    Personalization --> ReviewValidator
    ReviewValidator -->|PASS| MemoryAgent
    ReviewValidator -->|FAIL| DraftWriter
    ReviewValidator -->|BLOCKED| END[/"End"/]
    MemoryAgent --> END

    style UI fill:#FAF0F3,stroke:#8B4557
    style END fill:#FAF0F3,stroke:#8B4557
    style InputParser fill:#FDF9FA,stroke:#6B3A4A
    style IntentDetection fill:#FDF9FA,stroke:#6B3A4A
    style ToneStylist fill:#FDF9FA,stroke:#6B3A4A
    style DraftWriter fill:#FDF9FA,stroke:#6B3A4A
    style Personalization fill:#FDF9FA,stroke:#6B3A4A
    style ReviewValidator fill:#FDF9FA,stroke:#6B3A4A
    style MemoryAgent fill:#FDF9FA,stroke:#6B3A4A
```

### Data Model

#### data/email_assist.db (sqlite)

```mermaid
erDiagram
    USER_PROFILES {
        text user_id PK
        text profile_json
        text created_at
        text updated_at
    }
    
    EMAIL_TEMPLATES {
        text template_id PK
        text intent
        text tone_label
        text name
        text body
        text meta_json
        text created_at
        text updated_at
    }
    
    EMAIL_SUMMARIES {
        text user_id PK
        text recipient_key PK
        text summary_json
        text created_at
        text updated_at
    }
    
    USER_PROFILES ||--o{ EMAIL_SUMMARIES : "has summaries"
```

#### LangGraph Memory
Session based memory uses LangGraph checkpointer MemorySaver with thread_id tied to the session_id.

session_id is computed as a hash of the user_id + salt (SECRET_SALT env var).

### Agents

| Agent | Responsibility |
|-------|----------------|
| **InputParsingAgent** | Extracts structured fields from raw user input (recipient, subject hints, key points) |
| **IntentDetectionAgent** | Classifies email intent (outreach, follow_up, apology, request, etc.) |
| **ToneStylistAgent** | Determines or refines tone (formal, friendly, assertive, apologetic, concise) |
| **DraftWriterAgent** | Generates email draft using templates and LLM |
| **PersonalizationAgent** | Injects user profile data and recipient context |
| **ReviewValidatorAgent** | Validates draft quality, returns PASS/FAIL/BLOCKED |
| **MemoryAgent** | Persists interaction context for future reference |

### Directory Structure
```
email_assist/
├── README.md
├── LICENSE
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── .gitattributes
├── start.sh
├── data/
│   └── email_assist.db          # SQLite DB (created at runtime)
├── src/
│   ├── ui/
│   │   └── app.py                # Streamlit UI
│   ├── workflow/
│   │   ├── workflow.py           # LangGraph StateGraph definition and app entry-point
│   │   └── router.py             # LiteLLM / MCP model router
│   ├── agents/
│   │   ├── base_agent.py
│   │   ├── state.py              # AgentState for the StateGraph
│   │   ├── response.py           # AgentResponse for agent.run() return type
│   │   ├── input_parser_agent.py
│   │   ├── intent_detection_agent.py
│   │   ├── tone_stylist_agent.py
│   │   ├── draft_writer_agent.py
│   │   ├── personalization_agent.py
│   │   ├── review_validator_agent.py
│   │   └── memory_agent.py
│   ├── memory/
│   │   └── sqlite_memory_store.py
│   ├── templates/
│   │   ├── fixtures/
│   │   │   └── templates.py      # Templates to initially populate the data store
│   │   ├── seed_templates.py
│   │   └── seed_templates_store.py
│   ├── profiles/
│   │   ├── seed_profile.py
│   │   ├── profile_store.py
│   │   └── sqlite_profile_store.py
│   └── utils/
│       ├── logging.py            # Colored logging + ECID
│       ├── sessionid.py          # Session ID helpers
│       └── recipient.py          # normalize_recipient / compute_recipient_key
├── tests/
│   ├── test_input_parser.py
│   ├── test_intent_detection.py
│   ├── test_tone_stylist.py
│   ├── test_draft_writer.py
│   ├── test_review_validator.py
│   ├── test_personalization.py
│   ├── test_memory_agent.py
│   └── utils/
│       └── mock_llm.py           
├── pyproject.toml
└── requirements.txt
```

## Contributing
This was done as a capstone project for the Interview Kickstart Agentic AI course. I'm not likely to be maintaining this going forward, but if you feel strongly you'd like to improve this, do the following:

1. Fork the repo
2. Create a feature branch
3. Add tests for any new behavior
4. Ensure `pytest` passes
5. Open a PR with a clear description

Code style favors clarity over cleverness.

## License
MIT