-- Explicit, bounded Lightroom operations. Requests are data, never executable Lua.
local App = import 'LrApplication'
local Tasks = import 'LrTasks'
local Files = import 'LrFileUtils'
local Paths = import 'LrPathUtils'
local Json = dofile(_PLUGIN.path .. '/Json.lua')
local M = {}
local ranges = {
    Exposure2012={-5,5}, Contrast2012={-100,100}, Highlights2012={-100,100},
    Shadows2012={-100,100}, Whites2012={-100,100}, Blacks2012={-100,100},
    RedHue={-100,100}, GreenHue={-100,100}, BlueHue={-100,100},
    GrainAmount={0,100}, GrainSize={0,100}, GrainFrequency={0,100},
    Vibrance={-100,100}, Saturation={-100,100}, Temperature={2000,50000},
    Tint={-150,150}, IncrementalTemperature={-100,100}, IncrementalTint={-100,100},
    SplitToningShadowHue={0,360}, SplitToningHighlightHue={0,360},
    SplitToningShadowSaturation={0,100}, SplitToningHighlightSaturation={0,100},
    SplitToningBalance={-100,100}, ColorGradeMidtoneHue={0,360},
    ColorGradeMidtoneSat={0,100}, ColorGradeMidtoneLum={-100,100},
    ColorGradeShadowLum={-100,100}, ColorGradeHighlightLum={-100,100},
    ColorGradeGlobalHue={0,360}, ColorGradeGlobalSat={0,100},
    ColorGradeGlobalLum={-100,100}, ColorGradeBlending={0,100},
    ParametricShadows={-100,100}, ParametricDarks={-100,100},
    ParametricLights={-100,100}, ParametricHighlights={-100,100},
}
for _, color in ipairs({'Red','Orange','Yellow','Green','Aqua','Blue','Purple','Magenta'}) do
    for _, prefix in ipairs({'HueAdjustment','SaturationAdjustment','LuminanceAdjustment'}) do
        ranges[prefix .. color] = {-100,100}
    end
end
M.ranges = ranges
local function norm(path) return tostring(path):gsub('\\','/'):gsub('/+$',''):lower() end
local function required(fields,key)
    local value = fields[key]
    if not value or value == '' then error('Missing field: ' .. key) end
    return value
end
local function unescape(value)
    if value:gsub('%%[0-9a-fA-F][0-9a-fA-F]',''):find('%%') then error('Invalid percent encoding') end
    return (value:gsub('%%(%x%x)', function(h) return string.char(tonumber(h,16)) end))
end
function M.parse(text)
    if #text > 65536 then error('Command too large') end
    local fields = {}
    for line in text:gmatch('[^\r\n]+') do
        local key,value = line:match('^([%w_.]+)=(.*)$')
        if not key or fields[key] ~= nil then error('Malformed or repeated command field') end
        fields[key] = unescape(value)
        if fields[key]:find('%z') then error('NUL is not allowed') end
    end
    if fields.protocol ~= '1' then error('Unsupported protocol') end
    if not required(fields,'id'):match('^[a-f0-9]+$') or #fields.id ~= 32 then error('Invalid request ID') end
    return fields
end
local function settings(photo)
    local raw = photo:getDevelopSettings()
    local result = { ProcessVersion = tostring(raw.ProcessVersion or ''), WhiteBalance = tostring(raw.WhiteBalance or '') }
    for key in pairs(ranges) do if type(raw[key]) == 'number' then result[key] = raw[key] end end
    return result
end
-- Read-only context: preserve the panel switch, region boundaries, and point curves.
-- The JSON encoder accepts objects only; numeric point indices become string keys.
local function curveState(photo)
    local raw,result = photo:getDevelopSettings(),{}
    for _,key in ipairs({'EnableToneCurve','HDREditMode','CameraProfile','ParametricShadowSplit','ParametricMidtoneSplit',
        'ParametricHighlightSplit','ToneCurveName','ToneCurveName2012','ToneCurve',
        'ToneCurvePV2012','ToneCurvePV2012Red','ToneCurvePV2012Green','ToneCurvePV2012Blue',
        'ExtendedToneCurvePV2012','ExtendedToneCurvePV2012Red',
        'ExtendedToneCurvePV2012Green','ExtendedToneCurvePV2012Blue'}) do
        local value=raw[key]
        if type(value)=='table' then
            local points={}
            for i,v in ipairs(value) do
                if type(v)~='number' then error('Unsupported point curve representation: ' .. key) end
                points[tostring(i)]=v
            end
            result[key]=points
        elseif type(value)=='number' or type(value)=='string' or type(value)=='boolean' then
            result[key]=value
        end
    end
    return result
