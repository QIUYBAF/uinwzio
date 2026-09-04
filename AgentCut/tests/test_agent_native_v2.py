from pathlib import Path
import json
from PIL import Image
from jsonschema import Draft202012Validator

from agentcut import Editor


def _img(path: Path, color=(30,45,65), size=(640,360)):
    Image.new('RGB',size,color).save(path)


def test_context_pack_is_compact_and_scene_scoped(tmp_path: Path):
    src=tmp_path/'x.png'; _img(src)
    root=tmp_path/'p'; e=Editor.create(root,width=640,height=360,fps=24)
    a=e.add_asset(src,asset_id='img')
    for i in range(3): e.add_scene(a['id'],duration=1.0,scene_id=f's{i}')
    full=json.dumps(e.get_project(),ensure_ascii=False)
    compact=json.dumps(e.context_pack(),ensure_ascii=False)
    one=json.dumps(e.context_pack(scene_ids=['s1']),ensure_ascii=False)
    assert len(compact) < len(full)
    assert len(one) < len(compact)
    assert e.context_pack(scene_ids=['s1'])['scenes'][0]['id']=='s1'


def test_project_facts_resolve_and_qa_missing(tmp_path: Path):
    src=tmp_path/'x.png'; _img(src)
    root=tmp_path/'p'; e=Editor.create(root,width=640,height=360,fps=24)
    a=e.add_asset(src,asset_id='img'); e.add_scene(a['id'],duration=1.0,scene_id='s1')
    e.set_fact('tests',42)
    assert e.resolve_text('{{tests}} / {{missing}}') == '42 / {{missing}}'
    e.add_caption('tests={{tests}} missing={{missing}}',0,.8)
    q=e.qa()
    assert q['status']=='fail'
    assert any(x['code']=='UNRESOLVED_FACT' for x in q['issues'])


def test_graphics_text_layer_render_and_fact_resolution(tmp_path: Path):
    src=tmp_path/'x.png'; _img(src,(20,26,38))
    root=tmp_path/'p'; e=Editor.create(root,width=640,height=360,fps=24)
    a=e.add_asset(src,asset_id='img'); e.add_scene(a['id'],duration=.55,scene_id='s1')
    e.set_fact('count',129)
    e.add_layer('s1','rect',layer_id='card',x=40,y=90,width=360,height=140,fill='#162434cc',radius=18,z=0)
    e.add_layer('s1','text',layer_id='title',x=72,y=125,text='{{count}} LIBRARY ITEMS',font_size=38,color='#ffffff',bold=True,z=1)
    e.apply_layer_motion('s1','title','reveal_right',duration=.25)
    out=e.render_scene('s1',profile='preview')
    assert out.exists() and out.stat().st_size>0
    assert e.qa(out)['status'] != 'fail'


def test_shared_element_plan(tmp_path: Path):
    src=tmp_path/'x.png'; _img(src)
    root=tmp_path/'p'; e=Editor.create(root,width=640,height=360,fps=24)
    a=e.add_asset(src,asset_id='img'); e.add_scene(a['id'],duration=1,scene_id='a'); e.add_scene(a['id'],duration=1,scene_id='b')
    e.add_layer('a','rect',layer_id='x1',shared_id='hero',x=10,y=20,width=100,height=60)
    e.add_layer('b','rect',layer_id='x2',shared_id='hero',x=300,y=120,width=140,height=90,scale=1.2)
    plan=e.shared_element_plan('a','b')
    assert plan==[{'shared_id':'hero','mode':'morph','from':{'x':10.0,'y':20.0,'scale':1.0,'opacity':1.0,'rotation':0.0},'to':{'x':300.0,'y':120.0,'scale':1.2,'opacity':1.0,'rotation':0.0}}]


def test_project_schema_accepts_layers_facts_filters(tmp_path: Path):
    src=tmp_path/'x.png'; _img(src)
    root=tmp_path/'p'; e=Editor.create(root,width=640,height=360,fps=24)
    a=e.add_asset(src,asset_id='img'); e.add_scene(a['id'],duration=1,scene_id='s1')
    e.set_fact('version','0.2.0-alpha.5'); e.add_filter('s1','cool'); e.add_layer('s1','text',text='v{{version}}',layer_id='t',duration=.8)
    schema=json.loads((Path(__file__).parents[1]/'project.schema.json').read_text())
    Draft202012Validator(schema).validate(e.get_project())


def test_layer_atomic_operations(tmp_path: Path):
    src=tmp_path/'x.png'; _img(src)
    root=tmp_path/'p'; e=Editor.create(root,width=640,height=360,fps=24)
    a=e.add_asset(src,asset_id='img'); e.add_scene(a['id'],duration=1.0,scene_id='s1')
    result=e.apply_operations([
        {'action':'set_fact','args':{'key':'n','value':36}},
        {'action':'add_layer','args':{'scene_id':'s1','layer_type':'text','layer_id':'t','text':'{{n}} tests','x':30,'y':30,'duration':.8}},
        {'action':'apply_layer_motion','args':{'scene_id':'s1','layer_id':'t','preset_id':'fade_in','duration':.2}},
    ])
    assert result['applied']==3
    assert e.get_scene('s1')['layers'][0]['motion']['preset_id']=='fade_in'
