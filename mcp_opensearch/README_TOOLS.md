# Events MCP Tools Documentation

## Overview

This MCP server provides **17 granular tools** designed for the `events` OpenSearch index. These tools enable agentic assistants (particularly plan-and-execute agents) to perform advanced analytical queries by breaking down complex user requests into atomic operations.

## Tool Categories

### 1. Search Tools (5 tools)
Advanced search capabilities with fuzzy matching and different strategies

### 2. Filter Tools (5 tools)
Precise filtering by country, year, attendance, and combined filters

### 3. Aggregation/Analytics Tools (4 tools)
Statistical analysis and data aggregation

### 4. Retrieval Tools (3 tools)
Basic document retrieval and counting

---

## Detailed Tool Reference

### 1. SEARCH TOOLS

#### 1.1 `search_events`
**Description:** Basic fuzzy search across all searchable fields (title, theme, highlight, summary, objective)

**Use Case:** General search when user doesn't specify a particular field

**Parameters:**
- `query` (string, required): Search query text (spelling mistakes tolerated)
- `size` (integer, optional): Number of results (default: 10, max: 100)

**Example:**
```json
{
  "name": "search_events",
  "arguments": {
    "query": "renewable energy",
    "size": 5
  }
}
```

**Agent Scenario:** User asks "Find events about renewable energy"

---

#### 1.2 `search_events_by_title`
**Description:** Search specifically in event titles with fuzzy matching

**Use Case:** When user wants to find events by title

**Parameters:**
- `query` (string, required): Search query for event titles
- `size` (integer, optional): Number of results (default: 10, max: 100)

**Example:**
```json
{
  "name": "search_events_by_title",
  "arguments": {
    "query": "summit",
    "size": 10
  }
}
```

**Agent Scenario:** User asks "Find events with 'summit' in the title"

---

#### 1.3 `search_events_by_theme`
**Description:** Search events by theme/topic with fuzzy matching

**Use Case:** When user wants to find events by topic or theme

**Parameters:**
- `theme` (string, required): Theme or topic to search for
- `size` (integer, optional): Number of results (default: 10, max: 100)

**Example:**
```json
{
  "name": "search_events_by_theme",
  "arguments": {
    "theme": "technology",
    "size": 10
  }
}
```

**Agent Scenario:** User asks "Show me technology-themed events"

---

#### 1.4 `search_events_hybrid`
**Description:** Advanced hybrid search combining standard and ngram analyzers for best fuzzy matching

**Use Case:** When dealing with potentially misspelled queries or need maximum recall

**Parameters:**
- `query` (string, required): Search query text
- `size` (integer, optional): Number of results (default: 10, max: 100)

**Example:**
```json
{
  "name": "search_events_hybrid",
  "arguments": {
    "query": "climat chang",
    "size": 5
  }
}
```

**Agent Scenario:** User query has typos or fuzzy search needed

---

#### 1.5 `search_events_autocomplete`
**Description:** Autocomplete/prefix search for event titles and themes

**Use Case:** Search-as-you-type functionality or partial word matching

**Parameters:**
- `prefix` (string, required): Prefix text to autocomplete (min 2 characters)
- `size` (integer, optional): Number of results (default: 10, max: 50)

**Example:**
```json
{
  "name": "search_events_autocomplete",
  "arguments": {
    "prefix": "tech",
    "size": 10
  }
}
```

**Agent Scenario:** User types partial words or wants autocomplete suggestions

---

### 2. FILTER TOOLS

#### 2.1 `filter_events_by_country`
**Description:** Filter events by country (Denmark or Dominica), optionally with search query

**Use Case:** When user wants events from a specific country

**Parameters:**
- `country` (string, required): "Denmark" or "Dominica"
- `query` (string, optional): Optional search query to combine
- `size` (integer, optional): Number of results (default: 10, max: 100)

**Example:**
```json
{
  "name": "filter_events_by_country",
  "arguments": {
    "country": "Denmark",
    "query": "renewable energy",
    "size": 10
  }
}
```

**Agent Scenario:** User asks "Find renewable energy events in Denmark"

---

#### 2.2 `filter_events_by_year`
**Description:** Filter events by a specific year, optionally with search query

**Use Case:** When user wants events from a particular year

**Parameters:**
- `year` (integer, required): Year to filter (e.g., 2021, 2022, 2023)
- `query` (string, optional): Optional search query to combine
- `size` (integer, optional): Number of results (default: 10, max: 100)

**Example:**
```json
{
  "name": "filter_events_by_year",
  "arguments": {
    "year": 2023,
    "query": "technology",
    "size": 10
  }
}
```

**Agent Scenario:** User asks "What technology events happened in 2023?"

---

#### 2.3 `filter_events_by_year_range`
**Description:** Filter events by year range, optionally with search query

**Use Case:** When user wants events within a date range

**Parameters:**
- `start_year` (integer, required): Start year (inclusive)
- `end_year` (integer, required): End year (inclusive)
- `query` (string, optional): Optional search query to combine
- `size` (integer, optional): Number of results (default: 10, max: 100)

