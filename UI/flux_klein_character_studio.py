r"""
Flux 2 Klein Character Studio GUI (Clean Version)

Focused only on making the Flux 2 Klein 9B 2-Reference Character workflow easy and reliable.

Run with: UI\launch_ui.bat
"""

import gradio as gr
import json
import os
import shutil
from pathlib import Path
from datetime import datetime
import requests  # for direct ComfyUI API calls

# Paths
WORKSPACE = Path(__file__).parent.parent.resolve()
# REFS_DIR kept only for prompt-pack .txt loading (CHARACTER-BATCH-PROMPTS etc). No longer used for reference *images*.
REFS_DIR = WORKSPACE / "2-PROMPTS" / "20yo woman"
CUSTOM_DIR = WORKSPACE / "UI" / "custom_workflows"
COMFY_INPUT = WORKSPACE / "App" / "ComfyUI" / "input"

CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
COMFY_INPUT.mkdir(parents=True, exist_ok=True)

# Note: REFS_DIR is kept only because load_pack() currently looks for the prompt .txt packs inside the 20yo woman folder.
# The old image gallery (get_refs + ref_names) has been removed per user request. Users now drag & drop their own 0/1/2 images.

# LoRAs (for the lora variant of the API workflow)
LORAS_DIR = WORKSPACE / "App" / "ComfyUI" / "models" / "loras"
if LORAS_DIR.exists():
    LORA_CHOICES = ["None"] + sorted([p.name for p in LORAS_DIR.glob("*.safetensors") if p.is_file()])
else:
    LORA_CHOICES = ["None"]

def load_pack(name):
    p = REFS_DIR / name
    if not p.exists():
        return ""
    text = p.read_text(encoding="utf-8")
    # Take the first substantial prompt block
    for line in text.splitlines():
        line = line.strip()
        if len(line) > 40 and not line.startswith(("#", "positive:", "----")):
            return line
    return text[:500]


def get_recent():
    """Scan ComfyUI output dir for latest images (used by output preview and after queue)."""
    outs = []
    out_dir = WORKSPACE / "App" / "ComfyUI" / "output"
    if out_dir.exists():
        for p in sorted(out_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:12]:
            outs.append(str(p))
    return outs


