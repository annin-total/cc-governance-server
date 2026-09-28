"""ビューのテストが使う `table_body`・`rows_in_table` の検査。属性の付いた行を 0 件と数えると、0 行を期待する検査が素通りする。"""

import pytest
from conftest import rows_in_table, table_body

_HTML = (
    '<table data-testid="t1"><thead><tr><th>h</th></tr></thead>'
    '<tbody><tr data-tags="a b" data-q="x"><td>1</td></tr><tr><td>2</td></tr></tbody></table>'
    '<table data-key="k2" data-testid="t2"><tr><th>h</th></tr><tr><td>3</td></tr></table>'
    '<table data-testid="t2-other"><tr><th>h</th></tr></table>'
)


def test_rows_with_attributes_are_counted():
    assert len(rows_in_table(_HTML, "t1")) == 2


def test_attribute_order_and_key_do_not_matter():
    assert len(rows_in_table(_HTML, "t2", key="k2")) == 1
    assert "<td>3</td>" in table_body(_HTML, "t2")


def test_testid_does_not_match_by_prefix():
    assert rows_in_table(_HTML, "t2-other") == []
    with pytest.raises(AssertionError):
        table_body(_HTML, "t")
