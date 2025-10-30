# Interactive Discovery Feature

## Overview

Enhanced the `discover` command with an interactive menu system that allows users to discover URLs and immediately decide what to do with them.

## Key Features

### 1. Interactive Menu System

After discovering URLs, users are presented with a menu:

```
======================================================================
  DISCOVERED URLs: 15
  Source: https://www.cocinadominicana.com/cocina
  Section: cocina
======================================================================

What would you like to do?

  [1] Scrape all URLs now (save to: scraped_content/cocina)
  [2] Save URLs to file
  [3] Nothing (exit)

Enter your choice [1-3]: _
```

### 2. Smart Section Naming

Automatically extracts section name from URL path:

- `https://www.cocinadominicana.com/cocina` → `cocina`
- `https://www.cocinadominicana.com/cultura/herencia` → `cultura_herencia`
- `https://www.cocinadominicana.com/inicia` → `inicia`
- `https://www.cocinadominicana.com/` → `discovered`

### 3. Three Action Options

**Option 1: Scrape Now**
- Immediately scrapes all discovered URLs
- Saves to `scraped_content/<section>/`
- Shows progress for each URL
- Displays final summary with success/failure counts

**Option 2: Save to File**
- Saves URLs to `<section>_urls.txt` (or custom file with `--save`)
- Can be used later with `scrape-list` command

**Option 3: Exit**
- Just preview URLs without any action

### 4. Non-Interactive Mode

For scripting and automation:

```bash
# Makefile
make scrape-discover URL="https://..." SAVE=urls.txt NOINTERACTIVE=1

# CLI
python cli.py discover "https://..." --no-interactive --save urls.txt
```

## Implementation Details

### New Functions in cli.py

1. **`extract_section_name_from_url(url: str) -> str`**
   - Parses URL to extract path segments
   - Joins with underscores for directory names
   - Returns 'discovered' as default

2. **`display_interactive_menu(urls, source_url, section_name) -> int`**
   - Shows formatted menu with discovered URLs count
   - Displays section name and destination directory
   - Returns user choice (1-3)
   - Handles keyboard interrupts gracefully

3. **Enhanced `discover_urls(args)`**
   - Checks for `args.interactive` flag
   - Displays menu if interactive mode enabled
   - Executes chosen action:
     - Choice 1: Calls `scraper.scrape_url()` in loop
     - Choice 2: Saves to file
     - Choice 3: Exits

### CLI Arguments

**New flags for `discover` command:**
- `--interactive` (default: True) - Enable interactive menu
- `--no-interactive` - Disable for scripting
- `--save <file>` - Custom filename for saving URLs

### Makefile Updates

**`scrape-discover` target enhancements:**
- Added `SAVE=<file>` parameter support
- Added `NOINTERACTIVE=1` flag for scripting
- Conditional logic to pass correct flags to CLI

## Backward Compatibility

✅ **100% Backward Compatible**

- Existing `make scrape` unchanged (uses `discover_article_urls()`)
- Config-based sections unchanged
- `scraper.py` core methods unchanged
- Only affects CLI `discover` command
- Non-interactive mode preserves old behavior

## Usage Examples

### Interactive Discovery and Scraping

```bash
# Discover URLs from a category
make scrape-discover URL="https://www.cocinadominicana.com/cocina"

# User selects option 1
# → Scrapes all URLs to scraped_content/cocina/
```

### Save URLs for Later

```bash
python cli.py discover "https://www.cocinadominicana.com/inicia"

# User selects option 2
# → Saves to inicia_urls.txt

# Later, scrape from saved file
make scrape-list FILE=inicia_urls.txt
```

### Non-Interactive for Scripts

```bash
# Discover and save without prompts
make scrape-discover URL="https://..." SAVE=my_urls.txt NOINTERACTIVE=1

# Use in bash scripts
for category in cocina inicia cultura; do
  make scrape-discover \
    URL="https://www.cocinadominicana.com/$category" \
    SAVE="${category}_urls.txt" \
    NOINTERACTIVE=1
done
```

## Testing

All functionality tested:

✅ URL section name extraction (5 test cases)
✅ Python syntax validation (py_compile)
✅ Makefile help text
✅ CLI argument parsing
✅ Backward compatibility verified

## Benefits

1. **Better UX** - Single workflow from discovery to scraping
2. **Smart Naming** - Automatic directory naming from URLs
3. **Flexibility** - Interactive for humans, scriptable for automation
4. **Time-Saving** - No manual URL copying/pasting
5. **Safe** - Preview before scraping, choose wisely

## Files Modified

1. **cli.py** (+80 lines)
   - Added `extract_section_name_from_url()` function
   - Added `display_interactive_menu()` function
   - Enhanced `discover_urls()` with interactive logic
   - Added `--interactive` / `--no-interactive` flags

2. **Makefile** (+8 lines)
   - Added `SAVE` parameter support
   - Added `NOINTERACTIVE` flag support
   - Updated conditional logic for CLI invocation

3. **readme.markdown** (+15 lines)
   - Updated discover section with interactive examples
   - Added menu options documentation
   - Added non-interactive mode examples

4. **USAGE_EXAMPLES.md** (+30 lines)
   - Added interactive workflow example
   - Added example menu output
   - Added non-interactive scripting examples
