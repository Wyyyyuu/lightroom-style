-- Native mask controls with a separately validated luminance schema adapter.
local M = {}
local function canonical(value)
    if type(value) ~= 'table' then
        if type(value) == 'number' or type(value) == 'string' or type(value) == 'boolean' or value == nil then return value end
        error('Unsupported develop-state value')
    end
    local out = {}
    for k,v in pairs(value) do out[type(k) .. ':' .. tostring(k)] = canonical(v) end
    return out
end

-- UI controls can settle to float32 representations after an SDK write.
local function sameLocal(a,b)
    if type(a)~=type(b) then return false end
    if type(a)=='number' then return a==a and b==b and math.abs(a-b)<=0.00001 end
    if type(a)~='table' then return a==b end
    for k,v in pairs(a) do if not sameLocal(v,b[k]) then return false end end
    for k in pairs(b) do if a[k]==nil then return false end end
    return true
end

function M.execute(photo, catalog, fields, progress, ctx)
    local App = import 'LrApplication'
    local D = import 'LrDevelopController'
    local V = import 'LrApplicationView'
    local MD5 = import 'LrMD5'
    local Tasks = import 'LrTasks'
    local Json = ctx.json
    local Lum=dofile(_PLUGIN.path .. '/Luminance.lua')
    local mutation = fields.action ~= 'mask-read'
    local maskingReady=false
    local localParams={'local_ToningLuminance','local_Temperature','local_Tint','local_Exposure',
        'local_Contrast','local_Highlights','local_Shadows','local_Clarity','local_Saturation',
        'local_ToningHue','local_ToningSaturation','local_Sharpness','local_LuminanceNoise',
        'local_Moire','local_Defringe','local_Blacks','local_Whites','local_Dehaze','local_Texture',
        'local_Hue','local_Amount','local_Maincurve','local_Redcurve','local_Greencurve',
        'local_Bluecurve','local_PointColors','local_Grain','local_RefineSaturation'}
    for _,name in ipairs({'getAllMasks','getSelectedMask','getSelectedTool','selectMask','goToMasking','getValue','getRange','setValue','createNewMask'}) do
        if type(D[name]) ~= 'function' then error('Mask API unavailable: ' .. name) end
    end
    if not photo:getRawMetadata('isVirtualCopy') or not (photo:getFormattedMetadata('copyName') or ''):match('^PhotoStyle%-') then
        error('Mask operations require a PhotoStyle- virtual copy; originals are protected')
    end
    local expected = mutation and ctx.required(fields,'expected_mask_revision') or nil
    local subtype = fields.mask_type
    local maskId = fields.mask_id
    if fields.action == 'mask-create' then
        if subtype ~= 'subject' and subtype ~= 'sky' and subtype ~= 'background' and subtype ~= 'luminance' then error('Unsupported automatic mask type') end
        if maskId then error('New mask must not specify an existing ID') end
    elseif fields.action == 'mask-adjust' then
        maskId = ctx.required(fields,'mask_id')
        if subtype then error('Existing mask must not specify a new type') end
    end
    local range=fields.luminance_range and Lum.parse(fields.luminance_range,100) or nil
    if range and (not mutation or (fields.action=='mask-create' and subtype~='luminance')) then error('Range only applies to luminance mask writes') end
    if fields.action=='mask-create' and subtype=='luminance' and not range then error('Luminance creation requires an explicit range') end
    if range then Lum.checkVersion() end
    local targets = {}
    if mutation then
        for _,key in ipairs({'clarity','texture'}) do
            if fields[key] then targets[key] = ctx.number(fields[key],key,{-100,0}) end
        end
        if not next(targets) and not range then error('Supply local clarity, texture, or luminance range') end
    end
    for key in pairs(fields) do
        if key:match('^set%.') or key:match('^expect%.') then error('Mask actions cannot mix global slider writes') end
    end
    local function active()
        ctx.fresh(fields,catalog)
        local currentCatalog=App.activeCatalog()
        if not currentCatalog or currentCatalog:getPath()~=catalog:getPath() then error('Active catalog changed during mask operation') end
        local selected,target = currentCatalog:getTargetPhotos(),currentCatalog:getTargetPhoto()
        if not target or tostring(target.localIdentifier) ~= tostring(photo.localIdentifier)
            or #selected ~= 1 or tostring(selected[1].localIdentifier) ~= tostring(photo.localIdentifier)
            or V.getCurrentModuleName() ~= 'develop'
            or (maskingReady and D.getSelectedTool()~='masking') then
            error('Exact single-photo Develop selection changed; mask operation stopped')
        end
    end
    -- Native SDK selection; never infer a target from whatever was selected.
    ctx.fresh(fields,catalog)
    local folder = catalog:getFolderByPath((import 'LrPathUtils').parent(fields.path))
    if not folder or not catalog:setActiveSources({folder}) then error('Cannot activate mask target folder') end
    catalog:setSelectedPhotos(photo,{})
    V.switchToModule('develop')
    local ready = false
    for attempt=1,40 do
        local selected,target = catalog:getTargetPhotos(),catalog:getTargetPhoto()
        if target and tostring(target.localIdentifier)==tostring(photo.localIdentifier) and #selected==1
            and tostring(selected[1].localIdentifier)==tostring(photo.localIdentifier)
            and V.getCurrentModuleName()=='develop' then ready=true; break end
        ctx.fresh(fields,catalog); Tasks.sleep(0.1)
    end
    if not ready then error('Cannot establish single-photo Develop selection') end
    active(); D.goToMasking()
    for attempt=1,40 do
        active()
        if D.getSelectedTool()=='masking' then maskingReady=true; break end
        Tasks.sleep(0.1)
    end
    if not maskingReady then error('Masking tool did not become active') end
    active()
    local function inventory(allowPending)
        active()
        local raw = D.getAllMasks()
        if raw==nil and allowPending then return nil end
        if type(raw) ~= 'table' then error('Mask inventory unavailable') end
        local masks={}
        for index,entry in pairs(raw) do
            if type(index)~='number' or type(entry)~='table' or type(entry.ID)~='string'
                or type(entry.Tools)~='table' or masks[entry.ID] then
                progress.mask_inventory=canonical(raw)
                error('Unsupported mask inventory representation')
            end
            masks[entry.ID]=entry
        end
        return masks
    end
    local function select(id)
        active()
        if type(id) ~= 'string' or not inventory()[id] then error('Mask ID not present on this photo') end
        if D.getSelectedMask()~=id then D.selectMask(id) end
        if D.getSelectedMask() ~= id then error('Exact mask selection failed') end
        active()
    end
    local function selected(id)
        active()
        if D.getSelectedMask() ~= id then error('Mask selection changed before local adjustment') end
    end
    local function values(id)
        select(id)
        local out = {}
        for _,key in ipairs({'clarity','texture'}) do
            selected(id)
            local param = key=='clarity' and 'local_Clarity' or 'local_Texture'
            local lo,hi = D.getRange(param)
            local val = D.getValue(param)
            if type(lo)~='number' or type(hi)~='number' or lo>=0 or hi<=0 or type(val)~='number' or val~=val then
                error('Local slider unavailable or unsupported range: ' .. param)
            end
            out[key] = val < 0 and val / (-lo) * 100 or val / hi * 100
        end
        return out
    end
    local function controlState(id)
        select(id)
        local out={}
        for _,param in ipairs(localParams) do
            selected(id)
            local ok,value=Tasks.pcall(function() return D.getValue(param) end)
            selected(id)
            if ok and value~=nil then out[param]=canonical(value) end
        end
        return out
    end
    local function revision(id)
        local localValues = id and values(id) or {}
        local state = {develop=canonical(photo:getDevelopSettings()),masks=canonical(inventory()),
                       mask_id=id or '',local_values=localValues}
        local digest=MD5.digest(Json.encode(state))
        return (digest:gsub('.',function(c) return string.format('%02x',string.byte(c)) end))
    end
    local function response(id)
        local masks=inventory()
        local ids={}
        for key,entry in pairs(masks) do
            local count=0; for _ in pairs(entry.Tools) do count=count+1 end
            ids[key]={tool_count=count,hidden=entry.Hidden}
        end
        local nativeRange=id and Lum.read(photo:getDevelopSettings().MaskGroupBasedCorrections,id,false)
        local result={luminance_range=nativeRange or nil,mask_id=id,mask_settings=id and values(id) or nil,masks=ids,mask_revision=revision(id)}
        if id and fields.action=='mask-read' then
            result.local_controls=controlState(id)
            result.local_ranges={}
            for _,param in ipairs(localParams) do
                local ok,lo,hi=Tasks.pcall(function() return D.getRange(param) end)
                if ok and type(lo)=='number' and type(hi)=='number' then result.local_ranges[param]={min=lo,max=hi} end
            end
        end
        return result
    end
    if not mutation then return response(maskId) end
    local rawBefore=photo:getDevelopSettings()
    if not tonumber(rawBefore.ProcessVersion) or tonumber(rawBefore.ProcessVersion)<11 then
        error('Texture requires a modern process version; automatic process upgrades are not allowed')
    end
    if rawBefore.HDREditMode==true or (type(rawBefore.HDREditMode)=='number' and rawBefore.HDREditMode~=0) then
        error('HDR mask editing has not been validated')
    end
    if revision(maskId) ~= expected then error('Stale expected mask revision') end
    local function globalState()
        local state={}
        for key,value in pairs(photo:getDevelopSettings()) do
            if key~='MaskGroupBasedCorrections' and key~='PaintBasedCorrections'
                and key~='GradientBasedCorrections' and key~='CircularGradientBasedCorrections' then
                state[key]=canonical(value)
            end
        end
        return Json.encode(state)
    end
    if range and maskId then Lum.read(rawBefore.MaskGroupBasedCorrections,maskId,true) end
    local rawGroupsBefore=Lum.clone(rawBefore.MaskGroupBasedCorrections or {})
    local beforeGlobal=globalState()
    local oldInventory=canonical(inventory())
    local oldIds={}
    for id in pairs(inventory()) do oldIds[id]=true end
    local oldValues={}
    for id in pairs(oldIds) do oldValues[id]=controlState(id) end
    if maskId then select(maskId) end
    local snapshot='PhotoStyle-before-' .. fields.id
    progress.snapshot_name=snapshot
    ctx.write(catalog,'Lightroom Style: preserve local mask',function()
        active()
        if revision(maskId) ~= expected then error('Mask context changed before snapshot') end
        if not photo:createDevelopSnapshot(snapshot,false) then error('Could not create mask recovery snapshot') end
    end)
    active()
    if revision(maskId) ~= expected then error('Mask context changed before write') end
    local nativeRangeId
    if range then
        local updates
        updates,nativeRangeId=Lum.build(photo:getDevelopSettings().MaskGroupBasedCorrections,maskId,range)
        ctx.write(catalog,'Lightroom Style: luminance range',function()
            active()
            if revision(maskId)~=expected then error('Mask context changed before range write') end
            progress.luminance_range_requested=true
            if not maskId then progress.planned_mask_id=nativeRangeId end
            photo:applyDevelopSettings({MaskGroupBasedCorrections=updates},'Lightroom Style luminance '..fields.id,false)
            progress.parameters_applied=true
        end)
    end
    if fields.action == 'mask-create' then
        if not nativeRangeId then D.createNewMask('aiSelection',subtype) end
        progress.mask_creation_requested=true
        -- AI completion is bounded and is never retried with another create.
        for attempt=1,160 do
            active()
            local candidate=nativeRangeId or D.getSelectedMask()
            local masks=inventory(true)
            if masks and type(candidate)=='string' and not oldIds[candidate] and masks[candidate] and next(masks[candidate].Tools) then
                maskId=candidate; break
            end
            Tasks.sleep(0.1)
        end
        if not maskId then error('Mask creation not confirmed; reconcile request and inventory, do not create again') end
        progress.created_mask_id=maskId
        local created=0
        for id in pairs(inventory()) do if not oldIds[id] then created=created+1 end end
        if created~=1 then error('Expected exactly one new mask; inspect snapshot') end
        select(maskId)
    end
    if range then
        local actual=Lum.read(photo:getDevelopSettings().MaskGroupBasedCorrections,nativeRangeId,true)
        for key,value in pairs(range) do
            if math.abs(actual[key]-value)>0.00011 then error('Luminance range readback mismatch') end
        end
        -- Compare complete pre-existing native corrections, including geometry.
        -- For an adjusted range, only its four handles may differ.
        local afterGroups=photo:getDevelopSettings().MaskGroupBasedCorrections
        for _,old in pairs(rawGroupsBefore) do
            local expectedGroup=Lum.clone(old)
            if old.CorrectionID==nativeRangeId then expectedGroup.CorrectionMasks[1].CorrectionRangeMask.LumRange=Lum.encode(range) end
            if Json.encode(canonical(Lum.locate(afterGroups,old.CorrectionID)))~=Json.encode(canonical(expectedGroup)) then
                error('Unrelated native correction data changed during range write')
            end
        end
    end
    -- Recheck protected state after creation, before touching local sliders.
    if globalState()~=beforeGlobal then error('Global settings changed during mask creation') end
    for id in pairs(oldIds) do
        if not sameLocal(controlState(id),oldValues[id]) then
            error('Existing local mask changed during creation; inspect snapshot')
        end
    end
    select(maskId)
    if inventory()[maskId].Hidden then error('Selected mask is hidden; enable it through verified UI') end
    values(maskId)
    local targetState=controlState(maskId)
    local function correctionState(geometryOnly)
        local state={}
        local develop=photo:getDevelopSettings()
        for _,key in ipairs({'MaskGroupBasedCorrections','PaintBasedCorrections','GradientBasedCorrections','CircularGradientBasedCorrections'}) do
            state[key]=Lum.clone(develop[key])
        end
        if geometryOnly then
            for _,groups in pairs(state) do
                for _,group in pairs(groups) do
                    if type(group)~='table' then error('Unsupported native correction representation') end
                    for key in pairs(group) do
                        if type(key)=='string' and (key:match('^Local') or key=='CorrectionAmount') then group[key]=nil end
                    end
                end
            end
        end
        return Json.encode(canonical(state))
    end
    local expectedCorrections=correctionState(false)
    local expectedGeometry=correctionState(true)
    local function writeLocal(param,value)
        selected(maskId)
        if globalState()~=beforeGlobal or correctionState(false)~=expectedCorrections or not sameLocal(controlState(maskId),targetState) then
            error('Mask context changed before local write')
        end
        selected(maskId)
        progress.local_parameter=param
        D.setValue(param,value)
        progress.parameters_applied=true
        selected(maskId)
        local after=controlState(maskId)
        for key,old in pairs(targetState) do
            if key~=param and not sameLocal(after[key],old) then error('Unrelated local control changed: ' .. key) end
        end
        for key in pairs(after) do
            if key~=param and targetState[key]==nil then error('Unexpected local control appeared: ' .. key) end
        end
        if (type(after[param])~='number' or math.abs(after[param]-value)>0.0001) then
            error('Local mask readback mismatch: ' .. param)
        end
        if correctionState(true)~=expectedGeometry then error('Native mask geometry changed during local adjustment') end
        expectedCorrections=correctionState(false)
        targetState=after
    end
    if fields.action=='mask-create' then
        local function linearCurve(points)
            local count=0
            for key in pairs(points) do
                if not key:match('^number:%d+$') then return false end
                count=count+1
            end
            if count<4 or count%2~=0 or points['number:1']~=0 or points['number:'..(count-1)]~=255 then return false end
            for i=1,count,2 do
                if type(points['number:'..i])~='number' or points['number:'..i]~=points['number:'..(i+1)] then return false end
            end
            return true
        end
        -- SDK 13 returns local curves as arrays, but resetToDefault on those
        -- arrays raises rangeScale errors. Preserve verified neutral curves;
        -- reject inherited non-neutral structures rather than write raw tables.
        for param,value in pairs(targetState) do
            if type(value)=='table' and next(value) then
                if not param:match('curve$') or not linearCurve(value) then
                    error('New mask has unsupported non-neutral local structure: ' .. param)
                end
            elseif type(value)~='number' and type(value)~='table' and value~=false then
                error('Unsupported inherited local control: ' .. param)
            end
        end
        for _,param in ipairs(localParams) do
            local value=targetState[param]
            if type(value)=='number' then
                local neutral=0
                if param=='local_Amount' or param=='local_RefineSaturation' then
                    local lo,hi=D.getRange(param)
                    local expectedMax=param=='local_Amount' and 200 or 100
                    if lo~=0 or hi~=expectedMax then error('Unsupported neutral range: '..param) end
                    neutral=100
                end
                if value~=neutral then writeLocal(param,neutral) end
            end
        end
    end
    for _,key in ipairs({'clarity','texture'}) do
        if targets[key] then
            local param=key=='clarity' and 'local_Clarity' or 'local_Texture'
            selected(maskId)
            local lo=D.getRange(param)
            writeLocal(param,targets[key] / 100 * (-lo))
        end
    end
    local after=values(maskId)
    for key,value in pairs(targets) do
        if math.abs(after[key]-value)>0.0001 then error('Local mask readback mismatch; inspect snapshot') end
    end
    if beforeGlobal~=globalState() then error('Global settings changed during mask operation; inspect snapshot') end
    local afterInventory=inventory()
    local actualCount,expectedCount=0,fields.action=='mask-create' and 1 or 0
    for _ in pairs(oldIds) do expectedCount=expectedCount+1 end
    for _ in pairs(afterInventory) do actualCount=actualCount+1 end
    if actualCount~=expectedCount then error('Unexpected mask appeared or disappeared') end
    if range then
        local finalRange=Lum.read(photo:getDevelopSettings().MaskGroupBasedCorrections,maskId,true)
        for key,value in pairs(range) do
            if math.abs(finalRange[key]-value)>0.00011 then error('Final luminance range changed') end
        end
    end
    for id in pairs(oldIds) do
        if not afterInventory[id] or Json.encode(canonical(afterInventory[id]))~=Json.encode(oldInventory['string:'..id]) then
            error('Existing mask geometry changed; inspect snapshot')
        end
        if id==maskId then
            local current=controlState(id)
            for key,value in pairs(oldValues[id]) do
                local requested=(key=='local_Clarity' and targets.clarity~=nil) or (key=='local_Texture' and targets.texture~=nil)
                if not requested and not sameLocal(current[key],value) then error('Unrequested target mask control changed') end
            end
        else
            local current=controlState(id)
            if not sameLocal(current,oldValues[id]) then error('Unrelated local mask values changed; inspect snapshot') end
        end
    end
    select(maskId)
    local result=response(maskId)
    result.snapshot_name=snapshot
    result.readback_verified=true
    result.mask_type=subtype
    result.needs_visual_review=true
    return result
end
return M
