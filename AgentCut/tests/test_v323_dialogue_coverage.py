from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw

from agentcut.editor import Editor
from agentcut.qa import run_qa


def make_scene(path: Path):
    im = Image.new('RGB',(640,360),'#301417'); d=ImageDraw.Draw(im)
    for x,c in [(90,'#ff6b6b'),(240,'#ffd166'),(400,'#63b3ed'),(545,'#f093fb')]:
        d.ellipse((x-25,80,x+25,130),fill=c); d.rectangle((x-30,128,x+30,285),fill=c)
    im.save(path)


def seed(tmp_path: Path, duration=6.0):
    src=tmp_path/'scene.png'; make_scene(src)
    e=Editor.create(tmp_path/'p',width=640,height=360,fps=12)
    e.add_asset(src,asset_id='a'); e.add_scene('a',duration,scene_id='s')
    e.define_character('a1',display_name='甲',focus_x=.16,focus_y=.56)
    e.define_character('a2',display_name='乙',focus_x=.68,focus_y=.56)
    return e


def test_long_dialogue_qa_requests_coverage_then_clears(tmp_path):
    e=seed(tmp_path)
    e.add_caption('第一句',.3,2.0,speaker='甲')
    e.add_caption('第二句',2.7,4.8,speaker='乙')
    before=run_qa(e.root,e.get_project())
    assert any(x['code']=='LONG_SINGLE_COVERAGE' for x in before['issues'])
    out=e.direct_dialogue_coverage('s',intensity=.6)
    assert out['shot_count'] >= 2
    assert e.get_scene('s')['camera']['shot_path']
    after=run_qa(e.root,e.get_project())
    assert not any(x['code']=='LONG_SINGLE_COVERAGE' for x in after['issues'])


def test_coverage_uses_scene_staging_and_group_resets(tmp_path):
    e=seed(tmp_path)
    e.stage_character('s','a1',focus_x=.82,focus_y=.52)
    e.add_caption('右边说话',.5,1.6,speaker='甲')
    e.add_caption('左边回应',3.0,4.2,speaker='乙')
    out=e.direct_dialogue_coverage('s',reset_gap=.8)
    speaker=[x for x in out['shots'] if x['kind']=='speaker']
    assert len(speaker)==2
    path=e.get_scene('s')['camera']['shot_path']
    assert any(abs(x['x']-.82)<.01 for x in path)
    assert any(x['kind']=='group_reset' for x in out['shots'])


def test_native_dialogue_segments_are_coverage_sources(tmp_path):
    e=seed(tmp_path)
    e.compose_dialogue_scene('s',['甲：你好。','乙：收到。'],fit_scene=False,direction='off')
    out=e.direct_dialogue_coverage('s')
    assert out['shot_count'] >= 2
    assert {x.get('character_id') for x in out['shots'] if x['kind']=='speaker'} == {'a1','a2'}


def test_auto_dialogue_chooses_coverage_for_long_scene(tmp_path):
    e=seed(tmp_path)
    out=e.compose_dialogue_scene('s',['甲：长镜头第一句。','乙：第二句。'],fit_scene=False,direction='auto',replace_existing=True)
    assert out['direction_mode']=='coverage'
    assert out['coverage_shots'] >= 2
    assert len(e.get_scene('s')['camera']['shot_path']) >= 3
    assert not e.get_scene('s')['composition'].get('focus_path')


def test_short_dialogue_keeps_speaker_tracking(tmp_path):
    e=seed(tmp_path,duration=2.0)
    out=e.compose_dialogue_scene('s',['甲：你好。','乙：收到。'],fit_scene=False,direction='auto')
    assert out['direction_mode']=='speaker_tracking'
    assert e.get_scene('s')['composition'].get('focus_path')
    assert not e.get_scene('s')['camera'].get('shot_path')


def test_agent_alias_dialogue_coverage(tmp_path):
    e=seed(tmp_path)
    e.add_caption('第一句',.3,2.0,speaker='甲')
    e.add_caption('第二句',2.7,4.8,speaker='乙')
    check=e.preflight_operations({'action':'对白分镜','scene':'s','energy':.7})
    assert check['ok'] is True
    assert check['operations'][0]['action']=='direct_dialogue_coverage'


def test_actual_shot_path_proxy_renders(tmp_path):
    e=seed(tmp_path,duration=3.0)
    e.add_caption('第一句',.2,1.2,speaker='甲')
    e.add_caption('第二句',1.5,2.7,speaker='乙')
    e.direct_dialogue_coverage('s',intensity=.75,reset_gap=.5)
    out=e.render_proxy(tmp_path/'coverage.mp4')
    assert Path(out).exists() and Path(out).stat().st_size > 0

def test_attention_insert_merges_before_dialogue_coverage(tmp_path):
    e=seed(tmp_path)
    e.add_caption('后面才说话',3.0,4.5,speaker='甲')
    e.add_caption('再一句',4.6,5.6,speaker='乙')
    e.direct_dialogue_coverage('s')
    out=e.direct_attention_insert('s',start=.45,duration=1.6,focus_x=.5,focus_y=.25,intensity=.8)
    assert out['keyframes'] >= 6
    path=e.get_scene('s')['camera']['shot_path']
    assert any(abs(x['x']-.5)<.01 and abs(x['y']-.25)<.01 and x.get('cut') for x in path)
    qa=run_qa(e.root,e.get_project())
    assert not any(x['code']=='LONG_PRE_DIALOGUE_HOLD' for x in qa['issues'])


def test_attention_insert_refuses_to_overwrite_existing_cut(tmp_path):
    e=seed(tmp_path)
    e.add_caption('一句',1.0,2.0,speaker='甲')
    e.add_caption('二句',3.0,4.0,speaker='乙')
    e.direct_dialogue_coverage('s')
    import pytest
    with pytest.raises(Exception) as exc:
        e.direct_attention_insert('s',start=.5,duration=3.0,focus_x=.5,focus_y=.3)
    assert 'ATTENTION_BEAT_CONFLICT' in str(exc.value)


def test_agent_alias_attention_insert(tmp_path):
    e=seed(tmp_path)
    check=e.preflight_operations({'action':'物件特写','scene':'s','time':.5,'length':1.0,'x':.5,'y':.25})
    assert check['ok'] is True
    assert check['operations'][0]['action']=='direct_attention_insert'
