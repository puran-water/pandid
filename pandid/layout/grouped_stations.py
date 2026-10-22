"""Keep a grouped PFD device and its witnessed parallel tapping paths together.

A projected pair has one equipment appearance, two real instrument taps on
each side and explicit fan headers. Treating those headers as unrelated boxes
scattered a single filter station across the sheet. No role or path is removed.
"""
from pandid.geometry import Frame
from pandid.portgeom import port_point
from pandid.layout.stages import slot
from pandid.layout.halo import Pad
from pandid.layout.operating_banks import Assembly


def stations(fs, membership, pads):
    metadata=fs.drawio_metadata.get('units',{})
    material=[s for s in fs.streams if s.kind=='material']
    result,claimed=[],set()
    for unit in membership:
        meta=metadata.get(unit.name,{})
        if not meta.get('attributes',{}).get('equipment-group'):
            continue
        sides=[]
        for incoming in (True,False):
            stems=[s for s in material if (s.dest.owner if incoming else s.source.owner) is unit
                   and metadata.get((s.source.owner if incoming else s.dest.owner).name,{})
                   .get('attributes',{}).get('projection-for')==meta.get('id')]
            if len(stems)!=1:
                break
            stem=stems[0]
            fan=stem.source.owner if incoming else stem.dest.owner
            branches=[s for s in material if s is not stem
                      and (s.dest.owner if incoming else s.source.owner) is fan]
            taps=[s.source.owner if incoming else s.dest.owner for s in branches]
            if len(taps)<2 or any(t.kind!='junction' for t in taps):
                break
            outside=[]
            for tap in taps:
                edges=[s for s in material if (s.dest.owner if incoming else s.source.owner) is tap]
                if len(edges)>1:
                    edges=[s for s in edges if s.flow_class=='main']
                if len(edges)!=1:
                    break
                outside.append(edges[0])
            if len(outside)!=len(taps):
                break
            outers={s.source.owner if incoming else s.dest.owner for s in outside}
            if len(outers)!=1 or next(iter(outers)).kind!='junction':
                break
            sides.append((incoming,stem,fan,branches,taps,outside,next(iter(outers))))
        if len(sides)!=2:
            continue
        members={unit,*[v for _,_,fan,_,taps,_,outer in sides for v in [fan,*taps,outer]]}
        if members & claimed or any(v not in membership for v in members):
            continue
        if len({membership[v] for v in members})!=1:
            continue
        us=slot(unit);up=pads.get(unit,Pad())
        frames={unit:(up.west,up.north,us.w,us.h)}
        # Unnumbered PFDs need nozzle approach, not a line-number caption bay.
        gap=25.
        for incoming,stem,fan,branches,taps,outside,outer in sides:
            sign=-1 if incoming else 1
            endpoint=stem.dest if incoming else stem.source
            ux,uy=port_point(unit,Frame(x=up.west,y=up.north,w=us.w,h=us.h),endpoint.name)
            pitch=max(slot(t).h+pads.get(t,Pad()).north+pads.get(t,Pad()).south for t in taps)
            clearance=fs.layout_options.parallel_train_clearance
            pitch=max(140.,pitch+100.) if clearance is None else pitch+clearance
            axes=[uy+(i-(len(taps)-1)/2)*pitch for i in range(len(taps))]
            fw=slot(fan).w;fh=axes[-1]-axes[0]+24
            fx=ux+sign*(gap+(up.west if incoming else up.east))-(fw if incoming else 0)
            fy=axes[0]-12
            fan._operating_header=True
            fan._operating_port_y={}
            fan._operating_header_height=fh
            fan._operating_port_y[(stem.source if incoming else stem.dest).name]=uy-fy
            for edge,y in zip(branches,axes):
                fan._operating_port_y[(edge.dest if incoming else edge.source).name]=y-fy
            frames[fan]=(fx,fy,fw,fh)
            extent=fx if incoming else fx+fw
            tap_width=max(slot(t).w+pads.get(t,Pad()).west+pads.get(t,Pad()).east for t in taps)
            bay=extent+sign*gap-(tap_width if incoming else 0)
            for tap,y,branch,out in zip(taps,axes,branches,outside):
                ts,pad=slot(tap),pads.get(tap,Pad())
                px=bay+pad.west
                main_in=out.dest if incoming else branch.dest
                main_out=branch.source if incoming else out.source
                selected={main_in.name:ts.h/2,main_out.name:ts.h/2}
                spare=[p for p in tap.ports if p not in selected]
                for i,name in enumerate(spare):selected[name]=ts.h/2+(i+1)*60
                th=max(ts.h,max(selected.values())+12)
                tap._operating_header=True
                tap._operating_port_y=selected
                tap._operating_header_height=th
                frames[tap]=(px,y-ts.h/2,ts.w,th)
            ow=slot(outer).w;oy=axes[0]-12
            ox=bay-gap-ow if incoming else bay+tap_width+gap
            selected={(edge.source if incoming else edge.dest).name:y-oy for edge,y in zip(outside,axes)}
            other_side=[p for p in outer.ports.values() if p.name not in selected
                        and p.direction==('inlet' if incoming else 'outlet')]
            for i,p in enumerate(other_side):
                selected[p.name]=12+(fh-24)*(i/(len(other_side)-1) if len(other_side)>1 else .5)
            for i,p in enumerate(p for p in outer.ports.values() if p.name not in selected):
                selected[p.name]=axes[-1]-oy+(i+1)*60
            outer._operating_header=True
            outer._operating_port_y=selected
            outer._operating_header_height=max(fh,max(selected.values())+12)
            frames[outer]=(ox,oy,ow,outer._operating_header_height)
        left=min(x-pads.get(u,Pad()).west for u,(x,y,w,h) in frames.items())
        top=min(y-pads.get(u,Pad()).north for u,(x,y,w,h) in frames.items())
        right=max(x+w+pads.get(u,Pad()).east for u,(x,y,w,h) in frames.items())
        bottom=max(y+h+pads.get(u,Pad()).south for u,(x,y,w,h) in frames.items())
        frames={u:(x-left,y-top,w,h) for u,(x,y,w,h) in frames.items()}
        result.append(Assembly('grouped:'+unit.name,tuple(frames),frames,right-left,bottom-top))
        claimed.update(frames)
    return result
