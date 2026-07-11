"""Regression coverage for fever_chart_display_point - the progress_pct/
consumption_pct math that used to be hand-copied identically into three
places (on-screen chart, PNG export, CSV export) with no shared test.
"""
from src.model.task_resource_model import fever_chart_display_point


class TestFeverChartDisplayPoint:
    def test_normal_case(self):
        entry = {'cpsl': 20, 'ppf': 10, 'forecast_lateness': 3}
        progress_pct, consumption_pct = fever_chart_display_point(entry, 5)
        assert progress_pct == 50.0
        assert consumption_pct == 60.0

    def test_zero_cpsl_gives_zero_progress(self):
        entry = {'cpsl': 0, 'ppf': 0, 'forecast_lateness': 2}
        progress_pct, _ = fever_chart_display_point(entry, 5)
        assert progress_pct == 0.0

    def test_zero_baseline_duration_gives_zero_consumption(self):
        entry = {'cpsl': 10, 'ppf': 5, 'forecast_lateness': 3}
        _, consumption_pct = fever_chart_display_point(entry, 0)
        assert consumption_pct == 0.0

    def test_consumption_can_exceed_100(self):
        entry = {'cpsl': 10, 'ppf': 5, 'forecast_lateness': 8}
        _, consumption_pct = fever_chart_display_point(entry, 5)
        assert consumption_pct == 160.0

    def test_negative_forecast_lateness_gives_negative_consumption(self):
        # Chain forecast to finish ahead of schedule - not clamped here,
        # display-layer flooring at 0 is the caller's job.
        entry = {'cpsl': 10, 'ppf': 5, 'forecast_lateness': -2}
        _, consumption_pct = fever_chart_display_point(entry, 5)
        assert consumption_pct == -40.0
