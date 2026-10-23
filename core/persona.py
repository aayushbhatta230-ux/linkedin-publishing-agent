"""
Builder persona definition and prompt templates for technical LinkedIn publishing.
Grounds generated drafts in direct engineering realities, trade-offs, and humility.
Strictly eliminates generic corporate buzzwords, fake metrics, and AI clichés.
"""
from typing import Any, Dict, Optional

BANNED_PHRASES = [
    "in today's fast-paced world",
    "delve into",
    "testament to",
    "thrilled to announce",
    "super excited",
    "game changer",
    "groundbreaking",
    "synergy",
    "leverage",
    "revolutionize",
    "paradigm shift",
    "a journey of",
    "next level",
    "seamlessly integrate",
]


def build_system_prompt(author_name: str = "Aayush Bhatta", author_role: str = "Technical Builder & Engineer") -> str:
    """Builds a strict, high-signal system prompt for local LLMs."""
    return f"""You are the personal technical writing engine for {author_name} ({author_role}).
PROFILE:
- Passionate technical builder focused on Computer Science, AI agents, Robotics, Hardware, and Open Source.
- Persona: Real engineer and builder solving tangible software and system challenges. NOT a corporate marketer, NOT an influencer, NOT a generic tech enthusiast.

CORE WRITING PRINCIPLES:
1. Grounded & Authentic: Speak from hands-on code, hardware wiring, latency optimizations, and debugging logs.
2. Technically Specific: Mention real tools, architectures, trade-offs, and edge cases. Avoid vague generalities.
3. Hook First (reach matters, author is growing from zero followers): The first line must stop the scroll on its own, since LinkedIn cuts posts after roughly 210 characters ("...see more"). Use a concrete surprising result, a specific mistake, or a bold but true claim, under 120 characters. No clickbait, no fake numbers.
3b. Skimmable: One idea per short paragraph (1-3 lines), blank line between paragraphs, so the post reads well on a phone.
4. Humble & Curious: Acknowledge bugs, mistakes, performance limits, and ongoing questions.
5. Absolute Truthfulness: NEVER invent fake benchmarks, fake GitHub stars, or imaginary production deployments.
6. Zero Corporate Sludge: Strictly avoid: {', '.join(BANNED_PHRASES)}.
7. Minimal Emojis: Maximum 1 or 2 subtle, relevant emojis across the entire post, or none.
8. Relevant Hashtags: End with 3-4 specific technical hashtags (e.g. #Python #OpenSource #Robotics #ComputerVision).
9. Invite Conversation: Close (before the hashtags) with one specific, easy-to-answer question for other builders. Comments are the strongest reach signal.
10. Links: Put the repository/demo link near the end, never in the first lines.

Output ONLY the complete post text ready for review. Do not include meta commentary, preamble, or quotation marks around the post.
"""


def format_user_prompt(
    mode: str,
    title: str,
    summary_context: str,
    user_notes: str,
    image_analysis: Optional[str] = None,
    source_url: Optional[str] = None,
) -> str:
    """Combines intake inputs into a structured prompt based on content mode."""
    mode_instructions = {
        "launch": (
            "Goal: Announce this open-source project or tool release.\n"
            "Focus: What problem it solves, how it works under the hood, key technical constraints, and where to try it."
        ),
        "lesson": (
            "Goal: Share a specific technical lesson, bug, or debugging realization encountered while building this.\n"
            "Focus: The symptom, the wrong assumption, the actual root cause, and the cleaner solution."
        ),
        "progress": (
            "Goal: Share a realistic build-in-public milestone update.\n"
            "Focus: What shipped this week, engineering trade-offs faced, and what comes next."
        ),
        "architecture": (
            "Goal: Walk through the system architecture and data pipeline.\n"
            "Focus: Component interaction, why specific tools were picked, and latency/memory considerations."
        ),
    }

    selected_mode_text = mode_instructions.get(mode, mode_instructions["launch"])

    prompt_parts = [
        f"TASK: Write a professional technical LinkedIn post.",
        f"CONTENT ANGLE: {mode.upper()} - {selected_mode_text}",
        f"\nPROJECT / TOPIC: {title or 'Technical Project'}",
    ]

    if source_url:
        prompt_parts.append(f"SOURCE URL: {source_url}")

    if summary_context:
        prompt_parts.append(f"\nCONTEXT / CODE METADATA:\n{summary_context}")

    if image_analysis:
        prompt_parts.append(f"\nIMAGE / UI ANALYSIS:\n{image_analysis}")

    if user_notes:
        prompt_parts.append(f"\nAUTHOR'S SPECIFIC NOTES / KEY HIGHLIGHTS:\n{user_notes}")

    prompt_parts.append(
        "\nCRITICAL REQUIREMENT: Do NOT output a superficial or truncated summary. "
        "Feed and cover the ENTIRE technical context, README details, architecture blocks, and user notes thoroughly. "
        "Structure the post logically with:\n"
        "1. Concrete Problem & Motivation: What tangible real-world or developer friction is being solved?\n"
        "2. Technical Architecture & Stack: Name the real frameworks, models, hardware, and data flow from the context.\n"
        "3. Core Features & Hard Trade-offs: Dive into key capabilities, latency optimizations, edge cases, or bugs handled.\n"
        "4. Builder Takeaways: Honest reflection on what works and what is being refined next.\n"
        "5. Project Link: Include the repository/demo link cleanly at the end.\n"
        "6. Closing Question: One specific question that invites other engineers to comment.\n"
        "Ensure full, rich depth (between 1,300 to 2,000 characters) so readers get the full picture without important parts being omitted."
    )

    return "\n".join(prompt_parts)


