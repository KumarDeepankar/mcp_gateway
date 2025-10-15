# MCP OpenSearch Tools - Complete Reference Guide

## Overview

This document provides comprehensive documentation for the 4 MCP OpenSearch tools, including parameter specifications, query formulation guidelines, and expected outputs.

**Index Name:** `events` (101 documents)
**Countries:** Denmark, Dominica
**Years:** 2021-2023
**Protocol Version:** MCP 2025-06-18

---

## Table of Contents

1. [Tool 1: search_events_hybrid](#tool-1-search_events_hybrid)
2. [Tool 2: search_and_filter_events](#tool-2-search_and_filter_events)
3. [Tool 3: get_event_attendance_stats](#tool-3-get_event_attendance_stats)
4. [Tool 4: list_all_events](#tool-4-list_all_events)
5. [Query Formulation Guide](#query-formulation-guide)
6. [Parameter Type Reference](#parameter-type-reference)
7. [Common Use Cases](#common-use-cases)

---

## Tool 1: search_events_hybrid

### Description
Advanced hybrid search combining standard fuzzy matching with ngram-based matching for maximum robustness. Best for handling misspellings, partial words, and search term variations.

### When to Use
- User has uncertain or incomplete search terms
- Need to handle misspellings (e.g., "clima sumit" → "climate summit")
- Searching for partial words (e.g., "tech innov" → "technology innovation")
- Want best fuzzy matching quality

### Parameters

| Parameter | Type | Required | Default | Valid Values | Description |
|-----------|------|----------|---------|--------------|-------------|
| `query` | string | ✅ Yes | - | Any text | Search query with fuzzy matching support |
| `size` | integer | ❌ No | 10 | 1-100 | Number of results to return |

### Parameter Details

#### `query` (required)
- **Purpose:** Text to search for across event fields
- **Fuzzy Matching:** Handles misspellings automatically
- **Searched Fields:**
  - `event_title` (weight: 3x)
  - `event_theme` (weight: 2.5x)
  - `event_title.ngram` (weight: 1x)
  - `event_theme.ngram` (weight: 1x)
- **Examples:**
  - `"climate summit"` - exact match
  - `"clima sumit"` - misspelled
  - `"tech innov"` - partial words
  - `"envronment policy"` - misspelling

#### `size` (optional)
- **Purpose:** Limit number of results
- **Range:** 1-100
- **Default:** 10
- **Note:** Only returns documents that match the query

### Query Examples

#### Example 1: Basic Search
```json
{
  "query": "technology innovation",
  "size": 10
}
```

#### Example 2: Fuzzy Search with Misspellings
```json
{
  "query": "clima sumit",
  "size": 15
}
```

#### Example 3: Partial Word Search
```json
{
  "query": "tech",
  "size": 25
}
```

### Expected Output Format

```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 12 events matching hybrid:'technology innovation'. Showing top 10 results:\n\n[\n  {\n    \"id\": \"DOC001\",\n    \"score\": 8.5,\n    \"year\": 2023,\n    \"country\": \"Denmark\",\n    \"title\": \"Tech Innovation Summit 2023\",\n    \"theme\": \"Emerging Technologies and Digital Transformation\",\n    \"attendance\": 5000,\n    \"highlight\": \"Latest innovations in AI and blockchain...\",\n    \"url\": \"https://techinnovation.dk\",\n    \"rid\": \"REC001\",\n    \"docid\": \"DOC001\"\n  },\n  ...\n]"
    }
  ]
}
```

### Output Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Document ID |
| `score` | number | Relevance score (higher = better match) |
| `year` | integer | Event year |
| `country` | string | Event country (Denmark/Dominica) |
| `title` | string | Event title |
| `theme` | string | Event theme |
| `attendance` | integer | Number of attendees |
| `highlight` | string | Event highlight (truncated to 200 chars) |
| `url` | string | Event URL |
| `rid` | string | Record ID |
| `docid` | string | Document ID |

### Edge Cases

- **No matches:** Returns `"No events found matching hybrid:'query'"`
- **Empty query:** Returns error message
- **Size > matches:** Returns all matching documents (less than requested size)

---

## Tool 2: search_and_filter_events

### Description
Multi-dimensional filtering with optional text search and custom sorting. The most flexible tool supporting all filter combinations. Best for complex queries requiring multiple criteria.

### When to Use
- Need to combine multiple filters (country + year + attendance)
- Want to filter without text search
- Need custom sorting options
- Building complex queries with precise criteria

### Parameters

| Parameter | Type | Required | Default | Valid Values | Description |
|-----------|------|----------|---------|--------------|-------------|
| `query` | string | ❌ No | - | Any text | Optional text search across all fields |
| `country` | string | ❌ No | - | "Denmark" or "Dominica" | Country filter |
| `start_year` | integer | ❌ No | - | 4-digit year | Start of year range (inclusive) |
| `end_year` | integer | ❌ No | - | 4-digit year | End of year range (inclusive) |
| `min_attendance` | integer | ❌ No | - | Positive integer | Minimum attendance threshold |
| `max_attendance` | integer | ❌ No | - | Positive integer | Maximum attendance threshold |
| `size` | integer | ❌ No | 10 | 1-100 | Number of results to return |
| `sort_by` | string | ❌ No | "relevance" | "year", "event_count", "relevance" | Sort field |
| `sort_order` | string | ❌ No | "desc" | "asc", "desc" | Sort order |

### Parameter Details

#### `query` (optional)
- **Purpose:** Text search across all event fields
- **Behavior:** Uses fuzzy matching with AUTO fuzziness
- **Combined with filters:** AND logic (must match query AND all filters)
- **If omitted:** No text search, only filters apply
- **Examples:**
  - `"technology"` - search for technology-related events
  - `"climate policy"` - search for climate policy events
  - Empty/omitted - no text search

#### `country` (optional)
- **Purpose:** Filter by specific country
- **Valid values:** "Denmark" or "Dominica" (case-sensitive)
- **UI Rendering:** Dropdown menu (enum constraint)
- **If omitted:** Include all countries

#### `start_year` and `end_year` (optional)
- **Purpose:** Filter by year range
- **Format:** 4-digit integer (e.g., 2020, 2023)
- **Range behavior:**
  - Both specified: `start_year <= year <= end_year`
  - Only start: `year >= start_year`
  - Only end: `year <= end_year`
  - Neither: All years included
- **UI Rendering:** Text input (converted to integer)
- **Examples:**
  - `start_year: 2021, end_year: 2023` - events from 2021-2023
  - `start_year: 2022` - events from 2022 onwards
  - `end_year: 2022` - events up to 2022

#### `min_attendance` and `max_attendance` (optional)
- **Purpose:** Filter by attendance count
- **Format:** Positive integer
- **Range behavior:**
  - Both specified: `min_attendance <= attendance <= max_attendance`
  - Only min: `attendance >= min_attendance`
  - Only max: `attendance <= max_attendance`
  - Neither: All attendance values included
- **UI Rendering:** Text input (converted to integer)
- **Examples:**
  - `min_attendance: 100, max_attendance: 1000` - events with 100-1000 attendees
  - `min_attendance: 500` - events with 500+ attendees
  - `max_attendance: 200` - small events (up to 200 attendees)

#### `size` (optional)
- **Purpose:** Limit number of results
- **Range:** 1-100
- **Default:** 10
- **UI Rendering:** Text input (converted to integer)

#### `sort_by` (optional)
- **Purpose:** Choose sorting field
- **Valid values:**
  - `"year"` - Sort by event year
  - `"event_count"` - Sort by attendance count
  - `"relevance"` - Sort by search score (only works with query parameter)
- **UI Rendering:** Dropdown menu (enum constraint)
- **Default:** "relevance"
- **Note:** If using "relevance" without query, defaults to unsorted

#### `sort_order` (optional)
- **Purpose:** Choose sort direction
- **Valid values:**
  - `"asc"` - Ascending (oldest/smallest first)
  - `"desc"` - Descending (newest/largest first)
- **UI Rendering:** Dropdown menu (enum constraint)
- **Default:** "desc"

### Query Examples

#### Example 1: All Parameters Empty (All Events)
```json
{}
```
Returns: All 101 events, default sorting, size 10

#### Example 2: Filter Only (No Search)
```json
{
  "country": "Denmark",
  "start_year": 2022,
  "end_year": 2023,
  "min_attendance": 100,
  "size": 50
}
```
Returns: Danish events from 2022-2023 with 100+ attendees

#### Example 3: Search + Filters
```json
{
  "query": "technology",
  "country": "Denmark",
  "start_year": 2020,
  "end_year": 2023,
  "min_attendance": 100,
  "size": 25,
  "sort_by": "year",
  "sort_order": "desc"
}
```
Returns: Technology-related events in Denmark (2020-2023) with 100+ attendees, sorted by year (newest first)

#### Example 4: Search Only (No Filters)
```json
{
  "query": "climate",
  "size": 20,
  "sort_by": "relevance",
  "sort_order": "desc"
}
```
Returns: Top 20 climate-related events, sorted by relevance

#### Example 5: Attendance Range Filter
```json
{
  "min_attendance": 50,
  "max_attendance": 500,
  "size": 30,
  "sort_by": "event_count",
  "sort_order": "asc"
}
```
Returns: Events with 50-500 attendees, sorted by attendance (smallest first)

#### Example 6: Single Year Filter
```json
{
  "start_year": 2023,
  "end_year": 2023,
  "size": 100
}
```
Returns: All events from 2023 only

### Expected Output Format

```json
{
  "content": [
    {
      "type": "text",
      "text": "Found 45 events matching query='technology' AND country=Denmark AND year=[2020-2023] AND attendance=[100-any]. Showing top 25 results:\n\n[\n  {\n    \"id\": \"DOC005\",\n    \"score\": 7.2,\n    \"year\": 2023,\n    \"country\": \"Denmark\",\n    \"title\": \"Nordic Tech Conference 2023\",\n    \"theme\": \"Technology and Innovation\",\n    \"attendance\": 1500,\n    \"highlight\": \"Cutting-edge technology demonstrations...\",\n    \"url\": \"https://nordictechconf.dk\",\n    \"rid\": \"REC005\",\n    \"docid\": \"DOC005\"\n  },\n  ...\n]"
    }
  ]
}
```

### Filter Description Format

The output message describes active filters:
- `query='text'` - Text search applied
- `country=Denmark` - Country filter applied
- `year=[2020-2023]` - Year range filter (start-end)
- `year=[any-2022]` - Only end year specified
- `year=[2021-any]` - Only start year specified
- `attendance=[100-1000]` - Attendance range filter
- `all events` - No filters applied

### Edge Cases

- **No filters:** Returns all events (match_all query)
- **No matches:** Returns `"No events found matching [filters]"`
- **Conflicting filters:** Empty results (e.g., start_year > end_year)
- **Size > matches:** Returns all matching documents

---

## Tool 3: get_event_attendance_stats

### Description
Statistical analysis of event attendance including min, max, average, sum, and count. Best for attendance analysis, capacity planning, or understanding event size distribution.

### When to Use
- Need attendance statistics across all events or filtered subset
- Capacity planning and analysis
- Understanding event size trends
- Getting aggregate metrics

### Parameters

| Parameter | Type | Required | Default | Valid Values | Description |
|-----------|------|----------|---------|--------------|-------------|
| `year` | integer | ❌ No | - | 4-digit year | Filter stats by specific year |
| `country` | string | ❌ No | - | "Denmark" or "Dominica" | Filter stats by country |

### Parameter Details

#### `year` (optional)
- **Purpose:** Get statistics for specific year only
- **Format:** 4-digit integer (e.g., 2023)
- **UI Rendering:** Text input (converted to integer)
- **If omitted:** Statistics across all years
- **Examples:**
  - `2023` - Stats for 2023 events only
  - Omitted - Stats for all years (2021-2023)

#### `country` (optional)
- **Purpose:** Get statistics for specific country only
- **Valid values:** "Denmark" or "Dominica"
- **UI Rendering:** Dropdown menu (enum constraint)
- **If omitted:** Statistics across all countries
- **Examples:**
  - `"Denmark"` - Stats for Danish events only
  - Omitted - Stats for all countries

### Query Examples

#### Example 1: Global Statistics (All Events)
```json
{}
```

#### Example 2: Year-Specific Statistics
```json
{
  "year": 2023
}
```

#### Example 3: Country-Specific Statistics
```json
{
  "country": "Denmark"
}
```

#### Example 4: Year + Country Statistics
```json
{
  "year": 2022,
  "country": "Denmark"
}
```

### Expected Output Format

```json
{
  "content": [
    {
      "type": "text",
      "text": "Attendance statistics (year=2023, country=Denmark):\n\n{\n  \"count\": 15,\n  \"min\": 50,\n  \"max\": 5000,\n  \"avg\": 1250.75,\n  \"sum\": 18761\n}"
    }
  ]
}
```

### Output Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `count` | integer | Number of events in the dataset |
| `min` | integer | Minimum attendance value |
| `max` | integer | Maximum attendance value |
| `avg` | float | Average attendance (rounded to 2 decimals) |
| `sum` | integer | Total sum of all attendance values |

### Edge Cases

- **No matching events:** Returns all zeros
  ```json
  {
    "count": 0,
    "min": 0,
    "max": 0,
    "avg": 0.0,
    "sum": 0
  }
  ```
- **Invalid year:** Returns zeros (e.g., year 2025 has no data)
- **Invalid country:** Returns zeros

### Filter Description in Output

- No filters: `"Attendance statistics:"`
- Year only: `"Attendance statistics (year=2023):"`
- Country only: `"Attendance statistics (country=Denmark):"`
- Both: `"Attendance statistics (year=2023, country=Denmark):"`

---

## Tool 4: list_all_events

### Description
Paginated event listing with flexible sorting. Perfect for browsing all events, data exploration, or retrieving events in specific order.

### When to Use
- Browse through all events systematically
- Get a sample of events
- Retrieve events in specific order (by year or attendance)
- Pagination through large result sets

### Parameters

| Parameter | Type | Required | Default | Valid Values | Description |
|-----------|------|----------|---------|--------------|-------------|
| `size` | integer | ❌ No | 10 | 1-100 | Number of events per page |
| `from` | integer | ❌ No | 0 | 0+ | Pagination offset (starting position) |
| `sort_by` | string | ❌ No | "year" | "year", "event_count" | Sort field |
| `sort_order` | string | ❌ No | "desc" | "asc", "desc" | Sort order |

### Parameter Details

#### `size` (optional)
- **Purpose:** Number of results to return per page
- **Range:** 1-100
- **Default:** 10
- **UI Rendering:** Text input (converted to integer)
- **Recommendations:**
  - Small (10-20): Quick browsing
  - Medium (25-50): Balanced view
  - Large (75-100): Bulk retrieval

#### `from` (optional)
- **Purpose:** Offset for pagination (how many to skip)
- **Format:** Integer >= 0
- **Default:** 0 (start from first result)
- **UI Rendering:** Text input (converted to integer)
- **Pagination formula:**
  - Page 1: `from=0`
  - Page 2: `from=size` (e.g., from=10 with size=10)
  - Page 3: `from=size*2` (e.g., from=20 with size=10)
  - Page N: `from=size*(N-1)`
- **Examples:**
  - `from=0` - First page
  - `from=10` - Skip first 10 results
  - `from=50` - Skip first 50 results
- **⚠️ Warning:** `from` is NOT a year filter! Use `search_and_filter_events` for year filtering

#### `sort_by` (optional)
- **Purpose:** Choose sorting field
- **Valid values:**
  - `"year"` - Sort by event year
  - `"event_count"` - Sort by attendance count
- **UI Rendering:** Dropdown menu (enum constraint)
- **Default:** "year"
- **Note:** No "relevance" option (not a search tool)

#### `sort_order` (optional)
- **Purpose:** Choose sort direction
- **Valid values:**
  - `"asc"` - Ascending (oldest/smallest first)
  - `"desc"` - Descending (newest/largest first)
- **UI Rendering:** Dropdown menu (enum constraint)
- **Default:** "desc"

### Query Examples

#### Example 1: Default Listing (First Page)
```json
{
  "size": 10,
  "sort_by": "year",
  "sort_order": "desc"
}
```
Returns: 10 most recent events

#### Example 2: Large Bulk Retrieval
```json
{
  "size": 100,
  "from": 0,
  "sort_by": "year",
  "sort_order": "asc"
}
```
Returns: First 100 events (oldest first)

#### Example 3: Pagination - Page 2
```json
{
  "size": 20,
  "from": 20,
  "sort_by": "year",
  "sort_order": "desc"
}
```
Returns: Results 21-40 (second page)

#### Example 4: Sort by Attendance
```json
{
  "size": 50,
  "from": 0,
  "sort_by": "event_count",
  "sort_order": "desc"
}
```
Returns: 50 largest events (by attendance)

#### Example 5: Smallest Events
```json
{
  "size": 10,
  "sort_by": "event_count",
  "sort_order": "asc"
}
```
Returns: 10 smallest events

### Expected Output Format

```json
{
  "content": [
    {
      "type": "text",
      "text": "Total events: 101. Showing 20 events (offset: 0, sorted by year desc):\n\n[\n  {\n    \"id\": \"DOC001\",\n    \"year\": 2023,\n    \"country\": \"Denmark\",\n    \"title\": \"Tech Summit 2023\",\n    \"theme\": \"Digital Innovation\",\n    \"attendance\": 5000\n  },\n  ...\n]"
    }
  ]
}
```

### Output Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Document ID |
| `year` | integer | Event year |
| `country` | string | Event country |
| `title` | string | Event title |
| `theme` | string | Event theme |
| `attendance` | integer | Number of attendees |

**Note:** This tool returns fewer fields than search tools (no score, highlight, url, etc.)

### Pagination Guide

To paginate through all 101 events with page size 20:

```javascript
// Page 1 (events 1-20)
{ "size": 20, "from": 0 }

// Page 2 (events 21-40)
{ "size": 20, "from": 20 }

// Page 3 (events 41-60)
{ "size": 20, "from": 40 }

// Page 4 (events 61-80)
{ "size": 20, "from": 60 }

// Page 5 (events 81-100)
{ "size": 20, "from": 80 }

// Page 6 (event 101)
{ "size": 20, "from": 100 }
```

### Edge Cases

- **from > total events:** Returns empty results (e.g., from=2000 with 101 total)
- **from + size > total:** Returns remaining events (e.g., from=95, size=20 returns 6 events)
- **size=0 or negative:** Error or uses default (10)
- **No events:** Returns `"No events found in the index"`

### Mixed Type Sorting

**Technical Note:** The year field has mixed types (some integers, some strings). The tool handles this using OpenSearch's `unmapped_type: "long"` parameter to ensure consistent sorting.

---

## Query Formulation Guide

### Choosing the Right Tool

```
┌─────────────────────────────────────────────┐
│ Do you need to SEARCH for text?            │
├─────────────────────────────────────────────┤
│ YES → search_events_hybrid                  │
│       (Best fuzzy matching)                 │
│                                             │
│ NO → Do you need FILTERS or custom sort?   │
│      ├─ YES → search_and_filter_events     │
│      │         (Multi-filter + optional     │
│      │          text search)                │
│      │                                      │
│      └─ NO → Do you need STATISTICS?       │
│             ├─ YES → get_event_attendance_ │
│             │         stats                 │
│             │         (Min/max/avg/sum)     │
│             │                               │
│             └─ NO → list_all_events        │
│                     (Simple pagination)     │
└─────────────────────────────────────────────┘
```

### Decision Matrix

| Need | Best Tool | Alternative |
|------|-----------|-------------|
| Text search with fuzzy matching | `search_events_hybrid` | `search_and_filter_events` (with query) |
| Filter by country + year + attendance | `search_and_filter_events` | - |
| Text search + filters combined | `search_and_filter_events` | - |
| Browse all events | `list_all_events` | `search_and_filter_events` (no params) |
| Get attendance statistics | `get_event_attendance_stats` | - |
| Sort by attendance | `list_all_events` or `search_and_filter_events` | - |
| Pagination | `list_all_events` | `search_and_filter_events` (with size) |

### Common Scenarios

#### Scenario 1: User asks "Find climate events in Denmark"
**Best choice:** `search_and_filter_events`
```json
{
  "query": "climate",
  "country": "Denmark",
  "size": 20
}
```

#### Scenario 2: User asks "Show me all events from 2023"
**Best choice:** `search_and_filter_events`
```json
{
  "start_year": 2023,
  "end_year": 2023,
  "size": 100
}
```

#### Scenario 3: User asks "What are the largest events?"
**Best choice:** `list_all_events`
```json
{
  "sort_by": "event_count",
  "sort_order": "desc",
  "size": 25
}
```

#### Scenario 4: User asks "Search for tecnology events" (misspelled)
**Best choice:** `search_events_hybrid`
```json
{
  "query": "tecnology",
  "size": 10
}
```

#### Scenario 5: User asks "What's the average attendance in Denmark?"
**Best choice:** `get_event_attendance_stats`
```json
{
  "country": "Denmark"
}
```

---

## Parameter Type Reference

### String Parameters

**Tools:** All tools
**UI Rendering:** Text input or dropdown (if enum)
**Conversion:** No conversion needed (stays as string)
**Validation:**
- Enum values are case-sensitive
- Must match exactly (e.g., "Denmark" not "denmark")

**Examples:**
```javascript
// Text input
"query": "technology innovation"

// Enum dropdown
"country": "Denmark"  // Valid
"country": "denmark"  // Invalid (case mismatch)
"country": "Sweden"   // Invalid (not in enum)
```

### Integer Parameters

**Tools:** All except some string-only tools
**UI Rendering:** Text input (converted to integer on submit)
**Conversion:** `parseInt(value, 10)` applied by UI
**Validation:**
- Must be valid integer
- Range constraints apply (e.g., size: 1-100)

**Examples:**
```javascript
// User types "25" in UI → converted to integer 25
"size": 25

// User types "2023" in UI → converted to integer 2023
"year": 2023

// Invalid - would cause error before fix
"size": "25"  // String instead of integer
```

### Enum Parameters

**Tools:** All tools with sort/filter options
**UI Rendering:** Dropdown menu (select element)
**Valid Values:** Predefined list in schema
**Case Sensitivity:** Exact match required

**Enum Definitions:**

```javascript
// country enum
["Denmark", "Dominica"]

// sort_by enum (search_and_filter_events)
["year", "event_count", "relevance"]

// sort_by enum (list_all_events)
["year", "event_count"]

// sort_order enum
["asc", "desc"]
```

### Optional vs Required

**Required Parameters:**
- Must be provided
- UI marks with red asterisk (*)
- Request fails if missing

**Optional Parameters:**
- Can be omitted
- Use default value if specified in schema
- No validation error if missing

**Parameter Requirements by Tool:**

```javascript
search_events_hybrid: {
  required: ["query"],
  optional: ["size"]
}

search_and_filter_events: {
  required: [],  // ALL optional
  optional: ["query", "country", "start_year", "end_year",
             "min_attendance", "max_attendance", "size",
             "sort_by", "sort_order"]
}

get_event_attendance_stats: {
  required: [],  // ALL optional
  optional: ["year", "country"]
}

list_all_events: {
  required: [],  // ALL optional
  optional: ["size", "from", "sort_by", "sort_order"]
}
```

---

## Common Use Cases

### Use Case 1: General Search

**Scenario:** User wants to find events about "artificial intelligence"

**Tool:** `search_events_hybrid`

**Query:**
```json
{
  "query": "artificial intelligence",
  "size": 15
}
```

**Expected Output:** 15 events mentioning AI, ranked by relevance

---

### Use Case 2: Filtered Browse

**Scenario:** Show all Danish events from 2022 with over 100 attendees

**Tool:** `search_and_filter_events`

**Query:**
```json
{
  "country": "Denmark",
  "start_year": 2022,
  "end_year": 2022,
  "min_attendance": 100,
  "size": 50,
  "sort_by": "event_count",
  "sort_order": "desc"
}
```

**Expected Output:** Danish events from 2022 with 100+ attendance, sorted by size

---

### Use Case 3: Year Range Analysis

**Scenario:** Get statistics for all events from 2021-2023

**Tool:** `get_event_attendance_stats`

**Query:**
```json
{}
```

**Expected Output:** Aggregate stats across all years and countries

---

### Use Case 4: Top Events Discovery

**Scenario:** Find the 10 largest events by attendance

**Tool:** `list_all_events`

**Query:**
```json
{
  "size": 10,
  "sort_by": "event_count",
  "sort_order": "desc"
}
```

**Expected Output:** Top 10 events by attendance count

---

### Use Case 5: Fuzzy Search with Filters

**Scenario:** Search for "climate" events in Dominica with 50-500 attendees

**Tool:** `search_and_filter_events`

**Query:**
```json
{
  "query": "climate",
  "country": "Dominica",
  "min_attendance": 50,
  "max_attendance": 500,
  "size": 30,
  "sort_by": "year",
  "sort_order": "desc"
}
```

**Expected Output:** Climate-related events in Dominica with 50-500 attendees, newest first

---

### Use Case 6: Pagination Through All Events

**Scenario:** Retrieve all 101 events in batches of 25

**Tool:** `list_all_events`

**Queries:**
```json
// Batch 1 (events 1-25)
{"size": 25, "from": 0}

// Batch 2 (events 26-50)
{"size": 25, "from": 25}

// Batch 3 (events 51-75)
{"size": 25, "from": 50}

// Batch 4 (events 76-100)
{"size": 25, "from": 75}

// Batch 5 (event 101)
{"size": 25, "from": 100}
```

---

### Use Case 7: Country Comparison

**Scenario:** Compare average attendance between Denmark and Dominica in 2023

**Tool:** `get_event_attendance_stats`

**Queries:**
```json
// Denmark stats
{"year": 2023, "country": "Denmark"}

// Dominica stats
{"year": 2023, "country": "Dominica"}
```

**Analysis:** Compare the `avg` values from both responses

---

### Use Case 8: Small Events Discovery

**Scenario:** Find events with less than 100 attendees

**Tool:** `search_and_filter_events`

**Query:**
```json
{
  "max_attendance": 99,
  "size": 50,
  "sort_by": "event_count",
  "sort_order": "asc"
}
```

**Expected Output:** Events with <100 attendees, smallest first

---

## Technical Notes

### Type Conversion in UI

The UI (`mcp-portal.js`) automatically converts parameter types:

```javascript
if (param.type === 'integer') {
    value = parseInt(value, 10);
} else if (param.type === 'number') {
    value = parseFloat(value);
} else if (param.type === 'boolean') {
    value = value.toLowerCase() === 'true';
}
```

### Enum Rendering in UI

Parameters with `enum` constraints are automatically rendered as dropdowns:

```javascript
if (param.enum && Array.isArray(param.enum)) {
    // Generate <select> dropdown
    // Options populated from param.enum array
}
```

### OpenSearch Query Mapping

**search_events_hybrid:**
```json
{
  "query": {
    "bool": {
      "should": [
        {"multi_match": {"query": "...", "fields": ["event_title^3", "event_theme^2.5"], "fuzziness": "AUTO", "boost": 2}},
        {"multi_match": {"query": "...", "fields": ["event_title.ngram", "event_theme.ngram"], "boost": 1}}
      ],
      "minimum_should_match": 1
    }
  },
  "size": 10
}
```

**search_and_filter_events:**
```json
{
  "query": {
    "bool": {
      "must": [{"multi_match": {"query": "...", "fields": ["event_title^3", ...]}}],
      "filter": [
        {"term": {"country": "Denmark"}},
        {"range": {"year": {"gte": 2020, "lte": 2023}}},
        {"range": {"event_count": {"gte": 100, "lte": 1000}}}
      ]
    }
  },
  "size": 25,
  "sort": [{"year": {"order": "desc", "unmapped_type": "long"}}]
}
```

**list_all_events:**
```json
{
  "query": {"match_all": {}},
  "size": 10,
  "from": 0,
  "sort": [{"year": {"order": "desc", "unmapped_type": "long"}}]
}
```

**get_event_attendance_stats:**
```json
{
  "query": {
    "bool": {
      "filter": [
        {"term": {"country": "Denmark"}},
        {"term": {"year": 2023}}
      ]
    }
  },
  "size": 0,
  "aggs": {
    "attendance_stats": {
      "stats": {"field": "event_count"}
    }
  }
}
```

---

## Troubleshooting

### Issue: "No events found" but expected results

**Possible Causes:**
1. **Filters too restrictive** - Try removing some filters
2. **Typo in country name** - Must be exactly "Denmark" or "Dominica"
3. **Year out of range** - Data only available for 2021-2023
4. **Search term has no matches** - Try broader search terms
5. **Pagination offset too high** - `from` parameter exceeds total events

**Solutions:**
- Remove filters one by one to identify the issue
- Check parameter spelling and case sensitivity
- Use `list_all_events` with no filters to verify data exists

### Issue: Parameters sent as strings instead of integers

**Cause:** UI bug (now fixed)
**Symptoms:** Error like `'<' not supported between instances of 'int' and 'str'`
**Solution:** Refresh browser (Ctrl+F5) to load updated JavaScript

### Issue: Dropdown not showing for enum parameters

**Cause:** Schema doesn't define `enum` array
**Solution:** Verify tool schema in `tools/registry.py`

### Issue: Getting only 10 results when requesting more

**Causes:**
1. **Only 10 documents match query** - Use broader search terms
2. **Default size=10** - Explicitly set `size` parameter
3. **Results truncated** - Check total_hits in response message

**Solution:** Check the response message: `"Found X events... Showing top Y results"`
- X = total matches in database
- Y = actual results returned (min of X and requested size)

---

## Version History

- **v1.0** - Initial 4-tool implementation
- **v1.1** - Fixed None value handling in formatters
- **v1.2** - Added `unmapped_type` for mixed type sorting
- **v1.3** - UI fixes: enum dropdowns + integer conversion

---

## Related Files

- **Tool Definitions:** `/mcp_opensearch/tools/registry.py`
- **Handlers:**
  - `/mcp_opensearch/tools/handlers/search.py`
  - `/mcp_opensearch/tools/handlers/filter.py`
  - `/mcp_opensearch/tools/handlers/aggregation.py`
  - `/mcp_opensearch/tools/handlers/retrieval.py`
- **Formatters:** `/mcp_opensearch/tools/formatters.py`
- **UI Code:** `/tools_gateway/static/js/mcp-portal.js`
- **Architecture:** `/mcp_opensearch/SIMPLIFIED_STRUCTURE.md`

---

**Last Updated:** 2025-10-15
**MCP Protocol Version:** 2025-06-18
**Total Tools:** 4
**Total Documents:** 101 events
