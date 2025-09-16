# OpenHands Server

As of 2025-09-16 this is a work in progress and subject to rapid change.

A REST/WebSocket interface for OpenHands AI Agent. This server provides HTTP and WebSocket endpoints to interact with the OpenHands agent programmatically.

## Quickstart

- Prerequisites: Python 3.12+, curl
- Install uv (package manager):

  ```
  curl -LsSf https://astral.sh/uv/install.sh | sh
  # Restart your shell so "uv" is on PATH, or follow the installer hint
  ```

### Run the server locally

```
# Install dependencies (incl. dev tools)
make install-dev

# Optional: install pre-commit hooks
make install-pre-commit-hooks

# Start the server
make run
# or
uv run openhands-server
```

Tip: Set your model key (one of) so the agent can talk to an LLM:

```
export OPENAI_API_KEY=...
# or
export LITELLM_API_KEY=...
```

### Build a standalone executable

```
# Build (installs PyInstaller if needed)
./build.sh --install-pyinstaller

# The binary will be in dist/
./dist/openhands-server            # macOS/Linux
# dist/openhands-server.exe        # Windows
```

For advanced development (adding deps, updating the spec file, debugging builds), see Development.md.

## API Endpoints

### Conversation Management
- `GET /conversations/search` - List/search conversations
- `GET /conversations/{id}` - Get conversation by ID
- `GET /conversations/` - Batch get conversations
- `POST /conversations/` - Start a new conversation
- `POST /conversations/{id}/pause` - Pause a conversation
- `POST /conversations/{id}/resume` - Resume a conversation
- `DELETE /conversations/{id}` - Delete a conversation

### Event Management
- `GET /conversations/{id}/events/search` - List/search events in a conversation
- `GET /conversations/{id}/events/{event_id}` - Get specific event
- `GET /conversations/{id}/events/` - Batch get events
- `POST /conversations/{id}/events/` - Send a message to the conversation
- `POST /conversations/{id}/events/respond_to_confirmation` - Respond to confirmation requests

### WebSocket API
- `WS /conversations/{id}/events/socket` - Real-time event streaming for a conversation

## About

REST/WebSocket interface for OpenHands AI Agent, providing programmatic access to agent capabilities.