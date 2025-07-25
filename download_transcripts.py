#!/usr/bin/env python3
"""
Granola Transcript Downloader - Phase 1

Downloads transcripts from Granola AI's API using the Supabase authentication
and saves them as JSON files in the format YYYY-MM-DD_(document_name).json
"""

import argparse
import logging
import json

import requests
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('transcript_downloader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_credentials() -> Optional[str]:
    """
    Load Granola credentials from supabase.json
    Reused from sample_python.py
    """
    creds_path = Path.home() / "Library/Application Support/Granola/supabase.json"
    if not creds_path.exists():
        logger.error(f"Credentials file not found at: {creds_path}")
        return None

    try:
        with open(creds_path, 'r') as f:
            data = json.load(f)

        # Parse the cognito_tokens string into a dict
        cognito_tokens = json.loads(data['cognito_tokens'])
        access_token = cognito_tokens.get('access_token')

        if not access_token:
            logger.error("No access token found in credentials file")
            return None

        logger.debug("Successfully loaded credentials")
        return access_token
    except Exception as e:
        logger.error(f"Error reading credentials file: {str(e)}")
        return None


def fetch_granola_documents(token: str, limit: int = 100) -> Optional[List[Dict]]:
    """
    Fetch documents from Granola API
    Adapted from sample_python.py
    """
    url = "https://api.granola.ai/v2/get-documents"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "Granola/5.354.0",
        "X-Client-Version": "5.354.0"
    }

    all_documents = []
    offset = 0

    while True:
        data = {
            "limit": limit,
            "offset": offset,
            "include_last_viewed_panel": False  # We don't need panel data for transcripts
        }

        try:
            logger.debug(f"Fetching documents with offset {offset}")
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()
            documents = result.get("docs", [])

            if not documents:
                break

            all_documents.extend(documents)

            # Check if we've reached the end
            if len(documents) < limit:
                break

            offset += limit

            # Add small delay to be respectful to the API
            time.sleep(0.1)

        except Exception as e:
            logger.error(f"Error fetching documents: {str(e)}")
            return None

    logger.info(f"Successfully fetched {len(all_documents)} documents")
    return all_documents


def fetch_transcript(token: str, document_id: str) -> Optional[List[Dict]]:
    """
    Fetch transcript for a specific document
    Adapted from sample_transcript.js
    """
    url = "https://api.granola.ai/v1/get-document-transcript"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "*/*",
        "User-Agent": "Granola/5.354.0",
        "X-Client-Version": "5.354.0"
    }
    data = {"document_id": document_id}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()

        transcript_data = response.json()

        # Return the full transcript data (array of entries)
        if isinstance(transcript_data, list):
            return transcript_data
        else:
            logger.warning(f"Unexpected transcript format for document {document_id}")
            return None

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.debug(f"No transcript found for document {document_id}")
            return None
        else:
            logger.error(f"HTTP error fetching transcript for {document_id}: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Error fetching transcript for {document_id}: {str(e)}")
        return None


def sanitize_filename(title: str) -> str:
    """
    Convert a title to a valid filename
    Reused from sample_python.py with improvements
    """
    if not title or title.strip() == "":
        return "untitled"

    # Remove invalid characters
    invalid_chars = '<>:"/\\|?*'
    filename = ''.join(c for c in title if c not in invalid_chars)

    # Replace multiple spaces with single underscore
    filename = '_'.join(filename.split())

    # Remove leading/trailing underscores and limit length
    filename = filename.strip('_')[:100]

    return filename if filename else "untitled"


def filter_documents_by_date(documents: List[Dict], days_ago: Optional[int]) -> List[Dict]:
    """
    Filter documents by creation date
    """
    if days_ago is None:
        return documents

    cutoff_date = datetime.now() - timedelta(days=days_ago)
    filtered_docs = []

    for doc in documents:
        try:
            # Parse the document creation date
            created_at = doc.get('created_at')
            if created_at:
                doc_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if doc_date >= cutoff_date:
                    filtered_docs.append(doc)
        except Exception as e:
            logger.debug(f"Error parsing date for document {doc.get('id', 'unknown')}: {e}")
            # Include documents with unparseable dates
            filtered_docs.append(doc)

    logger.info(f"Filtered to {len(filtered_docs)} documents from last {days_ago} days")
    return filtered_docs


