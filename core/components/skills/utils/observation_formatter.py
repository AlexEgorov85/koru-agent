"""
Форматирование observation для безопасного использования в промптах.
"""
import json
import statistics
from typing import Any, Dict


class ObservationFormatter:
    """Форматтер для формирования безопасного observation."""
    
    @classmethod
    def build(
        cls,
        raw_data: Any,
        save_type: str,
        step_id: str,
        answer: str,
        confidence: float
    ) -> Dict[str, Any]:
        """
        Формирует observation по типу сохранения.
        
        ARGS:
        - raw_data: исходные данные
        - save_type: 'raw_data' или 'summary'
        - step_id: ID шага
        - answer: ответ от анализа
        - confidence: уверенность (0-1)
        
        RETURNS:
        - Dict с observation для сохранения в data_context
        """
        base = {
            "step_id": step_id,
            "type": save_type,
            "answer": answer,
            "confidence": confidence,
            "metadata": {"source": "data_analysis.analyze_step_data"}
        }
        
        if save_type == "raw_data":
            base["data"] = raw_data
            base["access_hint"] = "observation.data содержит исходные данные. Используйте напрямую."
            if isinstance(raw_data, list):
                base["metadata"]["row_count"] = len(raw_data)
            elif isinstance(raw_data, str):
                base["metadata"]["char_count"] = len(raw_data)
        else:
            base["profile"] = cls._extract_profile(raw_data)
            base["sample"] = cls._safe_sample(raw_data, 3)
            base["access_hint"] = "Данные агрегированы. Используйте stats и sample. Для полного доступа вызовите навык заново."
            base["note"] = "Объём данных превышает порог безопасной передачи в контекст LLM"
        
        return base
    
    @classmethod
    def _extract_profile(cls, data: Any) -> Dict[str, Any]:
        """Извлекает профиль данных."""
        if isinstance(data, list) and data and isinstance(data[0], dict):
            cols = list(data[0].keys())[:15]
            numeric = [c for c in cols if isinstance(data[0][c], (int, float))]
            stats = {}
            for c in numeric:
                vals = [r[c] for r in data if isinstance(r.get(c), (int, float))]
                if vals:
                    stats[c] = {
                        "count": len(vals),
                        "mean": round(statistics.mean(vals), 2) if vals else None,
                        "min": min(vals) if vals else None,
                        "max": max(vals) if vals else None
                    }
            return {
                "type": "tabular",
                "row_count": len(data),
                "columns": cols,
                "numeric_stats": stats
            }
        if isinstance(data, str):
            return {
                "type": "text",
                "char_count": len(data),
                "line_count": data.count('\n') + 1
            }
        if isinstance(data, dict):
            return {
                "type": "dict",
                "key_count": len(data),
                "keys": list(data.keys())[:10]
            }
        return {"type": type(data).__name__}
    
    @classmethod
    def _safe_sample(cls, data: Any, n: int) -> Any:
        """Безопасная выборка данных."""
        if isinstance(data, list):
            return data[:n]
        if isinstance(data, str):
            return data[:300]
        if isinstance(data, dict):
            return {k: v for i, (k, v) in enumerate(data.items()) if i < n}
        return str(data)[:300]
    
    @classmethod
    def render_for_prompt(cls, obs: Dict[str, Any]) -> str:
        """
        Рендерит observation для промпта LLM.
        
        ARGS:
        - obs: observation из data_context
        
        RETURNS:
        - Отформатированная строка для промпта
        """
        obs_type = obs.get("type", "unknown")
        step_id = obs.get("step_id", "?")
        answer = obs.get("answer", "н/д")
        confidence = obs.get("confidence", 0.0)
        
        lines = []
        
        if obs_type == "raw_data":
            data = obs.get("data")
            if data is not None:
                preview = cls._safe_sample(data, 3)
                preview_str = json.dumps(preview, ensure_ascii=False)
                if len(preview_str) > 350:
                    preview_str = preview_str[:350] + "..."
                lines.append(f"📦 НАБЛЮДЕНИЕ (шаг {step_id}, тип: raw)")
                lines.append(f"📊 Данные: {preview_str}")
                lines.append(f"💡 Доступ: observation['data'] (полный набор)")
        elif obs_type == "summary":
            lines.append(f"📦 НАБЛЮДЕНИЕ (шаг {step_id}, тип: summary)")
            lines.append(f"• Ответ: {answer}")
            lines.append(f"• Уверенность: {confidence:.0%}")
            
            profile = obs.get("profile")
            if profile:
                ptype = profile.get("type", "?")
                if ptype == "tabular":
                    rows = profile.get("row_count", "?")
                    cols = profile.get("columns", [])
                    lines.append(f"• Профиль: таблица, {rows} строк, колонки: {cols[:5]}...")
                elif ptype == "text":
                    chars = profile.get("char_count", "?")
                    lines.append(f"• Профиль: текст, {chars} символов")
                else:
                    lines.append(f"• Профиль: {ptype}")
            
            sample = obs.get("sample")
            if sample:
                sample_str = json.dumps(cls._safe_sample(sample, 3), ensure_ascii=False)
                if len(sample_str) > 250:
                    sample_str = sample_str[:250] + "..."
                lines.append(f"• Пример: {sample_str}")
            
            access_hint = obs.get("access_hint", "")
            if access_hint:
                lines.append(f"• Доступ: {access_hint}")
        else:
            lines.append(f"📦 Наблюдение (шаг {step_id}, тип: {obs_type})")
            lines.append(f"• Ответ: {answer}")
        
        return "\n".join(lines)