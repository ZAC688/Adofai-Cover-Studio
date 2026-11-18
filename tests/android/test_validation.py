"""Run unchanged with desktop Pydantic 2 and Android's pure-Python Pydantic 1."""
from copy import deepcopy
import json

import pytest

from backend.app.schema import ChartRecipe, Project, Title, default_project
from backend.app.filter_schema import CATALOG, FilterSpec
from backend.app.text_presets import SaveTextPreset
from backend.app.validation import ValidationError


def test_full_style_survives_validation_and_json_roundtrip():
    project = default_project()
    project['titles'][0].update(text='中文测试 ADOFAI', text3d={'enabled': True, 'depth': 70},
                                shadow={'enabled': True, 'opacity': 80})
    parsed = Project.model_validate(project)
    restored = Project.model_validate_json(json.dumps(parsed.model_dump(), ensure_ascii=False))
    assert restored.titles[0].text == '中文测试 ADOFAI'
    assert restored.titles[0].text3d.depth == 70
    assert restored.titles[0].shadow.opacity == 80
    assert restored.model_dump() == parsed.model_dump()
    assert 'generatedTrack' not in restored.model_dump()


@pytest.mark.parametrize('change', [
    lambda p: p.update(unrecognized=True),
    lambda p: p.update(name=123),
    lambda p: p.update(titles=p['titles'][:1]),
    lambda p: p.update(titles=p['titles'] * 3),
    lambda p: p.update(layerOrder=['title1', 'title1', 'bg']),
    lambda p: p.update(layerOrder=['missing', 'bg']),
    lambda p: p.update(layerOrder=['bg', 'title1']),
    lambda p: p['titles'][0].update(text=123),
    lambda p: p['titles'][0].update(text='字' * 301),
    lambda p: p['titles'][0].update(color='red'),
    lambda p: p['titles'][0].update(fontId='../private-font'),
    lambda p: p['layouts']['16:9']['track'].update(scale=0),
    lambda p: p['layouts']['16:9']['track'].update(x=float('nan')),
    lambda p: p['titles'][0].update(text3d={'depth': 201}),
])
def test_original_project_limits_are_not_relaxed(change):
    project = default_project()
    change(project)
    with pytest.raises(ValidationError):
        Project.model_validate(project)


@pytest.mark.parametrize('updates', [
    {'start': 2, 'end': 1}, {'start': 1.5}, {'resolution': 1024},
    {'crop': [0, 0, 0, 1]}, {'crop': [0, 0, 1, 100001]},
])
def test_chart_limits_and_after_validator_are_retained(updates):
    recipe = {'sourceId': 'a' * 32, 'start': 0, 'end': 5, 'resolution': 1920, **updates}
    with pytest.raises(ValidationError):
        ChartRecipe.model_validate(recipe)


def test_nested_preset_validates_title_attributes():
    style = {'color': '#ffffff', 'glow': 0, 'fontId': 'system'}
    preset = {'name': '测试预设', 'style': style, 'fontSize': 120}
    assert SaveTextPreset.model_validate(preset).style.color == '#ffffff'
    invalid = deepcopy(preset)
    invalid['style']['color'] = 'invalid'
    with pytest.raises(ValidationError):
        SaveTextPreset.model_validate(invalid)


def test_filter_targets_and_custom_parameter_checks_are_retained():
    kind = next(iter(CATALOG))
    valid = {'id': 'a' * 32, 'type': kind, 'targets': ['track'], 'params': {}}
    assert FilterSpec.model_validate(valid).targets == ['track']
    for updates in ({'targets': []}, {'targets': [123]}, {'params': {'notAParameter': 1}}):
        with pytest.raises(ValidationError):
            FilterSpec.model_validate({**valid, **updates})


def test_title_cannot_accept_infinite_glow_or_unknown_properties():
    valid = {'text': '曲名', 'color': '#ffffff', 'glow': 0}
    for updates in ({'glow': float('inf')}, {'unknown': 1}):
        with pytest.raises(ValidationError):
            Title.model_validate({**valid, **updates})
