#!/usr/bin/env python3
"""
Granola Transcript to Markdown Converter - Phase 2

Converts downloaded JSON transcript files to formatted Markdown files.
Reads from /transcripts directory and outputs to /transcripts-markdown directory.
"""

import argparse
import json
import logging
import string
from datetime import datetime
from pathlib import Path
from typing import List, Dict


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transcript_converter.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename by replacing non-printable characters with '-'
    """
    if not filename:
        return "untitled"

    # Keep only printable characters, replace others with '-'
    sanitized = ''.join(char if char in string.printable and char not in '<>:"/\\|?*' else '-' for char in filename)

    # Remove multiple consecutive dashes
    while '--' in sanitized:
        sanitized = sanitized.replace('--', '-')

    # Remove leading/trailing dashes and limit length
    sanitized = sanitized.strip('-')[:100]

    return sanitized if sanitized else "untitled"


def format_datetime(iso_string: str) -> str:
    """
    Format ISO datetime string for display
    Adapted from granola-to-markdown/index.ts
    """
    try:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return dt.strftime('%A, %B %d, %Y at %I:%M %p')
    except Exception:
        return iso_string


def format_timestamp(timestamp_str: str) -> str:
    """
    Format timestamp for transcript entries
    """
    try:
        # Handle different timestamp formats
        if timestamp_str.endswith('Z'):
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.fromisoformat(timestamp_str)
        return dt.strftime('%H:%M:%S')
    except Exception:
        return timestamp_str


def format_transcript_entries(entries: List[Dict]) -> str:
    """
    Format transcript entries into markdown
    Adapted from granola-to-markdown/index.ts formatTranscript function
    """
    if not entries:
        return "*No transcript available*"

    # Sort entries by sequence_number if available, otherwise by timestamp
    try:
        if 'sequence_number' in entries[0]:
            sorted_entries = sorted(entries, key=lambda x: x.get('sequence_number', 0))
        elif 'start_timestamp' in entries[0]:
            sorted_entries = sorted(entries, key=lambda x: x.get('start_timestamp', ''))
        else:
            sorted_entries = entries
    except (IndexError, TypeError):
        sorted_entries = entries

    formatted_lines = []

    for entry in sorted_entries:
        text = entry.get('text', '').strip()
        if not text:
            continue

        # Determine speaker
        source = entry.get('source', '')
        speaker = entry.get('speaker', '')

        if source == 'microphone':
            speaker_name = 'me'
        elif speaker:
            speaker_name = speaker
        else:
            speaker_name = 'them'

        # Add timestamp if available
        start_timestamp = entry.get('start_timestamp')
        if start_timestamp:
            timestamp = format_timestamp(start_timestamp)
            formatted_lines.append(f"**[{timestamp}] {speaker_name}:** {text}")
        else:
            formatted_lines.append(f"**{speaker_name}:** {text}")

    return '\n\n'.join(formatted_lines)


def calculate_duration(entries: List[Dict]) -> str:
    """
    Calculate approximate duration from transcript entries
    """
    try:
        if not entries:
            return "Unknown"

        # Get start and end timestamps
        start_times = [e.get('start_timestamp') for e in entries if e.get('start_timestamp')]
        end_times = [e.get('end_timestamp') for e in entries if e.get('end_timestamp')]

        if not start_times or not end_times:
            return "Unknown"

        start_dt = datetime.fromisoformat(min(start_times).replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(max(end_times).replace('Z', '+00:00'))

        duration = end_dt - start_dt

        hours = duration.seconds // 3600
        minutes = (duration.seconds % 3600) // 60

        if hours > 0:
            return f"{hours} hour{'s' if hours > 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        else:
            return f"{minutes} minute{'s' if minutes != 1 else ''}"

    except Exception:
        return "Unknown"


def get_transcript_stats(entries: List[Dict]) -> Dict[str, int]:
    """
    Get basic statistics about the transcript
    """
    if not entries:
        return {"total_entries": 0, "speakers": 0, "words": 0}

    total_entries = len(entries)
    speakers = set()
    total_words = 0

    for entry in entries:
        # Count speakers
        source = entry.get('source', '')
        speaker = entry.get('speaker', '')

        if source == 'microphone':
            speakers.add('me')
        elif speaker:
            speakers.add(speaker)
        else:
            speakers.add('them')

        # Count words
        text = entry.get('text', '')
        total_words += len(text.split())

    return {
        "total_entries": total_entries,
        "speakers": len(speakers),
        "words": total_words
    }


def generate_markdown(transcript_data: Dict) -> str:
    """
    Generate markdown content from transcript JSON data
    """
    title = transcript_data.get('title', 'Untitled Meeting')
    created_at = transcript_data.get('created_at', '')
    updated_at = transcript_data.get('updated_at', '')
    document_id = transcript_data.get('document_id', '')
    entries = transcript_data.get('transcript_entries', [])

    # Format dates
    formatted_created = format_datetime(created_at) if created_at else 'Unknown'
    formatted_updated = format_datetime(updated_at) if updated_at else 'Unknown'

    # Get transcript statistics
    stats = get_transcript_stats(entries)
    duration = calculate_duration(entries)

    # Format transcript content
    formatted_transcript = format_transcript_entries(entries)

    # Generate markdown
    markdown_content = f"""# {title}

