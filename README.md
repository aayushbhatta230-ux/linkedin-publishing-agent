# Local LinkedIn Publishing Agent

> **100% Local, Zero Cloud Dependencies, RAM-Optimized for 8 GB Windows PCs.**  
> Automatically analyzes your project repositories, demo sites, screenshots, or engineering notes using local AI (`qwen2.5:3b` + `moondream`), drafts authentic technical posts without corporate clichés, and publishes them through LinkedIn's official OAuth 2.0 & Posts REST API.

---

## 🌟 Core Features

1. **Multi-Modal Intake**:
   - **GitHub URLs**: Auto-fetches repo description, language, topics, and README excerpts.
   - **Public Web / Demo URLs**: Extracts page title, meta description, and clean section previews.
   - **Project Photos & Diagrams**: Compresses and analyzes UI screenshots or circuit diagrams locally with `moondream`.
   - **Raw Engineering Notes**: Captures trade-offs, bugs, and latency optimizations.

2. **Authentic Technical Voice (Zero Corporate Sludge)**:
   - Grounded in real builder experience (Aayush Bhatta's persona).
   - Strictly bans generic buzzwords ("in today's fast-paced world", "delve into", "super excited", "synergy", "game changer").
   - Max 1–2 subtle emojis or zero; technical hooks instead of clickbait.
   - 4 Content Modes:
     - 🚀 **Project Launch / Open Source Release**
     - 🛠️ **Technical Lesson / Hard Debugging Story**
     - 📈 **Build-in-Public / Commit Milestone**
     - 📐 **System Architecture Deep-Dive**

3. **RAM-Optimized for 8 GB Windows Hardware**:
   - **Sequential Execution**: Never loads vision and writing models simultaneously.
   - **Automatic Image Downsizing**: Resizes images to max 1024px before base64 encoding, preventing VRAM/RAM exhaustion.
   - **Bounded Context**: Hard-capped at 2,048 tokens (`num_ctx: 2048`).
   - **Deterministic Offline Fallback**: If Ollama is offline or busy, authentic template generation ensures you are never blocked.

4. **Compliant Official LinkedIn API**:
   - Implements official OAuth 2.0 authorization code flow with CSRF state protection.
   - Posts via modern REST API (`POST https://api.linkedin.com/rest/posts` and `/rest/images`).
   - Full 3-step media upload sequence for image posts.
   - Safe Disconnect button to wipe tokens immediately.
   - **Never collects passwords, scrapes pages, or automates browser sessions.**

5. **Guardrails & History**:
   - **Duplicate Submission Detection**: Hashes post content (SHA-256) and warns if an identical post was published within 7 days.
   - **Explicit Confirmation**: Requires checking an explicit confirmation box before the Publish button unlocks.
   - **Local SQLite History**: Complete audit log with timestamps, post status, source URLs, and LinkedIn URNs.
   - **1-Click Manual Fallback**: If API access is unconfigured or pending approval, one click opens the official LinkedIn share dialog with your post ready to paste.

---

## 📂 Project Structure

```
linkedin-publishing-agent/
├── app.py                     # Interactive Streamlit UI
├── config.py                  # Environment settings & configuration
├── conftest.py                # Pytest configuration
├── run_app.ps1                # 1-click Windows PowerShell launch script
├── run_app.bat                # 1-click Windows batch launch script
├── requirements.txt           # Python dependencies
├── .env.example               # Configuration template
├── .gitignore                 # Secrets, token caches, and DB ignore rules
├── core/
│   ├── __init__.py
│   ├── config.py              # Typed configuration
│   ├── db.py                  # SQLite database manager & duplicate prevention
│   ├── token_store.py         # Windows Credential Locker (Keyring) manager
│   ├── oauth.py               # LinkedIn OAuth 2.0 flow & CSRF state manager
│   ├── linkedin_client.py     # Official REST Posts API & Media Upload client
│   ├── ollama_client.py       # Sequential Ollama client & RAM safeguards
│   ├── persona.py             # Technical builder persona & fallback templates
│   └── url_intake.py          # GitHub & public webpage metadata extractor
└── tests/
    ├── test_db.py             # SQLite CRUD & duplicate detection tests
    ├── test_linkedin_client.py# LinkedIn API client & error mapping tests
    ├── test_oauth.py          # OAuth state, URL builder & token exchange tests
    ├── test_ollama_client.py  # Prompt formatting, RAM resizing & fallback tests
    ├── test_token_store.py    # Keyring, expiration & safe disconnect tests
    └── test_url_intake.py     # GitHub & webpage parser tests
```

---

## ⚡ Quick Start (Windows PowerShell)

### 1. Prerequisites
- **Python 3.11+** installed (verify with `python --version`).
- **Ollama** installed on Windows (download from [ollama.com](https://ollama.com)).

### 2. Pull Local AI Models
Open PowerShell and download the two compact local models:

```powershell
# Writing model (~2.0 GB - runs comfortably in 8 GB RAM)
ollama pull qwen2.5:3b

# Vision model for photo/diagram analysis (~1.7 GB)
ollama pull moondream
```

### 3. Launch the Application
Navigate to the project directory and run:

```powershell
cd C:\Users\joshi\.gemini\antigravity\scratch\linkedin-publishing-agent

# Run the 1-click PowerShell launcher:
.\run_app.ps1
```

Or run manually:

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\streamlit run app.py
```

The application opens automatically in your browser at **`http://localhost:8501`**.

---

## 🔑 LinkedIn Developer App & OAuth 2.0 Setup

If you want direct 1-click API publishing:

### Step 1: Create a LinkedIn Developer Application
1. Go to the [LinkedIn Developer Portal](https://developer.linkedin.com) and click **Create App**.
2. Fill in:
   - **App Name**: e.g., `Aayush Local Publishing Agent`
   - **LinkedIn Page**: Link your personal or test LinkedIn page.
   - **App Logo**: Upload any square icon.

### Step 2: Request Required Products
In your app's **Products** tab, request access to:
- **Share on LinkedIn**: Grants the `w_member_social` permission to publish posts.
- **Sign In with LinkedIn using OpenID Connect**: Grants `openid` and `profile` permissions to authenticate and retrieve your member ID.

### Step 3: Configure Redirect URI
1. Go to the **Auth** tab in your LinkedIn developer portal.
2. Under **OAuth 2.0 settings**, click the edit pencil next to **Authorized redirect URLs for your app**.
3. Add:
   ```
   http://localhost:8501
   ```
4. Note your **Client ID** and **Client Secret**.

### Step 4: Configure Local `.env`
Copy `.env.example` to `.env`:

```powershell
cp .env.example .env
```

Edit `.env` with your credentials:
```ini
LINKEDIN_CLIENT_ID=your_actual_client_id
LINKEDIN_CLIENT_SECRET=your_actual_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8501
LINKEDIN_SCOPES=openid profile w_member_social
```

### Step 5: Connect in the App
1. Open the app (`http://localhost:8501`) and navigate to the **🔑 LinkedIn Auth & Status** tab.
2. Click **🔗 Connect with LinkedIn**.
3. Authorize your app on the LinkedIn consent screen.
4. LinkedIn redirects back to `http://localhost:8501`. The app validates the CSRF state token, exchanges the code for a secure access token, and stores it in Windows Credential Locker.

> [!NOTE]
> **Pending LinkedIn Developer Approval?**
> If your developer app is awaiting LinkedIn review for the `w_member_social` product, the application **automatically provides a 1-click manual fallback**. You can draft, review, and preview your post, then click **🌐 Open LinkedIn Web Share** to publish with zero friction.

---

## 🔒 Security & Privacy Guarantees

- **No Passwords Collected**: The app never prompts for or stores your LinkedIn credentials.
- **Zero Browser Automation / Scraping**: No Puppeteer/Playwright browser automation or cookie extraction. Everything uses official REST endpoints.
- **Windows Credential Locker (Keyring)**: Access tokens are stored using Windows DPAPI / Credential Manager. Tokens are **never** stored in SQLite, committed to Git, or shown raw in the UI.
- **CSRF State Validation**: OAuth handshakes enforce cryptographically random 32-byte state tokens verified with constant-time equality checks.
- **Bound to Localhost**: Binds strictly to `localhost` by default.

---

## 🧪 Verification & Automated Tests

All core modules are verified with a 30-test automated test suite using `pytest`. Network calls and LinkedIn endpoints are strictly mocked (zero real secrets exposed).

To run the test suite:

```powershell
cd C:\Users\joshi\.gemini\antigravity\scratch\linkedin-publishing-agent
.\.venv\Scripts\pytest -v
```

### Test Results:
```
tests/test_db.py::test_schema_initialization PASSED
tests/test_db.py::test_save_and_retrieve_draft PASSED
tests/test_db.py::test_update_status_published PASSED
tests/test_db.py::test_duplicate_submission_detection PASSED
tests/test_db.py::test_history_ordering_and_deletion PASSED
tests/test_linkedin_client.py::test_get_member_profile_userinfo PASSED
tests/test_linkedin_client.py::test_initialize_image_upload_success PASSED
tests/test_linkedin_client.py::test_upload_image_binary PASSED
tests/test_linkedin_client.py::test_create_text_post_success PASSED
tests/test_linkedin_client.py::test_create_post_with_media_success PASSED
tests/test_linkedin_client.py::test_linkedin_error_status_mapping PASSED
tests/test_oauth.py::test_build_auth_url_structure PASSED
tests/test_oauth.py::test_build_auth_url_missing_params PASSED
tests/test_oauth.py::test_state_verification_constant_time PASSED
tests/test_oauth.py::test_exchange_code_success PASSED
tests/test_oauth.py::test_exchange_code_error_handling PASSED
tests/test_ollama_client.py::test_persona_system_prompt_rules PASSED
tests/test_ollama_client.py::test_deterministic_offline_generator PASSED
tests/test_ollama_client.py::test_image_resizing_safeguard PASSED
tests/test_ollama_client.py::test_ollama_health_online PASSED
tests/test_ollama_client.py::test_ollama_health_offline PASSED
tests/test_ollama_client.py::test_generate_draft_online PASSED
tests/test_ollama_client.py::test_generate_draft_offline_fallback PASSED
tests/test_token_store.py::test_save_and_retrieve_token PASSED
tests/test_token_store.py::test_token_expiration_validation PASSED
tests/test_token_store.py::test_masked_token_status PASSED
tests/test_token_store.py::test_safe_disconnect_wipes_token PASSED
tests/test_url_intake.py::test_parse_github_repo PASSED
tests/test_url_intake.py::test_fetch_github_info_success PASSED
tests/test_url_intake.py::test_fetch_webpage_info_success PASSED

============================= 30 passed in 0.90s ==============================
```
