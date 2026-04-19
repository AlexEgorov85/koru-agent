#!/usr/bin/env python3
"""
Скрипт для конвертации папки логов Agent v5 в один структурированный текстовый файл.
Сохраняет ВСЕ данные без удалений и обрезаний.
Использование: python convert_logs.py <папка_логов> <выходной_файл>
"""
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import re


LOG_LINE_PATTERN = re.compile(
    r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})\s*\|\s*(\w+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(.*)"
)


class LogParser:
    def __init__(self, log_dir: Path):
        self.log_dir = log_dir
        self.raw_lines: List[str] = []
        self.events: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.tool_calls: List[Dict[str, Any]] = []

    def parse_file(self, filename: str) -> None:
        """Парсит один файл логов, сохраняя ВСЕ строки."""
        filepath = self.log_dir / filename
        if not filepath.exists():
            return

        content = filepath.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        for line in lines:
            line = line.rstrip()
            self.raw_lines.append(line)

            if not line.strip():
                continue

            event = self._parse_line(line, filename)
            if event:
                self.events.append(event)

    def _parse_line(self, line: str, source_file: str) -> Optional[Dict[str, Any]]:
        """Парсит одну строку лога."""
        match = LOG_LINE_PATTERN.match(line)
        if not match:
            return None

        timestamp, level, event_type, logger, message = match.groups()

        event = {
            "timestamp": timestamp,
            "level": level,
            "event_type": event_type,
            "logger": logger,
            "message": message,
            "source": source_file,
        }

        if level in ("ERROR", "CRITICAL"):
            event["is_error"] = True
            self.errors.append(event)
        if event_type == "TOOL_CALL":
            event["is_tool_call"] = True
            self.tool_calls.append(event)

        return event

    def parse_all(self) -> None:
        """Парсит все файлы в папке."""
        log_files = [
            "infra_context.log",
            "app_context.log",
            "llm_calls.log",
        ]

        for fname in log_files:
            self.parse_file(fname)

        self.events.sort(key=lambda x: x["timestamp"])

    def build_report(self) -> str:
        """Создаёт структурированный отчёт."""
        lines = []

        lines.append("=" * 80)
        lines.append("AGENT V5 SESSION LOG REPORT")
        lines.append(f"Log folder: {self.log_dir.name}")
        if self.events:
            lines.append(f"Session start: {self.events[0]['timestamp']}")
            lines.append(f"Session end: {self.events[-1]['timestamp']}")
        lines.append("=" * 80)

        if self.events:
            lines.append("")
            lines.append(f"[STATS] Parsed events: {len(self.events)}")
            lines.append(f"[STATS] Total raw lines: {len(self.raw_lines)}")
            lines.append(f"[STATS] Errors: {len(self.errors)}")
            lines.append(f"[STATS] Tool calls: {len(self.tool_calls)}")

        lines.append("")
        lines.append("=" * 80)
        lines.append("SECTION 1: RAW LOG LINES (ALL LINES PRESERVED)")
        lines.append("=" * 80)
        lines.append("")
        for line in self.raw_lines:
            lines.append(line)

        lines.append("")
        lines.append("=" * 80)
        lines.append("SECTION 2: PARSED EVENTS (STRUCTURED)")
        lines.append("=" * 80)
        lines.append("")

        for event in self.events:
            level_indicator = event["level"]

            source_file = event["source"]

            lines.append(f"[{event['timestamp']}] {level_indicator} | {event['event_type']} | {source_file} | {event['logger']}")
            lines.append(f"  MESSAGE: {event['message']}")

            if event.get("is_error"):
                lines.append(f"  *** ERROR DETECTED ***")

            if event.get("is_tool_call"):
                lines.append(f"  *** TOOL CALL ***")

            lines.append("")

        if self.errors:
            lines.append("")
            lines.append("=" * 80)
            lines.append("SECTION 3: ERRORS INDEX")
            lines.append("=" * 80)
            lines.append("")
            for i, err in enumerate(self.errors, 1):
                lines.append(f"{i}. [{err['timestamp']}] {err['logger']}")
                lines.append(f"   {err['message']}")
                lines.append("")

        if self.tool_calls:
            lines.append("")
            lines.append("=" * 80)
            lines.append("SECTION 4: TOOL CALLS INDEX")
            lines.append("=" * 80)
            lines.append("")
            for i, tc in enumerate(self.tool_calls, 1):
                lines.append(f"{i}. [{tc['timestamp']}] {tc['logger']}")
                lines.append(f"   {tc['message']}")
                lines.append("")

        return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <log_folder> [output_file]")
        sys.exit(1)

    log_dir = Path(sys.argv[1])
    if not log_dir.exists():
        print(f"Error: folder {log_dir} not found")
        sys.exit(1)

    output_file = sys.argv[2] if len(sys.argv) > 2 else log_dir.parent / f"{log_dir.name}_full_report.txt"

    parser = LogParser(log_dir)
    parser.parse_all()
    report = parser.build_report()

    Path(output_file).write_text(report, encoding="utf-8")
    print(f"[OK] Report saved to: {output_file}")
    print(f"    Raw lines: {len(parser.raw_lines)}, Events: {len(parser.events)}, Errors: {len(parser.errors)}, Tools: {len(parser.tool_calls)}")


if __name__ == "__main__":
    main()