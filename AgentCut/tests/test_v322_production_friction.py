from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw
import pytest

from agentcut import Editor
from agentcut.errors import AgentCutError
from agentcut.subtitles import fit_subtitle_layout, install_whisper_backend, asr_status
from agentcut.runtime import compact_bootstrap


def image(path: Path, subjects=4):
    im = Image.new("RGB", (800, 450), (18, 20, 25))
    d = ImageDraw.Draw(im)
    xs = [110, 300, 500, 690][:subjects]
    cols = [(230,80,100),(240,200,70),(80,180,220),(180,90,220)]
    for i,x in enumerate(xs):
        # simple head/body subject silhouettes with high local contrast
        d.ellipse((x-34,90,x+34,158), fill=cols[i])
        d.rounded_rectangle((x-48,155,x+48,355), radius=20, fill=cols[i], outline=(250,250,250), width=3)
    im.save(path)


def seed(tmp_path: Path, subjects=4):
    src=tmp_path/'scene.png'; image(src, subjects)
    e=Editor.create(tmp_path/'p', width=1280, height=720, fps=30, name='v322')
    aid=e.add_asset(src)['id']; e.add_scene(aid, 4.0, scene_id='s1')
    for cid,name,color in [('a','A','#FF6677'),('b','B','#F6C85F'),('c','C','#66CCEE'),('d','D','#BB77EE')][:subjects]:
        e.define_character(cid, display_name=name, color=color)
    return e


def test_bilingual_layout_autofit_does_not_rewrite_text_or_timing(tmp_path):
    e=seed(tmp_path,2)
    text='烈焰棒合成烈焰粉，再和末影珍珠合成末影之眼。'
    en='Craft blaze rods into powder, then combine it with ender pearls to make Eyes of Ender.'
    cap=e.add_caption(text,.2,2.0,secondary_text=en,subtitle_style='bilingual')
    assert cap['text']==text and cap['secondary_text']==en
    assert cap['start']==.2 and cap['end']==2.0
    assert cap['layout_auto_fit'] is True
    assert cap['secondary_font_scale'] < .72
    assert cap['max_line_chars'] <= 18
    assert cap['secondary_max_line_chars'] <= 34


def test_optimize_subtitles_upgrades_legacy_layout_only(tmp_path):
    e=seed(tmp_path,2)
    cap=e.add_caption('很长很长的一条中文字幕用于旧工程升级',.1,1.1,secondary_text='A long legacy translation line that should be fitted automatically.',auto_fit=False)
    before=(cap['text'],cap['start'],cap['end'])
    out=e.optimize_subtitle_layout([cap['id']],include_dialogue=False)
    now=next(x for x in e.get_project()['captions'] if x['id']==cap['id'])
    assert out['count']==1
    assert (now['text'],now['start'],now['end'])==before
    assert now['layout_auto_fit'] is True and now['max_line_chars'] is not None


def test_visual_anchor_suggestion_and_explicit_order_staging(tmp_path):
    e=seed(tmp_path,4)
    suggestion=e.suggest_scene_staging('s1',count=4)
    assert suggestion['identity_policy']=='anchors_only_no_character_guess'
    assert len(suggestion['anchors'])==4
    xs=[a['x'] for a in suggestion['anchors']]
    assert xs==sorted(xs)
    staged=e.stage_scene_by_order('s1',['a','b','c','d'],minimum_confidence=0.05)
    assert staged['identity_source']=='explicit_character_order'
    scene=e.get_scene('s1')
    assert list(scene['staging'])==['a','b','c','d']
    assert scene['staging']['a']['focus_x'] < scene['staging']['d']['focus_x']


def test_agent_checkpoint_and_edit_survive_warm_restart(tmp_path):
    e=seed(tmp_path,2)
    first=e.agent_bootstrap(task='EP07 subtitle pass',domains=['text'])
    assert first['mode']=='cold_resume'
    e.agent_checkpoint(goal='Finish EP07 bilingual subtitle pass',active_scene_ids=['s1'],domains=['text'],decisions=['Keep Chinese primary; English secondary smaller.'])
    receipt=e.apply_agent_operations({'action':'camera','scene':'s1','type':'slow_push'})
    resumed=e.agent_bootstrap()
    assert resumed['mode']=='warm_resume'
    assert resumed['project_changed_since_last_bootstrap'] is True
    assert resumed['checkpoint']['goal'].startswith('Finish EP07')
    assert resumed['last_receipt']['transaction_id']==receipt['transaction_id']
    assert 'set_camera' in resumed['last_receipt']['actions']


def test_upgrade_bootstrap_reports_only_schema_delta(tmp_path):
    e=seed(tmp_path,1)
    old=compact_bootstrap(e,package_version='3.2.1',write=True)
    runtime=Path(old['runtime_file'])
    data=json.loads(runtime.read_text())
    data['tool_signatures']['set_camera']='(scene_id, motion)'  # simulate old signature
    data['package_version']='3.2.1'
    runtime.write_text(json.dumps(data),encoding='utf-8')
    new=compact_bootstrap(e,package_version='3.2.2',write=False)
    assert new['mode']=='upgrade_resume'
    assert 'set_camera' in new['schema_delta']['changed']
    assert 'full tool schema' in new['read_policy']


def test_asr_installer_requires_explicit_acceptance(tmp_path, monkeypatch):
    monkeypatch.setenv('AGENTCUT_BACKEND_ROOT',str(tmp_path/'backends'))
    with pytest.raises(AgentCutError) as exc:
        install_whisper_backend(model_only=True)
    assert exc.value.code=='THIRD_PARTY_ACCEPTANCE_REQUIRED'


def test_asr_model_only_install_is_persistent_and_checksum_verified(tmp_path, monkeypatch):
    import agentcut.subtitles as sub
    backend=tmp_path/'backends'; monkeypatch.setenv('AGENTCUT_BACKEND_ROOT',str(backend))
    payload=b'fake quantized model for unit test'
    sha=hashlib.sha256(payload).hexdigest()
    spec=sub.ASR_INSTALL_REGISTRY['whisper.cpp']['models']['tiny-q5_1']
    monkeypatch.setitem(spec,'url','https://example.invalid/fake.bin')
    monkeypatch.setitem(spec,'sha256',sha)
    def fake_download(url,target):
        Path(target).write_bytes(payload); return str(target),None
    monkeypatch.setattr(sub.urllib.request,'urlretrieve',fake_download)
    out=install_whisper_backend(profile='tiny-q5_1',accept_third_party=True,model_only=True)
    assert Path(out['model']).read_bytes()==payload
    out2=install_whisper_backend(profile='tiny-q5_1',accept_third_party=True,model_only=True)
    assert out2['model_reused'] is True


def test_subtitle_status_advertises_one_command_installer(tmp_path):
    e=seed(tmp_path,1)
    status=e.subtitle_status()['asr']
    assert status['installer']['profile']=='tiny-q5_1'
    assert status['installer']['persistent'] is True
