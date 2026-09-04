from pathlib import Path

from PIL import Image

from agentcut import Editor
from agentcut.libraries import list_libraries, list_items, get_item
from agentcut.probe import probe, primary_video_info


def _img(path: Path, color=(28, 34, 50)):
    Image.new('RGB', (960, 540), color).save(path)


def test_library_counts_total_138():
    counts = list_libraries()
    assert counts == {
        'transitions': 40,
        'effects': 24,
        'filters': 14,
        'motions': 12,
        'layer_motions': 12,
        'subtitle_styles': 16,
        'audio_cues': 8,
        'materials': 12,
    }
    assert sum(counts.values()) == 138


def test_library_tag_query_and_inspect():
    winter = list_items('effects', tags=['weather', 'cold'])
    ids = {x['id'] for x in winter}
    assert {'snow_light', 'snow_wind', 'snow_heavy'} <= ids
    assert get_item('effects', 'fire')['backend'] == 'fire'


def test_apply_effect_filter_motion_transition_presets(tmp_path: Path):
    src = tmp_path / 'x.png'; _img(src)
    root = tmp_path / 'p'; e = Editor.create(root, width=960, height=540, fps=30)
    a = e.add_asset(src, asset_id='img')
    e.add_scene(a['id'], duration=1.2, scene_id='s1')
    fx = e.apply_effect_preset('s1', 'snow_wind', seed=9)
    assert fx['type'] == 'snow' and fx['preset_id'] == 'snow_wind' and fx['material'] == 'snow_crisp'
    assert e.add_filter('s1', 'cool') == ['cool']
    cam = e.apply_motion_preset('s1', 'gentle_push')
    assert cam['type'] == 'slow_push'
    tr = e.apply_transition_preset('s1', 'cut')
    assert tr == {'type': 'cut', 'duration': 0.0}


def test_showcase_profile_is_native_1080_when_project_is_1080(tmp_path: Path):
    src = tmp_path / 'x.png'; _img(src, (80, 40, 30))
    root = tmp_path / 'p'; e = Editor.create(root, width=1920, height=1080, fps=30)
    a = e.add_asset(src, asset_id='img')
    e.add_scene(a['id'], duration=0.6, scene_id='s1')
    out = e.render_showcase(root / 'show.mp4')
    meta = probe(out); vi = primary_video_info(out)
    assert vi['width'] == 1920 and vi['height'] == 1080
    assert round(float(meta['format']['duration']), 1) == 0.6


def test_filter_render_changes_pixels(tmp_path: Path):
    src = tmp_path / 'x.png'; _img(src, (120, 80, 40))
    root = tmp_path / 'p'; e = Editor.create(root, width=640, height=360, fps=24)
    a=e.add_asset(src, asset_id='img'); e.add_scene(a['id'], duration=0.4, scene_id='s1')
    e.add_filter('s1', 'monochrome')
    out=e.render_scene('s1', profile='preview')
    assert out.exists() and out.stat().st_size > 0


def test_particle_presets_smoke_render(tmp_path: Path):
    src = tmp_path / 'x.png'; _img(src, (12, 18, 26))
    root = tmp_path / 'p'; e=Editor.create(root, width=640, height=360, fps=24)
    a=e.add_asset(src, asset_id='img')
    for i,preset in enumerate(['snow_light','dust_motes','fog_low','fire','smoke_light','ash','bokeh_warm']):
        sid=f's{i}'
        e.add_scene(a['id'], duration=0.28, scene_id=sid)
        e.apply_effect_preset(sid,preset,seed=i+1)
        out=e.render_scene(sid, profile='preview')
        assert out.exists() and out.stat().st_size > 0


def test_experimental_transition_catalog_separated():
    all_rows=list_items('transitions')
    stable=list_items('transitions',stable_only=True)
    assert len(stable) < len(all_rows)
    assert any(x['stability']=='experimental' for x in all_rows)


def test_atomic_library_operations(tmp_path: Path):
    src=tmp_path/'x.png'; _img(src)
    root=tmp_path/'p'; e=Editor.create(root,width=640,height=360,fps=24)
    a=e.add_asset(src,asset_id='img'); e.add_scene(a['id'],duration=1.0,scene_id='s1')
    result=e.apply_operations([
        {'action':'apply_effect_preset','args':{'scene_id':'s1','preset_id':'dust_motes'}},
        {'action':'add_filter','args':{'scene_id':'s1','filter_id':'faded_film'}},
        {'action':'apply_motion_preset','args':{'scene_id':'s1','preset_id':'gentle_push'}},
    ])
    assert result['applied']==3
    s=e.get_scene('s1')
    assert s['effects'][0]['preset_id']=='dust_motes'
    assert s['filters']==['faded_film']
