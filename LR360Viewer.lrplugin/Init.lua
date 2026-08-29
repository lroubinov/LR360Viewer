local LrApplication = import 'LrApplication'
local LrTasks = import 'LrTasks'
local LrExportSession = import 'LrExportSession'
local LrPathUtils = import 'LrPathUtils'
local LrFileUtils = import 'LrFileUtils'
local LrDate = import 'LrDate'

local function readText(path)
    local f = io.open(path, "r")
    if not f then return nil end
    local value = f:read("*a")
    f:close()
    return value
end

local function writeText(path, value)
    local f = io.open(path, "w")
    if not f then return false end
    f:write(value or "")
    f:close()
    return true
end

local function cleanLine(value)
    return tostring(value or ""):gsub("[\r\n]", " ")
end

local function getActivePhoto(catalog)
    local target = catalog:getTargetPhoto()
    if target then return target end
    local photos = catalog:getTargetPhotos()
    return photos and photos[1] or nil
end

local function getPhotoPath(photo)
    if not photo then return nil end
    local path = photo:getRawMetadata("path")
    if not path or path == "" then return nil end
    return path
end

local function renderWithLightroom(photo, destination)
    local exportSession = LrExportSession {
        photosToExport = { photo },
        exportSettings = {
            LR_export_destinationType = "specificFolder",
            LR_export_destinationPathPrefix = destination,
            LR_export_useSubfolder = false,
            LR_collisionHandling = "overwrite",
            LR_format = "JPEG",
            LR_jpeg_quality = 0.95,
            LR_size_doConstrain = false,
            LR_outputSharpeningOn = false,
        },
    }
    for _, rendition in exportSession:renditions() do
        local ok, result = rendition:waitForRender()
        if not ok then return nil, tostring(result) end
        return result, nil
    end
    return nil, "Lightroom did not return a rendered file."
end

local tempRoot = LrPathUtils.child(
    LrPathUtils.getStandardFilePath("temp"), "LR360Viewer")
LrFileUtils.createAllDirectories(tempRoot)
local bridgeRequestFile = LrPathUtils.child(tempRoot, "external-bridge.request")
local bridgeLogFile = LrPathUtils.child(tempRoot, "external-bridge.log")
writeText(bridgeLogFile, "Init.lua loaded at " .. tostring(LrDate.currentTime()))


