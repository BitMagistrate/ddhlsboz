-- RoadPulse — OSRM 5.27 car profile for Vietnam.
-- Mirrors packages/python/roadpulse_routing/roadpulse_routing/profiles.py:car_vn.
api_version = 4

RP_ALPHA = 0.9
RP_BETA  = 1.5
RP_GAMMA = 0.10

properties = {
    weight_name                = 'duration',
    max_speed_for_map_matching = 120,
    u_turn_penalty             = 12,
    traffic_signal_penalty     = 3,
    use_turn_restrictions      = true,
    weight_precision           = 1,
}

speeds = {
    motorway = 90, motorway_link = 70, trunk = 70, trunk_link = 50,
    primary = 55, primary_link = 45, secondary = 45, secondary_link = 35,
    tertiary = 35, tertiary_link = 30, residential = 25, living_street = 0,
    service = 18, track = 0, unclassified = 30, hem = 0,
}

function process_way(_, way, result)
    local h = way:get_value_by_key('highway')
    local s = speeds[h] or 25
    if s == 0 then result.forward_mode = 'inaccessible' return end
    result.forward_speed = s
    result.backward_speed = s
    if way:get_value_by_key('oneway') == 'yes' then result.backward_speed = -1 end

    local cong = tonumber(way:get_value_by_key('rp:congestion')) or 0
    local flood = tonumber(way:get_value_by_key('rp:flood')) or 0
    local eco = tonumber(way:get_value_by_key('rp:eco')) or 0
    local penalty = 1 + RP_ALPHA*cong + RP_BETA*flood + RP_GAMMA*eco
    result.forward_rate = result.forward_speed / penalty
    result.backward_rate = result.backward_speed / penalty
end

return { setup = function() return profile end, process_way = process_way }
