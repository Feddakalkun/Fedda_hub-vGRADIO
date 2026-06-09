r"""
FEDDAKALKUN Studio - Multi-workflow Gradio frontend for ComfyUI

Brand: FEDDAKALKUN
Focus: Clean, powerful interfaces for high-quality AI image & video generation.

Current tabs:
- Klein Character Studio (Flux.2 Klein 9B with 0/1/2 reference images + optional LoRA)
- LTX Video (advanced video workflows)
- More coming (WAN, Qwen, Z-Image, Audio, etc.)

The goal is clean, focused tabs for each major workflow family, with direct API queuing
to a running ComfyUI instance.

Run with: UI\launch_ui.bat
"""

import gradio as gr
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from datetime import datetime
import requests  # for direct ComfyUI API calls
try:
    import yt_dlp
except ImportError:
    yt_dlp = None  # will be installed via requirements / launcher

# Paths
WORKSPACE = Path(__file__).parent.parent.resolve()
# REFS_DIR kept only for prompt-pack .txt loading (CHARACTER-BATCH-PROMPTS etc). No longer used for reference *images*.
REFS_DIR = WORKSPACE / "2-PROMPTS" / "20yo woman"
CUSTOM_DIR = WORKSPACE / "UI" / "custom_workflows"
COMFY_INPUT = WORKSPACE / "App" / "ComfyUI" / "input"

CUSTOM_DIR.mkdir(parents=True, exist_ok=True)
COMFY_INPUT.mkdir(parents=True, exist_ok=True)

# ====================== FEDDAKALKUN Dark Theme ======================
# Using only the Soft constructor with hue/font overrides.
# All color overrides are done via CSS because .set() parameters vary across Gradio versions
# (especially in the embedded python_embeded env). This avoids "unexpected keyword argument" errors.
fedda_theme = gr.themes.Soft(
    primary_hue="violet",
    secondary_hue="cyan",
    neutral_hue="zinc",
    font=["Inter", "system-ui", "sans-serif"],
    font_mono=["JetBrains Mono", "monospace"],
)

# Comprehensive dark cyber CSS. This forces a dark theme regardless of Gradio version.
fedda_css = """
.gradio-container {
    background: linear-gradient(180deg, #0a0a0f 0%, #0f0f14 100%) !important;
    color: #e4e4e7 !important;
}

/* Text colors */
h1, h2, h3, h4, label, .gradio-container, .gradio-container * {
    color: #e4e4e7 !important;
}
h1, h2, h3 { color: #c0c0ff !important; }

/* Tabs */
.tab-nav { 
    background-color: #111114 !important; 
    border-bottom: 1px solid #27272a !important; 
}
.tab-nav button {
    color: #a1a1aa !important;
}
.tab-nav button.selected {
    color: #e4e4e7 !important;
    border-bottom: 2px solid #7c3aed !important;
}

/* Blocks, panels, inputs */
.block, .form, .panel, input, textarea, select, .gr-box {
    background-color: #111114 !important;
    border-color: #27272a !important;
    color: #e4e4e7 !important;
}

/* Buttons */
button, .gr-button {
    background-color: #7c3aed !important;
    color: white !important;
    border: none !important;
}
button:hover, .gr-button:hover {
    background-color: #6d28d9 !important;
    filter: brightness(1.1);
}

/* Galleries */
.gallery, .gallery-item {
    background-color: #111114 !important;
    border-color: #27272a !important;
}
.gallery-item:hover {
    filter: brightness(1.1);
}

/* Video / output */
video {
    background-color: #000 !important;
}

/* Sliders, dropdowns etc. */
.gr-slider, .gr-dropdown {
    background-color: #111114 !important;
}
"""

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


