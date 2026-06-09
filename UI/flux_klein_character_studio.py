r"""
vGRADIO Studio - Multi-workflow Gradio frontend for ComfyUI

Current tabs:
- Klein Character Studio (Flux.2 Klein 9B with 0/1/2 reference images + optional LoRA)
- LTX Video (advanced video workflows like LTX-23-flf)
- More coming (WAN, Qwen, Z-Image, Audio, etc.)

The goal is clean, focused tabs for each major workflow family, with direct API queuing
to a running ComfyUI instance.

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
    """Scan ComfyUI output dir for latest images (used by Klein output preview)."""
    outs = []
    out_dir = WORKSPACE / "App" / "ComfyUI" / "output"
    if out_dir.exists():
        for p in sorted(out_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)[:12]:
            outs.append(str(p))
    return outs


def queue_ltx_workflow(guide1_path, guide2_path, prompt, steps=25, guidance=3.5, frame_count=25):
    """
    Direct queue for LTX video workflows (e.g. LTX-23-flf.json).
    This is more advanced than Klein — it uses guide images + LTX-specific conditioning.
    Best effort patching of LoadImage nodes and text prompt.
    """
    workflow_path = CUSTOM_DIR / "LTX-23-flf.json"
    if not workflow_path.exists():
        return f"❌ Workflow not found: {workflow_path}", None

    # Copy guides to ComfyUI input with stable names the workflow likely expects
    g1_name = "ltx_guide1.png"
    g2_name = "ltx_guide2.png"

    if guide1_path and os.path.exists(guide1_path):
        shutil.copy2(guide1_path, COMFY_INPUT / g1_name)
    if guide2_path and os.path.exists(guide2_path):
        shutil.copy2(guide2_path, COMFY_INPUT / g2_name)

    with open(workflow_path, encoding="utf-8") as f:
        wf = json.load(f)

    updated = []
    load_image_count = 0

    # The file is likely a full UI export. We try to patch widgets_values for LoadImage
    # and look for text prompt nodes.
    if "nodes" in wf:  # full UI format
        for node in wf.get("nodes", []):
            ntype = node.get("type", "")
            widgets = node.get("widgets_values", [])
            title = node.get("title", "")

            if ntype == "LoadImage" and widgets:
                if load_image_count == 0:
                    widgets[0] = g1_name
                    updated.append(f"LoadImage id {node.get('id')} → {g1_name}")
                elif load_image_count == 1 and guide2_path:
                    widgets[0] = g2_name
                    updated.append(f"LoadImage id {node.get('id')} → {g2_name}")
                load_image_count += 1

            # Try to find prompt nodes
            if "prompt" in title.lower() or ntype in ("CLIPTextEncode", "String Literal"):
                if widgets:
                    # Usually the prompt is the first string widget
                    for i, w in enumerate(widgets):
                        if isinstance(w, str) and len(w) > 15:
                            widgets[i] = prompt
                            updated.append(f"Prompt node id {node.get('id')} updated")
                            break

            # Patch some common numeric controls if they look like steps / guidance
            if ntype in ("PrimitiveInt", "easy int") and widgets:
                # Heuristic: first int widget that is in reasonable step range
                if 8 < widgets[0] < 100:
                    widgets[0] = int(steps)
                    updated.append(f"Steps/Int node {node.get('id')} → {steps}")

    else:
        # API format (cleaner)
        for nid, node in wf.items():
            if not isinstance(node, dict):
                continue
            ct = node.get("class_type", "")
            inputs = node.get("inputs", {})

            if ct == "LoadImage" and "image" in inputs:
                if load_image_count == 0:
                    inputs["image"] = g1_name
                    updated.append(f"LoadImage {nid} → {g1_name}")
                elif load_image_count == 1:
                    inputs["image"] = g2_name
                    updated.append(f"LoadImage {nid} → {g2_name}")
                load_image_count += 1

            if ct in ("CLIPTextEncode", "PrimitiveStringMultiline") or "text" in inputs:
                if "text" in inputs:
                    inputs["text"] = prompt
                    updated.append(f"Text node {nid} updated")

    # Send to ComfyUI
    url = "http://127.0.0.1:8188/prompt"
    payload = {
        "prompt": wf,
        "client_id": f"vgradio-ltx-{int(datetime.now().timestamp())}"
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            pid = resp.json().get("prompt_id", "unknown")
            return (
                f"✅ LTX queued! Prompt ID: {pid}\n\n"
                "Patched:\n" + "\n".join(updated) + "\n\n"
                "Watch ComfyUI. When finished, use the Refresh button to load the video."
            ), None
        else:
            return f"❌ API error {resp.status_code}\n{resp.text[:600]}", None
    except Exception as e:
        return f"❌ Error queuing LTX: {e}\n\nTip: Export an API version of the workflow for more reliable patching.", None


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
with gr.Blocks(title="vGRADIO Studio - Fedda Hub") as demo:
    gr.Markdown("# vGRADIO Studio\n**Multi-workflow direct API launcher for ComfyUI**")

    with gr.Tabs():
        # ==================== KLEIN TAB ====================
        with gr.TabItem("🎭 Klein Character Studio (Flux.2 9B)"):
            gr.Markdown("**Clean & focused on consistent character work with 0, 1 or 2 reference images + optional LoRA.**")

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

            def run_klein_queue(face_p, body_p, p, lora, strength):
                msg, recent_outs = queue_to_comfyui(face_p, body_p, p, lora, strength)
                live = update_live_preview(face_p, body_p)
                return msg, live, recent_outs

            queue_btn.click(
                fn=run_klein_queue,
                inputs=[face_img, body_img, prompt_box, lora_choice, lora_strength],
                outputs=[result_box, live_preview, output_preview]
            )

            refresh_btn.click(fn=get_recent, outputs=output_preview)

            gr.Markdown("""
            **How it works:**
            - Drag & drop 0, 1 or 2 reference images.
            - Edit prompt or load packs.
            - (Optional) LoRA + strength.
            - Queue → direct API to running ComfyUI.
            - Live + Output previews update automatically.
            """)

        # ==================== LTX TAB ====================
        with gr.TabItem("🎬 LTX Video (23)"):
            gr.Markdown("**Advanced LTX Video workflows** (e.g. LTX-23-flf with guides). More inputs = more advanced control.")

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Guide / Reference Images")
                    ltx_guide1 = gr.Image(label="Guide Image 1 (Start / Main)", type="filepath", height=180, interactive=True)
                    ltx_guide2 = gr.Image(label="Guide Image 2 (End / Secondary) - optional", type="filepath", height=180, interactive=True)

                with gr.Column():
                    gr.Markdown("### Prompt")
                    ltx_prompt = gr.Textbox(
                        label="",
                        lines=3,
                        value="cinematic video of the character walking in a beautiful environment, highly detailed, smooth motion"
                    )
                    gr.Markdown("### Key Parameters (adjust to taste)")
                    ltx_steps = gr.Slider(10, 60, value=25, step=1, label="Steps")
                    ltx_guidance = gr.Slider(1.0, 8.0, value=3.5, step=0.1, label="Guidance / CFG")
                    ltx_frames = gr.Slider(8, 49, value=25, step=1, label="Frame Count")

            with gr.Row():
                ltx_queue_btn = gr.Button("🚀 Queue LTX Video to ComfyUI", variant="primary", size="lg")

            ltx_result = gr.Textbox(label="Status / Log", lines=6, interactive=False)

            with gr.Row():
                ltx_video = gr.Video(label="Generated Video", height=320)
                ltx_refresh = gr.Button("Refresh Latest Video", size="sm")

            def run_ltx_queue(g1, g2, prompt, steps, guidance, frames):
                msg, video_path = queue_ltx_workflow(g1, g2, prompt, steps, guidance, frames)
                return msg, video_path

            ltx_queue_btn.click(
                fn=run_ltx_queue,
                inputs=[ltx_guide1, ltx_guide2, ltx_prompt, ltx_steps, ltx_guidance, ltx_frames],
                outputs=[ltx_result, ltx_video]
            )

            def get_latest_video():
                out_dir = WORKSPACE / "App" / "ComfyUI" / "output"
                if out_dir.exists():
                    vids = sorted(out_dir.glob("*.mp4"), key=lambda x: x.stat().st_mtime, reverse=True)
                    if vids:
                        return str(vids[0])
                return None

            ltx_refresh.click(fn=get_latest_video, outputs=ltx_video)

            gr.Markdown("""
            **Notes for LTX workflows:**
            - These are advanced video models. Expect longer generation times.
            - The workflow (LTX-23-flf.json) uses guide images + conditioning for better motion/control.
            - Make sure the required LTX models + custom nodes (LTXV*, VHS, rgthree, etc.) are installed in your ComfyUI.
            - Output preview looks for the latest .mp4 in ComfyUI/output.
            """)

        # ==================== HOME / LANDING TAB ====================
        with gr.TabItem("🏠 Workflows Overview"):
            gr.Markdown("""
            ## Available Workflow Studios

            Click the tabs above to use each focused studio.

            **Currently implemented:**
            - **Klein Character Studio** — Best for consistent character images with 0-2 refs + LoRA.
            - **LTX Video (23)** — Advanced LTX video generation with image guides.

            **More workflows you have added (will add dedicated tabs soon):**
            - LTX-23-img2vid, ltx-lipsync
            - Several WAN 2.1 / 2.2 video workflows
            - Qwen edit + multi-angle
            - Z-Image variants (txt2img, dual lora, controlnet)
            - Audio tools (TTS, voiceclone, lipsync)
            - Character V3, Expression, Remove BG, etc.

            **How everything works:**
            - Each tab has its own inputs tailored to that workflow.
            - "Queue" buttons send a clean execution prompt directly to your running ComfyUI (http://127.0.0.1:8188).
            - No more manual JSON dragging for the supported paths.

            Want a specific workflow turned into a nice tab next? Just tell me which one (e.g. a Qwen multi-angle or a particular WAN one).
            """)

            gr.Markdown("### Quick Launch All Recent Outputs")
            global_refresh = gr.Button("Refresh All Previews")
            global_gallery = gr.Gallery(label="Latest images + videos from ComfyUI output", columns=6, height=200)

            def get_all_recent():
                outs = []
                out_dir = WORKSPACE / "App" / "ComfyUI" / "output"
                if out_dir.exists():
                    for p in sorted(out_dir.glob("*.*"), key=lambda x: x.stat().st_mtime, reverse=True)[:18]:
                        if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".mp4", ".webm"):
                            outs.append(str(p))
                return outs

            global_refresh.click(fn=get_all_recent, outputs=global_gallery)
            demo.load(fn=get_all_recent, outputs=global_gallery)

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