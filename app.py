"""
Local LinkedIn Publishing Agent - Main Streamlit Application.
100% Local, Zero Cloud Dependencies, RAM-optimized for 8 GB Windows PCs.
Author: Aayush Bhatta
"""
import os
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st
from PIL import Image

from config import config
from core.db import db
from core.linkedin_client import (
    LinkedInAPIError,
    LinkedInAuthError,
    LinkedInPermissionError,
    LinkedInRateLimitError,
    linkedin_client,
)
from core.oauth import LinkedInOAuth, OAuthError, StateMismatchError, TokenExchangeError
from core.ollama_client import ollama_client
from core.token_store import token_store
from core.url_intake import url_intake

# Page Configuration
st.set_page_config(
    page_title="aayushifty's LinkedIn Agent",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for polished technical look
st.markdown(
    """
    <style>
    .main-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0A66C2;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #666;
        margin-bottom: 1.2rem;
    }
    .status-badge {
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.85rem;
        font-weight: 600;
    }
    .status-connected {
        background-color: #E8F5E9;
        color: #2E7D32;
        border: 1px solid #A5D6A7;
    }
    .status-disconnected {
        background-color: #FFF3E0;
        color: #E65100;
        border: 1px solid #FFCC80;
    }
    .linkedin-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 16px;
        margin-top: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .linkedin-author {
        font-weight: 600;
        font-size: 1rem;
        color: #191919;
    }
    .linkedin-headline {
        font-size: 0.8rem;
        color: #666666;
    }
    .linkedin-body {
        margin-top: 12px;
        font-size: 0.95rem;
        line-height: 1.45;
        white-space: pre-wrap;
        color: #191919;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def handle_oauth_callback():
    """Intercepts and handles OAuth 2.0 query parameters from LinkedIn redirect."""
    params = st.query_params
    code = params.get("code")
    received_state = params.get("state")
    error = params.get("error")
    error_desc = params.get("error_description")

    if error:
        st.error(f"LinkedIn OAuth Authorization Failed: {error_desc or error}")
        st.query_params.clear()
        return

    if code and received_state:
        # Retrieve expected state from session state or file
        expected_state = st.session_state.get("oauth_state")
        state_file = Path(config.media_upload_dir.parent / ".oauth_state_temp")

        if not expected_state and state_file.exists():
            try:
                expected_state = state_file.read_text(encoding="utf-8").strip()
            except Exception:
                expected_state = None

        if not LinkedInOAuth.verify_state(received_state, expected_state):
            st.error("Security Alert: OAuth state verification failed (CSRF check mismatch). Authorization aborted.")
            st.query_params.clear()
            return

        with st.spinner("Exchanging authorization code for secure access token..."):
            try:
                token_data = LinkedInOAuth.exchange_code_for_token(
                    code=code,
                    client_id=config.client_id,
                    client_secret=config.client_secret,
                    redirect_uri=config.redirect_uri,
                )
                access_token = token_data["access_token"]
                expires_in = token_data.get("expires_in", 5184000)
                scopes = token_data.get("scope", "")

                # Fetch member profile info
                profile = linkedin_client.get_member_profile(access_token)
                member_urn = profile.get("person_urn", "")
                member_name = profile.get("name", config.author_name)

                # Persist securely
                token_store.save_token(
                    access_token=access_token,
                    expires_in=expires_in,
                    member_urn=member_urn,
                    member_name=member_name,
                    scopes=scopes,
                )

                # Clean up state
                if state_file.exists():
                    state_file.unlink(missing_ok=True)
                st.session_state["oauth_state"] = None
                st.query_params.clear()
                st.success(f"Successfully connected to LinkedIn as **{member_name}**!")
                time.sleep(1)
                st.rerun()

            except TokenExchangeError as e:
                st.error(f"Token Exchange Error: {e}")
                st.query_params.clear()
            except Exception as e:
                st.error(f"Unexpected authentication error: {e}")
                st.query_params.clear()


# Process OAuth callback if present in URL
handle_oauth_callback()

# Get current token and Ollama health
auth_status = token_store.get_token_status()
ollama_health = ollama_client.check_health()

# ================= SIDEBAR =================
with st.sidebar:
    st.markdown("### 💼 aayushifty's LinkedIn Agent")
    st.markdown(f"**Author:** {config.author_name}")
    st.markdown(f"**Role:** {config.author_role}")
    st.divider()

    # Connection Status Pill
    if auth_status["connected"]:
        st.markdown(
            f'<div class="status-badge status-connected">● Connected: {auth_status["member_name"]}</div>',
            unsafe_allow_html=True,
        )
        st.caption(f"Expires in: **{auth_status['expires_in_days']} days** | Token: `{auth_status['masked_token']}`")
        if st.button("🔌 Disconnect", use_container_width=True, type="secondary"):
            token_store.delete_token()
            st.success("Disconnected and removed local credentials.")
            st.rerun()
    else:
        st.markdown(
            '<div class="status-badge status-disconnected">○ LinkedIn: Not Connected</div>',
            unsafe_allow_html=True,
        )
        st.caption("Using manual copy/fallback or configure OAuth in settings.")

    st.divider()

    # Ollama Local AI Health Pill
    if ollama_health["available"]:
        writer_icon = "✅" if ollama_health["has_writer"] else "⚠️"
        vision_icon = "✅" if ollama_health["has_vision"] else "ℹ️"
        st.markdown(f"**Local Ollama:** `Online`")
        st.caption(f"{writer_icon} Writing: `{config.ollama_writing_model}`")
        st.caption(f"{vision_icon} Vision: `{config.ollama_vision_model}`")
    else:
        st.markdown("**Local Ollama:** `Offline / Fallback`")
        st.caption("Automatic deterministic templates active.")
        st.info("To enable local LLMs:\n`ollama serve`")

    st.divider()
    menu = st.radio(
        "Navigation",
        ["✍️ Create & Publish", "🔑 LinkedIn Auth & Status", "🗄️ Publication History", "⚙️ Diagnostics & Help"],
        index=0,
    )

    st.divider()
    st.caption("Windows 8GB RAM Friendly | 100% Local Inference")


# ================= VIEW 1: CREATE & PUBLISH =================
if menu == "✍️ Create & Publish":
    st.markdown('<div class="main-header">aayushifty\'s LinkedIn Agent</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Feed your project repos, diagrams, or notes. '
        'Local AI writes grounded, authentic posts without corporate clichés and publishes via official LinkedIn API.</div>',
        unsafe_allow_html=True,
    )

    col_input, col_preview = st.columns([1.1, 1], gap="medium")

    with col_input:
        st.subheader("1. Project Intake")

        project_title = st.text_input(
            "Project or Milestone Title*",
            placeholder="e.g. OpenJarvis, HandChord MIDI, OfflinePay ESP32",
            value=st.session_state.get("draft_title", ""),
        )

        content_mode = st.selectbox(
            "Content Angle / Mode",
            [
                ("launch", "🚀 Project Launch / Open Source Release"),
                ("lesson", "🛠️ Technical Lesson / Hard Debugging Story"),
                ("progress", "📈 Build-in-Public / Commit Milestone"),
                ("architecture", "📐 System Architecture Deep-Dive"),
            ],
            format_func=lambda x: x[1],
            index=0,
        )[0]

        intake_tabs = st.tabs(["🐙 GitHub / URL Intake", "📷 Project Photo / Diagram", "📝 Raw Notes / Highlights"])

        # Tab 1: URL Intake
        with intake_tabs[0]:
            intake_url = st.text_input(
                "GitHub Repository or Demo URL",
                placeholder="https://github.com/aayushbhatta/OpenJarvis or https://mydemo.dev",
                value=st.session_state.get("draft_url", ""),
            )
            if st.button("🔍 Inspect URL & Fetch Metadata", type="secondary"):
                if intake_url:
                    with st.spinner("Fetching project metadata and README..."):
                        info = url_intake.inspect_url(intake_url)
                        if info.get("success"):
                            st.session_state["fetched_summary"] = info.get("formatted_summary", "")
                            if not project_title and info.get("title"):
                                st.session_state["draft_title"] = info.get("title")
                                project_title = info.get("title")
                            st.success(f"Retrieved metadata for **{info.get('title', intake_url)}**")
                        else:
                            st.error(info.get("error", "Failed to inspect URL"))
                else:
                    st.warning("Please enter a URL first.")

            if st.session_state.get("fetched_summary"):
                st.text_area(
                    "Fetched Metadata / Code Context",
                    value=st.session_state["fetched_summary"],
                    height=130,
                    key="fetched_summary_view",
                )

        # Tab 2: Image Intake
        with intake_tabs[1]:
            uploaded_file = st.file_uploader(
                "Upload Project Photo, Screenshot, or Architecture Diagram",
                type=["png", "jpg", "jpeg", "webp"],
                help="Image will be compressed and analyzed locally using Moondream vision model.",
            )
            image_analysis_text = ""
            media_saved_path = None

            if uploaded_file is not None:
                # Save locally in uploads dir
                file_ext = Path(uploaded_file.name).suffix or ".jpg"
                safe_name = f"upload_{int(time.time())}{file_ext}"
                target_path = config.media_upload_dir / safe_name
                with open(target_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                media_saved_path = str(target_path)
                st.session_state["current_media_path"] = media_saved_path

                # Display small thumbnail
                img = Image.open(target_path)
                st.image(img, caption=f"Uploaded: {uploaded_file.name} ({img.size[0]}x{img.size[1]}px)", width=320)

                if st.button("🧠 Analyze Image with Moondream", type="secondary"):
                    with st.spinner("Running local vision model (moondream)..."):
                        v_res = ollama_client.analyze_image(target_path)
                        if v_res.get("success"):
                            st.session_state["image_analysis"] = v_res.get("analysis", "")
                            st.success("Extracted visual context!")
                        else:
                            st.warning(v_res.get("analysis", "Vision model offline; proceed with manual notes."))

            if st.session_state.get("image_analysis"):
                st.text_area("Extracted Visual Context", value=st.session_state["image_analysis"], height=80)

        # Tab 3: Author Notes
        with intake_tabs[2]:
            author_notes = st.text_area(
                "Your Personal Engineering Notes / Hard Problems Solved*",
                placeholder="What trade-offs did you make? What was the hardest bug? What is unique about your approach?",
                value=st.session_state.get("draft_notes", ""),
                height=140,
            )

        st.markdown("---")

        # Draft Generation Button
        if st.button("✨ Generate Grounded Technical Post", type="primary", use_container_width=True):
            if not project_title and not author_notes and not intake_url and not uploaded_file:
                st.error("Please provide at least a Project Title, URL, Photo, or Notes.")
            else:
                summary_ctx = st.session_state.get("fetched_summary", "")
                img_analysis = st.session_state.get("image_analysis", "")

                # Auto-recognize repository / URL if not already fetched
                target_query = intake_url or project_title
                if not summary_ctx and target_query:
                    with st.spinner(f"Auto-recognizing repository for '{target_query}'..."):
                        auto_info = url_intake.inspect_url(target_query)
                        if auto_info.get("success"):
                            summary_ctx = auto_info.get("formatted_summary", "")
                            st.session_state["fetched_summary"] = summary_ctx
                            if auto_info.get("url"):
                                intake_url = auto_info.get("url")
                                st.session_state["draft_url"] = intake_url
                            if auto_info.get("title") and not project_title:
                                project_title = auto_info.get("title")
                                st.session_state["draft_title"] = project_title
                            st.info(f"Auto-recognized repository: **{auto_info.get('title', intake_url)}**")

                # If image attached but not yet analyzed, run analysis
                if media_saved_path and not img_analysis:
                    with st.spinner("Analyzing uploaded image context..."):
                        v_res = ollama_client.analyze_image(media_saved_path)
                        if v_res.get("success"):
                            img_analysis = v_res.get("analysis", "")
                            st.session_state["image_analysis"] = img_analysis

                with st.spinner(f"Generating full technical post with {ollama_client.writing_model}..."):
                    gen_result = ollama_client.generate_draft(
                        mode=content_mode,
                        title=project_title or "Technical Project",
                        summary_context=summary_ctx,
                        user_notes=author_notes,
                        image_analysis=img_analysis,
                        source_url=intake_url,
                    )

                    generated_text = gen_result.get("text", "")
                    st.session_state["active_post_text"] = generated_text
                    st.session_state["active_post_title"] = project_title or "Untitled Project"
                    st.session_state["active_post_url"] = intake_url or ""
                    st.session_state["active_post_type"] = (
                        "github" if "github.com" in (intake_url or "") else ("photo" if uploaded_file else "text")
                    )

                    # Save as draft in SQLite database
                    draft_id = db.save_draft(
                        project_title=project_title or "Untitled",
                        source_type=st.session_state["active_post_type"],
                        source_url=intake_url or "",
                        raw_input=f"{summary_ctx}\n{author_notes}".strip(),
                        post_text=generated_text,
                        media_path=st.session_state.get("current_media_path"),
                    )
                    st.session_state["active_draft_id"] = draft_id

                    if gen_result.get("is_fallback"):
                        st.info(gen_result.get("note", "Generated via offline engine."))
                    else:
                        st.success(f"Generated comprehensive technical post with {gen_result.get('model_used')}!")

    with col_preview:
        st.subheader("2. Review, Edit & Preview")

        current_text = st.session_state.get("active_post_text", "")
        edited_text = st.text_area(
            "Editable Post Text",
            value=current_text,
            height=280,
            help="Review and tweak the draft. Keep it high-signal and authentic.",
        )
        if edited_text != current_text:
            st.session_state["active_post_text"] = edited_text

        char_count = len(edited_text)
        max_chars = 3000
        color_char = "green" if char_count <= 2500 else ("orange" if char_count <= 3000 else "red")
        st.markdown(
            f"<small style='color:{color_char}'>Length: <b>{char_count}</b> / {max_chars} characters</small>",
            unsafe_allow_html=True,
        )

        # LinkedIn Card Preview
        st.markdown("**Live LinkedIn Card Preview:**")
        author_display = auth_status.get("member_name") or config.author_name
        media_path = st.session_state.get("current_media_path")

        preview_html = f"""
        <div class="linkedin-card">
            <div class="linkedin-author">{author_display}</div>
            <div class="linkedin-headline">{config.author_role} • 1st</div>
            <div class="linkedin-body">{edited_text or '<i>Your post preview will appear here...</i>'}</div>
        </div>
        """
        st.markdown(preview_html, unsafe_allow_html=True)

        if media_path and Path(media_path).exists():
            st.image(media_path, caption="Attached Media Preview", use_container_width=True)

        st.divider()

        # ================= PUBLISH & SAFEGUARDS =================
        st.subheader("3. Publish & Safeguards")

        if not edited_text.strip():
            st.info("Generate or type a post draft above to review publishing options.")
        else:
            # Check for duplicate submissions in last 7 days
            duplicate = db.check_duplicate(edited_text)
            allow_publish = True

            if duplicate:
                st.warning(
                    f"⚠️ **Duplicate Warning**: An identical post was already published on "
                    f"**{duplicate.get('created_at')}** (URN: `{duplicate.get('linkedin_post_urn')}`)."
                )
                duplicate_ack = st.checkbox(
                    "I acknowledge this is a duplicate and wish to publish anyway",
                    value=False,
                )
                if not duplicate_ack:
                    allow_publish = False

            # Explicit final publish confirmation requirement
            confirm_publish = st.checkbox(
                "☑️ I have reviewed this post and confirm publishing to LinkedIn",
                value=False,
                help="Explicit confirmation required to prevent accidental submissions.",
            )

            col_pub1, col_pub2 = st.columns([1, 1])

            with col_pub1:
                publish_btn = st.button(
                    "🚀 Publish to LinkedIn API",
                    type="primary",
                    disabled=not (confirm_publish and allow_publish and auth_status["connected"]),
                    use_container_width=True,
                )

                if publish_btn:
                    token_data = token_store.get_token()
                    if not token_data or not token_data.get("access_token"):
                        st.error("No valid LinkedIn token found. Please connect in LinkedIn Auth tab.")
                    else:
                        with st.spinner("Publishing post through official LinkedIn Posts API..."):
                            access_token = token_data["access_token"]
                            author_urn = token_data.get("member_urn") or auth_status.get("member_urn")

                            image_urn = None
                            # If media is attached, execute official image upload sequence
                            if media_path and Path(media_path).exists():
                                try:
                                    st.write("Initializing image upload asset...")
                                    upload_url, img_urn = linkedin_client.initialize_image_upload(
                                        access_token=access_token,
                                        owner_urn=author_urn,
                                    )
                                    with open(media_path, "rb") as img_file:
                                        img_bytes = img_file.read()
                                    linkedin_client.upload_image_binary(upload_url, img_bytes)
                                    image_urn = img_urn
                                except Exception as img_err:
                                    st.warning(f"Media upload encountered an issue: {img_err}. Posting commentary.")

                            draft_id = st.session_state.get("active_draft_id")
                            try:
                                post_result = linkedin_client.create_post(
                                    access_token=access_token,
                                    author_urn=author_urn,
                                    commentary=edited_text,
                                    image_urn=image_urn,
                                    article_url=st.session_state.get("active_post_url"),
                                )
                                post_urn = post_result.get("post_urn", "")

                                # Update DB status
                                if draft_id:
                                    db.update_status(
                                        post_id=draft_id,
                                        status="published",
                                        linkedin_post_urn=post_urn,
                                        updated_text=edited_text,
                                    )

                                st.balloons()
                                st.success(f"🎉 Successfully published to LinkedIn! Post URN: `{post_urn}`")

                            except LinkedInAuthError as e:
                                st.error(f"Authentication Error: {e}")
                                if draft_id:
                                    db.update_status(draft_id, "failed", error_message=str(e))
                            except LinkedInPermissionError as e:
                                st.error(f"Permission Error: {e}")
                                if draft_id:
                                    db.update_status(draft_id, "failed", error_message=str(e))
                            except LinkedInAPIError as e:
                                st.error(f"API Error: {e}")
                                if draft_id:
                                    db.update_status(draft_id, "failed", error_message=str(e))
                            except Exception as e:
                                st.error(f"Publishing failed: {e}")

            with col_pub2:
                # Convenient Manual Fallback
                st.caption("Manual Publishing Fallback:")
                share_url = f"https://www.linkedin.com/feed/?shareActive=true&text={edited_text[:200]}"
                st.link_button(
                    "🌐 Open LinkedIn Web Share",
                    url="https://www.linkedin.com/feed/?shareActive=true",
                    use_container_width=True,
                )

                if st.button("📋 Save to History as Manual Post", use_container_width=True):
                    draft_id = st.session_state.get("active_draft_id")
                    if draft_id:
                        db.update_status(draft_id, "copied_manually", updated_text=edited_text)
                    else:
                        db.save_draft(
                            project_title=st.session_state.get("active_post_title", "Manual Post"),
                            source_type="text",
                            source_url=st.session_state.get("active_post_url", ""),
                            raw_input="",
                            post_text=edited_text,
                        )
                    st.success("Saved to local history as 'Copied Manually'.")


# ================= VIEW 2: LINKEDIN AUTH & STATUS =================
elif menu == "🔑 LinkedIn Auth & Status":
    st.markdown('<div class="main-header">Official LinkedIn OAuth 2.0 Connection</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Connect using official OAuth 2.0 flow. '
        'Passwords, scraping, or browser automations are never used.</div>',
        unsafe_allow_html=True,
    )

    col_stat1, col_stat2 = st.columns([1, 1])

    with col_stat1:
        st.subheader("Current Connection State")
        if auth_status["connected"]:
            st.success(f"✅ **Connected as:** {auth_status['member_name']}")
            st.markdown(f"**Member URN:** `{auth_status['member_urn']}`")
            st.markdown(f"**Masked Token:** `{auth_status['masked_token']}`")
            st.markdown(f"**Access Token Validity:** ~{auth_status['expires_in_days']} days remaining")
            st.markdown(f"**Approved Scopes:** `{auth_status.get('scopes', 'openid profile w_member_social')}`")

            if st.button("🔴 Safe Disconnect", type="primary"):
                token_store.delete_token()
                st.info("Access token safely wiped from local secure storage.")
                st.rerun()
        else:
            st.warning("⚠️ **Disconnected / Not Authorized**")
            st.write(
                "To publish directly through the official API, connect your LinkedIn Developer App below. "
                "If you haven't created one yet, the manual fallback in the draft tab is always available."
            )

    with col_stat2:
        st.subheader("Connect via Official OAuth Flow")

        if not config.is_linkedin_configured():
            st.error("Missing `LINKEDIN_CLIENT_ID` or `LINKEDIN_CLIENT_SECRET` in `.env` configuration.")
            st.info(
                "**Setup Steps:**\n"
                "1. Go to [LinkedIn Developer Portal](https://developer.linkedin.com)\n"
                "2. Create an App and add the **'Share on LinkedIn'** and **'Sign In with LinkedIn using OpenID Connect'** products.\n"
                "3. Add Redirect URI: `http://localhost:8501`\n"
                "4. Copy Client ID and Client Secret into your `.env` file."
            )
        else:
            try:
                auth_url, state_token = LinkedInOAuth.build_auth_url(
                    client_id=config.client_id,
                    redirect_uri=config.redirect_uri,
                    scopes=config.scopes,
                )
                # Store state token in session and backup file
                st.session_state["oauth_state"] = state_token
                state_file = Path(config.media_upload_dir.parent / ".oauth_state_temp")
                try:
                    state_file.write_text(state_token, encoding="utf-8")
                except Exception:
                    pass

                st.write("Click below to authorize with LinkedIn's official consent screen:")
                st.link_button(
                    "🔗 Connect with LinkedIn",
                    url=auth_url,
                    type="primary",
                    use_container_width=True,
                )
                st.caption(f"Redirect URI configured: `{config.redirect_uri}`")
                st.caption(f"Scopes requested: `{', '.join(config.scopes)}`")

            except OAuthError as e:
                st.error(f"Configuration error: {e}")

    st.divider()
    st.subheader("Security & Privacy Guarantees")
    st.markdown(
        """
        - **No Password Collection**: We never prompt for or handle your LinkedIn password.
        - **Zero Browser Automation / Scraping**: All actions use official LinkedIn REST endpoints (`/rest/posts`, `/rest/images`).
        - **Secure Local Storage**: Access tokens are stored using Windows Credential Locker / DPAPI. Tokens are never placed in SQLite, Git, or logs.
        - **Localhost Isolation**: The application and OAuth redirect URI are strictly bound to `localhost`.
        - **CSRF Protection**: All OAuth handshakes use cryptographically secure constant-time state validation.
        """
    )


# ================= VIEW 3: PUBLICATION HISTORY =================
elif menu == "🗄️ Publication History":
    st.markdown('<div class="main-header">Publication & Draft History</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Local SQLite audit log of generated drafts, posts, and API results.</div>', unsafe_allow_html=True)

    history = db.get_history(limit=50)

    if not history:
        st.info("No publication history yet. Generate and publish your first post!")
    else:
        status_colors = {
            "published": "🟢 Published",
            "draft": "🟡 Draft",
            "copied_manually": "🔵 Copied Manually",
            "failed": "🔴 Failed",
        }

        for item in history:
            status_label = status_colors.get(item["status"], item["status"])
            with st.expander(f"{status_label} | {item['project_title']} ({item['created_at'][:16]})"):
                col_h1, col_h2 = st.columns([2, 1])

                with col_h1:
                    st.text_area("Post Content", value=item["post_text"], height=160, key=f"hist_txt_{item['id']}")

                with col_h2:
                    st.markdown(f"**Status:** {item['status'].upper()}")
                    if item.get("source_url"):
                        st.markdown(f"**Source URL:** [{item['source_url']}]({item['source_url']})")
                    if item.get("linkedin_post_urn"):
                        st.markdown(f"**LinkedIn URN:** `{item['linkedin_post_urn']}`")
                    if item.get("error_message"):
                        st.error(f"Error: {item['error_message']}")
                    if item.get("media_path") and Path(item["media_path"]).exists():
                        st.image(item["media_path"], caption="Attached Media", width=160)

                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        if st.button("Load into Editor", key=f"load_{item['id']}"):
                            st.session_state["active_post_text"] = item["post_text"]
                            st.session_state["active_post_title"] = item["project_title"]
                            st.session_state["active_post_url"] = item.get("source_url", "")
                            st.session_state["current_media_path"] = item.get("media_path")
                            st.session_state["active_draft_id"] = item["id"]
                            st.success("Draft loaded! Switch to 'Create & Publish' tab to view.")
                    with col_act2:
                        if st.button("🗑️ Delete", key=f"del_{item['id']}"):
                            db.delete_post(item["id"])
                            st.rerun()


# ================= VIEW 4: DIAGNOSTICS & HELP =================
elif menu == "⚙️ Diagnostics & Help":
    st.markdown('<div class="main-header">System Diagnostics & Windows Guide</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Monitor local resources, model statuses, and environment configuration.</div>', unsafe_allow_html=True)

    col_d1, col_d2 = st.columns(2)

    with col_d1:
        st.subheader("Local Inference Engine (Ollama)")
        st.markdown(f"**Base URL:** `{config.ollama_base_url}`")
        st.markdown(f"**Writing Model:** `{config.ollama_writing_model}`")
        st.markdown(f"**Vision Model:** `{config.ollama_vision_model}`")

        if ollama_health["available"]:
            st.success("✅ Ollama service is running and reachable!")
            st.write(f"**Detected Models:** {', '.join(ollama_health['models']) or 'None'}")
            if not ollama_health["has_writer"]:
                st.warning(f"Writing model `{config.ollama_writing_model}` not found in Ollama.")
                st.code(f"ollama pull {config.ollama_writing_model}", language="powershell")
            if not ollama_health["has_vision"]:
                st.info(f"Vision model `{config.ollama_vision_model}` not found (optional for images).")
                st.code(f"ollama pull {config.ollama_vision_model}", language="powershell")
        else:
            st.error("❌ Ollama service is not responding at localhost:11434.")
            st.markdown(
                """
                **How to start Ollama on Windows:**
                1. Open PowerShell or Command Prompt.
                2. Run `ollama serve` (or launch the Ollama Windows app from Start menu).
                3. Download the writing model:
                ```powershell
                ollama pull qwen2.5:3b
                ollama pull moondream
                ```
                """
            )

    with col_d2:
        st.subheader("8 GB RAM Performance Safeguards")
        st.markdown(
            """
            This application is engineered specifically for 8 GB RAM Windows systems:
            - **Sequential Model Execution**: Never runs Moondream and Qwen simultaneously.
            - **Image Resizing**: Images are scaled to max 1024px before base64 encoding, preventing VRAM/RAM spikes.
            - **Bounded Context Window**: LLM context capped at 2,048 tokens (`num_ctx: 2048`).
            - **Zero Cloud Costs**: All inferences run locally offline once weights are pulled.
            - **Deterministic Fallback**: If Ollama is offline or busy, authentic template generation ensures you are never blocked.
            """
        )

        st.subheader("Configuration Status")
        st.write(f"Database Path: `{config.db_path}`")
        st.write(f"Uploads Path: `{config.media_upload_dir}`")
        st.write(f"LinkedIn Client ID Configured: `{'Yes' if config.is_linkedin_configured() else 'No'}`")
        st.write(f"LinkedIn Redirect URI: `{config.redirect_uri}`")

