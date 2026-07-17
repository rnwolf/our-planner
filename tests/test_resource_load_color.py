"""Resource-grid cell coloring: a load that equals capacity is full, not
overloaded (it used to fall into the '>= 100%' light-red branch), and the
comparison tolerates the float drift that comes from summing per-task
allocations one += at a time in calculate_resource_loading.
"""

from src.utils.colors import get_resource_load_color

WHITE = 'white'
YELLOW = '#ffffcc'  # high usage, 80% up to and including capacity
RED = '#ffcccc'  # genuinely over capacity


def test_no_usage_is_white():
    assert get_resource_load_color(0.0, 1.0) == WHITE


def test_below_80_pct_is_bluish():
    color = get_resource_load_color(0.5, 1.0)
    assert color not in (WHITE, YELLOW, RED)
    assert color.startswith('#') and color.endswith('ff')


def test_high_usage_is_yellow():
    assert get_resource_load_color(0.9, 1.0) == YELLOW


def test_load_equal_to_capacity_is_not_overloaded():
    # The reported bug: a '1/1.0' cell went light red
    assert get_resource_load_color(1.0, 1.0) == YELLOW
    assert get_resource_load_color(0.5, 0.5) == YELLOW


def test_accumulated_float_load_at_capacity_is_not_overloaded():
    # Ten 0.1 allocations summed the way the model sums them
    load = 0.0
    for _ in range(10):
        load += 0.1
    assert load != 1.0  # the drift this test is about
    assert get_resource_load_color(load, 1.0) == YELLOW

    # An ordering that drifts to the high side of exact
    load = 0.1 + 0.7 + 0.2 + 1.0 - 1.0
    assert get_resource_load_color(load, 1.0) == YELLOW


def test_real_overload_is_still_red():
    assert get_resource_load_color(1.05, 1.0) == RED
    assert get_resource_load_color(2.0, 1.0) == RED


def test_load_with_zero_capacity_is_red():
    assert get_resource_load_color(0.5, 0.0) == RED
