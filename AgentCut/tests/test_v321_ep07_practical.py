from pathlib import Path
from PIL import Image
from agentcut.editor import Editor
from agentcut.qa import run_qa


def seed(tmp_path):
    img=tmp_path/'a.png'; Image.new('RGB',(640,360),'#221010').save(img)
    e=Editor.create(tmp_path/'p',width=640,height=360,fps=12)
    e.add_asset(img,asset_id='a'); e.add_scene('a',3.0,scene_id='s1')
    e.define_character('k',display_name='喜多',focus_x=.8,focus_y=.5,color='#DD4433',aliases=['Kita'])
    e.define_character('n',display_name='虹夏',focus_x=.2,focus_y=.5,color='#EEC044',aliases=['Nijika'])
    return e


def test_scene_staging_overrides_global_reaction_focus(tmp_path):
    e=seed(tmp_path)
    e.stage_character('s1','喜多',focus_x=.22,focus_y=.61)
    out=e.direct_reaction_scene('s1','喜多',intensity=.5)
    assert out['focus']=={'x':.22,'y':.61}
    assert e.get_scene('s1')['staging']['k']['focus_x']==.22


def test_smart_srt_import_parses_known_cast_styles_and_bilingual(tmp_path):
    e=seed(tmp_path)
    zh=tmp_path/'zh.srt'; en=tmp_path/'en.srt'
    zh.write_text('1\n00:00:00,100 --> 00:00:01,000\n喜多：水呢？！\n\n2\n00:00:01,100 --> 00:00:02,100\n30 秒前\n',encoding='utf-8')
    en.write_text('1\n00:00:00,100 --> 00:00:01,000\nWhere is the water?!\n\n2\n00:00:01,100 --> 00:00:02,100\n30 seconds earlier\n',encoding='utf-8')
    out=e.import_subtitle_file(zh,secondary_path=en)
    caps=e.get_project()['captions']
    assert out['recognized_speakers']==1 and out['bilingual_count']==2
    assert caps[0]['speaker']=='喜多' and caps[0]['character_id']=='k'
    assert caps[0]['text']=='水呢？！' and caps[0]['subtitle_style']=='shout'
    assert caps[0]['secondary_text']=='Where is the water?!'
    assert caps[1]['subtitle_style']=='cinematic'


def test_smart_srt_does_not_parse_unknown_colon_as_speaker(tmp_path):
    e=seed(tmp_path)
    s=tmp_path/'x.srt'; s.write_text('1\n00:00:00,100 --> 00:00:01,000\n提示：未知规则\n',encoding='utf-8')
    e.import_subtitle_file(s)
    cap=e.get_project()['captions'][0]
    assert cap['speaker'] is None and cap['text']=='提示：未知规则'


def test_library_effect_id_is_accepted_by_add_effect(tmp_path):
    e=seed(tmp_path)
    fx=e.add_effect('s1','embers_light')
    assert fx['type']=='embers' and fx['preset_id']=='embers_light'


def test_qa_flags_unparsed_known_cast_prefix(tmp_path):
    e=seed(tmp_path)
    e.add_caption('喜多：水呢？！',.1,.8)
    qa=run_qa(e.root,e.get_project())
    assert 'UNPARSED_CAPTION_SPEAKER' in {x['code'] for x in qa['issues']}

def test_proxy_profile_is_low_cost_and_exposed(tmp_path):
    from agentcut.render import Renderer, list_render_profiles
    e=seed(tmp_path)
    p=Renderer(e.root,e.get_project())._profile('proxy')
    assert p['width']==640 and p['height']==360 and p['fps']==12 and p['camera_supersample']==1
    assert 'proxy' in list_render_profiles()


def test_stage_operation_is_agent_callable(tmp_path):
    e=seed(tmp_path)
    out=e.apply_agent_operations({'action':'角色站位','场景':'s1','角色':'喜多','x':.25,'y':.6})
    assert out['ok'] is True
    assert e.get_scene('s1')['staging']['k']['focus_x']==.25
