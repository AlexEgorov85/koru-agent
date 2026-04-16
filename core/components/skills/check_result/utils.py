import re
from typing import Dict, List, Any, Optional


class ScriptsContextBuilder:
    """Формирует LLM-оптимизированное описание скриптов с метаданными таблиц."""

    MAX_COLUMNS_PER_TABLE = 6
    MAX_TABLES_PER_SCRIPT = 2

    def __init__(self, scripts_registry: Dict[str, Any], tables_config: Optional[List[Dict]] = None):
        self.registry = scripts_registry
        self.tables_meta = tables_config or []
        self._table_index: Dict[str, List[Dict]] = {}
        for t in self.tables_meta:
            key = f"{t.get('schema', 'public')}.{t.get('table', '')}"
            self._table_index[key] = t.get('columns', [])

    def build(self, limit_scripts: int = 10) -> str:
        """Собирает текст для промпта."""
        lines = ["### 📜 ДОСТУПНЫЕ СКРИПТЫ (`check_result.execute_script`)"]

        scripts = list(self.registry.items())[:limit_scripts]

        for name, meta in scripts:
            lines.append(f"\n**`{name}`**")
            lines.append(f"📖 {meta.get('description', '')}")

            params = meta.get('parameters', {})
            if params:
                lines.append("⚙️ Параметры:")
                for pname, pmeta in params.items():
                    if pname == 'max_rows':
                        continue
                    if not isinstance(pmeta, dict):
                        continue
                    p_type = pmeta.get('type', 'str')
                    p_req = "обяз." if pmeta.get('required') else "опц."
                    p_desc = pmeta.get('description', '')

                    if 'validation' in pmeta and pmeta['validation']:
                        validation = pmeta['validation']
                        if validation.get('type') == 'enum':
                            vals = validation.get('allowed_values', [])
                            if vals:
                                p_desc += f" Варианты: {', '.join(vals)}"

                    lines.append(f"  • `{pname}` ({p_type}, {p_req}): {p_desc}")

            sql = meta.get('sql_template', '') or meta.get('sql', '')
            tables_in_sql = re.findall(
                r'(?:FROM|JOIN)\s+([a-zA-Z_]\w*(?:\.[a-zA-Z_]\w*)?)',
                sql,
                re.IGNORECASE
            )

            if tables_in_sql:
                tables_str = ", ".join(set(t.split('.')[-1] for t in tables_in_sql[:self.MAX_TABLES_PER_SCRIPT]))
                lines.append(f"📊 Источники: {tables_str}")

                cols = set()
                for t_name in tables_in_sql[:self.MAX_TABLES_PER_SCRIPT]:
                    if t_name in self._table_index:
                        table_cols = self._table_index[t_name]
                        for col in table_cols[:self.MAX_COLUMNS_PER_TABLE]:
                            col_name = col.get('column_name') or col.get('name', '')
                            if col_name:
                                cols.add(f"`{col_name}`")

                if cols:
                    lines.append(f"🔍 Доступные поля: {', '.join(sorted(cols))}")

        return "\n".join(lines)