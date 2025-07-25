# Granola Transcript and Meeting Downloader

These scripts download transcripts and meeting summaries from Granola.

...on the shoulders of these giants:
- [Granola MCP](https://www.npmjs.com/package/@daanvanhulsen/granola-mcp?activeTab=code)
- [Granola-to-Markdown](https://github.com/mikedemarais/granola-to-markdown)
- [Reverse Engineering Granola](https://josephthacker.com/hacking/2025/05/08/reverse-engineering-granola-notes.html)

## How it works

From the above reading, Granola provides a daily updated credential file, stored locally here (on MacOS):

`~/Library/Application Support/Granola/supabase.json`

These scripts use the above credentials to authenticate with the Granola API (https://api.granola.com) and then download the files that are otherwise available to directly copy/download from the Granola desktop application.

## Usage

Three python files. Works with Python 3.12.9 (as of writing). Run in order:

```sh
python download_transcript.py
python download_meeting.py
python convert_to_markdown.py
```

A bunch of folders will be created in this document with obvious names.

Could I have made this better? Yes. Will I? Probably not. Fork away.

### Script Options

Claude Code said that all its scripts support common flags:

- `-v, --verbose` - Enable debug logging
- `-f, --force` - Overwrite existing files
- `-o, --output DIR` - Specify output directory
- `-d, --days N` - Only process items from last N days

I have not tested them. YMMV.

## Why?

Meeting transcripts and summary integrations currently unavailable beyond a few select vendors. (None of which I particularly use.) These scripts temporarily fill that gap.
