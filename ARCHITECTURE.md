# Architecture

## High-Level Workflow (Mermaid)

```mermaid
flowchart LR
    UI --> InputParser
    InputParser --> IntentDetection
    IntentDetection --> ToneStylist
    ToneStylist --> DraftWriter
    DraftWriter --> Personalization
    Personalization --> ReviewValidator
    ReviewValidator -->|PASS| MemoryAgent
    ReviewValidator -->|FAIL| DraftWriter
    ReviewValidator -->|BLOCKED| END
    MemoryAgent --> END
```