def queue_to_comfyui(face_path, body_path, prompt, lora_name="None", lora_strength=0.8):
    """
    Direct launch to running ComfyUI via its API.
    Uses the user's provided lora API-format JSON based on number of refs (0/1/2).
    Copies dropped images (if any) to input/ as klein_face.png / klein_body.png.
    Overrides LoadImage(s) (only the ones supplied), prompt node, and LoRA node.
    No JSON files are ever created/saved by this path.
    """
    face_file = "klein_face.png"
    body_file = "klein_body.png"

    # Copy only the images the user actually dropped (supports 0, 1 or 2 refs)
    has_face = bool(face_path and os.path.exists(face_path))
    has_body = bool(body_path and os.path.exists(body_path))

    if has_face:
        shutil.copy2(face_path, COMFY_INPUT / face_file)
    if has_body:
        shutil.copy2(body_path, COMFY_INPUT / body_file)

    num_refs = 2 if has_body else (1 if has_face else 0)
    api_path = CUSTOM_DIR / f"flux_klein_9b_{num_refs}-reference_lora.json"

    if not api_path.exists():
        return (
            f"❌ Required API format JSON not found for {num_refs} reference(s).\n"
            f"Expected: {api_path}\n\n"
            "Make sure the three lora files (0/1/2) are present in UI/custom_workflows/."
        ), get_recent()

    with open(api_path, encoding="utf-8") as f:
        api_prompt = json.load(f)

    # Patch the execution prompt
    updated = []
    load_image_count = 0
    for node_id, node in api_prompt.items():
        if not isinstance(node, dict):
            continue
        class_type = node.get("class_type", "")
        inputs = node.get("inputs", {})
        meta_title = node.get("_meta", {}).get("title", "")

        if class_type == "LoadImage" and "image" in inputs:
            if load_image_count == 0 and has_face:
                inputs["image"] = face_file
                updated.append(f"LoadImage {node_id} → {face_file}")
            elif load_image_count == 1 and has_body:
                inputs["image"] = body_file
                updated.append(f"LoadImage {node_id} → {body_file}")
            load_image_count += 1

        # Prompt node (PrimitiveStringMultiline titled "Prompt" or similar with long text)
        is_prompt_node = (
            "Prompt" in meta_title or
            class_type in ("String Literal", "PrimitiveStringMultiline", "Primitive String", "Text") or
            "value" in inputs or "string" in inputs or "text" in inputs
        )
        if is_prompt_node:
            current_val = inputs.get("value") or inputs.get("string") or inputs.get("text") or ""
            if len(str(current_val)) > 20 or "young woman" in str(current_val).lower() or "portrait" in str(current_val).lower():
                if "value" in inputs:
                    inputs["value"] = prompt
                elif "string" in inputs:
                    inputs["string"] = prompt
                elif "text" in inputs:
                    inputs["text"] = prompt
                updated.append(f"Prompt node {node_id} updated")

        # LoRA handling
        if class_type == "LoraLoaderModelOnly":
            if lora_name != "None":
                inputs["lora_name"] = lora_name
                if "strength_model" in inputs:
                    inputs["strength_model"] = lora_strength
                if "strength_clip" in inputs:
                    inputs["strength_clip"] = lora_strength
                updated.append(f"LoRA {node_id} → {lora_name} @ {lora_strength}")
            else:
                if "strength_model" in inputs:
                    inputs["strength_model"] = 0.0
                if "strength_clip" in inputs:
                    inputs["strength_clip"] = 0.0
                updated.append(f"LoRA {node_id} disabled (strength 0)")

    # Send to ComfyUI
    url = "http://127.0.0.1:8188/prompt"
    payload = {
        "prompt": api_prompt,
        "client_id": f"klein-gui-{int(datetime.now().timestamp())}"
    }

    try:
        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code == 200:
            data = resp.json()
            pid = data.get("prompt_id", "unknown")
            ref_info = f"{num_refs}-ref" + (" + LoRA" if lora_name != "None" else "")
            return (
                f"✅ Queued successfully to ComfyUI (API) using {ref_info} workflow!\n\n"
                f"Prompt ID: {pid}\n\n"
                "Patched nodes:\n" + ("\n".join(updated) if updated else "(no overrides needed)") + "\n\n"
                "Watch the generation in your ComfyUI window. Output preview will update with new images."
            ), get_recent()
        else:
            detail = resp.text[:900] if resp.text else "(no response body)"
            return (
                f"❌ ComfyUI API error {resp.status_code}\n{detail}\n\n"
                "Check the ComfyUI console for the full traceback."
            ), get_recent()
    except requests.exceptions.ConnectionError:
        return (
            "❌ Cannot reach ComfyUI at http://127.0.0.1:8188\n\n"
            "Please start ComfyUI (the one in App/ComfyUI) and make sure the server is running, then try again."
        ), get_recent()
    except Exception as e:
        return f"❌ Unexpected error while queuing: {e}", get_recent()

