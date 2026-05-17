-- RoadPulse — OSRM 5.27 motorbike profile tuned for Vietnam.
--
-- This profile mirrors the Python `roadpulse_routing.profiles.motorbike_vn` so
-- both engines apply the exact same blended cost formula:
--    cost = free_flow_seconds × (1 + α·congestion + β·flood + γ·eco)
-- with α=0.6, β=2.5, γ=0.05.
--
-- The flood/congestion signals are layered on at query time via the
-- ``--algorithm=MLD`` traffic-update mechanism: a CSV is dropped onto a tmpfs
-- volume every 5 minutes and OSRM re-weights edges without rebuilding the
-- contraction hierarchy.

api_version = 4

Set = require('lib/set')
Sequence = require('lib/sequence')

properties = {
    weight_name                   = 'duration',
    max_speed_for_map_matching    = 90,
    use_turn_restrictions         = true,
    continue_straight_at_waypoint = true,
    left_hand_driving             = false,
    traffic_signal_penalty        = 2,
    u_turn_penalty                = 8,
    weight_precision              = 1,
}

-- α (congestion), β (flood), γ (eco). Must be kept in sync with
-- packages/python/roadpulse_routing/roadpulse_routing/profiles.py.
RP_ALPHA = 0.6
RP_BETA  = 2.5
RP_GAMMA = 0.05

speeds = {
    motorway       = 0,    -- bikes forbidden on highways in VN
    motorway_link  = 0,
    trunk          = 50,
    trunk_link     = 45,
    primary        = 45,
    primary_link   = 40,
    secondary      = 38,
    secondary_link = 33,
    tertiary       = 32,
    tertiary_link  = 28,
    residential    = 28,
    living_street  = 18,
    service        = 22,
    track          = 18,
    unclassified   = 30,
    hem            = 14, -- VN-specific: narrow alley (≤ 2m wide)
}

restricted_access = Set { 'motorway', 'motorway_link' }

function process_way(profile, way, result)
    local highway = way:get_value_by_key('highway')
    if not highway then return end
    if restricted_access[highway] then result.forward_mode = 'inaccessible' return end

    local speed = speeds[highway] or 25
    result.forward_speed = speed
    result.backward_speed = speed
    if way:get_value_by_key('oneway') == 'yes' then
        result.backward_speed = -1
    end

    -- The traffic-update CSV stores per-osm-edge: congestion ∈ [0,1],
    -- flood ∈ [0,1], eco ∈ [0,1]. They are surfaced here as edge tags.
    local cong = tonumber(way:get_value_by_key('rp:congestion')) or 0
    local flood = tonumber(way:get_value_by_key('rp:flood')) or 0
    local eco = tonumber(way:get_value_by_key('rp:eco')) or 0

    local penalty = 1 + RP_ALPHA*cong + RP_BETA*flood + RP_GAMMA*eco
    result.forward_rate = result.forward_speed / penalty
    result.backward_rate = result.backward_speed / penalty
end

function process_node() return nil end
function process_turn(_, turn) turn.duration = turn.duration + properties.u_turn_penalty end

return {
    setup            = function() return profile end,
    process_way      = process_way,
    process_node     = process_node,
    process_turn     = process_turn,
}
