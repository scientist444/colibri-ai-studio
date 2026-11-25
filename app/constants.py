"""Application-wide constants, supported Colibri families, and defaults."""

from __future__ import annotations

from typing import Final

APP_NAME: Final[str] = "Colibri AI Studio"
APP_SLUG: Final[str] = "ColibriAIStudio"
APP_VERSION: Final[str] = "1.0.0"
APP_ORGANIZATION: Final[str] = "ColibriAIStudio"

# Official Colibri repository and API endpoints
COLIBRI_GITHUB_REPO: Final[str] = "JustVugg/colibri"
COLIBRI_GITHUB_RELEASES_URL: Final[str] = "https://api.github.com/repos/JustVugg/colibri/releases"
COLIBRI_GITHUB_HTML_URL: Final[str] = "https://github.com/JustVugg/colibri"
HUGGINGFACE_API_BASE: Final[str] = "https://huggingface.co"

# Keyring service/account identifiers for Windows Credential Manager
KEYRING_SERVICE_NAME: Final[str] = "ColibriAIStudio"
KEYRING_HF_TOKEN_ACCOUNT: Final[str] = "huggingface_api_token"
KEYRING_LOCAL_API_KEY_ACCOUNT: Final[str] = "local_server_api_key"

# Default local server settings
DEFAULT_HOST: Final[str] = "127.0.0.1"
DEFAULT_PORT: Final[int] = 8000
DEFAULT_CTX_TOKENS: Final[int] = 4096
DEFAULT_TEMPERATURE: Final[float] = 0.6
DEFAULT_TOP_P: Final[float] = 0.95
DEFAULT_MAX_TOKENS: Final[int] = 1024

# Default memory safety reserves (GB)
DEFAULT_SYSTEM_RAM_RESERVE_GB: Final[float] = 4.0
MIN_SAFE_SYSTEM_RAM_RESERVE_GB: Final[float] = 2.0
DEFAULT_VRAM_HEADROOM_GB: Final[float] = 1.5

# Official Colibri family registry mapping (mirrors c/family_registry.py)
COLIBRI_SUPPORTED_FAMILIES: Final[dict[str, dict[str, object]]] = {
    "glm53": {
        "engine_exe": "glm53.exe",
        "model_types": ("glm5_next", "glm5_next_text"),
        "gguf_archs": ("glm5-next",),
        "display_name": "GLM-5.3 MoE",
    },
    "glm": {
        "engine_exe": "colibri.exe",
        "model_types": ("glm_moe_dsa", "glm5_moe", "glm", "mistral_large4"),
        "gguf_archs": ("glm-dsa", "mistral-large4"),
        "display_name": "GLM-5 / Mistral Large 4 MoE",
    },
    "inkling": {
        "engine_exe": "inkling.exe",
        "model_types": ("inkling_mm_model", "inkling"),
        "gguf_archs": ("inkling",),
        "display_name": "Inkling MoE",
    },
    "kimi": {
        "engine_exe": "kimi_k3.exe",
        "model_types": ("kimi_k3", "kimi_linear"),
        "gguf_archs": ("kimi-k3",),
        "display_name": "Kimi-K3 MoE",
    },
    "olmoe": {
        "engine_exe": "olmoe.exe",
        "model_types": ("olmoe",),
        "gguf_archs": ("olmoe",),
        "display_name": "OLMoE",
    },
    "qwen36": {
        "engine_exe": "qwen36.exe",
        "model_types": (
            "qwen3_5_moe",
            "qwen3_5_moe_text",
            "qwen3_5",
            "qwen3_5_text",
            "qwen3_moe",
            "qwen3",
            "flint",
            "muse_spark",
            "lfm3",
            "lfm3_vl",
        ),
        "gguf_archs": (
            "qwen35moe",
            "qwen35",
            "qwen3moe",
            "qwen3",
            "flint",
            "muse-spark",
            "lfm3",
        ),
        "display_name": "Qwen3 / Qwen3.5 / Qwen3.6 / LFM3",
    },
    "qwen38": {
        "engine_exe": "qwen38.exe",
        "model_types": ("qwen4_exp", "qwen4_exp_text"),
        "gguf_archs": ("qwen4exp",),
        "display_name": "Qwen3.8 Flash Next",
    },
    "deepseek_v4": {
        "engine_exe": "deepseek_v4.exe",
        "model_types": ("deepseek_v4",),
        "gguf_archs": ("deepseek4",),
        "display_name": "DeepSeek-V4",
    },
    "deepseek_v41": {
        "engine_exe": "deepseek_v41.exe",
        "model_types": ("deepseek_v41", "deepseek_v41_text"),
        "gguf_archs": ("deepseek41",),
        "display_name": "DeepSeek-V4.1",
    },
    "mimo": {
        "engine_exe": "mimo.exe",
        "model_types": ("mimo_v2",),
        "gguf_archs": ("mimo2",),
        "display_name": "Xiaomi MiMo-V2.6",
    },
    "qwen_image": {
        "engine_exe": "qwenimage.exe",
        "model_types": ("qwenimage21pipeline",),
        "gguf_archs": (),
        "display_name": "Qwen-Image 2.1",
    },
    "laya": {
        "engine_exe": "laya.exe",
        "model_types": ("laya_modernbert",),
        "gguf_archs": (),
        "display_name": "Laya RL Router",
    },
    "gliner_decide": {
        "engine_exe": "gliner_decide.exe",
        "model_types": ("gliner2_span_deberta-v2",),
        "gguf_archs": (),
        "display_name": "GLiNER Decide",
    },
}