end
local function curveRevision(photo)
    return Json.encode({settings=settings(photo),curve_state=curveState(photo)})
end
local function grainState(photo)
    local raw,result=photo:getDevelopSettings(),{}
    for _,key in ipairs({'EnableGrain','EnableEffects'}) do
        if type(raw[key])=='boolean' then result[key]=raw[key] end
    end
    return result
end
local function calibrationState(photo)
    local raw,result=photo:getDevelopSettings(),{}
    for _,key in ipairs({'EnableCalibration','ShadowTint','RedSaturation','GreenSaturation','BlueSaturation'}) do
        if type(raw[key])=='boolean' or type(raw[key])=='number' then result[key]=raw[key] end
    end
    return result
end
local function describe(photo)
    return { photo_id=tostring(photo.localIdentifier), path=photo:getRawMetadata('path'),
        filename=photo:getFormattedMetadata('fileName'),
        is_virtual_copy=photo:getRawMetadata('isVirtualCopy') == true,
        copy_name=photo:getFormattedMetadata('copyName') or '', settings=settings(photo),
        curve_state=curveState(photo), curve_revision=curveRevision(photo), grain_state=grainState(photo), calibration_state=calibrationState(photo) }
end
local function validNumber(value,key,range)
    local number = tonumber(value)
    if not number or number ~= number or math.abs(number) == math.huge then error('Invalid numeric value: ' .. key) end
    if range and (number < range[1] or number > range[2]) then error('Out-of-range value: ' .. key) end
    return number
end
local function write(catalog,name,callback)
    local executed = catalog:withWriteAccessDo(name,callback,{timeout=8,asynchronous=false})
    if executed ~= 'executed' then error('Catalog write gate did not execute: ' .. tostring(executed)) end
end
local function resolve(catalog,fields)
    local path = required(fields,'path')
    local id = required(fields,'photo_id')
    local master = catalog:findPhotoByPath(path)
    if not master then error('Photo is not in this catalog: ' .. path) end
    if tostring(master.localIdentifier) == id then return master end
    for _,copy in ipairs(master:getRawMetadata('virtualCopies') or {}) do
        if tostring(copy.localIdentifier) == id then return copy end
    end
    error('Photo ID does not match the specified file in this catalog')
end
local function fresh(fields,catalog)
    if os.time() > validNumber(required(fields,'deadline'),'deadline') then error('Command expired before the next operation') end
    if norm(App.activeCatalog():getPath()) ~= norm(fields.catalog) or norm(catalog:getPath()) ~= norm(fields.catalog) then
        error('Active catalog changed; command stopped')
    end