**Example:**
```json
{
  "name": "filter_events_by_year_range",
  "arguments": {
    "start_year": 2021,
    "end_year": 2023,
    "query": "climate",
    "size": 10
  }
}
```

**Agent Scenario:** User asks "Show climate events from 2021 to 2023"

---

#### 2.4 `filter_events_by_attendance`
**Description:** Filter events by attendance/participation count range

**Use Case:** When user wants large or small events based on attendance

**Parameters:**
- `min_attendance` (integer, optional): Minimum attendance
- `max_attendance` (integer, optional): Maximum attendance
- `query` (string, optional): Optional search query to combine
- `size` (integer, optional): Number of results (default: 10, max: 100)

**Example:**
```json
{
  "name": "filter_events_by_attendance",
  "arguments": {
    "min_attendance": 10000,
    "query": "summit",
    "size": 5
  }
}
```

**Agent Scenario:** User asks "Find large summits with over 10,000 attendees"

---

#### 2.5 `search_and_filter_events`
**Description:** Combined search with multiple filters (country, year range, attendance)

**Use Case:** Complex queries requiring multiple filter combinations

**Parameters:**
- `query` (string, optional): Search query text
- `country` (string, optional): "Denmark" or "Dominica"
- `start_year` (integer, optional): Start year for range
- `end_year` (integer, optional): End year for range
- `min_attendance` (integer, optional): Minimum attendance
- `max_attendance` (integer, optional): Maximum attendance
- `size` (integer, optional): Number of results (default: 10, max: 100)
- `sort_by` (string, optional): "year", "event_count", or "relevance" (default: "relevance")
- `sort_order` (string, optional): "asc" or "desc" (default: "desc")

**Example:**
```json
{
  "name": "search_and_filter_events",
  "arguments": {
    "query": "energy",
    "country": "Denmark",
    "start_year": 2022,
    "end_year": 2023,
    "min_attendance": 5000,
    "size": 10,
    "sort_by": "year",
    "sort_order": "desc"
  }
}
```

**Agent Scenario:** User asks "Find large energy-related events in Denmark from 2022-2023 with over 5000 attendees"

---

### 3. AGGREGATION/ANALYTICS TOOLS

#### 3.1 `get_events_stats_by_year`
**Description:** Get year-wise statistics including event count and average attendance per year

**Use Case:** When user wants year-over-year analysis

**Parameters:**
- `country` (string, optional): Filter by "Denmark" or "Dominica"

**Example:**
```json
{
  "name": "get_events_stats_by_year",
  "arguments": {
    "country": "Denmark"
  }
}
```

**Agent Scenario:** User asks "Show me yearly event statistics for Denmark"

**Output:**
```json
{
  "year": 2023,
  "event_count": 33,
  "avg_attendance": 8543.21,
  "total_attendance": 281926,
  "min_attendance": 2500,
  "max_attendance": 15000
}
```

---

#### 3.2 `get_events_stats_by_country`
**Description:** Get country-wise statistics including event count and average attendance per country

**Use Case:** When user wants country comparison

**Parameters:**
- `year` (integer, optional): Filter by specific year

**Example:**
```json
{
  "name": "get_events_stats_by_country",
  "arguments": {
    "year": 2023
  }
}
```

**Agent Scenario:** User asks "Compare event statistics between countries in 2023"

---

#### 3.3 `get_events_by_theme_aggregation`
**Description:** Get aggregated count of events by theme/topic

**Use Case:** When user wants to know popular themes or topics

**Parameters:**
- `top_n` (integer, optional): Number of top themes (default: 10, max: 50)
- `year` (integer, optional): Filter by year
- `country` (string, optional): Filter by country

**Example:**
```json
{
  "name": "get_events_by_theme_aggregation",
  "arguments": {
    "top_n": 10,
    "year": 2023
  }
}
```

**Agent Scenario:** User asks "What are the most popular event themes in 2023?"

---

#### 3.4 `get_event_attendance_stats`
**Description:** Get statistical analysis of event attendance (min, max, avg, sum, count)

**Use Case:** When user wants attendance analysis

**Parameters:**
- `year` (integer, optional): Filter by year
- `country` (string, optional): Filter by country

**Example:**
```json
{
  "name": "get_event_attendance_stats",
  "arguments": {
    "country": "Denmark",
    "year": 2023
  }
}
```

**Agent Scenario:** User asks "What's the average event attendance in Denmark for 2023?"

**Output:**
```json
{
  "count": 33,
  "min": 2500,
  "max": 15000,
  "avg": 8543.21,
  "sum": 281926
}
```

---

### 4. RETRIEVAL TOOLS

#### 4.1 `get_event_by_id`
**Description:** Retrieve a specific event by its document ID

**Use Case:** When user wants full details of a specific event

**Parameters:**
- `event_id` (string, required): The document ID of the event

**Example:**
```json
{
  "name": "get_event_by_id",
  "arguments": {
    "event_id": "abc123"
  }
}
```