# Flattened lookup tables for verified architecture checking
SUPPORTED_CONFIG_MODEL_TYPES: Final[dict[str, str]] = {
    str(mt).lower(): family
    for family, meta in COLIBRI_SUPPORTED_FAMILIES.items()
    for mt in meta["model_types"]  # type: ignore[attr-defined]
}

SUPPORTED_GGUF_ARCHITECTURES: Final[dict[str, str]] = {
    str(arch).lower(): family
    for family, meta in COLIBRI_SUPPORTED_FAMILIES.items()
    for arch in meta["gguf_archs"]  # type: ignore[attr-defined]
}

# Workload memory profiles
WORKLOAD_PROFILES: Final[dict[str, dict[str, object]]] = {
    "ai_dedicated": {
        "label": "AI Dedicated",
        "description": "Maximum safe resources for model inference. Reserves 4 GB system RAM for Windows and 1.0 GB GPU VRAM.",
        "system_ram_reserve_gb": 4.0,
        "vram_headroom_gb": 1.0,
        "ram_fraction_cap": 0.85,
        "policy": "quality",
    },
    "balanced_desktop": {
        "label": "Balanced Desktop",
        "description": "Leaves sufficient memory for normal Windows applications, browsers, and productivity tools.",
        "system_ram_reserve_gb": 6.0,
        "vram_headroom_gb": 1.5,
        "ram_fraction_cap": 0.72,
        "policy": "balanced",
    },
    "engineering_workstation": {
        "label": "Engineering Workstation",
        "description": "Reserves extra RAM and GPU VRAM for heavy applications such as CAD, Blender, Unity, or industrial SCADA.",
        "system_ram_reserve_gb": 12.0,
        "vram_headroom_gb": 4.0,
        "ram_fraction_cap": 0.55,
        "policy": "balanced",
    },
    "custom": {
        "label": "Custom",
        "description": "User-defined RAM and GPU VRAM allocation budgets.",
        "system_ram_reserve_gb": 4.0,
        "vram_headroom_gb": 1.5,
        "ram_fraction_cap": 0.80,
        "policy": "balanced",
    },
}

# Performance Lab Tuning Presets
PERFORMANCE_PROFILES: Final[dict[str, dict[str, object]]] = {
    "eco": {
        "label": "Eco",
        "description": "Lower CPU thread count and conservative memory cache to minimize power and thermal output.",
        "thread_ratio": 0.5,
        "policy": "balanced",
        "ctx_tokens": 2048,
    },
    "balanced": {
        "label": "Balanced",
        "description": "Optimal balance of physical P-cores, expert cache budget, and desktop responsiveness.",
        "thread_ratio": 0.85,
        "policy": "balanced",
        "ctx_tokens": 4096,
    },
    "maximum_safe": {
        "label": "Maximum Safe Performance",
        "description": "Uses all physical P-cores, maximum safe RAM/VRAM expert caching, and quality retention policy.",
        "thread_ratio": 1.0,
        "policy": "quality",
        "ctx_tokens": 8192,
    },
    "engineering_multitasking": {
        "label": "Engineering Multitasking",
        "description": "Caps CPU threads and reserves GPU VRAM so 3D/CAD/IDE tools remain responsive during inference.",
        "thread_ratio": 0.5,
        "policy": "balanced",
        "ctx_tokens": 4096,
    },
    "custom": {
        "label": "Custom",
        "description": "Manual control over CPU threads, context window, cache policy, and GPU offload.",
        "thread_ratio": 1.0,
        "policy": "balanced",
        "ctx_tokens": 4096,
    },
}