# ====================== UI ======================
with gr.Blocks(title="Flux 2 Klein Character Studio") as demo:
    gr.Markdown("# Flux 2 Klein Character Studio\n**Simple & focused on the 9B 2-Ref workflow**")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Reference Images (Drag & Drop 0, 1 or 2 images)")
            with gr.Row():
                face_img = gr.Image(
                    label="Primary Reference (Face) - optional",
                    type="filepath",
                    height=200,
                    interactive=True
                )
                body_img = gr.Image(
                    label="Secondary Reference (Body/Outfit) - optional",
                    type="filepath",
                    height=200,
                    interactive=True
                )

        with gr.Column(scale=2):
            gr.Markdown("### Prompt")
            prompt_box = gr.Textbox(
                label="",
                lines=4,
                value="The same young woman with shoulder-length wavy light brown hair and striking hazel eyes, wearing an elegant flowing dress, standing in a beautiful cinematic setting with dramatic lighting, photorealistic, highly detailed"
            )

            with gr.Row():
                gr.Button("Load Good Batch Prompt").click(
                    fn=lambda: load_pack("CHARACTER-BATCH-PROMPTS.txt"),
                    outputs=prompt_box
                )
                gr.Button("Load Surprise Prompt").click(
                    fn=lambda: load_pack("SURPRISE-GENRE-PACK.txt"),
                    outputs=prompt_box
                )
                gr.Button("Clear").click(lambda: "", outputs=prompt_box)

            gr.Markdown("### LoRA (optional)")
            lora_choice = gr.Dropdown(
                choices=LORA_CHOICES,
                value="None",
                label="LoRA"
            )
            lora_strength = gr.Slider(
                minimum=0.0,
                maximum=2.0,
                value=0.8,
                step=0.05,
                label="LoRA Strength (model)"
            )

    with gr.Row():
        queue_btn = gr.Button("⚡ Queue Directly to ComfyUI (API)", variant="primary", size="lg")

    result_box = gr.Textbox(label="Status / Log", lines=8, interactive=False)

    with gr.Row():
        with gr.Column():
            gr.Markdown("### Live Preview (Current References)")
            live_preview = gr.Gallery(label="", columns=2, height=160, interactive=False)
        with gr.Column():
            gr.Markdown("### Output Preview")
            output_preview = gr.Gallery(label="", columns=3, height=160, interactive=False)
            refresh_btn = gr.Button("Refresh Outputs", size="sm")

    # Events for drag-drop refs -> live preview
    def update_live_preview(face_p, body_p):
        previews = []
        if face_p and os.path.exists(face_p):
            previews.append(face_p)
        if body_p and os.path.exists(body_p):
            previews.append(body_p)
        return previews

    face_img.change(fn=update_live_preview, inputs=[face_img, body_img], outputs=live_preview)
    body_img.change(fn=update_live_preview, inputs=[face_img, body_img], outputs=live_preview)

    def run_queue(face_p, body_p, p, lora, strength):
        msg, recent_outs = queue_to_comfyui(face_p, body_p, p, lora, strength)
        # update live too
        live = update_live_preview(face_p, body_p)
        return msg, live, recent_outs

    queue_btn.click(
        fn=run_queue,
        inputs=[face_img, body_img, prompt_box, lora_choice, lora_strength],
        outputs=[result_box, live_preview, output_preview]
    )

    def get_recent():
        outs = []
        out_dir = WORKSPACE / "App" / "ComfyUI" / "output"
        if out_dir.exists():
            for p in sorted(out_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:12]:
                outs.append(str(p))
        return outs

    refresh_btn.click(fn=get_recent, outputs=output_preview)

    demo.load(fn=get_recent, outputs=output_preview)

    gr.Markdown("""
    **How it works (clean):**
    - Drag & drop 0, 1 or 2 reference images (Primary Face first, optional Body second).
    - Load or edit a prompt.
    - (Optional) Select a LoRA and strength.
    - Click Queue.
    - Live preview shows your current refs.
    - Output preview updates with recent generations from ComfyUI.

    This version is deliberately minimal. We will add more workflows later once Klein is solid.
    """)

def _find_free_port(start=7860, end=7870):
    import socket
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return None

if __name__ == "__main__":
    import os
    port = int(os.environ.get("GRADIO_SERVER_PORT", 7860))
    if port == 7860:
        free = _find_free_port(7860, 7870)
        if free:
            port = free
    print(f"Launching on http://127.0.0.1:{port}")
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        inbrowser=True,
        show_error=True,
        theme=gr.themes.Soft()
    )