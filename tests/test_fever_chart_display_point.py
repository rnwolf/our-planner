"""Regression coverage for fever_chart_display_point - the progress_pct/
consumption_pct math that used to be hand-copied identically into three
places (on-screen chart, PNG export, CSV export) with no shared test.
"""

from src.model.task_resource_model import (
    declutter_label_positions,
    fever_chart_display_point,
    fever_chart_title_lines,
    sorted_fever_chart_history,
)


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


class TestFeverChartTitleLines:
    def test_project_name_and_buffer_title(self):
        buffer_task = {'task_id': 5, 'description': 'Project buffer'}
        project = {'name': 'Sample Project'}
        project_name, buffer_title = fever_chart_title_lines(buffer_task, project)
        assert project_name == 'Sample Project'
        assert buffer_title == '5 - Project buffer'


class TestSortedFeverChartHistory:
    def test_sorts_out_of_order_entries(self):
        buffer_task = {
            'fever_chart_history': [
                {'date': '2026-06-23', 'cpsl': 1, 'ppf': 1, 'forecast_lateness': 1},
                {'date': '2026-06-18', 'cpsl': 2, 'ppf': 2, 'forecast_lateness': 2},
                {'date': '2026-06-08', 'cpsl': 3, 'ppf': 3, 'forecast_lateness': 3},
            ]
        }
        result = sorted_fever_chart_history(buffer_task)
        assert [e['date'] for e in result] == [
            '2026-06-08',
            '2026-06-18',
            '2026-06-23',
        ]

    def test_collapses_duplicate_dates_to_the_last_recorded(self):
        buffer_task = {
            'fever_chart_history': [
                {'date': '2026-06-18', 'cpsl': 2, 'ppf': 2, 'forecast_lateness': 2},
                {'date': '2026-06-18', 'cpsl': 3, 'ppf': 3, 'forecast_lateness': 3},
            ]
        }
        result = sorted_fever_chart_history(buffer_task)
        assert len(result) == 1
        assert result[0]['cpsl'] == 3

    def test_empty_history(self):
        assert sorted_fever_chart_history({'fever_chart_history': []}) == []
        assert sorted_fever_chart_history({}) == []


class TestDeclutterLabelPositions:
    def test_far_apart_anchors_stay_put(self):
        anchors = [(0.0, 0.0), (200.0, 0.0)]
        result = declutter_label_positions(anchors, box_w=32, box_h=11)
        assert result == anchors

    def test_close_anchors_are_separated(self):
        anchors = [(0.0, 0.0), (5.0, 0.0)]
        result = declutter_label_positions(anchors, box_w=32, box_h=11)
        assert result[0] == (0.0, 0.0)
        assert result[1] != (5.0, 0.0)
        assert abs(result[1][1] - result[0][1]) >= 11
