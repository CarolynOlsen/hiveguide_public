#!/usr/bin/env python3
"""
Generate LaTeX commands from metrics_summary.json for automatic inclusion in paper.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
METRICS_JSON = PROJECT_ROOT / "validation" / "results" / "metrics_summary.json"
OUTPUT_TEX = Path(__file__).parent / "metrics.tex"
TABLE_OUTPUT_TEX = Path(__file__).parent / "metrics_table.tex"


def format_percentage(value, decimals=1):
    """Format a decimal value as a percentage."""
    return f"{value * 100:.{decimals}f}"


def format_decimal(value, decimals=3):
    """Format a decimal value."""
    return f"{value:.{decimals}f}"


def format_latency_ms(value_ms, decimals=1):
    """Convert milliseconds to seconds and format."""
    return f"{value_ms / 1000:.{decimals}f}"


def bold_if_best(formatted_value, raw_value, all_raw_values, lower_is_better=False):
    """Return formatted value wrapped in \\textbf{} if it's the best among values"""
    if raw_value is None or any(v is None for v in all_raw_values):
        return formatted_value
    
    if lower_is_better:
        is_best = raw_value == min(all_raw_values)
    else:
        is_best = raw_value == max(all_raw_values)
    
    if is_best:
        return f"\\textbf{{{formatted_value}}}"
    return formatted_value


