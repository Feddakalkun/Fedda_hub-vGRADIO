# Fedda Hub - vGRADIO (Flux 2 Klein Character Studio)

Deliberately minimal and clean Gradio frontend for high-quality consistent character work with **Flux.2 Klein 9B**.

## Current State (as of June 2026 refactor)
- **Drag & drop 0, 1 or 2 reference images** directly (Primary Face + optional Body/Outfit). No more hardcoded gallery.
- Live Preview pane that updates instantly when you drop images.
- Output Preview pane + refresh button (shows latest generations from ComfyUI/output).
- **No JSON creation / "Prepare" path anymore** — fully removed. Direct ComfyUI API is the only way.
- One prominent **"⚡ Queue Directly to ComfyUI (API)"** button.
- Optional LoRA selector + strength slider (works with the lora variants).
- Prompt packs (batch + surprise) + editable prompt box.
- Automatically selects the correct base workflow:
  - `flux_klein_9b_0-reference_lora.json`
  - `flux_klein_9b_1-reference_lora.json`
  - `flux_klein_9b_2-reference_lora.json`
- Patches refs (LoadImage), prompt text, and LoRA node on the fly before sending to `http://127.0.0.1:8188/prompt`.

## How to Run
1. Make sure ComfyUI is running (http://127.0.0.1:8188).
2. Double-click `UI/launch_ui.bat` (it prefers the embedded python in `App/python_embeded`).
3. Browser opens → drag images → edit prompt / pick LoRA → click Queue.

## Key Files for the Future Custom Installer
- `UI/REQUIRED_NODES.md` — Complete inventory of every `class_type` used by the workflows (name, source repo, install command, notes). This is the contract for building a tailored ComfyUI installer.
- `UI/BREADCRUMBS.md` + `UI/HANDOFF.md` — Full development log + handoff notes (strict process followed on every change).

## Structure
- `UI/flux_klein_character_studio.py` — The Gradio app
- `UI/custom_workflows/` — The three lora API-format execution JSONs (the only ones the Queue button loads)
- `UI/launch_ui.bat` + `requirements.txt`

## Philosophy
Keep it **Klein-first and minimal** until the character workflow is rock solid. Then expand with a landing page + cards for the other workflows (Qwen, WAN, LTX, Z-Image, etc.).

See `UI/BREADCRUMBS.md` for the complete change history of this refactor.

## Next
- Landing page with cards for additional workflows.
- More direct API integrations.
- The custom ComfyUI installer built around `REQUIRED_NODES.md`.
