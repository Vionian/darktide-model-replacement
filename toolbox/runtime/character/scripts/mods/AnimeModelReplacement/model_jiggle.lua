local M = {}

local PROFILES = {
    hair = { mass = 0.5, damping = 15, stiffness = 25, angle = 12, total = 24, carry = 0.60, zeta = 0.55 },
    cloth = { mass = 0.75, damping = 20, stiffness = 35, angle = 8, total = 18, carry = 0.72, zeta = 0.65, hang = true },
    tail = { mass = 0.7, damping = 17, stiffness = 24, angle = 12, total = 28, carry = 0.68, zeta = 0.58 },
}

local function clamp(value, minimum, maximum)
    return math.max(minimum, math.min(maximum, value))
end

local function limit_direction(origin, direction, radians)
    local axis = Vector3.cross(origin, direction)
    local size = Vector3.length(axis)
    local angle = math.acos(clamp(Vector3.dot(origin, direction), -1, 1))
    if angle > radians and size > 1e-7 then
        return Quaternion.rotate(Quaternion.axis_angle(axis / size, radians), origin)
    end
    return direction
end

local function setting(opt, key, fallback)
    local value = tonumber(opt(key))
    return value == nil and fallback or value
end

local function init(unit, config)
    local bones, by_name = {}, {}
    for _, def in ipairs(config.bones or {}) do
        local name, parent_name, group, length = def[1], def[2], def[3], def[4]
        local parent = by_name[parent_name]
        if Unit.has_node(unit, name) and (parent or Unit.has_node(unit, parent_name)) then
            local node = Unit.node(unit, name)
            local bone = {
                node = node,
                parent = parent,
                parent_node = not parent and Unit.node(unit, parent_name) or nil,
                group = group,
                length = length,
                rest = QuaternionBox(Unit.local_rotation(unit, node)),
                lpos = Vector3Box(Unit.local_position(unit, node)),
            }
            bones[#bones + 1] = bone
            by_name[name] = bone
        end
    end
    return { bones = bones, active = false }
end

local function reset(unit, state)
    for _, bone in ipairs(state.bones) do
        Unit.set_local_rotation(unit, bone.node, bone.rest:unbox())
        bone.px = nil
        bone.vx, bone.vy, bone.vz = nil, nil, nil
    end
    state.rx = nil
    state.active = false
end

local function damped_step(displacement, velocity, omega, zeta, dt)
    local alpha = zeta * omega
    local damped = omega * math.sqrt(1 - zeta * zeta)
    local decay = math.exp(-alpha * dt)
    local cosine, sine = math.cos(damped * dt), math.sin(damped * dt)
    local next_displacement = (displacement * cosine + (velocity + displacement * alpha) * (sine / damped)) * decay
    local next_velocity = (velocity * cosine - (velocity * alpha + displacement * (omega * omega)) * (sine / damped)) * decay
    return next_displacement, next_velocity
end

function M.new(opt, config)
    local states = setmetatable({}, { __mode = "k" })
    local api = {}

    function api.update(unit, dt)
        if not (unit and Unit.alive(unit)) then return end
        local state = states[unit]
        if not state then
            state = init(unit, config)
            states[unit] = state
        end
        if opt("jiggle") == false then
            if state.active then reset(unit, state) end
            return
        end
        if not dt or dt <= 0 then return end

        local stiffness_setting = clamp(setting(opt, "jiggle_stiffness", 1), 0.25, 3)
        local damping_setting = clamp(setting(opt, "jiggle_damping", 1), 0.25, 3)
        local limit_setting = clamp(setting(opt, "jiggle_limit", 1), 0.25, 3)
        local hang_setting = math.max(setting(opt, "jiggle_hang", 0.15), 0)
        local root = Unit.world_position(unit, 1)
        local travel = state.rx and root - Vector3(state.rx, state.ry, state.rz) or Vector3(0, 0, 0)
        if dt > 0.15 or Vector3.length(travel) > 1 then
            reset(unit, state)
            travel = Vector3(0, 0, 0)
        end
        state.active = true
        state.rx, state.ry, state.rz = root.x, root.y, root.z
        dt = math.min(dt, 0.05)

        for _, bone in ipairs(state.bones) do
            local profile = PROFILES[bone.group] or PROFILES.cloth
            local amount_key = bone.group == "hair" and "jiggle_hair" or "jiggle_cloth"
            local amount = math.max(setting(opt, amount_key, 1), 0)
            local parent_rot, head, scale
            if bone.parent then
                parent_rot, scale = bone.parent.rot, bone.parent.scale
                head = bone.parent.head + Quaternion.rotate(parent_rot, bone.lpos:unbox()) * scale
            else
                parent_rot = Unit.world_rotation(unit, bone.parent_node)
                head = Unit.world_position(unit, bone.node)
                local local_length = Vector3.length(bone.lpos:unbox())
                scale = local_length > 1e-3 and Vector3.length(head - Unit.world_position(unit, bone.parent_node)) / local_length or 1
                if scale < 1e-4 then scale = 1 end
            end

            local rest_rot = Quaternion.multiply(parent_rot, bone.rest:unbox())
            local rigid_rot = bone.parent and Quaternion.multiply(bone.parent.rigid, bone.rest:unbox()) or rest_rot
            local offset = Quaternion.rotate(rest_rot, Vector3(0, 0, bone.length)) * scale
            local length = Vector3.length(offset)
            local direction = length > 1e-6 and offset / length or Vector3(0, 0, 1)
            local goal = direction
            if profile.hang and hang_setting > 0 then
                local lean = direction + Vector3(0, 0, -0.25 * hang_setting)
                local lean_length = Vector3.length(lean)
                if lean_length > 1e-5 then
                    goal = limit_direction(direction, lean / lean_length, math.rad(3) * hang_setting)
                end
            end

            local world_rot = rest_rot
            if amount <= 0 or length <= 1e-6 then
                bone.px = nil
                bone.vx, bone.vy, bone.vz = nil, nil, nil
            else
                local target = head + goal * length
                local point = bone.px and Vector3(bone.px, bone.py, bone.pz) + travel * profile.carry or target
                local velocity = Vector3(bone.vx or 0, bone.vy or 0, bone.vz or 0)
                if Vector3.length(point - target) > 0.5 then
                    point, velocity = target, Vector3(0, 0, 0)
                end
                local omega = math.sqrt(profile.stiffness / profile.mass) * math.sqrt(stiffness_setting / math.max(amount, 0.25))
                omega = clamp(omega, 0.5, 32)
                local zeta = clamp(profile.zeta + (damping_setting - 1) * 0.18, 0.25, 0.95)
                local displacement, next_velocity = damped_step(point - target, velocity, omega, zeta, dt)
                local next_point = target + displacement
                local next_direction = next_point - head
                local direction_length = Vector3.length(next_direction)
                next_direction = direction_length > 1e-6 and next_direction / direction_length or goal

                local joint_limit = profile.angle
                if length < 0.08 * scale then joint_limit = math.min(joint_limit, 2) end
                local absolute_joint_limit = bone.group == "hair" and 18 or 10
                next_direction = limit_direction(goal, next_direction,
                    math.min(math.rad(joint_limit) * amount * limit_setting, math.rad(absolute_joint_limit)))
                local rigid_direction = Quaternion.rotate(rigid_rot, Vector3(0, 0, 1))
                local absolute_chain_limit = bone.group == "hair" and 30 or 22
                next_direction = limit_direction(rigid_direction, next_direction,
                    math.min(math.rad(profile.total) * amount * limit_setting, math.rad(absolute_chain_limit)))
                next_velocity = next_velocity - next_direction * Vector3.dot(next_velocity, next_direction)

                local axis = Vector3.cross(direction, next_direction)
                local axis_size = Vector3.length(axis)
                local angle = math.acos(clamp(Vector3.dot(direction, next_direction), -1, 1))
                if axis_size > 1e-6 and angle > 1e-5 then
                    world_rot = Quaternion.multiply(Quaternion.axis_angle(axis / axis_size, angle), rest_rot)
                end

                next_point = head + next_direction * length
                bone.px, bone.py, bone.pz = next_point.x, next_point.y, next_point.z
                bone.vx, bone.vy, bone.vz = next_velocity.x, next_velocity.y, next_velocity.z
            end
            Unit.set_local_rotation(unit, bone.node, Quaternion.multiply(Quaternion.inverse(parent_rot), world_rot))
            bone.rot, bone.head, bone.scale, bone.rigid = world_rot, head, scale, rigid_rot
        end
    end

    function api.clear(unit)
        if not unit then return end
        local state = states[unit]
        if state and unit and Unit.alive(unit) then reset(unit, state) end
        states[unit] = nil
    end

    return api
end

return M