def generate_comparison_table(metrics):
    """Generate LaTeX table with automatic bolding of best values and significance markers"""
    
    # Get statistical tests
    stat_tests = metrics.get("statistical_tests", {})
    
    def get_significance_marker(test_name):
        """Return significance marker (* or **) based on p-value."""
        test = stat_tests.get(test_name)
        if not test or test.get("p_value") is None:
            return ""
        
        if test.get("significant_at_0.01"):
            return "$^{**}$"  # p < 0.01
        elif test.get("significant_at_0.05"):
            return "$^{*}$"   # p < 0.05
        return ""
    
    # Extract values
    latency_p90 = {
        'intent_aware': metrics['latency']['p90_ms']['intent_aware'] / 1000,
        'always_both': metrics['latency']['p90_ms']['always_both'] / 1000,
        'agent_discretion': metrics['latency']['p90_ms']['agent_discretion'] / 1000
    }
    latency_p95 = {
        'intent_aware': metrics['latency']['p95_ms']['intent_aware'] / 1000,
        'always_both': metrics['latency']['p95_ms']['always_both'] / 1000,
        'agent_discretion': metrics['latency']['p95_ms']['agent_discretion'] / 1000
    }
    hit3 = {
        'intent_aware': metrics['retrieval_hit_rate']['retrieval_hit_rate@3']['intent_aware'] * 100,
        'always_both': metrics['retrieval_hit_rate']['retrieval_hit_rate@3']['always_both'] * 100,
        'agent_discretion': metrics['retrieval_hit_rate']['retrieval_hit_rate@3']['agent_discretion'] * 100
    }
    hit5 = {
        'intent_aware': metrics['retrieval_hit_rate']['retrieval_hit_rate@5']['intent_aware'] * 100,
        'always_both': metrics['retrieval_hit_rate']['retrieval_hit_rate@5']['always_both'] * 100,
        'agent_discretion': metrics['retrieval_hit_rate']['retrieval_hit_rate@5']['agent_discretion'] * 100
    }
    relevance = {
        'intent_aware': metrics['response_quality']['context_relevance']['intent_aware'],
        'always_both': metrics['response_quality']['context_relevance']['always_both'],
        'agent_discretion': metrics['response_quality']['context_relevance']['agent_discretion']
    }
    groundedness = {
        'intent_aware': metrics['response_quality']['response_groundedness']['intent_aware'],
        'always_both': metrics['response_quality']['response_groundedness']['always_both'],
        'agent_discretion': metrics['response_quality']['response_groundedness']['agent_discretion']
    }
    
    # Format values with bolding for best and add significance markers
    # Latency p90
    p90_vals = list(latency_p90.values())
    p90_ia = bold_if_best(f'{latency_p90["intent_aware"]:.1f}', latency_p90["intent_aware"], p90_vals, lower_is_better=True)
    p90_ab = bold_if_best(f'{latency_p90["always_both"]:.1f}', latency_p90["always_both"], p90_vals, lower_is_better=True)
    p90_ad = bold_if_best(f'{latency_p90["agent_discretion"]:.1f}', latency_p90["agent_discretion"], p90_vals, lower_is_better=True)
    # Add significance markers comparing intent-aware to baselines (markers go on baseline values)
    marker_ab = get_significance_marker("latency_vs_always_both")
    marker_ad = get_significance_marker("latency_vs_agent_discretion")
    if marker_ab:
        p90_ab = f"{p90_ab}{marker_ab}"
    if marker_ad:
        p90_ad = f"{p90_ad}{marker_ad}"
    
    # Latency p95
    p95_vals = list(latency_p95.values())
    p95_ia = bold_if_best(f'{latency_p95["intent_aware"]:.1f}', latency_p95["intent_aware"], p95_vals, lower_is_better=True)
    p95_ab = bold_if_best(f'{latency_p95["always_both"]:.1f}', latency_p95["always_both"], p95_vals, lower_is_better=True)
    p95_ad = bold_if_best(f'{latency_p95["agent_discretion"]:.1f}', latency_p95["agent_discretion"], p95_vals, lower_is_better=True)
    marker_ab = get_significance_marker("latency_vs_always_both")
    marker_ad = get_significance_marker("latency_vs_agent_discretion")
    if marker_ab:
        p95_ab = f"{p95_ab}{marker_ab}"
    if marker_ad:
        p95_ad = f"{p95_ad}{marker_ad}"
    
    # Hit@3 (no significance tests for retrieval metrics)
    h3_vals = list(hit3.values())
    h3_ia = bold_if_best(f'{hit3["intent_aware"]:.1f}', hit3["intent_aware"], h3_vals)
    h3_ab = bold_if_best(f'{hit3["always_both"]:.1f}', hit3["always_both"], h3_vals)
    h3_ad = bold_if_best(f'{hit3["agent_discretion"]:.1f}', hit3["agent_discretion"], h3_vals)
    
    # Hit@5
    h5_vals = list(hit5.values())
    h5_ia = bold_if_best(f'{hit5["intent_aware"]:.1f}', hit5["intent_aware"], h5_vals)
    h5_ab = bold_if_best(f'{hit5["always_both"]:.1f}', hit5["always_both"], h5_vals)
    h5_ad = bold_if_best(f'{hit5["agent_discretion"]:.1f}', hit5["agent_discretion"], h5_vals)
    
    # Context Relevance
    rel_vals = list(relevance.values())
    rel_ia = bold_if_best(f'{relevance["intent_aware"]:.3f}', relevance["intent_aware"], rel_vals)
    rel_ab = bold_if_best(f'{relevance["always_both"]:.3f}', relevance["always_both"], rel_vals)
    rel_ad = bold_if_best(f'{relevance["agent_discretion"]:.3f}', relevance["agent_discretion"], rel_vals)
    marker_ab = get_significance_marker("context_relevance_vs_always_both")
    marker_ad = get_significance_marker("context_relevance_vs_agent_discretion")
    if marker_ab:
        rel_ab = f"{rel_ab}{marker_ab}"
    if marker_ad:
        rel_ad = f"{rel_ad}{marker_ad}"
    
    # Response Groundedness
    grd_vals = list(groundedness.values())
    grd_ia = bold_if_best(f'{groundedness["intent_aware"]:.3f}', groundedness["intent_aware"], grd_vals)
    grd_ab = bold_if_best(f'{groundedness["always_both"]:.3f}', groundedness["always_both"], grd_vals)
    grd_ad = bold_if_best(f'{groundedness["agent_discretion"]:.3f}', groundedness["agent_discretion"], grd_vals)
    marker_ab = get_significance_marker("response_groundedness_vs_always_both")
    marker_ad = get_significance_marker("response_groundedness_vs_agent_discretion")
    if marker_ab:
        grd_ab = f"{grd_ab}{marker_ab}"
    if marker_ad:
        grd_ad = f"{grd_ad}{marker_ad}"
    
    # Generate table - make it narrower to fit in single column
    table_lines = [
        "% Auto-generated comparison table from metrics_summary.json",
        "% DO NOT EDIT MANUALLY - regenerate with: python generate_metrics_tex.py",
        "",
        "\\begin{table}[h]",
        "\\centering",
        "\\footnotesize",
        "\\begin{tabular}{l@{\\hspace{0.1cm}}r@{\\hspace{0.08cm}}r@{\\hspace{0.08cm}}r}",
        "\\hline",
        "\\textbf{Metric} & \\textbf{Intent-Aware} & \\textbf{Always-Both} & \\textbf{Agent-Disc} \\\\",
        "\\hline",
        "\\multicolumn{4}{l}{\\textit{Latency (s, lower is better)}} \\\\",
        f"p90 & {p90_ia} & {p90_ab} & {p90_ad} \\\\",
        f"p95 & {p95_ia} & {p95_ab} & {p95_ad} \\\\",
        "\\hline",
        "\\multicolumn{4}{l}{\\textit{Hit Rate (\\%, higher is better)}} \\\\",
        f"Hit@3 & {h3_ia} & {h3_ab} & {h3_ad} \\\\",
        f"Hit@5 & {h5_ia} & {h5_ab} & {h5_ad} \\\\",
        "\\hline",
        "\\multicolumn{4}{l}{\\textit{Quality (0-1, higher is better)}} \\\\",
        f"Context Rel. & {rel_ia} & {rel_ab} & {rel_ad} \\\\",
        f"Response Grd. & {grd_ia} & {grd_ab} & {grd_ad} \\\\",
        "\\hline",
        "\\end{tabular}",
        "\\caption{System performance comparison across \\querycountIntentaware{} validation queries. Bold values indicate best performance. Significance markers: $^*$ p$<$0.05, $^{{**}}$ p$<$0.01 (t-test comparing intent-aware to each baseline). Hit@5 uses a 0.5 similarity threshold filter.}",
        "\\label{tab:results}",
        "\\end{table}",
    ]
    
    with open(TABLE_OUTPUT_TEX, 'w') as f:
        f.write("\n".join(table_lines))
    
    print(f"✓ Generated {TABLE_OUTPUT_TEX} with auto-bolded best values")


