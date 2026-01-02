# Email Assist

![MIT License](https://img.shields.io/badge/license-MIT-green.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)

Email Assist is a multi-agent, LangGraph-powered AI email assistant that parses intent,
applies tone, drafts emails using templates, validates output, and maintains lightweight
memory across interactions.

## Quickstart

### Requirements
- Python 3.11+
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

## Architecture
See [ARCHITECTURE.md](ARCHITECTURE.md) for diagrams and agent flow.

## Agents
- InputParsingAgent
- IntentDetectionAgent
- ToneStylistAgent
- DraftWriterAgent
- PersonalizationAgent
- ReviewValidatorAgent
- MemoryAgent

## License
MIT