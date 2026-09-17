-- Classic 13.0.2 native luminance schema, captured and render-validated locally.
-- Only the four native range handles are changed on existing simple range masks.
local M={}
M.keys={'lower_none','lower_full','upper_full','upper_none'}
function M.clone(value)
    if type(value)~='table' then return value end
    local out={}; for k,v in pairs(value) do out[k]=M.clone(v) end; return out
end
function M.parse(text,scale)
    if type(text)~='string' then error('Missing luminance range') end
    if scale==100 then
        local _,commas=text:gsub(',','')
        if commas~=3 or text:match('^%s*,') or text:match(',%s*$') or text:match(',%s*,') then
            error('Invalid luminance range: exactly four comma-separated values required')
        end
    elseif text:find(',') then error('Unsupported native luminance range encoding') end
    local values={}
    for token in text:gmatch('[^,%s]+') do
        local n=tonumber(token)
        if not n or n~=n or n<0 or n>scale then error('Invalid luminance range') end
        values[#values+1]=n
    end
    if #values~=4 or values[1]>values[2] or values[2]>values[3] or values[3]>values[4]
        or values[1]==values[4] then error('Luminance range needs four ordered nonempty handles') end
    local out={}; for i,key in ipairs(M.keys) do out[key]=values[i]/scale*100 end
    return out
end
function M.encode(range)
    local parts={}; for _,key in ipairs(M.keys) do parts[#parts+1]=string.format('%.6f',range[key]/100) end
    return table.concat(parts,' ')
end
function M.locate(groups,id)
    local found
    for _,group in pairs(groups or {}) do
        if group.CorrectionID==id then
            if found then error('Duplicate native correction ID') end
            found=group
        end
    end
    return found
end
function M.read(groups,id,strict)
    local group=M.locate(groups,id)
    local masks=group and group.CorrectionMasks
    local mask=type(masks)=='table' and #masks==1 and masks[1]
    local range=mask and mask.CorrectionRangeMask
    if not range or mask.What~='Mask/RangeMask' or range.Type~=2 or range.Version~=3
        or mask.MaskInverted~=false or range.Invert~=false or mask.MaskBlendMode~=0
        or mask.MaskActive~=true or group.CorrectionActive~=true then
        if strict then error('Range writes require one active, non-inverted native luminance tool (schema 3)') end
        return nil
    end
    return M.parse(range.LumRange,1)
end
function M.checkVersion()
    local App=import 'LrApplication'
    local version=App.versionString()
    if version~='13.0.2' and not version:match('^13%.0%.2[%s%[]') then
        error('Luminance schema write is verified only on Classic 13.0.2; use verified UI')
    end
end
function M.build(groups,id,range)
    M.checkVersion()
    local out=M.clone(groups or {})
    if id then
        M.read(out,id,true)
        M.locate(out,id).CorrectionMasks[1].CorrectionRangeMask.LumRange=M.encode(range)
    else
        local uuid=import 'LrUUID'
        local seed=dofile(_PLUGIN.path .. '/LuminanceSeed.lua')
        id=uuid.generateUUID()
        seed.CorrectionID=id
        seed.CorrectionSyncID=uuid.generateUUID():gsub('-','')
        seed.CorrectionMasks[1].MaskID=uuid.generateUUID()
        seed.CorrectionMasks[1].MaskSyncID=uuid.generateUUID():gsub('-','')
        seed.CorrectionMasks[1].CorrectionRangeMask.LumRange=M.encode(range)
        out[#out+1]=seed
    end
    return out,id
end
return M
