"""ndjson.parse_line / parse_lines の検査と列変換を確かめる。"""

from ccgov.ingestion.ndjson import parse_line, parse_lines
from ccgov.vendor.contract import EXTRA_COLUMNS, HOOK_FIELDS, POLICY_COLUMNS

_EVENTS_COLUMNS = tuple(EXTRA_COLUMNS) + tuple(
    (name, type_) for name, _, type_ in HOOK_FIELDS
)
_EVENTS_NAMES = [name for name, _ in _EVENTS_COLUMNS]
_POLICY_NAMES = [name for name, _ in POLICY_COLUMNS]


def _events_value(values: tuple, name: str):
    """events 列定義における `name` の値を取り出す。"""
    return values[_EVENTS_NAMES.index(name)]


def _policy_value(values: tuple, name: str):
    """policy_state 列定義における `name` の値を取り出す。"""
    return values[_POLICY_NAMES.index(name)]


def test_event_with_tool_name_is_accepted():
    """通常の event 行を採用し、tool_name と day を正しく持つ。"""
    line = b'{"kind":"event","event_id":"e1","ts":1758400000,"tool_name":"Bash"}'
    result = parse_line(line)
    assert result is not None
    kind, values = result
    assert kind == "event"
    assert _events_value(values, "tool_name") == "Bash"
    assert _events_value(values, "day") == 20352


def test_day_is_recomputed_at_jst_midnight_boundary():
    """JST 当日 0 時ちょうどの ts は当日の day になる。"""
    line = b'{"kind":"event","event_id":"e2","ts":1758380400}'
    kind, values = parse_line(line)
    assert kind == "event"
    assert _events_value(values, "day") == 20352


def test_day_is_recomputed_just_before_jst_midnight():
    """JST 前日 23:59:59 の ts は前日の day になる。"""
    line = b'{"kind":"event","event_id":"e3","ts":1758380399}'
    kind, values = parse_line(line)
    assert kind == "event"
    assert _events_value(values, "day") == 20351


def test_day_field_in_payload_is_ignored_and_recomputed():
    """行が持つ day は無視し、ts から再計算した値を使う。"""
    line = b'{"kind":"event","event_id":"e4","ts":1758400000,"day":1}'
    kind, values = parse_line(line)
    assert kind == "event"
    assert _events_value(values, "day") == 20352


def test_is_interrupt_true_is_coerced_to_one():
    """is_interrupt=true は INTEGER 1 に変換される。"""
    line = b'{"kind":"event","event_id":"e5","ts":1758400000,"is_interrupt":true}'
    kind, values = parse_line(line)
    assert kind == "event"
    assert _events_value(values, "is_interrupt") == 1


def test_is_interrupt_non_numeric_string_becomes_none():
    """is_interrupt="yes" は INTEGER に変換できず None になる。"""
    line = b'{"kind":"event","event_id":"e6","ts":1758400000,"is_interrupt":"yes"}'
    kind, values = parse_line(line)
    assert kind == "event"
    assert _events_value(values, "is_interrupt") is None


def test_prompt_and_tool_response_never_appear_in_any_column():
    """prompt / tool_response はどの列定義にも現れず、行は採用される。"""
    line = (
        b'{"kind":"event","event_id":"e7","ts":1758400000,'
        b'"prompt":"\xe7\xa7\x98\xe5\xaf\x86","tool_response":"x"}'
    )
    result = parse_line(line)
    assert result is not None
    assert "prompt" not in _EVENTS_NAMES
    assert "tool_response" not in _EVENTS_NAMES


def test_missing_optional_hook_fields_become_none():
    """tool_name / skill_name / context_tokens が無ければすべて None になる。"""
    line = b'{"kind":"event","event_id":"e8","ts":1758400000}'
    kind, values = parse_line(line)
    assert kind == "event"
    assert _events_value(values, "tool_name") is None
    assert _events_value(values, "skill_name") is None
    assert _events_value(values, "context_tokens") is None


def test_missing_event_id_is_dropped():
    """event_id が無い行は破棄する。"""
    line = b'{"kind":"event","ts":1758400000}'
    assert parse_line(line) is None


def test_empty_event_id_is_dropped():
    """event_id が空文字の行は破棄する。"""
    line = b'{"kind":"event","event_id":"","ts":1758400000}'
    assert parse_line(line) is None


def test_missing_ts_is_dropped():
    """ts が無い行は破棄する。"""
    line = b'{"kind":"event","event_id":"e11"}'
    assert parse_line(line) is None


def test_null_ts_is_dropped():
    """ts が null の行は破棄する。"""
    line = b'{"kind":"event","event_id":"e12","ts":null}'
    assert parse_line(line) is None


def test_unknown_kind_is_dropped():
    """kind が未知の値の行は破棄する。"""
    line = b'{"kind":"foo","event_id":"e13","ts":1758400000}'
    assert parse_line(line) is None


