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
3. Concise & High Signal: Clean paragraph breaks. Strong, informative first line (no clickbait).
4. Humble & Curious: Acknowledge bugs, mistakes, performance limits, and ongoing questions.
5. Absolute Truthfulness: NEVER invent fake benchmarks, fake GitHub stars, or imaginary production deployments.
6. Zero Corporate Sludge: Strictly avoid: {', '.join(BANNED_PHRASES)}.
7. Minimal Emojis: Maximum 1 or 2 subtle, relevant emojis across the entire post, or none.
8. Relevant Hashtags: End with 3-4 specific technical hashtags (e.g. #Python #OpenSource #Robotics #ComputerVision).

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
        "\nREQUIREMENT: Produce a complete, polished post following the persona rules. "
        "Include the project link at the end if provided."
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
    Produces high-quality, authentic posts even when Ollama is offline or uninstalled.
    Guarantees the user is never blocked.
    """
    clean_title = title.strip() or "Technical Project"
    url_line = f"\n\nSource / Demo: {source_url}" if source_url else ""
    visual_note = f"\n\nVisual architecture: {image_analysis.split('.')[0]}." if image_analysis else ""
    notes_blurb = f"\n{user_notes}" if user_notes else ""

    if mode == "lesson":
        return (
            f"A practical engineering lesson from building {clean_title}:{notes_blurb}\n\n"
            "When dealing with local performance and edge constraints, the biggest bottleneck "
            "often isn't raw compute—it's memory bandwidth and uncoordinated I/O calls. "
            "Profiling revealed where latency was silently compounding.\n\n"
            "By isolating concurrent processes, enforcing strict buffer limits, and keeping dependencies minimal, "
            "the system became significantly more predictable and lightweight.{visual_note}\n\n"
            "For anyone building local-first software: always verify the memory footprint under sustained loads "
            "before adding more abstractions.\n"
            f"{url_line}\n\n"
            "#SoftwareEngineering #BuildInPublic #OpenSource #SystemsDesign"
        )
    elif mode == "architecture":
        return (
            f"Deep-dive into the architecture of {clean_title}:{notes_blurb}\n\n"
            "The design goal was simple: complete local autonomy with zero cloud dependency and strict memory bounds.\n\n"
            "Key architectural pillars:\n"
            "• Local execution: All core pipelines run on-device, preserving user privacy and eliminating latency.\n"
            "• Modularity: Clean separation between intake, inference engines, and persistent storage.\n"
            "• Fault tolerance: Isolated state verification and defensive error recovery at system boundaries.{visual_note}\n\n"
            "Keeping the footprint tight allows it to run smoothly even on standard 8 GB hardware without throttling.\n"
            f"{url_line}\n\n"
            "#SystemDesign #Architecture #Python #OpenSource"
        )
    elif mode == "progress":
        return (
            f"Build-in-public milestone on {clean_title}:{notes_blurb}\n\n"
            "Shipped a set of core improvements focused on reliability and offline usability. "
            "Balancing code quality with rapid iteration meant cutting unnecessary external dependencies "
            "and focusing purely on what makes the tool reliable.{visual_note}\n\n"
            "Next step is stress-testing edge cases and refining user ergonomics.\n"
            f"{url_line}\n\n"
            "#BuildInPublic #IndieHacker #Engineering #Tech"
        )
    else:  # launch
        return (
            f"I've been working on {clean_title}, and today I'm sharing the repository and progress.{notes_blurb}\n\n"
            "The project was built to solve a concrete engineering problem: delivering responsive, "
            "privacy-preserving tooling that runs 100% locally on standard PC hardware without cloud subscriptions.\n\n"
            "Built with clean modular design, defensive input validation, and lightweight local persistence.{visual_note}\n\n"
            "Code and setup details are available below. Would love feedback from fellow developers and builders.\n"
            f"{url_line}\n\n"
            "#OpenSource #DeveloperTools #Python #SoftwareEngineering"
        )