**Agent Scenario:** Follow-up query "Show me details of that event"

---

#### 4.2 `list_all_events`
**Description:** List all events with pagination support

**Use Case:** When user wants to browse events

**Parameters:**
- `size` (integer, optional): Number of events (default: 10, max: 100)
- `from` (integer, optional): Offset for pagination (default: 0)
- `sort_by` (string, optional): "year" or "event_count" (default: "year")
- `sort_order` (string, optional): "asc" or "desc" (default: "desc")

**Example:**
```json
{
  "name": "list_all_events",
  "arguments": {
    "size": 20,
    "from": 0,
    "sort_by": "event_count",
    "sort_order": "desc"
  }
}
```

**Agent Scenario:** User asks "Show me the largest events by attendance"

---

#### 4.3 `count_events`
**Description:** Get total count of events with optional filters

**Use Case:** When user wants to know how many events match criteria

**Parameters:**
- `country` (string, optional): Filter by country
- `year` (integer, optional): Filter by year

**Example:**
```json
{
  "name": "count_events",
  "arguments": {
    "country": "Denmark",
    "year": 2023
  }
}
```

**Agent Scenario:** User asks "How many events were held in Denmark in 2023?"

---

## Agentic Assistant Usage Examples

### Example 1: Multi-Step Query
**User Query:** "Show me technology events in Denmark from 2022-2023 and tell me the average attendance"

**Agent Plan:**
1. Use `search_and_filter_events` with:
   - query: "technology"
   - country: "Denmark"
   - start_year: 2022, end_year: 2023
2. Use `get_event_attendance_stats` with:
   - country: "Denmark"
   - start_year: 2022, end_year: 2023

---

### Example 2: Exploratory Analysis
**User Query:** "What were the main themes of events in 2023?"

**Agent Plan:**
1. Use `get_events_by_theme_aggregation` with:
   - year: 2023
   - top_n: 10

---

### Example 3: Comparison Query
**User Query:** "Compare event counts and attendance between Denmark and Dominica"

**Agent Plan:**
1. Use `get_events_stats_by_country` (no filters)
2. Present comparison

---

### Example 4: Filtered Search
**User Query:** "Find large renewable energy summits in the last two years"

**Agent Plan:**
1. Use `search_and_filter_events` with:
   - query: "renewable energy summit"
   - start_year: 2022
   - end_year: 2023
   - min_attendance: 10000

---

## Tool Selection Guidelines for Agents

### For Search Queries:
- **Simple text search** → `search_events`
- **Title-specific search** → `search_events_by_title`
- **Theme-specific search** → `search_events_by_theme`
- **Typo-tolerant search** → `search_events_hybrid`
- **Partial/autocomplete** → `search_events_autocomplete`

### For Filtering:
- **Single country filter** → `filter_events_by_country`
- **Single year filter** → `filter_events_by_year`
- **Year range** → `filter_events_by_year_range`
- **Attendance range** → `filter_events_by_attendance`
- **Multiple filters** → `search_and_filter_events`

### For Analytics:
- **Year-over-year trends** → `get_events_stats_by_year`
- **Country comparison** → `get_events_stats_by_country`
- **Popular themes** → `get_events_by_theme_aggregation`
- **Attendance analysis** → `get_event_attendance_stats`

### For Retrieval:
- **Specific event details** → `get_event_by_id`
- **Browse/list events** → `list_all_events`
- **Count matching events** → `count_events`

---

## Index Schema Reference

### Searchable Fields:
- `event_title` (text, boost: 3.0)
- `event_theme` (text, boost: 2.5)
- `event_highlight` (text, boost: 2.0)
- `event_summary` (text, boost: 1.5)
- `event_object` (text, boost: 1.2)

### Filterable Fields:
- `country` (keyword)
- `year` (integer)
- `event_count` (integer)

### Stored-Only Fields:
- `rid`, `docid`, `url`
- `commentary_summary`
- `next_event_plan`
- `event_conclusion`
- `event_conclusion_overall`
- `next_event_suggestion`

---

## Testing

Run the test script to validate all tools:
```bash
cd mcp_opensearch
python test_events_tools.py
```

This will:
1. Test all 17 tools with sample queries
2. Demonstrate agent use cases
3. Show expected outputs

---

## Performance Considerations

- **Fuzzy search** queries may take 100-200ms
- **Aggregations** typically complete in <200ms
- **Exact filters** are fastest (<50ms)
- Use `size` parameter to limit results and improve performance
- Hybrid search is slower but provides better recall

---

## Migration from Stories Index

**Previous tools (removed):**
- `search_stories`
- `get_story`
- `list_stories`
- `count_stories`

**New tools (17 total):**
- 5 search tools with different strategies
- 5 filter tools with various combinations
- 4 aggregation tools for analytics
- 3 retrieval tools for basic operations

**Benefits:**
- More granular and composable
- Better support for agentic workflows
- Advanced analytics capabilities
- Optimized for events index schema
