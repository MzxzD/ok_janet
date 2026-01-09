# Installing Janet-seed for Janet Mesh

Janet Mesh integrates with [Janet-seed](https://github.com/MzxzD/Janet-seed) to use DeepSeek (deep thinking model) via LiteLLM.

## Installation Options

### Option 1: Clone as Subdirectory (Recommended)

```bash
cd janet-mesh
git clone https://github.com/MzxzD/Janet-seed.git janet-seed
```

The model loader will automatically find Janet-seed in this location.

### Option 2: Add to PYTHONPATH

```bash
# Clone Janet-seed anywhere
git clone https://github.com/MzxzD/Janet-seed.git ~/Janet-seed

# Add to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:~/Janet-seed"
```

### Option 3: Install as Package

```bash
cd Janet-seed
pip install -e .
```

## Configure DeepSeek

Janet-seed uses LiteLLM for model routing. To use DeepSeek, you have several options:

### Option 1: Use DeepSeek API (Recommended)

1. **Set DeepSeek API Key**:
   ```bash
   export DEEPSEEK_API_KEY="your-api-key"
   ```

2. **Modify JanetBrain** to use DeepSeek:
   Edit `janet-seed/src/core/janet_brain.py`:
   ```python
   # In generate_response method, change:
   response = litellm.completion(
       model="deepseek/deepseek-chat",  # or "deepseek/deepseek-reasoner"
       messages=messages,
       temperature=0.7,
       max_tokens=500
   )
   ```

### Option 2: Use DeepSeek via Ollama (Local)

1. **Install DeepSeek model in Ollama**:
   ```bash
   ollama pull deepseek-coder:6.7b
   # or
   ollama pull deepseek-r1:7b
   ```

2. **Configure JanetBrain** to use DeepSeek model:
   - Edit `janet-seed/src/core/janet_core.py` or pass model_name when initializing
   - Set `model_name="deepseek-coder:6.7b"` or your preferred DeepSeek model

### Option 3: Use LiteLLM Router

Configure the delegation router in `janet-seed/src/delegation/litellm_router.py` to route to DeepSeek for specific tasks.

### Verify Configuration

```bash
cd janet-seed
python3 src/main.py --verify
```

## Testing Integration

After installing Janet-seed, test the integration:

```bash
cd janet-mesh
python3 server/run.py
```

You should see:
```
Loading all models...
✓ STT model loaded
✗ TTS model failed to load: ...
Loading LLM model via janet_seed
Loading Janet-seed core (DeepSeek via LiteLLM)...
✓ Janet-seed core loaded in X.XX seconds
  Using DeepSeek via LiteLLM router
✓ LLM model loaded
```

## Fallback to Ollama

If Janet-seed is not found or fails to load, the system will automatically fall back to Ollama:

```
✗ LLM model failed to load: Janet-seed not found
  Attempting fallback to Ollama...
✓ LLM model loaded (Ollama fallback)
```

## Troubleshooting

### "Janet-seed not found"
- Ensure Janet-seed is cloned in `janet-mesh/janet-seed/`
- Or add it to PYTHONPATH
- Or install as package

### "Could not access Janet-seed's brain component"
- Check that `src/core/janet_brain.py` exists in Janet-seed
- Verify Janet-seed's structure matches expected layout

### "DeepSeek not configured"
- Check LiteLLM router configuration in Janet-seed
- Verify API key is set (if using API)
- Check that DeepSeek model is available

## Manual Configuration

You can specify Janet-seed path manually:

```python
# In server/models/model_loader.py or via environment variable
model_loader.load_janet_seed_core(janet_seed_path="/path/to/Janet-seed")
```

Or set environment variable:
```bash
export JANET_SEED_PATH="/path/to/Janet-seed"
```
