# FEDDAKALKUN Studio

**Official creative control surface for FEDDAKALKUN** — Multi-workflow Gradio frontend for ComfyUI with direct API queuing.

Dark-themed official **FEDDAKALKUN** creative control surface.

Multi-tab Gradio frontend for ComfyUI with direct API queuing. Currently includes:

- **Klein Character Studio** — Flux.2 Klein 9B with drag & drop 0/1/2 reference images + optional LoRA, live + output previews.
- **LTX Video** — Advanced LTX video workflows with guide images.
- **Overview** — Dashboard + quick access to all recent outputs.

More dedicated tabs (WAN, Qwen, Z-Image, Audio, etc.) are planned as the brand expands.

## How to Run
1. Make sure ComfyUI is running at http://127.0.0.1:8188.
2. Double-click `UI/launch_ui.bat`.
3. Use the tabs to switch between studios. Each has its own inputs and "Queue" button.

## Key Files
- `UI/flux_klein_character_studio.py` — The main FEDDAKALKUN Studio app
- `UI/REQUIRED_NODES.md` — Complete list of custom nodes for the future FEDDAKALKUN custom ComfyUI installer.
- `UI/custom_workflows/` — API-format workflow definitions
- `UI/BREADCRUMBS.md` + `UI/HANDOFF.md` — Development log (strict process)

## Design
- Dark cyber aesthetic with FEDDAKALKUN cyber bunny branding.
- Direct API (no JSON dragging for supported workflows).
- Clean per-workflow tabs.

See `UI/BREADCRUMBS.md` for history.

## Next
- Landing page with cards for additional workflows.
- More direct API integrations.
- The custom ComfyUI installer built around `REQUIRED_NODES.md`.