**Date:** {formatted_created}
**Updated:** {formatted_updated}
**Duration:** {duration}
**Document ID:** `{document_id}`

---

## Meeting Statistics

- **Total Entries:** {stats['total_entries']}
- **Speakers:** {stats['speakers']}
- **Total Words:** {stats['words']}

---

## Transcript

{formatted_transcript}

---

*This transcript was downloaded and converted from Granola AI*
"""

    return markdown_content


def convert_transcript_file(json_path: Path, output_path: Path, force: bool = False) -> bool:
    """
    Convert a single JSON transcript file to Markdown
    """
    try:
        # Check if output file already exists
        if output_path.exists() and not force:
            logger.debug(f"Skipping {output_path.name} (already exists)")
            return False

        # Read JSON file
        with open(json_path, 'r', encoding='utf-8') as f:
            transcript_data = json.load(f)

        # Generate markdown
        markdown_content = generate_markdown(transcript_data)

        # Write markdown file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)

        logger.debug(f"Converted: {json_path.name} -> {output_path.name}")
        return True

    except Exception as e:
        logger.error(f"Error converting {json_path.name}: {str(e)}")
        return False


def convert_transcripts(input_dir: str = "transcripts", output_dir: str = "transcripts-markdown",
                       force: bool = False, verbose: bool = False) -> None:
    """
    Convert all JSON transcript files to Markdown
    """
    try:
        # Set up logging level
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Set up directories
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if not input_path.exists():
            logger.error(f"Input directory '{input_path}' does not exist")
            return

        # Create output directory
        output_path.mkdir(exist_ok=True)
        logger.info(f"Input directory: {input_path.absolute()}")
        logger.info(f"Output directory: {output_path.absolute()}")

        # Find all JSON files
        json_files = list(input_path.glob("*.json"))

        if not json_files:
            logger.warning(f"No JSON files found in {input_path}")
            return

        logger.info(f"Found {len(json_files)} JSON files to convert")

        # Convert files
        converted_count = 0
        skipped_count = 0
        error_count = 0

        for json_file in json_files:
            # Generate output filename (replace .json with .md and sanitize)
            sanitized_stem = sanitize_filename(json_file.stem)
            output_file = output_path / f"{sanitized_stem}.md"

            logger.info(f"Converting: {json_file.name}")

            result = convert_transcript_file(json_file, output_file, force)

            if result:
                converted_count += 1
            elif output_file.exists() and not force:
                skipped_count += 1
            else:
                error_count += 1

        # Summary
        logger.info(f"Conversion complete!")
        logger.info(f"Converted: {converted_count} files")
        logger.info(f"Skipped: {skipped_count} (already exist)")
        logger.info(f"Errors: {error_count}")
        logger.info(f"Markdown files saved to: {output_path.absolute()}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Convert JSON transcript files to Markdown format"
    )
    parser.add_argument(
        "-i", "--input",
        default="transcripts",
        help="Input directory containing JSON transcript files (default: transcripts)"
    )
    parser.add_argument(
        "-o", "--output",
        default="transcripts-markdown",
        help="Output directory for Markdown files (default: transcripts-markdown)"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite of existing Markdown files"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    try:
        convert_transcripts(
            input_dir=args.input,
            output_dir=args.output,
            force=args.force,
            verbose=args.verbose
        )
    except KeyboardInterrupt:
        logger.info("Conversion interrupted by user")
    except Exception as e:
        logger.error(f"Conversion failed: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
