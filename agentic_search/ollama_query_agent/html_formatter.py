"""
Python HTML Response Generator
Formats task results into rich HTML responses without LLM
"""

from typing import List, Dict, Any
import html as html_lib
import logging

logger = logging.getLogger(__name__)


def format_task_results_to_html(
    user_query: str,
    task_results: List[Dict[str, Any]],
    sources_used: List[str],
    use_rich_formatting: bool = True
) -> str:
    """
    Convert task results directly to HTML without LLM

    Args:
        user_query: The user's original query
        task_results: List of task results from execution
        sources_used: List of tool names used
        use_rich_formatting: Whether to use enhanced formatting

    Returns:
        HTML string with formatted results
    """
    logger.info(f"[HTML Formatter] Generating HTML response for {len(task_results)} task results")

    query_escaped = html_lib.escape(user_query)
    html_parts = []

    # Header section
    html_parts.append("<div>")
    html_parts.append(f"<h3>Search Results: {query_escaped}</h3>")

    # Summary section
    total_items = _count_total_items(task_results)
    html_parts.append("<p>")
    html_parts.append(f"<strong>Data Summary:</strong> Processed {len(task_results)} data source(s)")
    if total_items > 0:
        html_parts.append(f" and found {total_items} total items")
    html_parts.append(f". Tools used: {', '.join(sources_used)}")
    html_parts.append("</p>")

    # Process each task result
    for idx, task_result in enumerate(task_results, 1):
        logger.debug(f"[HTML Formatter] Processing task result {idx}/{len(task_results)}")

        tool_name = html_lib.escape(task_result.get("tool_name", "Unknown"))
        description = html_lib.escape(task_result.get("description", ""))
        result_data = task_result.get("result", {})

        html_parts.append(f"<h4>{idx}. {tool_name}</h4>")
        if description:
            html_parts.append(f"<p><em>{description}</em></p>")

        # Format based on result type
        if isinstance(result_data, dict):
            if "error" in result_data:
                html_parts.extend(_format_error(result_data))
            elif "events" in result_data:
                html_parts.extend(_format_events(result_data, use_rich_formatting))
            elif "data" in result_data:
                html_parts.extend(_format_data_items(result_data, use_rich_formatting))
            elif "count" in result_data or "total" in result_data:
                html_parts.extend(_format_count(result_data))
            elif "stats" in result_data or "statistics" in result_data:
                html_parts.extend(_format_statistics(result_data))
            else:
                html_parts.extend(_format_generic_dict(result_data))
        else:
            html_parts.extend(_format_generic_value(result_data))

    html_parts.append("</div>")

    result_html = "".join(html_parts)
    logger.info(f"[HTML Formatter] Generated {len(result_html)} characters of HTML")
    return result_html


def _count_total_items(task_results: List[Dict[str, Any]]) -> int:
    """Count total items across all task results"""
    total = 0
    for task in task_results:
        result_data = task.get("result", {})
        if isinstance(result_data, dict):
            if "events" in result_data:
                total += len(result_data.get("events", []))
            elif "data" in result_data:
                total += len(result_data.get("data", []))
            elif "count" in result_data:
                total += result_data.get("count", 0)
            elif "total" in result_data:
                total += result_data.get("total", 0)
    return total


def _format_error(result_data: Dict[str, Any]) -> List[str]:
    """Format error messages"""
    error_msg = html_lib.escape(str(result_data["error"])[:300])
    return [
        f"<div style='background: #fff3cd; padding: 12px; border-radius: 4px; border-left: 3px solid #ffc107; margin: 10px 0;'>",
        f"<p style='margin: 0; color: #856404;'><strong>⚠️ Error:</strong> {error_msg}</p>",
        "</div>"
    ]


