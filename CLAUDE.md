# CLAUDE.md - aayushifty's LinkedIn Agent

This document is the single source of truth for Claude to understand, develop, and maintain this project efficiently while minimizing token usage.

---

## 1. Project Overview & Architecture
A 100% local, privacy-first desktop & web application for software engineers to generate, preview, and publish grounded technical LinkedIn posts with media attachments.

- **Stack:** Python 3.10+ / Streamlit UI / SQLite audit log / Local Ollama LLMs.
- **Hardware Profile:** Optimized for Windows with 8 GB RAM (runs models sequentially; memory-capped image resizing).
- **Core Principles:** Zero scraping, zero password collection, strictly official LinkedIn REST API (`v202610`), local SQLite history, Windows Credential Locker (`keyring`).

---

## 2. Directory Structure & Key Files
- `app.py`: Streamlit main frontend UI, tab navigation, in-app credential manager, OAuth callback handler.
- `config.py`: Environment configuration via `.env` with fallback defaults.
- `core/`
  - `linkedin_client.py`: Official REST API client for post publishing and media uploads (`/rest/posts`, `/rest/images`, version `202610`).
  - `oauth.py`: Constant-time CSRF validation, token exchange with browser User-Agent and connection retries.
  - `token_store.py`: Windows Credential Locker token storage with secure JSON fallback.
  - `ollama_client.py`: Sequential inference client for Ollama (`qwen2.5:3b`, `qwen3:4b-instruct`, `moondream`).
  - `persona.py`: Grounded technical voice generator ("Aayush Bhatta / @aayushifty"), bans buzzwords, structures posts.
  - `url_intake.py`: Fetches GitHub READMEs (up to 8,000 characters) from URLs or repo names.
  - `db.py`: SQLite persistence (`posts` table), SHA-256 duplicate detection.
- `assets/`: App branding (`logo.png`, `icon.ico`).
- `tests/`: 30 unit tests covering all core modules (`pytest`).

---

## 3. Important Development Rules (Token Saver)
1. **Never read or index:** `.venv/`, `uploads/`, `__pycache__/`, `.pytest_cache/`, `*.db`.
2. **Never break 8 GB RAM optimizations:** Do not run concurrent Ollama calls. Always keep image processing capped at 1024px.
3. **LinkedIn API Version:** Must remain pinned to `202610` (LinkedIn sunset versions prior to 2024).
4. **Testing:** Run all tests before and after changes with:
   ```powershell
   .\.venv\Scripts\pytest
   ```
5. **Running App:**
   ```powershell
   .\.venv\Scripts\streamlit run app.py --server.port 8501 --server.headless true
   ```

---

## 4. Current Challenge & Next Objectives
- **Friction in Multi-User / Friend Setup:** Currently requires friends to enter a LinkedIn Developer `Client ID` and `Client Secret` if they want to publish via the API.
- **Goal:** Simplify user onboarding so friends do NOT need to create their own developer app. Provide a seamless login experience where users just log in with their LinkedIn credentials or app accounts.
