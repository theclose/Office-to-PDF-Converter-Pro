#!/usr/bin/env python
"""
Benchmark Report Generator
===========================
Analyzes benchmark results and generates performance reports.

Usage:
    python scripts/benchmark_report.py
    python scripts/benchmark_report.py --compare baseline current
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List
import statistics


class BenchmarkAnalyzer:
    """Analyzes benchmark results."""
    
    def __init__(self, benchmarks_dir: str = ".benchmarks"):
        self.benchmarks_dir = Path(benchmarks_dir)
        
    def load_latest_results(self) -> Dict:
        """Load most recent benchmark results."""
        result_files = list(self.benchmarks_dir.glob("**/*.json"))
        
        if not result_files:
            return {}
            
        # Get most recent
        latest = max(result_files, key=lambda p: p.stat().st_mtime)
        
        with open(latest, 'r') as f:
            return json.load(f)
            
    def analyze_results(self, results: Dict) -> Dict:
        """Analyze benchmark data."""
        analysis = {
            'total_benchmarks': len(results.get('benchmarks', [])),
            'fastest': None,
            'slowest': None,
            'by_category': {},
            'regression_warnings': []
        }
        
        benchmarks = results.get('benchmarks', [])
        
        if not benchmarks:
            return analysis
            
        # Find fastest/slowest
        benchmarks_sorted = sorted(benchmarks, key=lambda b: b['stats']['mean'])
        analysis['fastest'] = benchmarks_sorted[0]
        analysis['slowest'] = benchmarks_sorted[-1]
        
        # Group by category
        for bench in benchmarks:
            group = bench.get('group', 'default')
            if group not in analysis['by_category']:
                analysis['by_category'][group] = []
            analysis['by_category'][group].append(bench)
            
        # Check for slow tests
        mean_times = [b['stats']['mean'] for b in benchmarks]
        avg_mean = statistics.mean(mean_times) if mean_times else 0
        
        for bench in benchmarks:
            if bench['stats']['mean'] > avg_mean * 3:  # 3x slower than average
                analysis['regression_warnings'].append({
                    'name': bench['name'],
                    'mean': bench['stats']['mean'],
                    'reason': 'Much slower than average'
                })
                
        return analysis
        
    def generate_report(self, analysis: Dict) -> str:
        """Generate markdown report."""
        lines = [
            "# 📊 Performance Benchmark Report",
            f"\n**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"\n**Total Benchmarks**: {analysis['total_benchmarks']}",
            "\n---\n"
        ]
        
        # Fastest/Slowest
        if analysis['fastest']:
            fast = analysis['fastest']
            lines.append(f"## ⚡ Fastest: `{fast['name']}`")
            lines.append(f"- Mean: {fast['stats']['mean']*1000:.3f}ms")
            lines.append(f"- Median: {fast['stats']['median']*1000:.3f}ms")
            lines.append("")
            
        if analysis['slowest']:
            slow = analysis['slowest']
            lines.append(f"## 🐌 Slowest: `{slow['name']}`")
            lines.append(f"- Mean: {slow['stats']['mean']*1000:.3f}ms")
            lines.append(f"- Median: {slow['stats']['median']*1000:.3f}ms")
            lines.append("")
            
        # By category
        if analysis['by_category']:
            lines.append("## 📋 By Category\n")
            
            for category, benchmarks in analysis['by_category'].items():
                lines.append(f"### {category}")
                lines.append("\n| Benchmark | Mean (ms) | Median (ms) | Ops/sec |")
                lines.append("|:---|---:|---:|---:|")
                
                for bench in sorted(benchmarks, key=lambda b: b['stats']['mean']):
                    name = bench['name'].split('::')[-1]
                    mean = bench['stats']['mean'] * 1000
                    median = bench['stats']['median'] * 1000
                    ops = 1 / bench['stats']['mean'] if bench['stats']['mean'] > 0 else 0
                    
                    lines.append(f"| {name} | {mean:.3f} | {median:.3f} | {ops:.0f} |")
                    
                lines.append("")
                
        # Warnings
        if analysis['regression_warnings']:
            lines.append("## ⚠️ Performance Warnings\n")
            
            for warning in analysis['regression_warnings']:
                lines.append(f"- **{warning['name']}**: {warning['mean']*1000:.3f}ms - {warning['reason']}")
                
        return '\n'.join(lines)
        
    def compare_results(self, baseline_file: str, current_file: str) -> str:
        """Compare two benchmark results."""
        with open(baseline_file, 'r') as f:
            baseline = json.load(f)
        with open(current_file, 'r') as f:
            current = json.load(f)
            
        lines = [
            "# 📊 Benchmark Comparison",
            f"\n**Baseline**: {baseline_file}",
            f"**Current**: {current_file}",
            "\n---\n"
        ]
        
        # Build lookup
        baseline_map = {b['name']: b for b in baseline.get('benchmarks', [])}
        current_map = {b['name']: b for b in current.get('benchmarks', [])}
        
        # Compare
        lines.append("## Performance Changes\n")
        lines.append("| Benchmark | Baseline (ms) | Current (ms) | Change |")
        lines.append("|:---|---:|---:|:---:|")
        
        for name in sorted(current_map.keys()):
            if name in baseline_map:
                base_mean = baseline_map[name]['stats']['mean'] * 1000
                curr_mean = current_map[name]['stats']['mean'] * 1000
                
                if base_mean > 0:
                    pct_change = ((curr_mean - base_mean) / base_mean) * 100
                    
                    if pct_change > 10:
                        status = f"🔴 +{pct_change:.1f}%"
                    elif pct_change < -10:
                        status = f"🟢 {pct_change:.1f}%"
                    else:
                        status = f"⚪ {pct_change:+.1f}%"
                        
                    short_name = name.split('::')[-1]
                    lines.append(f"| {short_name} | {base_mean:.3f} | {curr_mean:.3f} | {status} |")
                    
        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="Benchmark Report Generator")
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "CURRENT"),
                       help="Compare two benchmark files")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    
    args = parser.parse_args()
    
    analyzer = BenchmarkAnalyzer()
    
    if args.compare:
        report = analyzer.compare_results(args.compare[0], args.compare[1])
    else:
        results = analyzer.load_latest_results()
        if not results:
            print("No benchmark results found in .benchmarks/")
            return
            
        analysis = analyzer.analyze_results(results)
        report = analyzer.generate_report(analysis)
        
    if args.output:
        with open(args.output, 'w') as f:
            f.write(report)
        print(f"Report written to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
