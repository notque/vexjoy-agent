#!/usr/bin/env python3
"""
Generate text using Google Gemini Pro APIs.

Uses gemini-2.5-pro or gemini-2.5-flash for text generation.
Designed for voice comparison testing against Claude outputs.

Usage:
    # Single prompt
    gemini-text-generate.py --prompt "Write about a product launch" --output output.md

    # With system prompt from file
    gemini-text-generate.py --prompt "topic" --system-file voice-rules.md --output output.md

    # With full context injection
    gemini-text-generate.py --prompt "topic" --context-file samples.md --output output.md

    # JSON output mode (for pipeline integration)
    gemini-text-generate.py --prompt "topic" --json --output output.json
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Valid model names
VALID_MODELS = [
    "gemini-2.5-pro",  # Stable Pro (latest)
    "gemini-2.5-flash",  # Stable Flash (latest)
    "gemini-2.5-flash-preview-09-2025",  # Flash preview (September 2025)
    "gemini-2.0-flash",  # Legacy Flash fallback
]

# Default model
DEFAULT_MODEL = "gemini-2.5-pro"

# Defer import checks until after argument parsing (allows --help to work)
genai = None


@dataclass
class GenerationResult:
    """Result of text generation."""

    success: bool
    content: str
    model: str
    prompt_tokens: int
    output_tokens: int
    total_tokens: int
    finish_reason: str
    error: Optional[str] = None


def _check_imports():
    """Import required packages, checking availability."""
    global genai

    try:
        from google import genai as _genai

        genai = _genai
    except ImportError:
        print("ERROR: google-genai package not installed")
        print("Install with: pip install google-genai")
        sys.exit(1)


def generate_text(
    prompt: str,
    system_prompt: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.7,
    max_tokens: int = 8192,
    retries: int = 3,
) -> GenerationResult:
    """Generate text using Gemini API."""
    client = genai.Client()

    print("Generating text...")
    print(f"  Model: {model}")
    print(f"  Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
    if system_prompt:
        print(f"  System prompt: {len(system_prompt)} chars")

    # Build the full prompt
    full_prompt = prompt
    if system_prompt:
        # Gemini handles system prompts as part of the conversation
        full_prompt = f"{system_prompt}\n\n---\n\nUser request:\n{prompt}"

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=full_prompt,
                config={
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )

            # Extract response
            if not response.candidates:
                return GenerationResult(
                    success=False,
                    content="",
                    model=model,
                    prompt_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    finish_reason="no_candidates",
                    error="No candidates in response",
                )

            candidate = response.candidates[0]
            content = ""

            if hasattr(candidate.content, "parts"):
                for part in candidate.content.parts:
                    if hasattr(part, "text"):
                        content += part.text

            # Get token usage if available
            prompt_tokens = 0
            output_tokens = 0
            if hasattr(response, "usage_metadata"):
                usage = response.usage_metadata
                prompt_tokens = getattr(usage, "prompt_token_count", 0)
                output_tokens = getattr(usage, "candidates_token_count", 0)

            finish_reason = "complete"
            if hasattr(candidate, "finish_reason"):
                finish_reason = str(candidate.finish_reason)

            print(f"  SUCCESS: Generated {len(content)} chars")
            if prompt_tokens or output_tokens:
                print(
                    f"  Tokens: {prompt_tokens} prompt + {output_tokens} output = {prompt_tokens + output_tokens} total"
                )

            return GenerationResult(
                success=True,
                content=content,
                model=model,
                prompt_tokens=prompt_tokens,
                output_tokens=output_tokens,
                total_tokens=prompt_tokens + output_tokens,
                finish_reason=finish_reason,
            )

        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "rate" in error_str.lower():
                wait_time = (attempt + 1) * 5
                print(f"  Rate limited, waiting {wait_time}s (attempt {attempt + 1}/{retries})")
                time.sleep(wait_time)
            elif "400" in error_str:
                print("  ERROR: Content policy violation or invalid request")
                print(f"  Details: {e}")
                return GenerationResult(
                    success=False,
                    content="",
                    model=model,
                    prompt_tokens=0,
                    output_tokens=0,
                    total_tokens=0,
                    finish_reason="error",
                    error=f"Content policy violation: {e}",
                )
            else:
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"  Error: {e}")
                    print(f"  Retrying in {wait_time}s (attempt {attempt + 1}/{retries})")
                    time.sleep(wait_time)
                else:
                    print(f"  ERROR after {retries} attempts: {e}")
                    return GenerationResult(
                        success=False,
                        content="",
                        model=model,
                        prompt_tokens=0,
                        output_tokens=0,
                        total_tokens=0,
                        finish_reason="error",
                        error=str(e),
                    )

    return GenerationResult(
        success=False,
        content="",
        model=model,
        prompt_tokens=0,
        output_tokens=0,
        total_tokens=0,
        finish_reason="max_retries",
        error="Max retries exceeded",
    )


def build_voice_prompt(
    topic: str,
    voice_rules: str,
    samples: Optional[str] = None,
    research_data: Optional[str] = None,
) -> str:
    """Build a complete voice generation prompt.

    This assembles the full prompt with voice rules, samples, and research data
    in a format optimized for Gemini Pro.
    """
    parts = []

    # Voice rules (system-like)
    parts.append("# WRITING VOICE AND RULES")
    parts.append("")
    parts.append(voice_rules)
    parts.append("")

    # Sample content (few-shot)
    if samples:
        parts.append("# REFERENCE SAMPLES (Match this voice and style)")
        parts.append("")
        parts.append(samples)
        parts.append("")

    # Research data
    if research_data:
        parts.append("# RESEARCH DATA (Use these specific facts)")
        parts.append("")
        parts.append(research_data)
        parts.append("")

    # The actual request
    parts.append("# YOUR TASK")
    parts.append("")
    parts.append("Write the following in the target voice:")
    parts.append("")
    parts.append(topic)
    parts.append("")
    parts.append("Remember:")
    parts.append("- NO em-dashes (use commas or periods)")
    parts.append("- Third person for articles")
    parts.append("- Be SPECIFIC - use exact match names, dates, events from research")
    parts.append("- Include warmth and celebration but EARN it through specifics")
    parts.append("- Do NOT use 'It's not X. It's Y.' pattern")
    parts.append("- Do NOT narrate emotion - SHOW it through rhythm")

    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(
        description="Generate text using Google Gemini Pro APIs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --prompt "Write about a product launch" --output page.md
  %(prog)s --prompt "topic" --system-file rules.md --output out.md
  %(prog)s --prompt "topic" --context-file samples.md --system-file rules.md --output out.md
  %(prog)s --blog "2025 Annual Awards" --voice-file voice.md --output awards.md

Models:
  gemini-2.5-pro                 Stable Pro model (default)
  gemini-2.5-flash               Stable Flash model (faster)
  gemini-2.5-flash-preview-09-2025  Flash preview (September 2025)
  gemini-2.0-flash               Legacy Flash fallback
        """,
    )

    # Basic generation options
    parser.add_argument("--prompt", help="Text prompt for generation")
    parser.add_argument("--output", "-o", help="Output file path")
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        choices=VALID_MODELS,
        help=f"Model to use (default: {DEFAULT_MODEL})",
    )

    # Context injection options
    parser.add_argument("--system-file", help="File containing system prompt/rules")
    parser.add_argument("--context-file", help="File containing context/samples to inject")

    # Voice blog-specific options
    parser.add_argument("--blog", help="Voice blog topic (enables voice-specific mode)")
    parser.add_argument("--voice-file", help="Voice rules file (for --blog)")
    parser.add_argument("--samples-file", help="Voice samples file (for --blog)")
    parser.add_argument("--research-file", help="Research data file (for --blog)")

    # Generation parameters
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.7,
        help="Temperature for generation (default: 0.7)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=8192,
        help="Max output tokens (default: 8192)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Max retry attempts (default: 3)",
    )

    # Output format
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON (includes metadata)",
    )

    args = parser.parse_args()

    # Now check imports (after --help can work)
    _check_imports()

    # Validate API key
    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable not set")
        print("Set with: export GEMINI_API_KEY='your-api-key'")
        sys.exit(1)

    # Build the prompt
    prompt = None
    system_prompt = None

    if args.blog:
        # Voice blog mode - build specialized prompt
        if not args.voice_file:
            print("ERROR: --voice-file required with --blog")
            sys.exit(1)

        voice_path = Path(args.voice_file)
        if not voice_path.exists():
            print(f"ERROR: Voice file not found: {args.voice_file}")
            sys.exit(1)

        voice_rules = voice_path.read_text()

        samples = None
        if args.samples_file:
            samples_path = Path(args.samples_file)
            if samples_path.exists():
                samples = samples_path.read_text()

        research = None
        if args.research_file:
            research_path = Path(args.research_file)
            if research_path.exists():
                research = research_path.read_text()

        prompt = build_voice_prompt(
            topic=args.blog,
            voice_rules=voice_rules,
            samples=samples,
            research_data=research,
        )

    elif args.prompt:
        # Standard mode
        prompt = args.prompt

        # Load system prompt if provided
        if args.system_file:
            system_path = Path(args.system_file)
            if not system_path.exists():
                print(f"ERROR: System file not found: {args.system_file}")
                sys.exit(1)
            system_prompt = system_path.read_text()

        # Load and inject context if provided
        if args.context_file:
            context_path = Path(args.context_file)
            if not context_path.exists():
                print(f"ERROR: Context file not found: {args.context_file}")
                sys.exit(1)
            context = context_path.read_text()
            prompt = f"{context}\n\n---\n\n{prompt}"

    else:
        print("ERROR: --prompt or --blog required")
        parser.print_help()
        sys.exit(1)

    # Generate text
    result = generate_text(
        prompt=prompt,
        system_prompt=system_prompt,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        retries=args.retries,
    )

    # Output handling
    if args.json:
        output_data = {
            "success": result.success,
            "content": result.content,
            "model": result.model,
            "prompt_tokens": result.prompt_tokens,
            "output_tokens": result.output_tokens,
            "total_tokens": result.total_tokens,
            "finish_reason": result.finish_reason,
        }
        if result.error:
            output_data["error"] = result.error

        output_text = json.dumps(output_data, indent=2)
    else:
        output_text = result.content

    # Write or print output
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text)
        print(f"  Output written to: {args.output}")
    else:
        print()
        print("=" * 60)
        print(output_text)
        print("=" * 60)

    # Exit code
    if not result.success:
        print(f"\nERROR: {result.error}")
        sys.exit(1)

    print("\nDONE")
    sys.exit(0)


if __name__ == "__main__":
    main()