# ====================== Steady Dancer / TikTok Pose Helpers ======================
def download_tiktok(url: str) -> str:
    """Download video from TikTok link using yt-dlp into ComfyUI input folder."""
    if yt_dlp is None:
        raise RuntimeError("yt-dlp not available. Make sure it is installed (added to requirements.txt).")
    output_dir = COMFY_INPUT
    output_template = str(output_dir / "tiktok_%(id)s.%(ext)s")
    ydl_opts = {
        "outtmpl": output_template,
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"tiktok": {"api_hostname": "api16-normal-c-useast1a.tiktokv.com"}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = ydl.prepare_filename(info)
    # Ensure we return the final mp4
    if not str(video_path).endswith(".mp4"):
        # yt-dlp with merge should produce mp4
        base = Path(video_path).with_suffix("")
        candidate = base.with_suffix(".mp4")
        if candidate.exists():
            video_path = str(candidate)
    return str(video_path)


def get_video_duration(video_path: str) -> float:
    """Get duration in seconds using ffprobe (available in most ComfyUI envs)."""
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        dur = float(result.stdout.strip())
        return dur
    except Exception:
        return 30.0  # safe fallback


def extract_frame(video_path: str, timestamp: float, output_name: str = "steady_dancer_pose.png") -> str:
    """Extract a single frame at the given timestamp (seconds) using ffmpeg."""
    output_path = COMFY_INPUT / output_name
    cmd = [
        "ffmpeg", "-y", "-ss", str(timestamp), "-i", video_path,
        "-vframes", "1", "-q:v", "2", str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    return str(output_path)


def queue_zimage_controlnet_pose(pose_image_path: str, prompt: str, lora_name: str = "None", lora_strength: float = 0.8):
    """
    Queue z-image-controlnet-api.json (or similar) for pose transfer.
    Uses the captured frame as ControlNet reference + user's LoRA for character.
    """
    api_path = CUSTOM_DIR / "z-image-controlnet-api.json"
    if not api_path.exists():
        return f"❌ ControlNet workflow not found: {api_path}", None

    pose_file = "steady_dancer_pose.png"
    if pose_image_path and os.path.exists(pose_image_path):
        shutil.copy2(pose_image_path, COMFY_INPUT / pose_file)

    with open(api_path, encoding="utf-8") as f:
        wf = json.load(f)

    updated = []
    for node_id, node in wf.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})
        meta_title = node.get("_meta", {}).get("title", "")

        # Patch the control / pose image (LoadImage nodes)
        if ct == "LoadImage" and "image" in inputs:
            inputs["image"] = pose_file
            updated.append(f"LoadImage {node_id} → {pose_file} (pose control)")

        # Patch prompt
        if ct in ("String Literal", "CLIPTextEncode") or "text" in inputs or "Prompt" in meta_title.lower():
            if "text" in inputs:
                inputs["text"] = prompt
                updated.append(f"Prompt {node_id} updated")
            elif "value" in inputs:
                inputs["value"] = prompt
                updated.append(f"Prompt {node_id} updated")

        # Patch LoRA - Power Lora Loader (rgthree) is common in these z-image/controlnet workflows
        if ct == "Power Lora Loader (rgthree)":
            if lora_name != "None":
                # rgthree Power Lora Loader often uses lora_1 / lora_1_strength pattern
                if "lora_1" in inputs:
                    inputs["lora_1"] = lora_name
                    if "lora_1_strength" in inputs:
                        inputs["lora_1_strength"] = lora_strength
                    updated.append(f"LoRA {node_id} → {lora_name} strength={lora_strength}")
                else:
                    # fallback for other structures
                    for k in list(inputs.keys()):
                        if "lora" in k.lower() and isinstance(inputs[k], str):
                            inputs[k] = lora_name
                            updated.append(f"LoRA {node_id} set {k}")
                    if "strength" in str(inputs).lower():
                        for k in inputs:
                            if "strength" in k.lower():
                                inputs[k] = lora_strength
            else:
                # disable by setting strength 0 if possible
                for k in inputs:
                    if "strength" in k.lower():
                        inputs[k] = 0.0
                updated.append(f"LoRA {node_id} disabled (strength 0)")

    url = "http://127.0.0.1:8188/prompt"
    payload = {
        "prompt": wf,
        "client_id": f"fedda-steady-pose-{int(datetime.now().timestamp())}"
    }

    try:
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 200:
            pid = resp.json().get("prompt_id", "unknown")
            return (
                f"✅ Queued pose-matched image via ControlNet + LoRA!\n"
                f"Prompt ID: {pid}\n\n"
                f"Patched: {', '.join(updated) if updated else 'defaults used'}"
            ), None
        else:
            detail = resp.text[:600] if resp.text else ""
            return f"❌ API error {resp.status_code}\n{detail}", None
    except Exception as e:
        return f"❌ Error queuing ControlNet pose: {e}", None


