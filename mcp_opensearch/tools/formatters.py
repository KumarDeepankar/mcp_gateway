#!/usr/bin/env python3
"""
Result Formatters for MCP OpenSearch Tools
Provides consistent formatting for different types of search results
"""
import json
from typing import Dict, List, Any, Optional


class ResultFormatter:
    """Formats OpenSearch results into human-readable text."""

    @staticmethod
    def format_search_results(result: Dict[str, Any], query_desc: str) -> str:
        """
        Format search results in a consistent way.

        Args:
            result: OpenSearch result dictionary
            query_desc: Description of the query for the response

        Returns:
            Formatted string representation of results
        """
        hits = result.get("hits", {}).get("hits", [])
        total_hits = result.get("hits", {}).get("total", {}).get("value", 0)

        if not hits:
            return f"No events found matching {query_desc}"

        # Format results
        events = []
        for hit in hits:
            source = hit.get("_source", {})
            events.append({
                "id": hit.get("_id"),
                "score": hit.get("_score"),
                "year": source.get("year"),
                "country": source.get("country"),
                "title": source.get("event_title"),
                "theme": source.get("event_theme"),
                "attendance": source.get("event_count"),
                "highlight": source.get("event_highlight", "")[:200] if source.get("event_highlight") else "",
                "url": source.get("url", ""),
                "rid": source.get("rid", ""),
                "docid": source.get("docid", "")
            })

        response = f"Found {total_hits} events matching {query_desc}. Showing top {len(hits)} results:\n\n"
        response += json.dumps(events, indent=2)

        return response

    @staticmethod
    def format_year_stats(result: Dict[str, Any], country: Optional[str]) -> str:
        """
        Format year-wise statistics.

        Args:
            result: OpenSearch aggregation result
            country: Optional country filter applied

        Returns:
            Formatted year-wise statistics
        """
        buckets = result.get("aggregations", {}).get("by_year", {}).get("buckets", [])

        if not buckets:
            return "No year-wise statistics available"

        stats = []
        for bucket in buckets:
            # Safely handle None values from aggregations
            avg_val = bucket.get("avg_attendance", {}).get("value")
            total_val = bucket.get("total_attendance", {}).get("value")
            min_val = bucket.get("min_attendance", {}).get("value")
            max_val = bucket.get("max_attendance", {}).get("value")

            stats.append({
                "year": bucket["key"],
                "event_count": bucket["doc_count"],
                "avg_attendance": round(avg_val, 2) if avg_val is not None else 0.0,
                "total_attendance": int(total_val) if total_val is not None else 0,
                "min_attendance": int(min_val) if min_val is not None else 0,
                "max_attendance": int(max_val) if max_val is not None else 0
            })

        filter_str = f" (country={country})" if country else ""
        response = f"Year-wise statistics{filter_str}:\n\n"
        response += json.dumps(stats, indent=2)

        return response

    @staticmethod
    def format_country_stats(result: Dict[str, Any], year: Optional[int]) -> str:
        """
        Format country-wise statistics.

        Args:
            result: OpenSearch aggregation result
            year: Optional year filter applied

        Returns:
            Formatted country-wise statistics
        """
        buckets = result.get("aggregations", {}).get("by_country", {}).get("buckets", [])

        if not buckets:
            return "No country-wise statistics available"

        stats = []
        for bucket in buckets:
            # Safely handle None values from aggregations
            avg_val = bucket.get("avg_attendance", {}).get("value")
            total_val = bucket.get("total_attendance", {}).get("value")
            min_val = bucket.get("min_attendance", {}).get("value")
            max_val = bucket.get("max_attendance", {}).get("value")

            stats.append({
                "country": bucket["key"],
                "event_count": bucket["doc_count"],
                "avg_attendance": round(avg_val, 2) if avg_val is not None else 0.0,
                "total_attendance": int(total_val) if total_val is not None else 0,
                "min_attendance": int(min_val) if min_val is not None else 0,
                "max_attendance": int(max_val) if max_val is not None else 0
            })

        filter_str = f" (year={year})" if year else ""
        response = f"Country-wise statistics{filter_str}:\n\n"
        response += json.dumps(stats, indent=2)

        return response

    @staticmethod
    def format_theme_aggregation(result: Dict[str, Any], year: Optional[int], country: Optional[str]) -> str:
        """
        Format theme aggregation results.

        Args:
            result: OpenSearch aggregation result
            year: Optional year filter applied
            country: Optional country filter applied

        Returns:
            Formatted theme aggregation
        """
        buckets = result.get("aggregations", {}).get("by_theme", {}).get("buckets", [])

        if not buckets:
            return "No theme data available"

        themes = []
        for bucket in buckets:
            themes.append({
                "theme": bucket["key"],
                "event_count": bucket["doc_count"]
            })

        filters = []
        if year:
            filters.append(f"year={year}")
        if country:
            filters.append(f"country={country}")
        filter_str = f" ({', '.join(filters)})" if filters else ""

        response = f"Top themes by event count{filter_str}:\n\n"
        response += json.dumps(themes, indent=2)

        return response

    @staticmethod
    def format_attendance_stats(result: Dict[str, Any], year: Optional[int], country: Optional[str]) -> str:
        """
        Format attendance statistics.

        Args:
            result: OpenSearch aggregation result
            year: Optional year filter applied
            country: Optional country filter applied

        Returns:
            Formatted attendance statistics
        """
        stats_data = result.get("aggregations", {}).get("attendance_stats", {})

        if not stats_data:
            return "No attendance statistics available"

        # Handle None values from OpenSearch when no documents match
        count = stats_data.get("count")
        min_val = stats_data.get("min")
        max_val = stats_data.get("max")
        avg_val = stats_data.get("avg")
        sum_val = stats_data.get("sum")

        stats = {
            "count": int(count) if count is not None else 0,
            "min": int(min_val) if min_val is not None else 0,
            "max": int(max_val) if max_val is not None else 0,
            "avg": round(avg_val, 2) if avg_val is not None else 0.0,
            "sum": int(sum_val) if sum_val is not None else 0
        }

        filters = []
        if year:
            filters.append(f"year={year}")
        if country:
            filters.append(f"country={country}")
        filter_str = f" ({', '.join(filters)})" if filters else ""

        response = f"Attendance statistics{filter_str}:\n\n"
        response += json.dumps(stats, indent=2)

        return response
