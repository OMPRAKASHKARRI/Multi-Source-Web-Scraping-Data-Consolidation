# Python Web Scraping & Data Consolidation Pipeline

A production-style Python web scraping pipeline that collects data from
**Books to Scrape** and **Quotes to Scrape**, cleans and standardizes
the records, validates the data, removes duplicates, and exports a
consolidated dataset with execution metrics and logs.

## Overview

This project was developed as a take-home web scraping assignment with a
focus on:

-   Reliable pagination without hard-coded page counts
-   Reusable scraper architecture
-   Data cleaning and normalization
-   Validation and duplicate detection
-   Structured logging and error handling
-   Consolidation of heterogeneous sources into a common schema
-   Automated testing
-   Reproducible output generation

## Data Sources

  Source               Records Scraped   Pages Fetched   Final Records
  ------------------ ----------------- --------------- ---------------
  Books to Scrape                1,000              50             999
  Quotes to Scrape                 100              10             100
  **Total**                  **1,100**          **60**       **1,099**

The live pipeline run completed successfully with no failed pages or
parse errors.

## Common Data Schema

The consolidated dataset uses a common structure:

``` text
source
source_url
name_or_title
category
price
rating
author
tags
description
scraped_at
```

Fields that are not applicable to a particular source are retained as
empty values rather than forcing unrelated data into the schema.

## Project Structure

``` text
scraping_assignment/
├── main.py
├── pipeline.py
├── data_model.py
├── output_writer.py
├── requirements.txt
├── pytest.ini
├── README.md
├── AI_USAGE.md
│
├── scrapers/
│   ├── base_scraper.py
│   ├── books_scraper.py
│   └── quotes_scraper.py
│
├── processing/
│   ├── cleaning.py
│   ├── deduplication.py
│   └── validation.py
│
├── tests/
│   ├── test_cleaning.py
│   ├── test_deduplication.py
│   ├── test_http_client.py
│   ├── test_pipeline.py
│   ├── test_scrapers.py
│   └── test_validation.py
│
├── output/
│   ├── final_dataset.csv
│   └── summary_report.json
│
└── logs/
    └── scraper.log
```

## Requirements

-   Python 3.10--3.12
-   `requests`
-   `beautifulsoup4`
-   `lxml`
-   `pytest`

## Installation

Create and activate a virtual environment:

``` bash
python -m venv venv
```

Windows:

``` powershell
venv\Scripts\activate
```

Install dependencies:

``` bash
python -m pip install -r requirements.txt
```

## Run the Pipeline

From the project root:

``` bash
python main.py
```

The pipeline automatically:

1.  Scrapes Books to Scrape using pagination until the final page.
2.  Scrapes Quotes to Scrape using pagination until the final page.
3.  Cleans and normalizes the collected fields.
4.  Validates records and tracks rejected records.
5.  Detects and removes duplicates.
6.  Consolidates both sources into one dataset.
7.  Writes the final CSV and JSON summary.
8.  Records execution details in the scraper log.

No page count is hard-coded into the execution flow.

## Output Files

### `output/final_dataset.csv`

Contains the consolidated cleaned dataset from both sources.

The verified live run produced **1,099 final records**.

### `output/summary_report.json`

Contains source-level and pipeline-level metrics, including:

-   Raw record count
-   Cleaned record count
-   Rejected record count
-   Duplicate count
-   Final record count
-   Pages fetched
-   Failed pages
-   Warnings/errors
-   Execution start and end time
-   Total duration
-   Count reconciliation status

### `logs/scraper.log`

Contains timestamped execution logs for scraping, processing, duplicate
detection, output generation, warnings, and errors.

## Data Quality

The verified live execution produced:

``` text
Books to Scrape
- Raw:       1000
- Cleaned:   1000
- Rejected:     0
- Duplicates:   1
- Final:      999

Quotes to Scrape
- Raw:        100
- Cleaned:    100
- Rejected:     0
- Duplicates:   0
- Final:      100

Combined Final Records: 1099
Count Reconciliation:   True
```

One duplicate book record was detected and removed during processing.

## Testing

The project includes unit and integration-style tests covering scraping,
cleaning, validation, deduplication, HTTP behavior, and pipeline
functionality.

Run the complete test suite with:

``` bash
pytest
```

Verified result:

``` text
88 passed
```

## Error Handling & Logging

The scraper handles request and parsing failures without silently
stopping the complete pipeline. Execution information is logged with
appropriate severity levels.

Examples include:

-   `INFO` --- successful page fetches and pipeline progress
-   `WARNING` --- rejected or incomplete records
-   `ERROR` --- request or processing failures

## Design Approach

The project separates responsibilities into clear layers:

-   **Scrapers** --- source-specific extraction
-   **Processing** --- cleaning, validation, and deduplication
-   **Pipeline** --- orchestration and source-level metrics
-   **Output writer** --- CSV and JSON generation
-   **Tests** --- automated verification of core behavior

This structure keeps source-specific scraping logic separate from
reusable data-processing logic and makes the pipeline easier to extend.

## Reproducibility

The complete pipeline can be executed from the project root with:

``` bash
python main.py
```

Generated output and logs are written to the `output/` and `logs/`
directories.

## AI Assistance

AI tools were used selectively during development for implementation
assistance, debugging, documentation refinement, and test-oriented
review.

Specific usage is documented in [`AI_USAGE.md`](AI_USAGE.md).

## Assignment Status

-   [x] Books to Scrape scraping
-   [x] Quotes to Scrape scraping
-   [x] Dynamic pagination
-   [x] Data cleaning and normalization
-   [x] Validation
-   [x] Duplicate detection
-   [x] Consolidated CSV output
-   [x] Summary JSON output
-   [x] Structured logging
-   [x] Automated tests
-   [x] Live pipeline verification
-   [x] Documentation

## Author

**Omprakash Karri**

Python \| Web Scraping \| Data Processing \| Backend Development