def generate_deterministic_offline_post(
    mode: str,
    title: str,
    context: str,
    user_notes: str,
    image_analysis: Optional[str] = None,
    source_url: Optional[str] = None,
) -> str:
    """
    Deterministic local fallback generator.
    Produces comprehensive, authentic posts even when Ollama is offline or uninstalled.
    Thoroughly weaves in README sections, features, and technical context.
    """
    clean_title = title.strip() or "Technical Project"
    url_line = f"\n\nSource & Setup Details: {source_url}" if source_url else ""
    visual_note = f"\n\nVisual Architecture / Interface: {image_analysis.strip()}" if image_analysis else ""

    # Extract high-signal snippets from README / context
    context_lines = [line.strip() for line in (context + "\n" + user_notes).splitlines() if line.strip()]
    tech_highlights = [l for l in context_lines if any(k in l.lower() for k in ["•", "-", "*", "architecture", "feature", "engine", "model", "local", "stack", "pipeline"])][:5]
    highlight_block = ("\n" + "\n".join(f"• {h.lstrip('•-* ')}" for h in tech_highlights)) if tech_highlights else ""

    notes_blurb = f"\n\nContext & Specific Notes:\n{user_notes.strip()}" if user_notes.strip() else ""

    if mode == "lesson":
        return (
            f"A practical engineering breakdown from building {clean_title}:{notes_blurb}\n\n"
            "When designing local-first technical systems, the most demanding bottlenecks rarely stem from raw compute—they "
            "arise from uncoordinated I/O pipelines, state synchronization, and unexpected memory fragmentation. "
            "Deep debugging revealed where latency silently aggregated across system boundaries.\n\n"
            f"Key technical areas addressed in this implementation:{highlight_block or chr(10) + '• Bounded memory footprint with sequential model execution' + chr(10) + '• Explicit error isolation at integration boundaries' + chr(10) + '• Zero reliance on brittle browser automation or third-party cloud services'}\n\n"
            "By enforcing strict buffer limits, separating intake from inference engines, and prioritizing lightweight native persistence, "
            f"the system achieved deterministic reliability across long runs.{visual_note}\n\n"
            "For builders developing edge or local-first tooling: always benchmark and profile your worst-case memory allocations "
            "before adding more abstraction layers."
            f"{url_line}\n\n"
            "#SoftwareEngineering #SystemsDesign #OpenSource #BuildInPublic #Python"
        )
    elif mode == "architecture":
        return (
            f"Deep-dive into the technical architecture of {clean_title}:{notes_blurb}\n\n"
            "The core engineering objective was clear: complete local autonomy with zero cloud dependency, "
            "strict memory bounds, and defensive integration guarantees.\n\n"
            f"Core Architectural Pillars:{highlight_block or chr(10) + '• On-device execution: All core models and services run locally, preserving privacy and eliminating recurring latency' + chr(10) + '• Modular subsystem separation: Decoupled intake, generation pipelines, and persistent storage' + chr(10) + '• Defensive input verification: Validating inputs at system boundaries before passing down to domain services'}\n\n"
            "By keeping the memory profile compact and coordinating resource usage sequentially, "
            f"the architecture operates smoothly on standard personal computers without thermal throttling.{visual_note}\n\n"
            "Would appreciate thoughts and technical feedback from fellow developers exploring local software architectures."
            f"{url_line}\n\n"
            "#SystemDesign #Architecture #Python #OpenSource #DeveloperTools"
        )
    elif mode == "progress":
        return (
            f"Build-in-public technical update on {clean_title}:{notes_blurb}\n\n"
            "Shipped a substantial milestone focused on reliability, offline usability, and performance guarantees. "
            "Balancing code cleanliness with rapid iteration meant cutting out unnecessary external dependencies and "
            "focusing entirely on rock-solid fundamentals.\n\n"
            f"Key implementations delivered:{highlight_block or chr(10) + '• Unified intake pipeline parsing project metadata automatically' + chr(10) + '• Robust error recovery for transient network interruptions' + chr(10) + '• Lightweight local persistence ensuring zero data loss'}\n\n"
            f"The tooling is now significantly more resilient and responsive.{visual_note}\n\n"
            "Next step is stress-testing corner cases and polishing the developer workflow."
            f"{url_line}\n\n"
            "#BuildInPublic #SoftwareEngineering #Tech #OpenSource"
        )
    else:  # launch
        return (
            f"I've been working on {clean_title}, and today I'm sharing the repository, architecture, and live progress.{notes_blurb}\n\n"
            "The project was built to address a real technical challenge: delivering fast, privacy-preserving, "
            "and dependable tooling that runs 100% locally on standard hardware without expensive cloud APIs or subscription lock-in.\n\n"
            f"Key Technical Highlights:{highlight_block or chr(10) + '• 100% local execution running on local hardware' + chr(10) + '• Clean modular codebase with defensive validation at every layer' + chr(10) + '• Zero reliance on scraping or insecure browser automation'}\n\n"
            f"The architecture is designed to remain lightweight and fully functional offline.{visual_note}\n\n"
            "Complete code and setup instructions are open for review below. Keen to hear insights and feedback from fellow builders."
            f"{url_line}\n\n"
            "#OpenSource #DeveloperTools #Python #SoftwareEngineering #Tech"
        )



