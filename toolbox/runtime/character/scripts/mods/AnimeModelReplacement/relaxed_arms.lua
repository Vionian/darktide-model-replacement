-- 3P only. Bounded source-proportion retarget, with native animation as pole.
local M = {}
local function clamp(x,a,b) return math.max(a,math.min(b,x)) end
local function limited(v,max_length)
    local length=Vector3.length(v)
    return length>max_length and v*(max_length/length) or v
end
local function align(a,b)
    local al,bl=Vector3.length(a),Vector3.length(b)
    if al<0.000001 or bl<0.000001 then return Quaternion.identity() end
    a,b=a/al,b/bl
    local axis=Vector3.cross(a,b)
    local length=Vector3.length(axis)
    local dot=clamp(Vector3.dot(a,b),-1,1)
    if length>0.000001 then return Quaternion.axis_angle(axis/length,math.acos(dot)) end
    if dot<0 then
        local reference=math.abs(a.x)<0.8 and Vector3(1,0,0) or Vector3(0,1,0)
        axis=Vector3.cross(a,reference)
        return Quaternion.axis_angle(axis/Vector3.length(axis),math.pi)
    end
    return Quaternion.identity()
end
function M.root_position(config,name,position,driver,node)
    local c=config.arm_relax
    if c and (name=='j_leftarm' or name=='j_rightarm') then
        local delta=(Unit.world_position(driver,node)-position)*c.native_root_blend
        return position+limited(delta,c.max_root_shift)
    end
    return position
end
function M.update(unit,driver,config,poses,bones,by_name,root_rotation)
    local c=config.arm_relax
    if not c then return end
    local metrics={}
    for _,side in ipairs({'left','right'}) do
        local prefix='j_'..side
        local upper,lower,hand=by_name[prefix..'arm'],by_name[prefix..'forearm'],by_name[prefix..'hand']
        if upper and lower and hand then
            local a,b,h=poses[upper.node],poses[lower.node],poses[hand.node]
            local l1,l2=Vector3.length(b.position-a.position),Vector3.length(h.position-b.position)
            local native_hand=Unit.world_position(driver,hand.driver_node)
            local native_arm=Unit.world_position(driver,upper.driver_node)
            local native_elbow=Unit.world_position(driver,lower.driver_node)
            local goal=h.position+(native_hand-h.position)*c.native_wrist_blend
            local direction=goal-a.position
            local distance=Vector3.length(direction)
            if distance>0.000001 then
                local axis=direction/distance
                local up=Quaternion.rotate(root_rotation,Vector3(0,0,1))
                local native_direction=native_hand-native_arm
                local native_span=Vector3.length(native_direction)
                local lowered=native_span>0.000001 and clamp((-Vector3.dot(native_direction/native_span,up)-0.55)/0.35,0,1) or 0
                local bend_floor=c.minimum_relaxed_bend_degrees*math.pi/180*lowered
                local reach=math.sqrt(l1*l1+l2*l2+2*l1*l2*math.cos(bend_floor))
                local span=clamp(distance,math.abs(l1-l2)+0.000001,math.max(math.abs(l1-l2)+0.000001,reach-0.000001))
                local along=(l1*l1-l2*l2+span*span)/(2*span)
                local height=math.sqrt(math.max(0,l1*l1-along*along))
                local pole=b.position+(native_elbow-b.position)*c.native_wrist_blend-a.position
                pole=pole-axis*Vector3.dot(pole,axis)
                if Vector3.length(pole)<0.000001 then
                    pole=Quaternion.rotate(root_rotation,Vector3(0,-1,0))
                    pole=pole-axis*Vector3.dot(pole,axis)
                end
                if Vector3.length(pole)<0.000001 then
                    pole=Vector3.cross(axis,up)
                end
                local bp=a.position+axis*along+pole*(height/math.max(Vector3.length(pole),0.000001))
                local hp=a.position+axis*span
                local ar=Quaternion.multiply(align(b.position-a.position,bp-a.position),a.rotation)
                local br=Quaternion.multiply(align(h.position-b.position,hp-bp),b.rotation)
                local hand_shift=hp-h.position
                local updates={
                    [upper.def.name]={position=a.position,rotation=ar},
                    [lower.def.name]={position=bp,rotation=br},
                    [hand.def.name]={position=hp,rotation=h.rotation},
                }
                -- Palm orientation and native finger gestures are retained.
                for _,bone in ipairs(bones) do
                    local name=bone.def.name
                    if name~=hand.def.name and (string.sub(name,1,#prefix+4)==prefix..'hand' or string.sub(name,1,#prefix+6)==prefix..'inhand') then
                        local p=poses[name]
                        updates[name]={position=p.position+hand_shift,rotation=p.rotation}
                    end
                end
                for _,bone in ipairs(bones) do
                    local p=updates[bone.def.name]
                    if p then
                        local parent=poses[bone.parent]
                        local pp,pr=parent.position,parent.rotation
                        Unit.set_local_position(unit,bone.node,Quaternion.rotate(Quaternion.inverse(pr),p.position-pp))
                        Unit.set_local_rotation(unit,bone.node,Quaternion.multiply(Quaternion.inverse(pr),p.rotation))
                        poses[bone.node]=p;poses[bone.def.name]=p
                    end
                end
                metrics[side]={upper_length=l1,forearm_length=l2,lowered=lowered,
                    bend_degrees=math.acos(clamp((span*span-l1*l1-l2*l2)/(2*l1*l2),-1,1))*180/math.pi,
                    wrist_shift=Vector3.length(hand_shift)}
            end
        end
    end
    poses.arm_relax_metrics=metrics
end
return M
