-- Fit the actual compiled head silhouette before the native atlas captures it.
-- HUD portraits only: cosmetics, equipment focus and end-of-round poses retain
-- their authored cameras. No camera change is accumulated across requests.
local M = {}

function M.install(mod)
    local bounds = mod:io_dofile("AnimeModelReplacement/scripts/mods/AnimeModelReplacement/portrait_bounds")

    local function fit(self)
        local settings = self._render_settings
        local request = self._active_request
        local context = request and request.render_context
        if not settings or settings.world_name ~= "portrait_world" or self._always_render
            or (context and (context.camera_focus_slot_name or context.use_end_of_round_camera)) then return end
        local spawner = self._profile_spawner
        local subject = spawner and spawner.__anime_portrait_subject
        local spec = subject and bounds[subject.asset]
        local unit = subject and subject.unit
        local world = self._world_spawner
        if not spec or not unit or not Unit.alive(unit) or not world then return end
        if not Unit.has_node(unit, "j_head") then return end
        local node = Unit.node(unit, "j_head")
        local head_position = Unit.world_position(unit, node)
        local head_rotation = Unit.world_rotation(unit, node)
        local camera = world:camera()
        local rotation = world:camera_rotation()
        local right = Quaternion.rotate(rotation, Vector3(1, 0, 0))
        local forward = Quaternion.rotate(rotation, Vector3(0, 1, 0))
        local up = Quaternion.rotate(rotation, Vector3(0, 0, 1))
        local size = request and request.size
        local aspect = (size and size[1] or settings.width or 140) / (size and size[2] or settings.height or 160)
        local tan_y = math.tan(Camera.vertical_fov(camera) * 0.5) * 0.80
        local tan_x = tan_y * aspect
        if tan_y <= 0 or tan_x <= 0 then return end
        local corners = {}
        local lo, hi = {math.huge, math.huge, math.huge}, {-math.huge, -math.huge, -math.huge}
        for x = 1, 2 do for y = 1, 2 do for z = 1, 2 do
            local p = head_position + Quaternion.rotate(head_rotation, Vector3(spec[x][1], spec[y][2], spec[z][3]))
            local point = {Vector3.dot(p, right), Vector3.dot(p, up), Vector3.dot(p, forward)}
            corners[#corners + 1] = point
            for axis = 1, 3 do
                lo[axis] = math.min(lo[axis], point[axis])
                hi[axis] = math.max(hi[axis], point[axis])
            end
        end end end
        local cx, cy, cz = (lo[1]+hi[1])*0.5, (lo[2]+hi[2])*0.5, (lo[3]+hi[3])*0.5
        local distance = 0.25
        for _, p in ipairs(corners) do
            distance = math.max(distance, math.abs(p[1]-cx)/tan_x-(p[3]-cz), math.abs(p[2]-cy)/tan_y-(p[3]-cz))
        end
        world:set_camera_position(right*cx + up*cy + forward*(cz-distance))
        self.__anime_portrait_framed = subject.asset
    end

    mod:hook(CLASS.PortraitUI, "_is_ready_to_capture_request", function(func, self, ...)
        local ready = func(self, ...)
        if ready then fit(self) end
        return ready
    end)
end

return M
