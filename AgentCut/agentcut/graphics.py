from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path
from copy import deepcopy

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .errors import AgentCutError
from .util import ensure_binary, hash_obj

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = list(FONT_CANDIDATES)
    if bold:
        candidates.insert(0, "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
        candidates.insert(1, "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, max(1, int(size)))
    return ImageFont.load_default()


def _parse_color(value, default=(255,255,255,255)):
    if isinstance(value, (list,tuple)) and len(value) in {3,4}:
        vals=tuple(max(0,min(255,int(x))) for x in value)
        return vals if len(vals)==4 else vals+(255,)
    if isinstance(value,str):
        s=value.strip().lstrip('#')
        if len(s) in {6,8}:
            try:
                vals=tuple(int(s[i:i+2],16) for i in range(0,len(s),2))
                return vals if len(vals)==4 else vals+(255,)
            except ValueError: pass
    return default


def _resolve_text(text: str, facts: dict) -> str:
    import re
    def repl(m):
        k=m.group(1).strip(); return str(facts[k]) if k in facts else m.group(0)
    return re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", repl, str(text))


def _lerp(a,b,t): return a+(b-a)*t

def _ease(t: float, easing: str='ease_out') -> float:
    t=max(0.0,min(1.0,t))
    if easing in {'ease','ease_in_out','smooth'}: return .5-.5*math.cos(math.pi*t)
    if easing=='ease_in': return t*t
    if easing=='ease_out': return 1-(1-t)*(1-t)
    return t


def _state(layer: dict, local_t: float) -> dict:
    state={k:float(layer.get(k,d)) for k,d in [('x',0),('y',0),('scale',1),('opacity',1),('rotation',0)]}
    motion=layer.get('motion') or {}
    if motion:
        ms=float(motion.get('start',layer.get('start',0))); md=max(.001,float(motion.get('duration',.4)))
        p=_ease((local_t-ms)/md, str(motion.get('easing','ease_out')))
        fr=motion.get('from',{}); to=motion.get('to',{})
        for k in ('scale','opacity','rotation'):
            if k in fr or k in to:
                a=float(fr.get(k,state[k])); b=float(to.get(k,state[k])); state[k]=_lerp(a,b,p)
        for axis in ('x','y'):
            off_key=f'{axis}_offset'; a=float(fr.get(off_key,0)); b=float(to.get(off_key,0)); state[axis]+= _lerp(a,b,p)
    kfs=sorted(layer.get('keyframes') or [], key=lambda x: float(x.get('t',0)))
    if kfs:
        lt=max(0.0,min(1.0,(local_t-float(layer.get('start',0)))/max(.001,float(layer.get('duration',1)))))
        lo=kfs[0]; hi=kfs[-1]
        for i in range(len(kfs)-1):
            if float(kfs[i].get('t',0)) <= lt <= float(kfs[i+1].get('t',1)):
                lo,hi=kfs[i],kfs[i+1]; break
        span=max(1e-9,float(hi.get('t',1))-float(lo.get('t',0))); q=_ease((lt-float(lo.get('t',0)))/span,str(hi.get('easing','linear')))
        for k in ('x','y','scale','opacity','rotation'):
            if k in lo or k in hi:
                a=float(lo.get(k,state[k])); b=float(hi.get(k,a)); state[k]=_lerp(a,b,q)
    return state


def _prepare_content(layer: dict, project: dict, root: Path, facts: dict) -> Image.Image:
    typ=layer.get('type')
    if typ=='text':
        text=_resolve_text(layer.get('text',''),facts); fs=int(layer.get('font_size',54)); f=_font(fs,bool(layer.get('bold',False)))
        stroke=int(layer.get('outline',0)); dummy=Image.new('RGBA',(8,8)); d=ImageDraw.Draw(dummy)
        bb=d.multiline_textbbox((0,0),text,font=f,stroke_width=stroke,spacing=int(layer.get('spacing',4)))
        w=max(1,bb[2]-bb[0]+12+stroke*2); h=max(1,bb[3]-bb[1]+12+stroke*2)
        im=Image.new('RGBA',(w,h),(0,0,0,0)); dr=ImageDraw.Draw(im)
        dr.multiline_text((6-bb[0]+stroke,6-bb[1]+stroke),text,font=f,fill=_parse_color(layer.get('color','#ffffff')),stroke_width=stroke,stroke_fill=_parse_color(layer.get('outline_color','#111111')),spacing=int(layer.get('spacing',4)))
        return im
    if typ=='rect':
        w=max(1,int(layer.get('width',320))); h=max(1,int(layer.get('height',140))); im=Image.new('RGBA',(w,h),(0,0,0,0)); dr=ImageDraw.Draw(im)
        radius=int(layer.get('radius',0)); fill=_parse_color(layer.get('fill','#202a38cc')); outline=_parse_color(layer.get('outline_color','#ffffff00')); ow=int(layer.get('outline_width',0))
        dr.rounded_rectangle((0,0,w-1,h-1),radius=radius,fill=fill,outline=outline,width=ow)
        return im
    if typ=='image':
        aid=layer.get('asset_id'); asset=project.get('assets',{}).get(aid)
        if not asset: raise AgentCutError('INVALID_ASSET','Layer image asset missing',asset_id=aid)
        p=Path(asset['path']); p=p if p.is_absolute() else root/p
        im=Image.open(p).convert('RGBA')
        if layer.get('width') or layer.get('height'):
            w=int(layer.get('width') or im.width); h=int(layer.get('height') or im.height); im=im.resize((max(1,w),max(1,h)),Image.Resampling.LANCZOS)
        return im
    raise AgentCutError('UNSUPPORTED_LAYER','Unsupported layer type',layer_type=typ)


def graphics_cache_path(cache_dir: Path, scene: dict, facts: dict, width: int, height: int, fps: int) -> Path:
    key=hash_obj({'layers':scene.get('layers',[]),'facts':facts,'w':width,'h':height,'fps':fps,'dur':scene.get('duration')})[:20]
    return cache_dir/f'graphics_{scene.get("id")}_{key}.mov'


def generate_graphics_video(path: Path, scene: dict, project: dict, root: Path, width: int, height: int, fps: int) -> Path:
    if path.exists() and path.stat().st_size>0: return path
    layers=sorted(scene.get('layers',[]) or [], key=lambda x:int(x.get('z',0)))
    if not layers: return path
    facts=project.get('facts',{}); prepared={l['id']:_prepare_content(l,project,root,facts) for l in layers}
    duration=float(scene['duration']); frames=max(1,int(math.ceil(duration*fps)))
    path.parent.mkdir(parents=True,exist_ok=True); partial=path.with_name(f'.{path.stem}.partial{path.suffix}'); partial.unlink(missing_ok=True)
    ffmpeg=ensure_binary('ffmpeg')
    proc=subprocess.Popen([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgba','-s',f'{width}x{height}','-r',str(fps),'-i','-','-an','-c:v','qtrle','-pix_fmt','argb',str(partial)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for fi in range(frames):
            t=fi/fps; canvas=Image.new('RGBA',(width,height),(0,0,0,0))
            for layer in layers:
                st=float(layer.get('start',0)); dur=float(layer.get('duration',duration-st))
                if not (st <= t < st+dur): continue
                state=_state(layer,t); content=prepared[layer['id']]
                scale=max(.01,state['scale']); nw=max(1,int(content.width*scale)); nh=max(1,int(content.height*scale))
                im=content if (nw,nh)==content.size else content.resize((nw,nh),Image.Resampling.LANCZOS)
                rot=state['rotation']
                if abs(rot)>1e-6: im=im.rotate(-rot,expand=True,resample=Image.Resampling.BICUBIC)
                op=max(0,min(1,state['opacity']))
                if op<.999:
                    alpha=im.getchannel('A').point(lambda v:int(v*op)); im=im.copy(); im.putalpha(alpha)
                x=int(round(state['x'])); y=int(round(state['y'])); canvas.alpha_composite(im,(x,y))
            if proc.stdin is None: raise AgentCutError('GRAPHICS_PIPE_FAILED','Graphics encoder stdin unavailable')
            proc.stdin.write(np.asarray(canvas,dtype=np.uint8).tobytes())
        if proc.stdin: proc.stdin.close()
        stderr=proc.stderr.read().decode(errors='replace') if proc.stderr else ''; code=proc.wait()
        if code!=0: raise AgentCutError('GRAPHICS_RENDER_FAILED','Failed to encode graphics overlay',stderr=stderr[-4000:],returncode=code)
        if not partial.exists() or partial.stat().st_size<=0: raise AgentCutError('GRAPHICS_RENDER_FAILED','Empty graphics overlay')
        os.replace(partial,path)
    except Exception:
        proc.kill(); partial.unlink(missing_ok=True); raise
    return path


def _content_signature(layer: dict) -> dict:
    typ = layer.get('type')
    if typ == 'text':
        keys = ('type','text','font_size','color','bold','outline','outline_color','spacing')
    elif typ == 'rect':
        keys = ('type','width','height','fill','radius','outline_color','outline_width')
    else:
        keys = ('type','asset_id','width','height')
    return {k: layer.get(k) for k in keys}


def _paste_transformed(canvas: Image.Image, content: Image.Image, state: dict, *, extra_opacity: float = 1.0) -> None:
    scale=max(.01,float(state.get('scale',1))); nw=max(1,int(content.width*scale)); nh=max(1,int(content.height*scale))
    im=content if (nw,nh)==content.size else content.resize((nw,nh),Image.Resampling.LANCZOS)
    rot=float(state.get('rotation',0))
    if abs(rot)>1e-6: im=im.rotate(-rot,expand=True,resample=Image.Resampling.BICUBIC)
    op=max(0,min(1,float(state.get('opacity',1))*float(extra_opacity)))
    if op<.999:
        alpha=im.getchannel('A').point(lambda v:int(v*op)); im=im.copy(); im.putalpha(alpha)
    canvas.alpha_composite(im,(int(round(float(state.get('x',0)))),int(round(float(state.get('y',0))))))


def shared_morph_cache_path(cache_dir: Path, from_scene: dict, to_scene: dict, facts: dict, width: int, height: int, fps: int, duration: float) -> Path:
    key=hash_obj({
        'from':from_scene.get('layers',[]),'to':to_scene.get('layers',[]),'facts':facts,
        'w':width,'h':height,'fps':fps,'duration':duration,'backend':'shared_morph_v1'
    })[:20]
    return cache_dir/f'shared_morph_{from_scene.get("id")}_{to_scene.get("id")}_{key}.mov'


def generate_shared_morph_video(path: Path, from_scene: dict, to_scene: dict, project: dict, root: Path, width: int, height: int, fps: int, duration: float) -> Path:
    if path.exists() and path.stat().st_size>0: return path
    facts=project.get('facts',{})
    a={x.get('shared_id'):x for x in from_scene.get('layers',[]) if x.get('shared_id')}
    b={x.get('shared_id'):x for x in to_scene.get('layers',[]) if x.get('shared_id')}
    shared=sorted(set(a)&set(b))
    if not shared:
        raise AgentCutError('SHARED_MORPH_EMPTY','shared_morph transition has no matching shared_id layers',from_scene=from_scene.get('id'),to_scene=to_scene.get('id'))
    prepared_a={sid:_prepare_content(a[sid],project,root,facts) for sid in shared}
    prepared_b={sid:_prepare_content(b[sid],project,root,facts) for sid in shared}
    same={sid:_content_signature(a[sid])==_content_signature(b[sid]) for sid in shared}
    frames=max(1,int(math.ceil(float(duration)*fps)))
    path.parent.mkdir(parents=True,exist_ok=True); partial=path.with_name(f'.{path.stem}.partial{path.suffix}'); partial.unlink(missing_ok=True)
    ffmpeg=ensure_binary('ffmpeg')
    proc=subprocess.Popen([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgba','-s',f'{width}x{height}','-r',str(fps),'-i','-','-an','-c:v','qtrle','-pix_fmt','argb',str(partial)],stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for fi in range(frames):
            q=0.0 if frames<=1 else fi/(frames-1)
            q=_ease(q,'ease_in_out')
            canvas=Image.new('RGBA',(width,height),(0,0,0,0))
            for sid in shared:
                la,lb=a[sid],b[sid]
                sa=_state(la,float(la.get('start',0))+max(0,float(la.get('duration',1))-1e-6))
                sb=_state(lb,float(lb.get('start',0)))
                st={k:_lerp(float(sa.get(k,0)),float(sb.get(k,0)),q) for k in ('x','y','scale','opacity','rotation')}
                if same[sid]:
                    _paste_transformed(canvas,prepared_a[sid],st)
                else:
                    _paste_transformed(canvas,prepared_a[sid],st,extra_opacity=1-q)
                    _paste_transformed(canvas,prepared_b[sid],st,extra_opacity=q)
            if proc.stdin is None: raise AgentCutError('GRAPHICS_PIPE_FAILED','Graphics encoder stdin unavailable')
            proc.stdin.write(np.asarray(canvas,dtype=np.uint8).tobytes())
        if proc.stdin: proc.stdin.close()
        stderr=proc.stderr.read().decode(errors='replace') if proc.stderr else ''; code=proc.wait()
        if code!=0: raise AgentCutError('GRAPHICS_RENDER_FAILED','Failed to encode shared morph overlay',stderr=stderr[-4000:],returncode=code)
        if not partial.exists() or partial.stat().st_size<=0: raise AgentCutError('GRAPHICS_RENDER_FAILED','Empty shared morph overlay')
        os.replace(partial,path)
    except Exception:
        proc.kill(); partial.unlink(missing_ok=True); raise
    return path
