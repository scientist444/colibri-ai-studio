# Security Policy

## Local-First Privacy Guarantees

Colibri AI Studio is designed as a **100% local AI workstation**:
- Inference runs locally on `127.0.0.1` via the Colibri engine (`coli serve`).
- Hugging Face Read Tokens and optional local API keys are stored encrypted in **Windows Credential Manager** via `keyring` (`ColibriAIStudio`).
- Application logs automatically redact Bearer tokens, Hugging Face tokens (`hf_...`), and API keys before writing to disk or exporting diagnostic bundles.

## Reporting a Vulnerability

If you discover a security issue (such as HTML/XSS injection in the Markdown renderer, unsafe path traversal during model downloads, or credential leakage in logs), please open a private security advisory on GitHub or report it responsibly with reproduction steps and affected file paths.
