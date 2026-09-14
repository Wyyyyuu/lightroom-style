-- Log before importing the worker so initialization failures stay observable.
local function note(message)
    local handle, err = io.open(_PLUGIN.path .. '/bridge-startup.log', 'a')
    if not handle then error('Cannot write plugin startup log: ' .. tostring(err)) end
    handle:write(tostring(message) .. '\n')
    handle:close()
end
note('Init entered: bridge 0.1.2')
local LrTasks = import 'LrTasks'
LrTasks.startAsyncTask(function()
    local ok, err = LrTasks.pcall(function()
        note('Loading Bridge.lua in SDK task')
        dofile(_PLUGIN.path .. '/Bridge.lua').start()
        note('Bridge worker scheduled')
    end)
    if not ok then
        note('Bootstrap error: ' .. tostring(err))
        error(err)
    end
end)
