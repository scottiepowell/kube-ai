# Autogen Kubernetes Workflow

This directory contains a minimal Autogen application and utility scripts.

## `mdmp_ghost_workflow.py`

Runs an example MDMP workflow for deploying a Ghost website using the HQ agent
matrix. It reads the CSV template under `src/templates/MDMP_ghost_website.csv`
and issues each step as a prompt to a local LLM via the Autogen library.

### Usage

```bash
python -m autogen.src.mdmp_ghost_workflow
```

The script expects an Ollama instance reachable at `$OLLAMA_URL` (defaults to
`http://127.0.0.1:11434`). It prints each step's LLM response to standard
output.

## `ollama_helper.py`

Provides `wait_for_server()` to confirm a local Ollama instance is up. The
function probes the `$OLLAMA_URL` and waits up to 30 seconds. Run it directly to
print the detected URL:

```bash
python -m autogen.src.ollama_helper
```
