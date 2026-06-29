from __future__ import annotations

from tradebox_workflows.output import print_metadata


def test_print_metadata_emits_stable_key_value_lines(capsys) -> None:
    print_metadata({"partition_id": "abc", "row_count": 1, "optional": None})

    assert capsys.readouterr().out == "partition_id=abc\nrow_count=1\noptional=\n"