def _format_events(result_data: Dict[str, Any], use_rich_formatting: bool) -> List[str]:
    """Format events data"""
    events = result_data.get("events", [])
    html = []

    html.append(f"<p><strong>Found {len(events)} events</strong></p>")

    if not events:
        return html

    if use_rich_formatting and len(events) > 0:
        # Create a table for rich formatting
        html.append("<table style='width:100%; border-collapse:collapse; margin:10px 0;'>")
        html.append("<thead>")
        html.append("<tr style='border-bottom:2px solid #333; background:#f5f5f5;'>")

        # Determine columns based on first event
        first_event = events[0] if isinstance(events[0], dict) else {}
        headers = []
        if "title" in first_event or "name" in first_event:
            headers.append("Event")
        if "location" in first_event or "country" in first_event:
            headers.append("Location")
        if "date" in first_event or "year" in first_event:
            headers.append("Date")
        if "attendance" in first_event or "attendees" in first_event:
            headers.append("Attendance")

        if not headers:
            headers = ["Event", "Details"]

        for header in headers:
            html.append(f"<th style='padding:10px; text-align:left;'>{header}</th>")
        html.append("</tr>")
        html.append("</thead>")
        html.append("<tbody>")

        # Add rows (limit to 15 for readability)
        for event in events[:15]:
            if isinstance(event, dict):
                html.append("<tr style='border-bottom:1px solid #ddd;'>")

                # Event name/title
                if "Event" in headers or "Details" in headers:
                    title = html_lib.escape(str(event.get("title", event.get("name", "Untitled"))))
                    html.append(f"<td style='padding:10px;'><strong>{title}</strong></td>")

                # Location
                if "Location" in headers:
                    location = html_lib.escape(str(event.get("location", event.get("country", "N/A"))))
                    html.append(f"<td style='padding:10px;'>{location}</td>")

                # Date
                if "Date" in headers:
                    date = html_lib.escape(str(event.get("date", event.get("year", "N/A"))))
                    html.append(f"<td style='padding:10px;'>{date}</td>")

                # Attendance
                if "Attendance" in headers:
                    attendance = html_lib.escape(str(event.get("attendance", event.get("attendees", "N/A"))))
                    html.append(f"<td style='padding:10px;'>{attendance}</td>")

                # Details fallback
                if headers == ["Event", "Details"]:
                    details = ", ".join([f"{k}: {v}" for k, v in list(event.items())[1:3] if k not in ["title", "name"]])
                    html.append(f"<td style='padding:10px;'>{html_lib.escape(details[:100])}</td>")

                html.append("</tr>")

        html.append("</tbody>")
        html.append("</table>")

        if len(events) > 15:
            html.append(f"<p><em>...and {len(events) - 15} more events</em></p>")
    else:
        # Simple list format
        html.append("<ul>")
        for event in events[:10]:
            if isinstance(event, dict):
                title = html_lib.escape(str(event.get("title", event.get("name", "Untitled"))))
                html.append(f"<li><strong>{title}</strong>")

                if "location" in event:
                    location = html_lib.escape(str(event["location"]))
                    html.append(f" - {location}")
                if "date" in event:
                    date = html_lib.escape(str(event["date"]))
                    html.append(f" ({date})")
                if "year" in event:
                    year = html_lib.escape(str(event["year"]))
                    html.append(f" - {year}")

                html.append("</li>")
        html.append("</ul>")

        if len(events) > 10:
            html.append(f"<p><em>...and {len(events) - 10} more events</em></p>")

    return html


def _format_data_items(result_data: Dict[str, Any], use_rich_formatting: bool) -> List[str]:
    """Format generic data items"""
    data_items = result_data.get("data", [])
    html = []

    html.append(f"<p><strong>Retrieved {len(data_items)} items</strong></p>")

    if not data_items:
        return html

    if use_rich_formatting and len(data_items) > 0 and isinstance(data_items[0], dict):
        # Try to create a table if items are dictionaries
        first_item = data_items[0]
        keys = [k for k in list(first_item.keys())[:4] if not k.startswith('_')]  # First 4 non-private keys

        if keys:
            html.append("<table style='width:100%; border-collapse:collapse; margin:10px 0;'>")
            html.append("<thead>")
            html.append("<tr style='border-bottom:2px solid #333; background:#f5f5f5;'>")
            for key in keys:
                html.append(f"<th style='padding:10px; text-align:left;'>{html_lib.escape(key.title())}</th>")
            html.append("</tr>")
            html.append("</thead>")
            html.append("<tbody>")

            for item in data_items[:15]:
                if isinstance(item, dict):
                    html.append("<tr style='border-bottom:1px solid #ddd;'>")
                    for key in keys:
                        value = html_lib.escape(str(item.get(key, ""))[:100])
                        html.append(f"<td style='padding:10px;'>{value}</td>")
                    html.append("</tr>")

            html.append("</tbody>")
            html.append("</table>")

            if len(data_items) > 15:
                html.append(f"<p><em>...and {len(data_items) - 15} more items</em></p>")
        else:
            html.extend(_format_simple_list(data_items))
    else:
        html.extend(_format_simple_list(data_items))

    return html


