import sys

import pytest

import roast


def parse(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["roast.py", *argv])
    return roast.parse_args()


def test_model_flag_is_accepted_with_agent(monkeypatch):
    args = parse(monkeypatch, "--agent", "--model", "nvidia/nemotron-3-super-120b-a12b:free")
    assert args.model == "nvidia/nemotron-3-super-120b-a12b:free"


def test_model_flag_without_agent_is_an_error(monkeypatch):
    with pytest.raises(SystemExit):
        parse(monkeypatch, "--model", "some/model")


def test_range_cannot_smuggle_options(monkeypatch):
    with pytest.raises(SystemExit):
        parse(monkeypatch, "--range=--output=x")