def queue_and_get_florence_caption(pose_image_path: str):
    """
    Run the FLORENCE-IMAGE-CAPTIONING.json on the captured pose frame.
    Returns (status_message, caption_text or None)
    The caption can then be used as the prompt for the pose-matched generation.
    """
    florence_path = CUSTOM_DIR / "FLORENCE-IMAGE-CAPTIONING.json"
    if not florence_path.exists():
        return f"❌ Florence caption workflow not found: {florence_path}", None

    pose_file = "steady_dancer_pose.png"
    if pose_image_path and os.path.exists(pose_image_path):
        shutil.copy2(pose_image_path, COMFY_INPUT / pose_file)

    with open(florence_path, encoding="utf-8") as f:
        wf = json.load(f)

    updated = []
    for node_id, node in wf.items():
        if not isinstance(node, dict):
            continue
        ct = node.get("class_type", "")
        inputs = node.get("inputs", {})

        if ct == "LoadImage" and "image" in inputs:
            inputs["image"] = pose_file
            updated.append(f"LoadImage {node_id} → {pose_file} (for captioning)")

    url = "http://127.0.0.1:8188/prompt"
    payload = {
        "prompt": wf,
        "client_id": f"fedda-florence-{int(datetime.now().timestamp())}"
    }

    try:
        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code != 200:
            return f"❌ Florence queue failed: {resp.status_code} {resp.text[:300]}", None

        prompt_id = resp.json().get("prompt_id")
        if not prompt_id:
            return "❌ No prompt_id returned", None

        # Poll history for the caption output (easy showAnything node usually)
        for _ in range(40):  # ~20 seconds max
            time.sleep(0.5)
            try:
                hresp = requests.get(f"http://127.0.0.1:8188/history/{prompt_id}", timeout=8)
                if hresp.status_code == 200:
                    hist = hresp.json()
                    if prompt_id in hist:
                        outputs = hist[prompt_id].get("outputs", {})
                        # Look for text outputs from caption nodes
                        for nid, out in outputs.items():
                            if "text" in out and out.get("text"):
                                texts = out["text"]
                                if isinstance(texts, list) and texts:
                                    caption = str(texts[0]).strip()
                                    if len(caption) > 5:
                                        return f"✅ Florence caption ready (id {prompt_id})", caption
                            if "anything" in out and out.get("anything"):
                                vals = out["anything"]
                                if isinstance(vals, list) and vals:
                                    caption = str(vals[0]).strip()
                                    if len(caption) > 5:
                                        return f"✅ Florence caption ready", caption
                        # Check if completed even if no text found yet
                        status = hist[prompt_id].get("status", {})
                        if status.get("completed") or status.get("status_str") == "success":
                            # fallback: any long string in outputs
                            for out in outputs.values():
                                for v in out.values():
                                    if isinstance(v, list) and v and isinstance(v[0], str) and len(v[0]) > 10:
                                        return "✅ Caption extracted", str(v[0]).strip()
            except Exception:
                pass

        return f"✅ Florence queued (prompt_id: {prompt_id}). Caption should appear in ComfyUI (easy showAnything node). You can copy it manually or re-run.", None

    except Exception as e:
        return f"❌ Error running Florence caption: {e}", None


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
with gr.Blocks(
    title="FEDDAKALKUN Studio",
    theme=fedda_theme,
    css=fedda_css
) as demo:
    # FEDDAKALKUN Branded Header with Cyber Bunny Logo
    with gr.Row():
        with gr.Column(scale=1, min_width=80):
            logo_path = str(Path(__file__).parent / "assets" / "feddakalkun_bunny_logo.png")
            if Path(logo_path).exists():
                gr.Image(
                    value=logo_path,
                    height=72,
                    width=72,
                    interactive=False,
                    show_label=False,
                    container=False
                )
            else:
                gr.Markdown("🐰")
        with gr.Column(scale=4):
            gr.Markdown("""
            # FEDDAKALKUN
            **Precision AI Creative Tools** — Direct ComfyUI Control
            """)

    gr.Markdown("---")

    with gr.Tabs():
        # ==================== KLEIN TAB ====================
        with gr.TabItem("🎭 Klein Character Studio"):
            gr.Markdown("**FEDDAKALKUN • Flux.2 Klein 9B** — Consistent character generation with 0, 1 or 2 reference images + optional LoRA.")

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
        with gr.TabItem("🎬 LTX Video"):
            gr.Markdown("**FEDDAKALKUN • LTX Video (23)** — Advanced video generation with image guides and conditioning.")

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

        # ==================== STEADY DANCER / TIKTOK POSE TAB ====================
        with gr.TabItem("💃 Steady Dancer (TikTok Pose)"):
            gr.Markdown("**FEDDAKALKUN • TikTok → Pose Frame → LoRA + ControlNet Image**")
            gr.Markdown("Add a TikTok link → preview & trim video → capture start frame pose → generate new image with your LoRA in the *exact same pose* using the Z-Image ControlNet workflow.")

            with gr.Row():
                tiktok_url = gr.Textbox(label="TikTok URL", placeholder="https://www.tiktok.com/@user/video/1234567890", scale=4)
                load_video_btn = gr.Button("Load & Preview Video", variant="secondary", scale=1)

            video_preview = gr.Video(label="Video Preview (play to check timing)", interactive=False, height=280)

            with gr.Row():
                start_sec = gr.Slider(0, 60, value=0, step=0.1, label="Start time (sec) - frame to capture for pose")
                end_sec = gr.Slider(0, 60, value=5, step=0.1, label="End time (sec) - optional trim reference")
                capture_btn = gr.Button("📸 Capture Start Frame as Pose", variant="primary")

            captured_pose = gr.Image(label="Captured Pose Reference (used for ControlNet)", type="filepath", height=220, interactive=False)

            with gr.Row():
                florence_btn = gr.Button("🖼️ Generate Florence Caption from Pose", variant="secondary")
                use_caption_btn = gr.Button("⬇️ Use Caption as Prompt", variant="secondary")

            florence_caption = gr.Textbox(label="Florence Generated Caption (edit before generating)", lines=4, interactive=True)

            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Pose-Matched Generation")
                    sd_prompt = gr.Textbox(
                        label="Prompt (describe the new scene/character while keeping the pose)",
                        lines=2,
                        value="the same person in exact same pose, highly detailed, cinematic lighting, photorealistic"
                    )
                    sd_lora = gr.Dropdown(choices=LORA_CHOICES, value="None", label="Character LoRA")
                    sd_lora_strength = gr.Slider(0.0, 2.0, value=0.85, step=0.05, label="LoRA Strength")
                    generate_btn = gr.Button("🚀 Generate Image with Exact Pose + LoRA", variant="primary", size="lg")

                with gr.Column():
                    sd_result = gr.Image(label="Generated Pose-Matched Image", height=320)
                    sd_status = gr.Textbox(label="Status / Log", lines=6, interactive=False)

            def do_load_tiktok(url):
                if not url or not url.strip():
                    return None, "Please enter a TikTok URL"
                try:
                    video_path = download_tiktok(url.strip())
                    dur = get_video_duration(video_path)
                    # clamp sliders later via updates if needed
                    return video_path, f"✅ Video loaded: {Path(video_path).name} (duration ~{dur:.1f}s)"
                except Exception as e:
                    return None, f"❌ Download failed: {e}\n(Make sure yt-dlp is installed and TikTok link is public)"

            load_video_btn.click(
                fn=do_load_tiktok,
                inputs=[tiktok_url],
                outputs=[video_preview, sd_status]
            )

            def do_capture(video_path, start_t):
                if not video_path:
                    return None, "Load a video first"
                try:
                    frame_path = extract_frame(video_path, float(start_t))
                    return frame_path, f"✅ Captured frame at {start_t}s → {Path(frame_path).name}"
                except Exception as e:
                    return None, f"❌ Frame capture failed: {e}"

            capture_btn.click(
                fn=do_capture,
                inputs=[video_preview, start_sec],
                outputs=[captured_pose, sd_status]
            )

            def do_generate_florence_caption(pose_path):
                if not pose_path:
                    return "", "Capture a pose frame first"
                msg, caption = queue_and_get_florence_caption(pose_path)
                return caption or "", msg

            florence_btn.click(
                fn=do_generate_florence_caption,
                inputs=[captured_pose],
                outputs=[florence_caption, sd_status]
            )

            use_caption_btn.click(
                fn=lambda c: c,
                inputs=[florence_caption],
                outputs=[sd_prompt]
            )

            def do_generate_pose(pose_path, prompt, lora, strength):
                if not pose_path:
                    return None, "Capture a pose frame first"
                msg, _ = queue_zimage_controlnet_pose(pose_path, prompt, lora, strength)
                # try to show latest generated image
                latest = None
                out_dir = WORKSPACE / "App" / "ComfyUI" / "output"
                if out_dir.exists():
                    imgs = sorted(out_dir.glob("*.png"), key=lambda x: x.stat().st_mtime, reverse=True)
                    if imgs:
                        latest = str(imgs[0])
                return latest, msg

            generate_btn.click(
                fn=do_generate_pose,
                inputs=[captured_pose, sd_prompt, sd_lora, sd_lora_strength],
                outputs=[sd_result, sd_status]
            )

            gr.Markdown("""
            **How it works (Steady Dancer Pose Flow):**
            1. Paste TikTok link → Load video (yt-dlp downloads it).
            2. Play the preview, set Start time to the desired pose moment.
            3. Capture Start Frame → this becomes the ControlNet pose reference.
            4. (Optional but recommended) Click **Generate Florence Caption** on the captured frame. This runs the FLORENCE-IMAGE-CAPTIONING.json workflow to create a rich descriptive prompt.
            5. Edit the caption if you want, or click **Use Caption as Prompt**.
            6. Choose your character LoRA + strength.
            7. Generate → uses z-image-controlnet-api.json (ControlNet + your LoRA) to create the image with the *exact same pose* + the good caption.
            """)

        # ==================== HOME / LANDING TAB ====================
        with gr.TabItem("🏠 Overview"):
            gr.Markdown("""
            ## FEDDAKALKUN • Workflow Studios

            Click the tabs above to use each focused studio.

            **Currently implemented:**
            - **Klein Character Studio** — Best for consistent character images with 0-2 refs + optional LoRA.
            - **LTX Video** — Advanced LTX video generation with image guides.

            **More workflows ready to activate:**
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

            This is the official **FEDDAKALKUN** creative control surface.
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
    print(f"FEDDAKALKUN Studio launching on http://127.0.0.1:{port}")
    demo.launch(
        server_name="127.0.0.1",
        server_port=port,
        inbrowser=True,
        show_error=True
        # theme is already set on Blocks
    )