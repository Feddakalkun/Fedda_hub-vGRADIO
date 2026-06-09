# REQUIRED CUSTOM NODES & CORE NODES INVENTORY
# For the Flux 2 Klein Character Studio UI (and future landing page workflows)

**Purpose**  
This file is the single source of truth for every `class_type` that appears in the workflow JSONs used by this UI (currently the three `flux_klein_9b_*reference_lora.json` files).  

It is **critical** for building the custom ComfyUI installer that will be tailored exactly to this UI + the workflows it drives.

Format is intentionally simple so it can be parsed by a future installer script (YAML/JSON conversion or direct markdown table parsing).

**Last updated**: 2026-06-09 (after the drag-drop + no-JSON refactor)  
**Source workflows**: `UI/custom_workflows/flux_klein_9b_0-reference_lora.json`, `_1-...`, `_2-...`

---

## Core ComfyUI Nodes (built into main ComfyUI – usually no extra install required)

These are part of the official ComfyUI distribution (comfyanonymous/ComfyUI). The installer should ensure a recent enough ComfyUI version that includes Flux support.

| class_type                  | Human / Title in workflows          | Source                  | Install / Notes |
|-----------------------------|-------------------------------------|-------------------------|-----------------|
| LoadImage                   | Load Image                          | Core                    | Built-in |
| SaveImage                   | Save Image                          | Core                    | Built-in |
| CLIPLoader                  | CLIP Loader                         | Core                    | Built-in |
| CLIPTextEncode              | CLIP Text Encode (Prompt)           | Core                    | Built-in |
| UNETLoader                  | UNET Loader (Flux)                  | Core                    | Built-in (Flux support required) |
| VAELoader                   | VAE Loader                          | Core                    | Built-in |
| VAEDecode                   | VAE Decode                          | Core                    | Built-in |
| VAEEncode                   | VAE Encode                          | Core                    | Built-in |
| KSamplerSelect              | KSampler Select                     | Core                    | Built-in |
| RandomNoise                 | RandomNoise                         | Core                    | Built-in |
| SamplerCustomAdvanced       | SamplerCustomAdvanced               | Core                    | Built-in |
| CFGGuider                   | CFGGuider                           | Core                    | Built-in |
| EmptyFlux2LatentImage       | EmptyFlux2LatentImage               | Core (Flux)             | Requires recent ComfyUI with Flux 2 support |
| Flux2Scheduler              | Flux2Scheduler                      | Core (Flux)             | Requires recent ComfyUI with Flux 2 support |
| ImageScaleToTotalPixels     | ImageScaleToTotalPixels             | Core / extras           | Often available in recent builds |
| ConditioningZeroOut         | ConditioningZeroOut                 | Core                    | Built-in |
| Text Concatenate            | Text Concatenate                    | Core / custom scripts   | May come from Custom-Scripts or Impact |

---

## Custom Nodes / Packs (must be installed)

These `class_type` values are added by third-party custom node repositories. The future installer **must** clone or Manager-install these.