local function validBridgeStatePath(path)
    if not path or path == "" then return false end
    local normalizedRoot = string.lower(tempRoot:gsub("/", "\\")) .. "\\"
    local normalizedPath = string.lower(path:gsub("/", "\\"))
    return normalizedPath:sub(1, #normalizedRoot) == normalizedRoot and
        normalizedPath:match("external%-%d+%-%d+%.state$") ~= nil
end

local function runBridgeSession(stateFile)
    writeText(bridgeLogFile, "Bridge request accepted: " .. tostring(stateFile))
    local aliveFile = stateFile .. ".alive"
    local renderRequestFile = stateFile .. ".render-request"
    local importRequestFile = stateFile .. ".import"
    local renderRoot = stateFile .. ".renders"
    LrFileUtils.createAllDirectories(renderRoot)
    if not LrFileUtils.exists(aliveFile) then return end

    local catalog = LrApplication.activeCatalog()
    local currentPhoto = getActivePhoto(catalog)
    local currentSourcePath = getPhotoPath(currentPhoto)
    if not currentPhoto or not currentSourcePath then return end

    local oldState = readText(stateFile) or ""
    local firstLine = oldState:match("^([^\r\n]+)")
    local revision = tonumber(firstLine) or 1
    local currentDisplayPath = currentSourcePath
    local currentDisplayKind = "source"
    local currentRendering = false
    local currentMessage = ""
    local renderedFiles = {}
    local photosByPath = { [currentSourcePath] = currentPhoto }

    local function publishState(imageChanged, connected)
        if imageChanged then revision = revision + 1 end
        return writeText(stateFile, table.concat({
            tostring(revision), cleanLine(currentSourcePath),
            cleanLine(currentDisplayPath), cleanLine(currentDisplayKind),
            currentRendering and "1" or "0", cleanLine(currentMessage),
            connected == false and "0" or "1",
        }, "\n"))
    end

    local function switchToDirectSource(photo, path)
        photosByPath[path] = photo
        currentPhoto = photo
        currentSourcePath = path
        currentDisplayPath = path
        currentDisplayKind = "source"
        currentRendering = false
        currentMessage = ""
        publishState(true, true)
    end

    publishState(true, true)

    local function processImportRequest()
        if not LrFileUtils.exists(importRequestFile) then return end
        local f = io.open(importRequestFile, "r")
        local sourcePath = f and f:read("*l") or nil
        local newPath = f and f:read("*l") or nil
        if f then f:close() end
        pcall(function() LrFileUtils.delete(importRequestFile) end)
        if not sourcePath or not newPath or
           not LrFileUtils.exists(newPath) then return end
        local stackPhoto = photosByPath[sourcePath] or
            catalog:findPhotoByPath(sourcePath)
        if not stackPhoto then return end
        catalog:withWriteAccessDo("Import 360 Perspective", function()
            catalog:addPhoto(newPath, stackPhoto, "below")
        end)
    end

    local function processRenderRequest()
        if not LrFileUtils.exists(renderRequestFile) then return nil end
        pcall(function() LrFileUtils.delete(renderRequestFile) end)
        local photo = getActivePhoto(catalog)
        local sourcePath = getPhotoPath(photo)
        if not photo or not sourcePath then
            currentMessage = "No active Lightroom photo is available to render."
            publishState(false, true)
            return nil
        end
        photosByPath[sourcePath] = photo
        if sourcePath ~= currentSourcePath then
            currentSourcePath = sourcePath
            currentDisplayPath = sourcePath
            currentDisplayKind = "source"
            revision = revision + 1
        end
        currentRendering = true
        currentMessage = "Rendering the active photo with Lightroom adjustments..."
        publishState(false, true)
        local renderedPath, renderError = renderWithLightroom(photo, renderRoot)
        currentRendering = false
        if renderedPath then renderedFiles[renderedPath] = true end
        local activeAfter = getActivePhoto(catalog)
        local activePath = getPhotoPath(activeAfter)
        if activeAfter and activePath and activePath ~= sourcePath then
            switchToDirectSource(activeAfter, activePath)
        elseif renderedPath then
            currentDisplayPath = renderedPath
            currentDisplayKind = "lightroom_render"
            currentMessage = ""
            publishState(true, true)
        else
            currentMessage = "Lightroom render failed: " .. tostring(renderError)
            publishState(false, true)
        end
        return activePath or sourcePath
    end

    local startedAt = LrDate.currentTime()
    local lastAliveValue = readText(aliveFile)
    local lastAliveChangeAt = startedAt
    local observedPath = currentSourcePath
    local pendingPath, pendingPhoto, pendingSince = nil, nil, 0

    while true do
        processImportRequest()
        local renderedSourcePath = processRenderRequest()
        if renderedSourcePath then
            observedPath = renderedSourcePath
            pendingPath, pendingPhoto = nil, nil
        end

        local now = LrDate.currentTime()
        local targetPhoto = getActivePhoto(catalog)
        local targetPath = getPhotoPath(targetPhoto)
        if targetPath and targetPath ~= observedPath then
            observedPath = targetPath
            pendingPath, pendingPhoto, pendingSince = targetPath, targetPhoto, now
        elseif pendingPath and targetPath == pendingPath and
               now - pendingSince >= 0.45 then
            switchToDirectSource(pendingPhoto, pendingPath)
            pendingPath, pendingPhoto = nil, nil
        end

        local aliveValue = readText(aliveFile)
        if aliveValue and aliveValue ~= lastAliveValue then
            lastAliveValue = aliveValue
            lastAliveChangeAt = now
        elseif not aliveValue or now - lastAliveChangeAt >= 15 then
            break
        end
        LrTasks.sleep(0.15)
    end

    processImportRequest()
    if LrFileUtils.exists(stateFile) then publishState(false, false) end
    for path, _ in pairs(renderedFiles) do
        pcall(function() LrFileUtils.delete(path) end)
    end
    pcall(function() LrFileUtils.delete(renderRoot) end)
end

LrTasks.startAsyncTask(function()
    while true do
        local stateFile = readText(bridgeRequestFile)
        if stateFile then stateFile = stateFile:gsub("[\r\n]+$", "") end
        if validBridgeStatePath(stateFile) then
            if LrFileUtils.exists(stateFile .. ".alive") then
                runBridgeSession(stateFile)
            elseif readText(bridgeRequestFile) == stateFile then
                pcall(function() LrFileUtils.delete(bridgeRequestFile) end)
            end
        end
        LrTasks.sleep(0.75)
    end
end)