def test_missing_kind_is_dropped():
    """kind が無い行は破棄する。"""
    line = b'{"event_id":"e14","ts":1758400000}'
    assert parse_line(line) is None


def test_invalid_json_is_dropped():
    """JSON としてパースできない行は破棄する。"""
    line = b'{"kind":"event","event_id":'
    assert parse_line(line) is None


def test_non_dict_json_is_dropped():
    """dict ではない JSON（配列）は破棄する。"""
    line = b"[1,2,3]"
    assert parse_line(line) is None


def test_blank_lines_are_ignored_and_not_counted_as_dropped():
    """空行・空白のみの行は無視し、dropped に数えない。"""
    rows, dropped = parse_lines(b"\n   \n")
    assert rows == []
    assert dropped == 0


def test_policy_row_is_accepted_with_policy_columns():
    """policy 行は policy_state の列定義で採用され、day も再計算される。"""
    line = (
        b'{"kind":"policy","event_id":"p1","ts":1758400000,'
        b'"key_name":"env.CLAUDE_AUTOCOMPACT_PCT_OVERRIDE","value":"60",'
        b'"prev_value":null,"apply_result":"applied"}'
    )
    kind, values = parse_line(line)
    assert kind == "policy"
    assert _policy_value(values, "prev_value") is None
    assert _policy_value(values, "apply_result") == "applied"
    assert _policy_value(values, "day") == 20352


def test_ts_non_numeric_string_is_dropped_but_sibling_row_is_stored():
    """ts が数値化できない文字列の行は破棄し、同じリクエスト内の正常行は保存される。"""
    good = b'{"kind":"event","event_id":"e19a","ts":1758400000}'
    poison = b'{"kind":"event","event_id":"e19b","ts":"abc"}'
    rows, dropped = parse_lines(good + b"\n" + poison)
    assert dropped == 1
    assert len(rows) == 1
    assert rows[0][0] == "event"


def test_ts_array_is_dropped_but_sibling_row_is_stored():
    """ts が配列の行は破棄し、同じリクエスト内の正常行は保存される。"""
    good = b'{"kind":"event","event_id":"e20a","ts":1758400000}'
    poison = b'{"kind":"event","event_id":"e20b","ts":[1]}'
    rows, dropped = parse_lines(good + b"\n" + poison)
    assert dropped == 1
    assert len(rows) == 1
    assert rows[0][0] == "event"


def test_ts_dict_is_dropped_but_sibling_row_is_stored():
    """ts が辞書の行は破棄し、同じリクエスト内の正常行は保存される。"""
    good = b'{"kind":"event","event_id":"e21a","ts":1758400000}'
    poison = b'{"kind":"event","event_id":"e21b","ts":{"a":1}}'
    rows, dropped = parse_lines(good + b"\n" + poison)
    assert dropped == 1
    assert len(rows) == 1
    assert rows[0][0] == "event"


def test_ts_40_digit_number_is_dropped_but_sibling_row_is_stored():
    """ts が 40 桁の整数の行は破棄し、同じリクエスト内の正常行は保存される。"""
    good = b'{"kind":"event","event_id":"e22a","ts":1758400000}'
    poison = b'{"kind":"event","event_id":"e22b","ts":' + b"1" * 40 + b"}"
    rows, dropped = parse_lines(good + b"\n" + poison)
    assert dropped == 1
    assert len(rows) == 1
    assert rows[0][0] == "event"


def test_context_tokens_40_digit_number_does_not_crash_sibling_row():
    """context_tokens が 40 桁の整数でも例外にならず、同じリクエスト内の正常行は保存される。

    context_tokens は必須列ではないため、桁あふれの列だけが None に落ち、行は破棄されない。
    """
    good = b'{"kind":"event","event_id":"e23a","ts":1758400000}'
    huge_context_tokens = (
        b'{"kind":"event","event_id":"e23b","ts":1758400000,"context_tokens":'
        + b"1" * 40
        + b"}"
    )
    rows, dropped = parse_lines(good + b"\n" + huge_context_tokens)
    assert dropped == 0
    assert len(rows) == 2
    assert _events_value(rows[1][1], "context_tokens") is None


def test_lone_surrogate_in_field_does_not_crash_and_row_is_stored():
    """孤立サロゲートを含む行も例外にならず保存され、同じリクエスト内の正常行も保存される。"""
    good = b'{"kind":"event","event_id":"e24a","ts":1758400000}'
    poison = (
        '{"kind":"event","event_id":"e24b","ts":1758400000,"tool_name":"\ud800"}'
    ).encode("utf-8", "surrogatepass")
    rows, dropped = parse_lines(good + b"\n" + poison)
    assert dropped == 0
    assert len(rows) == 2
    tool_name = _events_value(rows[1][1], "tool_name")
    assert "\ud800" not in tool_name
    tool_name.encode("utf-8")
