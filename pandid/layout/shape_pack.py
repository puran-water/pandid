"""Pack measured assembly footprints without treating their empty corners as ink.

The grid rounds occupied rectangles outward. It never scales a symbol, moves
a member within its assembly, or reduces an instrument/lettering reservation.
"""
import math


def pack(shapes, width, height, *, step=5., gap=20., obstacles=(), below=(), links=()):
    nx,ny=math.floor(width/step),math.floor(height/step)
    masks={}
    for name,w,h,parts in shapes:
        sw,sh=math.ceil((w+gap)/step),math.ceil((h+gap)/step)
        rows=[0]*sh
        for x,y,pw,ph in parts:
            # Subtracting a measured balloon pad from its translated frame
            # can leave -2.8e-14 at the origin. It is zero geometric distance,
            # but floor() turns it into a negative bit index. Retain genuine
            # negative extents as an invalid assembly, never clip its ink.
            if -1e-9 < x < 0:x=0.
            if -1e-9 < y < 0:y=0.
            if x<0 or y<0:
                raise ValueError('ASSEMBLY_FOOTPRINT_OUTSIDE_ENVELOPE: '+str(name))
            left,top=math.floor(x/step),math.floor(y/step)
            right,bottom=math.ceil((x+pw+gap)/step),math.ceil((y+ph+gap)/step)
            bits=((1<<(right-left))-1)<<left
            for row in range(top,min(sh,bottom)):
                rows[row] |= bits
        masks[name]=(sw,sh,tuple((i,bits) for i,bits in enumerate(rows) if bits))
    area={key:sum(bits.bit_count() for _,bits in rows) for key,(_,_,rows) in masks.items()}
    children={lower for upper,lower,clearance in below}
    orders=[lambda v:(-area[v[0]],-v[2],v[0]),
            lambda v:(-v[2],-v[1],v[0]),lambda v:(-v[1],-v[2],v[0]),
            lambda v:(v[0] in children,-area[v[0]],v[0])]
    # Dense mixed footprints can need a different greedy order despite ample
    # paper. These bounded, reproducible starts change placement only.
    import random
    for seed in range(24):
        rng=random.Random(seed)
        weights={key:rng.uniform(.45,1.55) for key in sorted(masks)}
        orders.append(lambda v,weights=weights:(-area[v[0]]*weights[v[0]],v[0]))
    dimensions={name:(w,h) for name,w,h,_ in shapes}
    candidates=[]
    for order in orders:
        occupied=[0]*ny
        for x,y,w,h in obstacles:
            left,right=max(0,math.floor(x/step)),min(nx,math.ceil((x+w)/step))
            top,bottom=max(0,math.floor(y/step)),min(ny,math.ceil((y+h)/step))
            if right>left:
                for row in range(top,bottom):occupied[row] |= ((1<<(right-left))-1)<<left
        result={}
        for name,w,h,_ in sorted(shapes,key=order):
            sw,sh,rows=masks[name]
            found=None
            for y in range(ny-sh+1):
                actual_y=y*step+gap/2
                if any((name==lower and actual_y <
                        (result[upper][1]+dimensions[upper][1] if upper in result else dimensions[upper][1])+clearance)
                       or (name==upper and lower in result and
                           actual_y+h+clearance>result[lower][1])
                       for upper,lower,clearance in below):
                    continue
                for x in range(nx-sw+1):
                    if not any(occupied[y+dy] & (bits<<x) for dy,bits in rows):
                        found=x,y
                        break
                if found is not None:
                    break
            if found is None:
                break
            x,y=found
            for dy,bits in rows:occupied[y+dy] |= bits<<x
            result[name]=(x*step+gap/2,y*step+gap/2)
        if len(result)==len(shapes):
            if not links:
                return result
            length=sum(abs(result[a][0]+dimensions[a][0]/2-result[b][0]-dimensions[b][0]/2)
                       +abs(result[a][1]+dimensions[a][1]/2-result[b][1]-dimensions[b][1]/2)
                       for a,b in links if a in result and b in result)
            candidates.append((length,len(candidates),result))
    return min(candidates,key=lambda item:item[:2])[2] if candidates else None