end
local function pointCurve(text)
    if #text>512 or text:find('[^%d,]') or text:find(',,') or text:sub(1,1)==',' or text:sub(-1)==',' then
        error('Malformed point curve coordinates')
    end
    local points,indexed={},{}
    for token in text:gmatch('[^,]+') do
        local value=validNumber(token,'curve coordinate',{0,255})
        points[#points+1]=value; indexed[tostring(#points)]=value
    end
    if #points<4 or #points>32 or #points%2~=0 or points[1]~=0 or points[#points-1]~=255 then
        error('Point curve needs 2-16 pairs with endpoint inputs 0 and 255')
    end
    for i=3,#points,2 do
        if points[i]<=points[i-2] or points[i+1]<points[i-1] then
            error('Point curve inputs must increase and outputs must not decrease')
        end
    end
    return points,indexed
end
function M.execute(fields,progress)
    local catalog = App.activeCatalog()
    if not catalog then error('No active catalog') end
    required(fields,'catalog'); fresh(fields,catalog)
    local action = required(fields,'action')
    if action == 'import' then
        local path = required(fields,'path')
        if not Paths.isAbsolute(path) or Files.exists(path) ~= 'file' then error('Import requires an existing absolute image path') end
        local photo = catalog:findPhotoByPath(path)
        local existed = photo ~= nil
        if not photo then
            fresh(fields,catalog)
            write(catalog,'Lightroom Style: import specified image',function() fresh(fields,catalog); catalog:addPhoto(path) end)
            photo = catalog:findPhotoByPath(path)
        end
        if not photo then error('Imported photo could not be retrieved') end
        return {photo=describe(photo),already_imported=existed}
    end
    local photo = resolve(catalog,fields)
    if photo:getRawMetadata('isVideo') then error('Video is not supported') end
    if action == 'read' then return {photo=describe(photo)} end
    if action == 'mask-read' or action == 'mask-create' or action == 'mask-adjust' then
        local result=dofile(_PLUGIN.path .. '/Masks.lua').execute(photo,catalog,fields,progress,
            {json=Json,required=required,number=validNumber,fresh=fresh,write=write,describe=describe})
        result.photo=describe(photo)
        return result
    end
    if action == 'curve' or action == 'curve-channel' then
        if not photo:getRawMetadata('isVirtualCopy') or not (photo:getFormattedMetadata('copyName') or ''):match('^PhotoStyle%-') then
            error('Writes require a PhotoStyle- virtual copy; originals and unrelated copies are protected')
        end
        for key in pairs(fields) do
            if key:match('^set%.') or key:match('^expect%.') then error('Curve action cannot mix scalar parameter writes') end
        end
        local channel=fields.curve_channel or 'composite'
        local suffixes={composite='',red='Red',green='Green',blue='Blue'}
        if suffixes[channel]==nil or (action=='curve-channel' and channel=='composite')
            or (action=='curve' and channel~='composite') then error('Invalid curve channel/action') end
        local curveKey='ToneCurvePV2012' .. suffixes[channel]
        local extendedKey='ExtendedToneCurvePV2012' .. suffixes[channel]
        local points,indexed=pointCurve(required(fields,'curve_points'))
        local revision=required(fields,'expected_revision')
        if curveRevision(photo)~=revision then error('Stale expected curve revision') end
        local before=describe(photo)
        local context=before.curve_state
        if context.EnableToneCurve~=true then error('Tone Curve panel must be verified enabled') end
        if context.HDREditMode==true or (type(context.HDREditMode)=='number' and context.HDREditMode~=0) then
            error('HDR point curve writes are not supported')
        end
        if not context.ToneCurvePV2012 or not context.ToneCurveName2012 then error('Composite PV2012 point curve is absent') end
        if not context[curveKey] then error('Requested channel point curve is absent') end
        local extended=context[extendedKey]
        if extended and Json.encode(extended)~=Json.encode(context[curveKey]) then
            error('Selected and extended curve representations differ; refusing an ambiguous write')
        end
        local updates={[curveKey]=points,ToneCurveName2012='Custom'}
        if extended then updates[extendedKey]=points end
        local expectedContext={}
        for k,v in pairs(context) do expectedContext[k]=v end
        expectedContext[curveKey]=indexed; expectedContext.ToneCurveName2012='Custom'
        if extended then expectedContext[extendedKey]=indexed end
        local snapshot='PhotoStyle-before-' .. fields.id
        progress.snapshot_name=snapshot
        fresh(fields,catalog)
        write(catalog,'Lightroom Style: ' .. channel .. ' point curve',function()
            fresh(fields,catalog)
            if curveRevision(photo)~=revision then error('Curve context changed before write') end
            if not photo:createDevelopSnapshot(snapshot,false) then error('Could not create a new recovery snapshot') end
            photo:applyDevelopSettings(updates,'Lightroom Style point curve ' .. fields.id,false)
        end)
        progress.parameters_applied=true
        local matched=false
        for attempt=1,20 do
            matched=Json.encode(curveState(photo))==Json.encode(expectedContext)
                and Json.encode(settings(photo))==Json.encode(before.settings)
            matched=matched and Json.encode(calibrationState(photo))==Json.encode(before.calibration_state)
                and Json.encode(grainState(photo))==Json.encode(before.grain_state)
            if matched then break end
            Tasks.sleep(0.25)
        end
        if not matched then error('Point curve readback did not match or unrelated settings changed; inspect snapshot, do not resend blindly') end
        return {photo=describe(photo),before=before,applied_curve=indexed,curve_channel=channel,readback_verified=true,snapshot_name=snapshot}
    end
    if action == 'copy' then
        local before = settings(photo)
        fresh(fields,catalog)
        local folder = catalog:getFolderByPath(Paths.parent(fields.path))
        if not folder or not catalog:setActiveSources({folder}) then error('Could not activate the specified photo folder') end
        Tasks.sleep(0.3)
        catalog:setSelectedPhotos(photo,{})
        local selectionVerified=false
        for attempt=1,20 do
            local selected = catalog:getTargetPhotos()
            local target = catalog:getTargetPhoto()
            if target and #selected==1 and tostring(target.localIdentifier)==tostring(photo.localIdentifier)
                and tostring(selected[1].localIdentifier)==tostring(photo.localIdentifier) then selectionVerified=true; break end
            Tasks.sleep(0.25)
        end
        if not selectionVerified then error('Could not establish exactly one source selection; check active folder filters') end
        local name = 'PhotoStyle-' .. fields.id
        fresh(fields,catalog)
        local copies = catalog:createVirtualCopies(name)
        if not copies or #copies ~= 1 then error('Expected exactly one virtual copy; inspect selection before retrying') end
        local copy = copies[1]
        progress.created_copy_id = tostring(copy.localIdentifier)
        if not copy:getRawMetadata('isVirtualCopy') or norm(copy:getRawMetadata('path')) ~= norm(fields.path) then error('New copy identity verification failed') end
        local sourceAfter = settings(photo)
        if Json.encode(before) ~= Json.encode(sourceAfter) then error('Source develop settings changed unexpectedly') end
        return {photo=describe(copy),source=describe(photo),source_settings_unchanged=true}
    end
    if action == 'apply' then
        if not photo:getRawMetadata('isVirtualCopy') or not (photo:getFormattedMetadata('copyName') or ''):match('^PhotoStyle%-') then
            error('Writes require a PhotoStyle- virtual copy; originals and unrelated copies are protected')
        end
        local before,updates,expected = settings(photo),{},{}
        for key,value in pairs(fields) do
            local name = key:match('^set%.(.+)$')
            if name then
                if not ranges[name] then error('Unsupported develop parameter: ' .. name) end
                if before[name] == nil then error('Parameter is absent for this photo/process: ' .. name) end
                updates[name] = validNumber(value,name,ranges[name])
                expected[name] = validNumber(required(fields,'expect.' .. name),name)
                if math.abs(before[name]-expected[name]) > 0.0001 then error('Stale expected value for ' .. name) end
            end
        end
        if next(updates) == nil then error('No parameter changes supplied') end
        local changesCalibration=updates.RedHue~=nil or updates.GreenHue~=nil or updates.BlueHue~=nil
        local beforeCalibration=calibrationState(photo)
        if changesCalibration and beforeCalibration.EnableCalibration~=true then
            error('Calibration panel must be verified enabled before primary hue edits')
        end
        local changesGrain=updates.GrainAmount~=nil or updates.GrainSize~=nil or updates.GrainFrequency~=nil
        local beforeGrain=grainState(photo)
        if changesGrain and (beforeGrain.EnableGrain==false or beforeGrain.EnableEffects==false) then
            error('Grain/Effects panel is disabled; verify it enabled through native UI before grain edits')
        end
        local changesCurve=false
        for key in pairs(updates) do if key:match('^Parametric') then changesCurve=true end end
        local beforeCurve=curveState(photo)
        if changesCurve and beforeCurve.EnableToneCurve~=true then
            error('Tone Curve panel must be verified enabled before parametric edits; existing point curves will not be activated implicitly')
        end
        local nativeUpdates={}
        for key,value in pairs(updates) do nativeUpdates[key]=value end
        local changesWhiteBalance = updates.Temperature or updates.Tint or updates.IncrementalTemperature or updates.IncrementalTint
        if changesWhiteBalance then nativeUpdates.WhiteBalance='Custom' end
        local snapshot = 'PhotoStyle-before-' .. fields.id
        progress.snapshot_name = snapshot
        fresh(fields,catalog)
        write(catalog,'Lightroom Style: set explicit parameters',function()
            fresh(fields,catalog)
            local current = settings(photo)
            if changesCalibration and (Json.encode(calibrationState(photo))~=Json.encode(beforeCalibration)
                or Json.encode(curveState(photo))~=Json.encode(beforeCurve)
                or Json.encode(current)~=Json.encode(before)) then
                error('Calibration context changed before write')
            end
            if changesGrain and Json.encode(grainState(photo))~=Json.encode(beforeGrain) then
                error('Grain context changed before write')
            end
            if (changesCurve or changesGrain) and Json.encode(curveState(photo))~=Json.encode(beforeCurve) then
                error('Curve context changed before write')
            end
            for key,value in pairs(expected) do if math.abs(current[key]-value)>0.0001 then error('Parameter changed before write: ' .. key) end end
            if not photo:createDevelopSnapshot(snapshot,false) then error('Could not create a new recovery snapshot') end
            photo:applyDevelopSettings(nativeUpdates,'Lightroom Style ' .. fields.id,false)
        end)
        progress.parameters_applied = true
        local after,matched
        for attempt=1,20 do
            after=settings(photo); matched=true
            for key,value in pairs(updates) do if type(after[key]) ~= 'number' or math.abs(after[key]-value)>0.0001 then matched=false end end
            if changesWhiteBalance and after.WhiteBalance~='Custom' then matched=false end
            if changesGrain and Json.encode(grainState(photo))~=Json.encode(beforeGrain) then matched=false end
            if (changesCurve or changesGrain) and Json.encode(curveState(photo))~=Json.encode(beforeCurve) then matched=false end
            if changesCalibration then
                if Json.encode(calibrationState(photo))~=Json.encode(beforeCalibration)
                    or Json.encode(curveState(photo))~=Json.encode(beforeCurve) then matched=false end
                for key,value in pairs(before) do
                    if updates[key]==nil and not (changesWhiteBalance and key=='WhiteBalance') and after[key]~=value then matched=false end
                end
            end
            if matched then break end
            Tasks.sleep(0.25)
        end
        if not matched then error('Write returned but parameter readback did not match; inspect the recovery snapshot, do not resend blindly') end
        return {photo=describe(photo),before=before,applied=updates,white_balance_set_to_custom=changesWhiteBalance~=nil,readback_verified=true,snapshot_name=snapshot}
    end
    if action == 'export' then
        local folder = required(fields,'output_dir')
        if not Paths.isAbsolute(folder) or Files.exists(folder) then error('Export requires a NEW absolute output directory') end
        fresh(fields,catalog)
        local ok,err = Files.createAllDirectories(folder)
        if not ok then error('Cannot create export directory: ' .. tostring(err)) end
        local Export = import 'LrExportSession'
        local session = Export {
            photosToExport={photo}, exportSettings={
                LR_exportServiceProvider='com.adobe.ag.export.file',
                LR_export_destinationType='specificFolder', LR_export_destinationPathPrefix=folder,
                LR_export_useSubfolder=false, LR_collisionHandling='ask', LR_format='JPEG',
                LR_jpeg_quality=0.95, LR_export_colorSpace='sRGB',
                LR_size_doConstrain=false, LR_outputSharpeningOn=false,
                LR_useWatermark=false, LR_reimportExportedPhoto=false,
                LR_renamingTokensOn=false, LR_export_postProcessing='doNothing',
                LR_embeddedMetadataOption='copyrightOnly', LR_removeLocationMetadata=true,
            },
        }
        local rendered,count={},0
        for _,rendition in session:renditions({stopIfCanceled=true}) do
            local success,path = rendition:waitForRender()
            if not success then error('Lightroom render failed: ' .. tostring(path)) end
            if Files.exists(path) ~= 'file' then error('Renderer returned a missing file') end
            count=count+1; rendered[tostring(count)]=path
        end
        if count ~= 1 then error('Expected exactly one exported image') end
        return {photo=describe(photo),files=rendered,rendered_by='Lightroom Classic',color_space='sRGB',format='JPEG'}
    end
    error('Unsupported action: ' .. action)
end

function M.poll(folder)
    local requests={}
    for path in Files.files(folder) do
        local id = Paths.leafName(path):match('^command%-([a-f0-9]+)%.request$')
        if id and #id==32 then requests[#requests+1]={path=path,id=id} end
    end
    table.sort(requests,function(a,b) return a.id < b.id end)
    for _,request in ipairs(requests) do
        local stem=Paths.child(folder,'command-' .. request.id)
        local claimed=stem .. '.running'
        if not Files.exists(claimed) and not Files.exists(stem .. '.result.json') then
            local moved=Files.move(request.path,claimed)
            if moved then
                local progress={}
                local ok,value=Tasks.pcall(function()
                    local fields=M.parse(Files.readFile(claimed))
                    if fields.id ~= request.id then error('Request ID/filename mismatch') end
                    return M.execute(fields,progress)
                end)
                local response={protocol=1,command_version='0.3.1',id=request.id,ok=ok,completed_at_epoch=os.time(),progress=progress}
                if ok then response.result=value else response.error=tostring(value) end
                local out,err=io.open(stem .. '.result.json','wb')
                if not out then error(err) end
                out:write(Json.encode(response)); out:close()
                local ready=assert(io.open(stem .. '.result.json.ready','wb'))
                ready:write('ready'); ready:close()
            end
        end
    end
end
return M