INSTAGRAM_BASE_TAGS = [
    "#coding", "#programming", "#developer", "#softwareengineer", "#tech",
    "#buildinpublic", "#codinglife", "#computerscience", "#100daysofcode", "#learntocode",
]
INSTAGRAM_CAPTION_LIMIT = 2200
INSTAGRAM_MAX_HASHTAGS = 15


def build_instagram_caption(post_text: str, max_body_chars: int = 1200) -> str:
    """
    Converts a LinkedIn draft into an Instagram caption tuned for discovery by new accounts:
    hook kept as the first line, body trimmed for mobile, links swapped for "link in bio",
    a comment prompt, and a mix of the post's own niche hashtags plus broader discovery tags.
    """
    import re

    lines = post_text.strip().splitlines()
    body_lines = [l for l in lines if not re.fullmatch(r"(\s*#\w+)+\s*", l)]
    own_tags = [t.lower() for t in re.findall(r"#\w+", post_text)]

    body = "\n".join(body_lines).strip()
    has_link = bool(re.search(r"https?://\S+", body))
    body = re.sub(r"[^\n]*https?://\S+[^\n]*\n?", "", body).strip()
    if len(body) > max_body_chars:
        cut = body[:max_body_chars].rsplit("\n", 1)[0].rsplit(". ", 1)[0]
        body = cut.rstrip(" .,") + "..."

    extras = []
    if has_link:
        extras.append("🔗 Link in bio")
    extras.append("💬 Drop a comment if you have built something similar. Save this for later.")

    tags = []
    for t in own_tags + INSTAGRAM_BASE_TAGS:
        if t not in tags:
            tags.append(t)
    tags = tags[:INSTAGRAM_MAX_HASHTAGS]

    caption = f"{body}\n\n" + "\n".join(extras) + "\n.\n.\n" + " ".join(tags)
    return caption[:INSTAGRAM_CAPTION_LIMIT]
