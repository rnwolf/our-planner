"""Tests for the Network Graph report (Stage 18): any set of tasks rendered
through ccpm_scheduler.render_network_html as the interactive
project-network HTML — a pure view of the tasks as they sit on the timeline.
"""

import json
import re
from unittest.mock import MagicMock

from src.model.task_resource_model import TaskResourceModel
from src.operations.report_operations import ReportOperations


def make_setup():
    model = TaskResourceModel()
    controller = MagicMock()
    controller.model = model
    return model, ReportOperations(controller, model)


def embedded_graph(html):
    m = re.search(r"const GRAPH = (\{.*?\});\n", html, re.S)
    assert m, "embedded GRAPH payload not found"
    return json.loads(m.group(1).replace("<\\/", "</"))


def render(ops, tasks, title="test"):
    from ccpm_scheduler import Schedule, render_network_html
    rows = ops.build_network_report_rows(tasks)
    return embedded_graph(render_network_html(Schedule(rows=rows), title=title))


class TestBuildNetworkReportRows:
    def test_field_mapping(self):
        model, ops = make_setup()
        a = model.add_task(row=1, col=5, duration=4, description='Spec',
                           resources={1: 1.0}, url='https://x/spec')
        b = model.add_task(row=2, col=9, duration=6, description='Build',
                           resources={1: 1.0, 2: 1.0},
                           predecessors=[{'id': a['task_id'],
                                          'type': 'SS', 'lag': 2}])
        rows = ops.build_network_report_rows([a, b])
        assert [r.id for r in rows] == [str(a['task_id']), str(b['task_id'])]
        first, second = rows
        assert (first.start, first.finish, first.duration) == (5, 9, 4)
        assert first.resource_ids == 'Resource A'
        assert first.url == 'https://x/spec'
        assert second.resource_ids == 'Resource A;Resource B'
        assert second.predecessor_ids == f"{a['task_id']}:SS+2"

    def test_realistic_only_when_it_differs(self):
        model, ops = make_setup()
        cut = model.add_task(row=1, col=0, duration=5, description='Cut',
                             resources={1: 1.0})
        cut['realistic_duration'] = 10          # a real cut happened
        raw = model.add_task(row=2, col=0, duration=8, description='Raw',
                             resources={1: 1.0})  # realistic defaults to 8
        rows = {r.name: r for r in ops.build_network_report_rows([cut, raw])}
        assert rows['Cut'].realistic_duration == 10
        assert rows['Raw'].realistic_duration is None

    def test_chain_mapping(self):
        model, ops = make_setup()
        critical = model.get_critical_chain()
        feeding = model.get_chain_by_name('Feeding-01')
        custom = model.add_chain('Integration stream', '#123456')
        t1 = model.add_task(row=1, col=0, duration=2, description='On CC',
                            resources={1: 1.0}, chain_id=critical['id'])
        t2 = model.add_task(row=2, col=0, duration=2, description='On feed',
                            resources={1: 1.0}, chain_id=feeding['id'])
        t3 = model.add_task(row=3, col=0, duration=2, description='On custom',
                            resources={1: 1.0}, chain_id=custom['id'])
        t4 = model.add_task(row=4, col=0, duration=2, description='Loose',
                            resources={1: 1.0})
        rows = {r.name: r for r in
                ops.build_network_report_rows([t1, t2, t3, t4])}
        assert rows['On CC'].chain == 'critical'
        assert rows['On feed'].chain == 'Feeding-01'
        assert rows['On custom'].chain == 'Integration stream'
        assert rows['Loose'].chain == 'none'

    def test_buffer_types_pass_through(self):
        model, ops = make_setup()
        t = model.add_task(row=1, col=0, duration=3, description='PB',
                           resources={})
        model.set_task_type(t['task_id'], 'project_buffer')
        rows = ops.build_network_report_rows([t])
        assert rows[0].type == 'project_buffer'


class TestRenderedGraph:
    def test_resource_filter_uses_names(self):
        model, ops = make_setup()
        a = model.add_task(row=1, col=0, duration=2, description='A',
                           resources={1: 1.0, 3: 1.0})
        graph = render(ops, [a])
        assert graph['resources'] == ['Resource A', 'Resource C']
        assert graph['nodes'][0]['data']['resource_list'] == \
            ['Resource A', 'Resource C']

    def test_custom_chain_in_legend(self):
        model, ops = make_setup()
        custom = model.add_chain('Integration stream', '#123456')
        t = model.add_task(row=1, col=0, duration=2, description='A',
                           resources={1: 1.0}, chain_id=custom['id'])
        graph = render(ops, [t])
        assert 'Integration stream' in {l['label'] for l in graph['legend']}

    def test_links_outside_selection_are_dropped(self):
        model, ops = make_setup()
        a = model.add_task(row=1, col=0, duration=2, description='A',
                           resources={1: 1.0})
        b = model.add_task(row=2, col=2, duration=2, description='B',
                           resources={1: 1.0},
                           predecessors=[{'id': a['task_id'],
                                          'type': 'FS', 'lag': 0}])
        c = model.add_task(row=3, col=4, duration=2, description='C',
                           resources={1: 1.0},
                           predecessors=[{'id': b['task_id'],
                                          'type': 'FS', 'lag': 0}])
        # select only B and C: the A->B edge has no source node and vanishes
        graph = render(ops, [b, c])
        assert len(graph['nodes']) == 2
        assert len(graph['edges']) == 1
        assert graph['edges'][0]['from'] == str(b['task_id'])
