# T0.2 -- Qwen3.6 Tool-Calling Round-Trip Test

Last updated: 2026-06-03 1440 PDT by Claude

## What this gate is

T0.2 is the second half of the Qwen3.6 GO/NO-GO gate from
`archive/handoffs/HANDOFF_2026-05-15_0127_compat-reeval-tiered.md`. T0.1 (model
loads and generates coherent output) PASSED 2026-05-18. T0.2 verifies that
Qwen3.6 emits a parseable tool call from an OpenAI-style request. It is the gate
that unblocks Hermes Phase 8 integration (Hermes drives the model through tool
calls). Until T0.2 passes, do NOT start the T1-T3 swap work.

Acceptance (from the source handoff): "Parseable tool call emitted."

## Preconditions

- Run on the Windows daily-driver (the Qwen3.6 prototype host), Git Bash shell.
- Model present: `models/Qwen3.6-35B-A3B-UD-Q5_K_XL.gguf` (26.6 GB).
- The launcher `scripts/start_llama_server_win.sh` serves on `127.0.0.1:8080`
  by default (PORT/MODEL_FILE/GPU_LAYERS are env-overridable).
- `curl` and `jq` available in the shell. `jq` ships with Git for Windows; if
  missing, read the raw JSON by hand.

## Step 1 -- Start the server with tool-call templating enabled

llama.cpp only applies the model chat template's tool-call grammar when started
with `--jinja`. Confirm the launcher passes it. If `--jinja` is absent from
`scripts/start_llama_server_win.sh`, add it to the `llama-server.exe` invocation
(or export it through the launcher) before running this test -- otherwise a
"missing tool call" result is a launcher artifact, not a model failure.

From `D:\Projects\Git\Project_Persona` in Git Bash:

```
bash scripts/start_llama_server_win.sh
```

## Step 2 -- Health check

```
curl -s http://127.0.0.1:8080/health
```

Expect a JSON body reporting status ok before continuing.

## Step 3 -- Tool-calling round-trip

Send an OpenAI-style request that defines one function and asks a question the
model can only answer by calling it.

```
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.6",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant with access to tools."},
      {"role": "user", "content": "What is the weather in Tokyo right now? Use the tool."}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_current_weather",
          "description": "Get the current weather for a city",
          "parameters": {
            "type": "object",
            "properties": {
              "city": {"type": "string", "description": "City name"},
              "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["city"]
          }
        }
      }
    ],
    "tool_choice": "auto",
    "temperature": 0.2,
    "stream": false
  }' | jq '.choices[0].message'
```

## Pass / fail criteria

PASS -- the response message contains a `tool_calls` array, and
`tool_calls[0].function.arguments` parses as JSON with `city` set to "Tokyo"
(unit optional). Example of a passing shape:

```
{
  "role": "assistant",
  "content": null,
  "tool_calls": [
    {
      "id": "call_abc123",
      "type": "function",
      "function": {
        "name": "get_current_weather",
        "arguments": "{\"city\": \"Tokyo\", \"unit\": \"celsius\"}"
      }
    }
  ]
}
```

Verify the arguments string actually parses:

```
curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d @/dev/stdin <<'JSON' | jq -r '.choices[0].message.tool_calls[0].function.arguments' | jq .
{"model":"qwen3.6","messages":[{"role":"user","content":"Weather in Tokyo? Use the tool."}],"tools":[{"type":"function","function":{"name":"get_current_weather","description":"Get the current weather for a city","parameters":{"type":"object","properties":{"city":{"type":"string"}},"required":["city"]}}}],"tool_choice":"auto","stream":false}
JSON
```

If that final `jq .` prints a clean object, the tool call is parseable -- PASS.

FAIL modes and what they mean:

- No `tool_calls` field; the model wrote the call as plain text inside
  `content` (for example a fenced JSON block or a `<tool_call>...</tool_call>`
  string). This is the expected "T0.2 fails" case from the handoff. Remedy:
  write a GBNF grammar to constrain output to the function schema (~1-2 hours,
  no architectural change), then re-run. Track as a T0.2a follow-up.
- `arguments` present but not valid JSON (trailing commas, unescaped quotes).
  Same GBNF remedy.
- Server error or template error on startup. Almost always the missing
  `--jinja` flag from Step 1, or a llama.cpp build too old for the
  `qwen3_5_moe` template. Fix the launcher / bump the build and retry; this is
  not a model-capability failure.

## After the test -- record the result

1. Update `todo.md`: replace the "T0.2 ... still open" caveat with the outcome
   (PASS unblocks T1; FAIL adds the T0.2a GBNF task).
2. Add a dated entry to `changelog.md` with the verdict and the llama.cpp build
   number used (`llama-server.exe --version`).
3. If PASS, the Qwen3.6 swap path is clear to begin at T1 (env_hermes venv +
   per-profile config.yaml template).
