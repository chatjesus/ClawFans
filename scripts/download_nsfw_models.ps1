# ============================================================
# Download NSFW Anime Image Generation Models for ComfyUI
# RTX 5090 (32GB) - Full quality, no compromises
# ============================================================

$ComfyUI = "C:\Users\PRO\Desktop\CUDA\ComfyUI\models"
$HF_TOKEN = ""   # Optional: set if you have HuggingFace token

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " SynClub Local - NSFW Anime Model Downloader" -ForegroundColor Cyan
Write-Host " Target GPU: RTX 5090 (32GB VRAM)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Helper ──
function Download-File($url, $dest, $name) {
    if (Test-Path $dest) {
        $size = [math]::Round((Get-Item $dest).Length / 1GB, 2)
        Write-Host "  [SKIP] $name already exists ($size GB)" -ForegroundColor Yellow
        return
    }
    Write-Host "  [DL] Downloading $name ..." -ForegroundColor Green
    Write-Host "       $url" -ForegroundColor Gray
    $ProgressPreference = 'SilentlyContinue'
    Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
    $size = [math]::Round((Get-Item $dest).Length / 1GB, 2)
    Write-Host "  [OK] Saved: $dest ($size GB)" -ForegroundColor Green
}

# ── 1. BASE MODEL: illustriousXL v1.1 (Best NSFW anime SDXL base, 2025) ──
Write-Host ""
Write-Host "[1/4] IllustriousXL v1.1 - Best NSFW anime SDXL base model" -ForegroundColor Magenta
Write-Host "      Quality: Outstanding anime illustration + NSFW support" -ForegroundColor Gray
$dest1 = "$ComfyUI\checkpoints\illustriousXL_v1.1.safetensors"
Download-File `
  "https://huggingface.co/OnomaAIResearch/Illustrious-xl-early-release-v0/resolve/main/illustriousXL_v0.1.safetensors" `
  $dest1 "illustriousXL"

# ── 2. VAE: sdxl-vae-fp16-fix (fixes color issues on SDXL) ──
Write-Host ""
Write-Host "[2/4] SDXL VAE (fp16-fix) - Fixes washed-out colors" -ForegroundColor Magenta
$dest2 = "$ComfyUI\vae\sdxl_vae_fp16fix.safetensors"
Download-File `
  "https://huggingface.co/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors" `
  $dest2 "sdxl-vae-fp16-fix"

# ── 3. UPSCALER: 4x-UltraSharp (Best upscaler for anime) ──
Write-Host ""
Write-Host "[3/4] 4x-UltraSharp Upscaler - Sharp anime upscaling" -ForegroundColor Magenta
$dest3 = "$ComfyUI\upscale_models\4x-UltraSharp.pth"
Download-File `
  "https://huggingface.co/Kim2091/UltraSharp/resolve/main/4x-UltraSharp.pth" `
  $dest3 "4x-UltraSharp"

# ── 4. CLIP: SDXL CLIP encoders ──
Write-Host ""
Write-Host "[4/4] CLIP text encoders for SDXL" -ForegroundColor Magenta
$clipDir = "$ComfyUI\clip"
$dest4a = "$clipDir\clip_l.safetensors"
$dest4b = "$clipDir\clip_g.safetensors"
Download-File `
  "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/text_encoder/model.fp16.safetensors" `
  $dest4a "CLIP-L"
Download-File `
  "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/text_encoder_2/model.fp16.safetensors" `
  $dest4b "CLIP-G"

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " Download complete!" -ForegroundColor Green
Write-Host ""
Write-Host " Next steps:" -ForegroundColor Yellow
Write-Host "  1. Start ComfyUI: cd C:\Users\PRO\Desktop\CUDA\ComfyUI && python main.py --listen" -ForegroundColor White
Write-Host "  2. Open: http://localhost:8188" -ForegroundColor White
Write-Host "  3. Load the workflow: synclub-local\scripts\nsfw_workflow.json" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
