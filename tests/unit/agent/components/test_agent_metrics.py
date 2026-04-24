"""
Tests for refactored AgentMetrics component.
Validates observer metrics tracking and correct calculation.
"""
import pytest
from core.agent.components.agent_metrics import AgentMetrics


class TestAgentMetricsOptimization:
    """Tests for AgentMetrics observer tracking."""

    def test_record_llm_call_increments_counter(self):
        """Test that LLM calls are counted correctly."""
        metrics = AgentMetrics()
        metrics.record_observer_call(used_llm=True)
        
        assert metrics.observer_llm_calls == 1
        assert metrics.observer_skips == 0

    def test_record_rule_based_call_increments_counter(self):
        """Test that rule-based calls are counted correctly."""
        metrics = AgentMetrics()
        metrics.record_observer_call(used_llm=False)
        
        assert metrics.observer_llm_calls == 0
        assert metrics.observer_skips == 1

    def test_mixed_calls_counting(self):
        """Test counting with mixed LLM and rule-based calls."""
        metrics = AgentMetrics()
        metrics.record_observer_call(used_llm=True)
        metrics.record_observer_call(used_llm=True)
        metrics.record_observer_call(used_llm=False)
        metrics.record_observer_call(used_llm=False)
        metrics.record_observer_call(used_llm=False)
        
        assert metrics.observer_llm_calls == 2
        assert metrics.observer_skips == 3

    def test_observer_skip_rate_calculation(self):
        """Test correct calculation of observer skip rate."""
        metrics = AgentMetrics()
        # 2 LLM calls, 3 rule-based calls => skip_rate = 3/5 = 0.6
        metrics.record_observer_call(used_llm=True)
        metrics.record_observer_call(used_llm=True)
        metrics.record_observer_call(used_llm=False)
        metrics.record_observer_call(used_llm=False)
        metrics.record_observer_call(used_llm=False)
        
        total = metrics.observer_llm_calls + metrics.observer_skips
        skip_rate = metrics.observer_skips / total if total > 0 else 0.0
        assert skip_rate == 0.6

    def test_skip_rate_zero_when_no_calls(self):
        """Test skip rate is 0 when no calls recorded."""
        metrics = AgentMetrics()
        total = metrics.observer_llm_calls + metrics.observer_skips
        skip_rate = metrics.observer_skips / total if total > 0 else 0.0
        assert skip_rate == 0.0

    def test_skip_rate_100_percent_rule_based(self):
        """Test skip rate is 1.0 when all calls are rule-based."""
        metrics = AgentMetrics()
        metrics.record_observer_call(used_llm=False)
        metrics.record_observer_call(used_llm=False)
        
        total = metrics.observer_llm_calls + metrics.observer_skips
        skip_rate = metrics.observer_skips / total if total > 0 else 0.0
        assert skip_rate == 1.0

    def test_to_dict_includes_observer_metrics(self):
        """Test that to_dict() includes observer metrics."""
        metrics = AgentMetrics()
        metrics.record_observer_call(used_llm=True)
        metrics.record_observer_call(used_llm=False)
        
        result = metrics.to_dict()
        
        # Should include essential observer metrics
        assert 'observer_llm_calls' in result
        assert 'observer_skips' in result
        assert result['observer_llm_calls'] == 1
        assert result['observer_skips'] == 1

    def test_to_dict_includes_token_metrics(self):
        """Test that token metrics are included in to_dict()."""
        metrics = AgentMetrics()
        metrics.add_tokens(150)
        
        result = metrics.to_dict()
        
        assert result['total_tokens_used'] == 150

    def test_initial_state(self):
        """Test initial state of metrics."""
        metrics = AgentMetrics()
        
        assert metrics.step_number == 0
        assert metrics.observer_llm_calls == 0
        assert metrics.observer_skips == 0
        assert metrics.total_tokens_used == 0
        assert len(metrics.errors) == 0

    def test_add_multiple_tokens(self):
        """Test adding tokens multiple times."""
        metrics = AgentMetrics()
        metrics.add_tokens(100)
        metrics.add_tokens(50)
        metrics.add_tokens(25)
        
        assert metrics.total_tokens_used == 175