def generate_metrics_tex():
    """Generate LaTeX commands from metrics JSON."""
    with open(METRICS_JSON) as f:
        metrics = json.load(f)
    
    lines = [
        "% Auto-generated metrics from metrics_summary.json",
        "% DO NOT EDIT MANUALLY - regenerate with: python generate_metrics_tex.py",
        ""
    ]
    
    # Query counts
    lines.append("% Query counts")
    if "query_counts" in metrics:
        for system in ["intent_aware", "always_both", "agent_discretion"]:
            if system in metrics["query_counts"]:
                count = metrics["query_counts"][system]
                cmd_name = f"querycount{system.replace('_', '').capitalize()}"
                lines.append(f"\\newcommand{{\\{cmd_name}}}{{{count}}}")
    lines.append("")
    
    # Latency metrics (convert ms to seconds)
    lines.append("% Latency metrics (in seconds)")
    percentile_map = {"p90": "Ninety", "p95": "NinetyFive"}
    for percentile in ["p90", "p95"]:
        for system in ["intent_aware", "always_both", "agent_discretion"]:
            key = f"{percentile}_ms"
            if key in metrics["latency"] and system in metrics["latency"][key]:
                value = metrics["latency"][key][system]
                # Use word names to avoid LaTeX parsing issues with numbers
                cmd_name = f"latency{percentile_map[percentile]}{system.replace('_', '')}"
                lines.append(f"\\newcommand{{\\{cmd_name}}}{{{format_latency_ms(value)}}}")
    lines.append("")
    
    # Retrieval hit rates (as percentages)
    lines.append("% Retrieval hit rates (as percentages)")
    k_map = {3: "Three", 5: "Five", 10: "Ten"}
    for k in [3, 5, 10]:
        for system in ["intent_aware", "always_both", "agent_discretion"]:
            key = f"retrieval_hit_rate@{k}"
            if key in metrics["retrieval_hit_rate"] and system in metrics["retrieval_hit_rate"][key]:
                value = metrics["retrieval_hit_rate"][key][system]
                # Use word names to avoid LaTeX parsing issues with numbers
                cmd_name = f"hitrate{k_map[k]}{system.replace('_', '')}"
                lines.append(f"\\newcommand{{\\{cmd_name}}}{{{format_percentage(value)}}}")
    lines.append("")
    
    # Response quality metrics
    lines.append("% Response quality metrics (RAGAS Nvidia metrics)")
    for metric in ["context_relevance", "response_groundedness"]:
        if metric in metrics["response_quality"]:
            for system in ["intent_aware", "always_both", "agent_discretion"]:
                if system in metrics["response_quality"][metric]:
                    value = metrics["response_quality"][metric][system]
                    # Replace underscores in metric name and system name
                    cmd_name = f"{metric.replace('_', '')}{system.replace('_', '')}"
                    lines.append(f"\\newcommand{{\\{cmd_name}}}{{{format_decimal(value)}}}")
    lines.append("")
    
    # Intent classification metrics
    lines.append("% Intent classification metrics")
    metric_map = {
        "macro avg_precision": "Precision",
        "macro avg_recall": "Recall", 
        "macro avg_f1-score": "FOneScore"  # Use "One" instead of "1" to avoid LaTeX parameter parsing
    }
    for metric_name, clean_suffix in metric_map.items():
        if metric_name in metrics["intent_metrics"]:
            value = metrics["intent_metrics"][metric_name].get("intent_aware")
            if value is not None:
                cmd_name = f"intentMacro{clean_suffix}"
                lines.append(f"\\newcommand{{\\{cmd_name}}}{{{format_decimal(value)}}}")
    lines.append("")
    
    # Write output
    with open(OUTPUT_TEX, "w") as f:
        f.write("\n".join(lines))
    
    cmd_count = len([l for l in lines if '\\newcommand' in l])
    print(f"✓ Generated {OUTPUT_TEX} with {cmd_count} metric commands")
    
    # Also generate the comparison table
    generate_comparison_table(metrics)


if __name__ == "__main__":
    generate_metrics_tex()