def generate_filename(title: str, created_at: str) -> str:
    """Generate a filename from document metadata"""
    try:
        if created_at:
            date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            date_str = date_obj.strftime('%Y-%m-%d')
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
    except Exception:
        date_str = datetime.now().strftime('%Y-%m-%d')

    sanitized_title = sanitize_filename(title)
    return f"{date_str}_{sanitized_title}.json"


def process_document(token: str, doc: Dict, output_path: Path, force: bool, doc_num: int, total_docs: int) -> str:
    """Process a single document and return result status"""
    doc_id = doc.get('id', 'unknown')
    title = doc.get('title', 'Untitled')
    created_at = doc.get('created_at', '')

    logger.info(f"Processing [{doc_num}/{total_docs}]: {title}")

    filename = generate_filename(title, created_at)
    file_path = output_path / filename

    # Skip if file exists and not forcing overwrite
    if file_path.exists() and not force:
        logger.debug(f"Skipping {filename} (already exists)")
        return "skipped"

    # Fetch transcript
    transcript = fetch_transcript(token, doc_id)

    if transcript is None:
        logger.warning(f"No transcript available for: {title}")
        return "error"

    # Prepare JSON data with metadata
    json_data = {
        "document_id": doc_id,
        "title": title,
        "created_at": created_at,
        "updated_at": doc.get('updated_at'),
        "download_timestamp": datetime.now().isoformat(),
        "transcript_entries": transcript
    }

    # Save to file
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        logger.debug(f"Saved: {filename}")
        return "downloaded"

    except Exception as e:
        logger.error(f"Error saving {filename}: {str(e)}")
        return "error"


def print_summary(downloaded_count: int, skipped_count: int, error_count: int, output_path: Path) -> None:
    """Print download summary"""
    logger.info("Download complete!")
    logger.info(f"Downloaded: {downloaded_count} transcripts")
    logger.info(f"Skipped: {skipped_count} (already exist)")
    logger.info(f"Errors: {error_count} (no transcript or save failed)")
    logger.info(f"Files saved to: {output_path.absolute()}")


def download_transcripts(output_dir: str = "transcripts", days_ago: Optional[int] = None,
                        force: bool = False, verbose: bool = False) -> None:
    """
    Main function to download all transcripts
    """
    try:
        # Set up logging level
        if verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        # Create output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)
        logger.info(f"Output directory: {output_path.absolute()}")

        # Load credentials
        logger.info("Loading Granola credentials...")
        token = load_credentials()
        if not token:
            logger.error("Failed to load credentials. Exiting.")
            return

        # Fetch all documents
        logger.info("Fetching documents from Granola API...")
        documents = fetch_granola_documents(token)
        if not documents:
            logger.error("Failed to fetch documents. Exiting.")
            return

        # Filter by date if specified
        if days_ago is not None:
            documents = filter_documents_by_date(documents, days_ago)

        if not documents:
            logger.warning("No documents found matching criteria.")
            return

        # Download transcripts
        logger.info(f"Starting transcript download for {len(documents)} documents...")

        downloaded_count = 0
        skipped_count = 0
        error_count = 0

        for i, doc in enumerate(documents, 1):
            result = process_document(token, doc, output_path, force, i, len(documents))

            if result == "downloaded":
                downloaded_count += 1
            elif result == "skipped":
                skipped_count += 1
            else:  # error
                error_count += 1

            # Small delay to be respectful to the API
            time.sleep(0.1)

        print_summary(downloaded_count, skipped_count, error_count, output_path)

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Download Granola meeting transcripts via API and save as JSON files"
    )
    parser.add_argument(
        "-o", "--output",
        default="transcripts",
        help="Output directory for transcript files (default: transcripts)"
    )
    parser.add_argument(
        "-d", "--days",
        type=int,
        help="Only download transcripts from the last N days (default: all time)"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Force overwrite of existing files"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    try:
        download_transcripts(
            output_dir=args.output,
            days_ago=args.days,
            force=args.force,
            verbose=args.verbose
        )
    except KeyboardInterrupt:
        logger.info("Download interrupted by user")
    except Exception as e:
        logger.error(f"Download failed: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
