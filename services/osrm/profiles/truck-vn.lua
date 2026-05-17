-- RoadPulse — OSRM 5.27 HGV profile for Vietnam.
-- Mirrors packages/python/roadpulse_routing/roadpulse_routing/profiles.py:truck_vn.
api_version = 4

RP_ALPHA = 1.0
RP_BETA  = 1.2
RP_GAMMA = 0.18

properties = {
    weight_name                = 'duration',
    max_speed_for_map_matching = 100,
    u_turn_penalty             = 25,
    traffic_signal_penalty     = 4,
    use_turn_restrictions      = true,
    weight_precision           = 1,
}

speeds = {
    motorway = 80, motorway_link = 55, trunk = 60, trunk_link = 45,
    primary = 50, primary_link = 40, secondary = 35, secondary_link = 30,
    tertiary = 28, tertiary_link = 24, residential = 18, living_street = 0,
    service = 0, track = 0, unclassified = 25, hem = 0,
}

function process_way(_, way, result)
    local h = way:get_value_by_key('highway')
    local s = speeds[h] or 25
    if s == 0 then result.forward_mode = 'inaccessible' return end
    -- Respect curfew-tag for inner-HCMC truck restrictions.
    if way:get_value_by_key('hgv') == 'no' then result.forward_mode = 'inaccessible' return end

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
