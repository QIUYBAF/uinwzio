from __future__ import annotations
from pathlib import Path
from PIL import Image

def split_2x2(input_path, output_dir, *, fmt="png"):
    src=Path(input_path); out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    with Image.open(src) as im:
        im.load(); w,h=im.size; xs=(0,w//2,w); ys=(0,h//2,h); files=[]
        for r in range(2):
            for c in range(2):
                tile=im.crop((xs[c],ys[r],xs[c+1],ys[r+1])); name=f"r{r+1}c{c+1}.{fmt.lower()}"; path=out/name
                kw={"quality":95,"subsampling":0} if fmt.lower() in {"jpg","jpeg"} else {}
                tile.save(path,**kw); files.append({"id":f"r{r+1}c{c+1}","path":str(path),"size":list(tile.size),"box":[xs[c],ys[r],xs[c+1],ys[r+1]]})
    return {"schema":"agentcut-image-tiles-v1","source":str(src),"source_size":[w,h],"layout":"2x2_exact","files":files,"instruction":"Preserve composition, perspective, geometry, crop boundary and lighting continuity; refine detail only."}

def stitch_2x2(output_path, tiles):
    if len(tiles)!=4: raise ValueError("requires exactly four tiles in r1c1,r1c2,r2c1,r2c2 order")
    ims=[]
    try:
        for p in tiles:
            im=Image.open(p); im.load(); ims.append(im.convert("RGBA"))
        left=max(ims[0].width,ims[2].width); right=max(ims[1].width,ims[3].width); top=max(ims[0].height,ims[1].height); bottom=max(ims[2].height,ims[3].height)
        canvas=Image.new("RGBA",(left+right,top+bottom),(0,0,0,0))
        for im,pos in zip(ims,((0,0),(left,0),(0,top),(left,top))): canvas.paste(im,pos)
        out=Path(output_path); out.parent.mkdir(parents=True,exist_ok=True)
        if out.suffix.lower() in {".jpg",".jpeg"}: canvas.convert("RGB").save(out,quality=95,subsampling=0)
        else: canvas.save(out)
        return {"schema":"agentcut-image-tiles-v1","output":str(out),"size":list(canvas.size),"order":["r1c1","r1c2","r2c1","r2c2"]}
    finally:
        for im in ims: im.close()
