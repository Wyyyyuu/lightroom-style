-- Encoder only. The bridge never evaluates a request as Lua code.
local M = {}
local escapes = { ['"'] = '\\"', ['\\'] = '\\\\', ['\b'] = '\\b', ['\f'] = '\\f', ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t' }
local function quote(value)
    return '"' .. value:gsub('[%z\1-\31\\"]', function(c)
        return escapes[c] or string.format('\\u%04x', string.byte(c))
    end) .. '"'
end
function M.encode(value, seen)
    local kind = type(value)
    if kind == 'nil' then return 'null' end
    if kind == 'string' then return quote(value) end
    if kind == 'boolean' then return value and 'true' or 'false' end
    if kind == 'number' then
        if value ~= value or value == math.huge or value == -math.huge then return 'null' end
        return tostring(value)
    end
    if kind ~= 'table' then error('Unsupported JSON type: ' .. kind) end
    seen = seen or {}
    if seen[value] then error('Circular JSON table') end
    seen[value] = true
    local keys, parts = {}, {}
    for key in pairs(value) do
        if type(key) ~= 'string' then error('JSON objects require string keys') end
        keys[#keys + 1] = key
    end
    table.sort(keys)
    for _, key in ipairs(keys) do parts[#parts + 1] = quote(key) .. ':' .. M.encode(value[key], seen) end
    seen[value] = nil
    return '{' .. table.concat(parts, ',') .. '}'
end
return M
