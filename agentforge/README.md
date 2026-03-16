# AgentForge

Enterprise AI Agent as a Service — define agents with YAML, run with one command, auto-repair with three levels.

## Features

- **YAML-driven**: Define your agent pipeline in a simple YAML file
- **Multi-provider**: OpenAI, Gemini, Ollama (local), and any OpenAI-compatible API
- **Three-level auto-repair**: Automatic retry, context injection, and re-planning on failure
- **Budget tracking**: Per-agent cost accounting with daily limit warnings
- **Execution history**: SQLite-backed run history with success rate and cost stats
- **Dry-run mode**: Preview execution plan without side effects

## Installation

```bash
pip install agentforge
```

For development:

```bash
git clone <repo>
cd agentforge
pip install -e ".[dev]"
```

## Quick Start (5 minutes)

### 1. Initialize a project

```bash
agentforge init my-project
cd my-project
```

This creates:
```
my-project/
  agentforge.yaml        # Global config (models, providers, budget)
  agents/
    example.yaml         # Example file-analyzer agent
  .agentforge/           # Runtime data (DB, logs)
```

### 2. Create an agent

Create `agents/summarizer.yaml`:

```yaml
name: summarizer
description: "Summarize a text file using LLM"
model: openai/gpt-4o-mini

steps:
  - name: read_file
    action: shell
    command: "cat README.md"

  - name: summarize
    action: llm
    prompt: |
      Summarize the following text in 3 bullet points:
      {{ steps.read_file.output }}

  - name: save_summary
    action: save
    path: "summary.md"
    content: "{{ steps.summarize.output }}"
```

### 3. Set your API key

```bash
export OPENAI_API_KEY=sk-...
```

Or use Ollama (free, local):

```yaml
# agents/summarizer.yaml
model: ollama/qwen3:14b
```

### 4. Run the agent

```bash
agentforge run summarizer
```

### 5. Check execution history

```bash
agentforge status
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `agentforge init <name>` | Initialize a new project |
| `agentforge list` | List all agents in current project |
| `agentforge run <agent>` | Execute an agent |
| `agentforge run <agent> --dry-run` | Preview without executing |
| `agentforge run <agent> --verbose` | Show detailed step output |
| `agentforge status` | Show execution history and cost stats |

## YAML Reference

### Agent definition (`agents/<name>.yaml`)

```yaml
name: my-agent              # Required: unique agent name
description: "..."          # Optional: description shown in `list`
model: openai/gpt-4o-mini  # Optional: default model (provider/model-name)
max_retries: 3              # Optional: 1-10, default 3

steps:
  - name: step-name         # Required: unique within agent
    action: shell           # Required: shell | llm | save
    command: "echo hello"   # shell only: command to run

  - name: analyze
    action: llm
    prompt: |               # llm only: prompt template
      Analyze: {{ steps.step-name.output }}
    model: ollama/qwen3:14b # Override agent-level model

  - name: save-result
    action: save
    path: "output.md"       # save only: output file path
    content: "{{ steps.analyze.output }}"
```

### Template syntax

Use `{{ steps.<step-name>.output }}` to reference previous step outputs:

```yaml
prompt: |
  The shell command produced:
  {{ steps.my-shell-step.output }}

  Please summarize it.
```

### Global config (`agentforge.yaml`)

```yaml
default_model: openai/gpt-4o-mini

providers:
  openai:
    api_key_env: OPENAI_API_KEY
    base_url: https://api.openai.com/v1

  ollama:
    base_url: http://localhost:11434/v1

  gemini:
    api_key_env: GEMINI_API_KEY

budget:
  daily_limit_usd: 10.0
  warn_at_percent: 80.0
```

## Provider Setup

### OpenAI

```bash
export OPENAI_API_KEY=sk-...
```

Supported models: `openai/gpt-4o`, `openai/gpt-4o-mini`, `openai/gpt-4.1`, `openai/gpt-4.1-mini`, `openai/gpt-4.1-nano`

### Ollama (Local, Free)

Install [Ollama](https://ollama.ai) and pull a model:

```bash
ollama pull qwen3:14b
# Then use: model: ollama/qwen3:14b
```

Default base URL: `http://localhost:11434/v1`

### Gemini

```bash
export GEMINI_API_KEY=...
```

Supported models: `gemini/gemini-2.0-flash`, `gemini/gemini-2.5-pro`

### Any OpenAI-compatible API

```yaml
providers:
  openai:
    base_url: https://api.groq.com/openai/v1
    api_key_env: GROQ_API_KEY
```

## Example Agents

Three ready-to-use agent templates are included in every new project:

### file-analyzer

Lists directory contents and generates a file structure summary using LLM.

```bash
cp $(python -c "import agentforge; print(agentforge.__file__.rsplit('/',1)[0])")/templates/example.yaml agents/
agentforge run file-analyzer
```

### code-reviewer

Runs `git diff` and generates a code review report.

```bash
cp $(python -c "import agentforge; print(agentforge.__file__.rsplit('/',1)[0])")/templates/code-reviewer.yaml agents/
agentforge run code-reviewer
```

Output: `code-review-report.md`

### data-processor

Reads `data.csv` or `data.json` and generates an analysis report.

```bash
cp $(python -c "import agentforge; print(agentforge.__file__.rsplit('/',1)[0])")/templates/data-processor.yaml agents/
echo "name,age,score" > data.csv
echo "Alice,30,95" >> data.csv
agentforge run data-processor
```

Output: `data-analysis-result.md`

## Three-Level Auto-Repair

When a step fails, AgentForge automatically:

1. **Level 1 (RETRY_WITH_FIX)**: Injects error context and retries immediately
2. **Level 2 (REPLAN)**: Escalates to re-planning with full error history
3. **Level 3 (HALT)**: Stops and reports — notifies you to intervene

Configure retries per agent:

```yaml
max_retries: 3  # 1-10, default 3
```

## Budget Management

AgentForge tracks API costs automatically:

```
agentforge status

┌─────────────────────────────────────────────────────────────┐
│                    AgentForge 執行統計                       │
├──────────────┬──────┬──────┬──────┬──────────┬─────────────┤
│ Agent 名稱   │ 執行 │ 成功 │ 失敗 │ 成功率   │ 總費用(USD) │
├──────────────┼──────┼──────┼──────┼──────────┼─────────────┤
│ summarizer   │   10 │   9  │   1  │  90.0%   │ $0.001500   │
│ code-reviewer│    5 │   5  │   0  │ 100.0%   │ $0.000750   │
└──────────────┴──────┴──────┴──────┴──────────┴─────────────┘
```

Set daily limits in `agentforge.yaml`:

```yaml
budget:
  daily_limit_usd: 5.0      # Hard limit
  warn_at_percent: 80.0     # Warning at 80%
```

## Development

```bash
# Run tests
python -m pytest tests/

# Run with coverage
python -m pytest tests/ --cov=agentforge

# Build wheel
python -m build
```