def _format_simple_list(items: List[Any]) -> List[str]:
    """Format items as a simple bullet list"""
    html = ["<ul>"]

    for item in items[:10]:
        if isinstance(item, dict):
            display_text = None
            for key in ["title", "name", "label", "description", "id"]:
                if key in item:
                    display_text = html_lib.escape(str(item[key])[:150])
                    break

            if display_text:
                html.append(f"<li>{display_text}</li>")
            else:
                item_summary = ", ".join([f"{k}: {str(v)[:40]}" for k, v in list(item.items())[:3]])
                html.append(f"<li>{html_lib.escape(item_summary)}</li>")
        else:
            html.append(f"<li>{html_lib.escape(str(item)[:150])}</li>")

    html.append("</ul>")

    if len(items) > 10:
        html.append(f"<p><em>...and {len(items) - 10} more items</em></p>")

    return html


def _format_count(result_data: Dict[str, Any]) -> List[str]:
    """Format count/total statistics"""
    count = result_data.get("count", result_data.get("total", 0))
    html = []

    html.append(f"<p><strong>Total Count:</strong> {count}</p>")

    # Show any additional stats
    other_stats = {k: v for k, v in result_data.items() if k not in ["count", "total"] and isinstance(v, (int, float, str))}
    if other_stats:
        html.append("<ul>")
        for key, value in list(other_stats.items())[:8]:
            key_escaped = html_lib.escape(str(key).replace("_", " ").title())
            value_escaped = html_lib.escape(str(value))
            html.append(f"<li><strong>{key_escaped}:</strong> {value_escaped}</li>")
        html.append("</ul>")

    return html


def _format_statistics(result_data: Dict[str, Any]) -> List[str]:
    """Format statistical data"""
    stats = result_data.get("stats", result_data.get("statistics", {}))
    html = []

    html.append("<p><strong>Statistics:</strong></p>")

    if isinstance(stats, dict):
        html.append("<table style='width:100%; border-collapse:collapse; margin:10px 0;'>")
        html.append("<tbody>")

        for key, value in stats.items():
            key_escaped = html_lib.escape(str(key).replace("_", " ").title())
            value_escaped = html_lib.escape(str(value))
            html.append("<tr style='border-bottom:1px solid #ddd;'>")
            html.append(f"<td style='padding:10px; font-weight:bold;'>{key_escaped}</td>")
            html.append(f"<td style='padding:10px;'>{value_escaped}</td>")
            html.append("</tr>")

        html.append("</tbody>")
        html.append("</table>")
    else:
        html.append(f"<p>{html_lib.escape(str(stats))}</p>")

    return html


def _format_generic_dict(result_data: Dict[str, Any]) -> List[str]:
    """Format generic dictionary data"""
    html = ["<ul>"]

    for key, value in list(result_data.items())[:10]:
        key_escaped = html_lib.escape(str(key).replace("_", " ").title())
        if isinstance(value, (list, dict)):
            value_escaped = html_lib.escape(str(value)[:200])
        else:
            value_escaped = html_lib.escape(str(value))
        html.append(f"<li><strong>{key_escaped}:</strong> {value_escaped}</li>")

    html.append("</ul>")

    if len(result_data) > 10:
        html.append(f"<p><em>...and {len(result_data) - 10} more fields</em></p>")

    return html


def _format_generic_value(result_data: Any) -> List[str]:
    """Format non-dict result data"""
    result_str = html_lib.escape(str(result_data)[:500])
    return [f"<p>{result_str}</p>"]


def generate_no_results_html(user_query: str) -> str:
    """Generate HTML for no results found"""
    query = html_lib.escape(user_query)
    return f"""<div>
    <h3>No Results Found</h3>
    <p>No data was found for your query: <strong>{query}</strong></p>
    <p>Try:</p>
    <ul>
        <li>Rephrasing your query</li>
        <li>Using different search terms</li>
        <li>Selecting different tools</li>
    </ul>
</div>"""