| class_type                | Human / Title in workflows                     | Source Pack / Repo                                      | Recommended Install Command (git or Manager) | Notes / Used by Klein |
|---------------------------|------------------------------------------------|---------------------------------------------------------|----------------------------------------------|-----------------------|
| LoraLoaderModelOnly       | LoraLoaderModelOnly (Model Only LoRA)          | Core (comfyanonymous/ComfyUI) loaders category          | Usually built-in in modern ComfyUI. If missing: update ComfyUI. Some older installs pull from custom lora packs. | Critical for the optional LoRA path in all 0/1/2 lora jsons. Sets strength 0 to disable. |
| PrimitiveStringMultiline  | Prompt (multiline string input)                | pythongosssss/ComfyUI-Custom-Scripts **or** rgthree-comfy **or** ltdrdata/ComfyUI-Impact-Pack | `git clone https://github.com/pythongosssss/ComfyUI-Custom-Scripts custom_nodes/ComfyUI-Custom-Scripts`<br>or via ComfyUI-Manager: "ComfyUI Custom Scripts" | The main prompt injection target (looks for title containing "Prompt" + "value"/"string" input). Very widely used. |
| ReferenceLatent           | ReferenceLatent (and Reference Conditioning groups) | User-specific Flux Klein setup + capitan01R/ComfyUI-Flux2Klein-Enhancer (and similar latent ref packs) | The Klein Character Studio workflow groups contain custom subgraphs. Installer should ensure the nodes that produce "ReferenceLatent" class are present (often part of the user's exported groups or the enhancer repo). | **Core to the character consistency** in the 1-ref and 2-ref lora workflows. The 0-ref json does not use it. |
| HuggingFaceDownloader     | 🤗 HuggingFace Model Downloader Pro            | jnxmx/ComfyUI_HuggingFace_Downloader **or** if-ai/ComfyUI-IF_AI_HFDownloaderNode | `git clone https://github.com/jnxmx/ComfyUI_HuggingFace_Downloader custom_nodes/ComfyUI_HuggingFace_Downloader`<br>Alternative: https://github.com/if-ai/ComfyUI-IF_AI_HFDownloaderNode | Appears in the workflows for auto model downloads. The title "Pro" version may be one of the IF_AI or similar forks. |
| easy int                  | easy int                                       | yolain/ComfyUI-Easy-Use                                 | `git clone https://github.com/yolain/ComfyUI-Easy-Use custom_nodes/ComfyUI-Easy-Use` (then run install.bat or pip -r requirements) | Very popular "easy" pack (2.5k+ stars). Provides many quality-of-life nodes. |
| easy showAnything         | easy showAnything                              | yolain/ComfyUI-Easy-Use                                 | Same as above | Debug / preview helper from the same pack. |
| Load Styles CSV           | Load Styles CSV                                | ltdrdata/ComfyUI-Impact-Pack (or pythongosssss Custom Scripts / Fooocus style nodes) | `git clone https://github.com/ltdrdata/ComfyUI-Impact-Pack custom_nodes/ComfyUI-Impact-Pack` | Present in the 0-ref and 2-ref lora jsons. (Note: the no-style 1-ref variant removed the need for style handling in UI.) |
| AspectRatioImageSize      | AspectRatioImageSize                           | ltdrdata/ComfyUI-Impact-Pack **or** yolain/ComfyUI-Easy-Use **or** WAS Node Suite | See Impact-Pack or Easy-Use above | Resolution helper used across the lora variants. |

---

## Additional Notes for the Future Installer

1. **Flux 2 Klein specific behavior** lives mostly in the **grouped subgraphs** ("Reference Conditioning", the 9B character studio groups, etc.) inside the user's exported JSONs. The class_types above are the leaf nodes; the groups themselves carry a lot of the magic. The installer may need to also copy or ensure certain "definitions" or extra files that the user has in their current ComfyUI setup.

2. Many "easy_*" and "Impact" nodes are extremely common in the broader v337 project (not just Klein). Installing ComfyUI-Easy-Use + ComfyUI-Impact-Pack early will cover a huge percentage of workflows the landing page will eventually expose.

3. **HuggingFaceDownloader** variants: There are several similarly-named nodes. The installer should prefer the one whose node title matches "🤗 HuggingFace Model Downloader Pro" if the exact class_type differs slightly between forks. The current workflows use the class_type `HuggingFaceDownloader`.

4. **Versioning**: Record exact commit or "as of 2026-06 in v337" for reproducibility. The table above uses "latest at time of UI refactor" as the baseline.

5. **ComfyUI-Manager compatibility**: All the repos listed above are Manager-installable. The future installer should support both "git clone + restart" and "ComfyUI-Manager batch install" modes.

6. **Core Flux requirements**: A reasonably recent ComfyUI (post-Flux2 / Klein support) is mandatory. The three lora jsons assume the Flux 2 model loaders and schedulers are present.

7. When new workflows are added (via the planned landing page with cards), **append** any new `class_type` values discovered by scanning their API-format JSONs to this file, with the same columns.

---

## Quick "Required for Klein Character Studio" Minimal Set (for a lean installer profile)

If someone wants the absolute smallest set that makes the current Klein UI work:

- Recent ComfyUI (with Flux 2 + Klein support)
- ComfyUI-Easy-Use (for easy int / showAnything + many others)
- ComfyUI-Impact-Pack (for Load Styles CSV, AspectRatio..., and many common nodes)
- ComfyUI_HuggingFace_Downloader (or equivalent HF downloader the user prefers)
- pythongosssss/ComfyUI-Custom-Scripts (or rgthree-comfy) for reliable PrimitiveStringMultiline
- The specific Flux2Klein reference latent / conditioning nodes the user currently has (ComfyUI-Flux2Klein-Enhancer or the subgraphs embedded in the studio JSON)

Everything else in the table is either core or a nice-to-have that the broader project already uses.

---

**How to keep this file in sync (for future agents)**:
- After adding a new workflow card/panel that uses a new API JSON:
  1. Parse the new JSON for unique class_type values.
  2. For any unknown ones, add a row (research the GitHub repo via class_type name + "comfyui").
  3. Append to the tables above.
  4. Update the "Last updated" date and the source workflows list.
  5. Mention the addition in BREADCRUMBS + HANDOFF.

This file + the three (or more) lora API JSONs in custom_workflows/ are the contract between the UI and the future custom ComfyUI installer.
