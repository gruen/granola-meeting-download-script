#!/usr/bin/env python3
"""
Granola Meeting Metadata Downloader

Downloads meeting metadata from Granola AI's API using Supabase authentication
and saves complete meeting information as JSON files in the format YYYY-MM-DD_(meeting_title).json
"""

import argparse
import logging
import json
import os
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
        logging.FileHandler('meeting_downloader.log'),
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
    Fetch all documents from Granola API with pagination
    Adapted from sample_python.py and download_transcripts.py
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
            "include_last_viewed_panel": True  # Include panel data for complete metadata
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


def sanitize_filename(title: str) -> str:
    """
    Convert a title to a valid filename
    Enhanced version from existing scripts
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


def process_document_metadata(doc: Dict) -> Dict:
    """
    Process and structure document metadata for JSON output
    """
    doc_id = doc.get('id', 'unknown')
    title = doc.get('title', 'Untitled Meeting')
    created_at = doc.get('created_at', '')
    updated_at = doc.get('updated_at', '')

    # Extract core metadata
    metadata = {
        'public': doc.get('public', False),
        'transcribe': doc.get('transcribe', False),
        'privacy_mode_enabled': doc.get('privacy_mode_enabled', False),
        'valid_meeting': doc.get('valid_meeting', False),
        'user_id': doc.get('user_id', ''),
        'deleted_at': doc.get('deleted_at'),
        'template_id': doc.get('template_id'),
        'sharing_settings': doc.get('sharing_settings'),
        'workspace_id': doc.get('workspace_id')
    }

    # Extract notes information
    notes = {
        'notes_plain': doc.get('notes_plain', ''),
        'notes_markdown': doc.get('notes_markdown', ''),
        'notes': doc.get('notes'),  # Structured notes object
        'last_viewed_panel': doc.get('last_viewed_panel')
    }

    # Extract calendar information
    calendar_info = {
        'google_calendar_event': doc.get('google_calendar_event'),
        'outlook_event': doc.get('outlook_event'),
        'zoom_meeting': doc.get('zoom_meeting')
    }

    # Structured meeting data
    meeting_data = {
        'document_id': doc_id,
        'title': title,
        'created_at': created_at,
        'updated_at': updated_at,
        'download_timestamp': datetime.now().isoformat(),
        'metadata': metadata,
        'notes': notes,
        'calendar_info': calendar_info,
        'raw_document': doc  # Complete API response for reference
    }

    return meeting_data


def download_meetings(output_dir: str = "meetings", days_ago: Optional[int] = None,
                     force: bool = False, verbose: bool = False) -> None:
    """
    Main function to download all meeting metadata
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

        # Download meeting metadata
        logger.info(f"Starting metadata download for {len(documents)} documents...")

        downloaded_count = 0
        skipped_count = 0
        error_count = 0

        for i, doc in enumerate(documents, 1):
            doc_id = doc.get('id', 'unknown')
            title = doc.get('title', 'Untitled')
            created_at = doc.get('created_at', '')

            logger.info(f"Processing [{i}/{len(documents)}]: {title}")

            # Format filename
            try:
                if created_at:
                    date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    date_str = date_obj.strftime('%Y-%m-%d')
                else:
                    date_str = datetime.now().strftime('%Y-%m-%d')
            except Exception:
                date_str = datetime.now().strftime('%Y-%m-%d')

            sanitized_title = sanitize_filename(title)
            filename = f"{date_str}_{sanitized_title}.json"
            file_path = output_path / filename

            # Skip if file exists and not forcing overwrite
            if file_path.exists() and not force:
                logger.debug(f"Skipping {filename} (already exists)")
                skipped_count += 1
                continue

            # Process document metadata
            try:
                meeting_data = process_document_metadata(doc)

                # Save to file
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(meeting_data, f, indent=2, ensure_ascii=False)

                logger.debug(f"Saved: {filename}")
                downloaded_count += 1

            except Exception as e:
                logger.error(f"Error processing {title}: {str(e)}")
                error_count += 1

            # Small delay to be respectful to the API
            time.sleep(0.05)  # Smaller delay since we're not making additional API calls

        # Summary
        logger.info(f"Download complete!")
        logger.info(f"Downloaded: {downloaded_count} meeting files")
        logger.info(f"Skipped: {skipped_count} (already exist)")
        logger.info(f"Errors: {error_count} (processing failed)")
        logger.info(f"Files saved to: {output_path.absolute()}")

    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Download Granola meeting metadata and save as JSON files"
    )
    parser.add_argument(
        "-o", "--output",
        default="meetings",
        help="Output directory for meeting metadata files (default: meetings)"
    )
    parser.add_argument(
        "-d", "--days",
        type=int,
        help="Only download meetings from the last N days (default: all time)"
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
        download_meetings(
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
