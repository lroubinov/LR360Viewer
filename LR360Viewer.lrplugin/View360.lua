local LrApplication = import 'LrApplication'
local LrDialogs = import 'LrDialogs'
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

local function getPhotoPath(photo)
    if not photo then return nil end
    -- Lightroom metadata access may yield; wrapping it in pcall can turn a
    -- valid active photo into path=nil in Lightroom's Lua runtime.
    local path = photo:getRawMetadata("path")
    if not path or path == "" then return nil end
    return path
end

local function getActivePhoto(catalog)
    local target = catalog:getTargetPhoto()
    if target then
        return target, "getTargetPhoto returned a photo"
    end

    -- Lightroom can briefly report no target while Grid/Filmstrip focus changes.
    -- Keep getTargetPhoto as the authority, with a compatibility fallback.
    local photos = catalog:getTargetPhotos()
    local count = photos and #photos or 0
    local diagnostic = "getTargetPhoto=nil; getTargetPhotos count=" ..
        tostring(count)
    if photos and photos[1] then return photos[1], diagnostic end
    return nil, diagnostic .. "; first item unavailable"
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

LrTasks.startAsyncTask(function()
    local catalog = LrApplication.activeCatalog()
    local initialPhoto, initialPath, selectionDiagnostic
    for _ = 1, 12 do
        initialPhoto, selectionDiagnostic = getActivePhoto(catalog)
        initialPath = getPhotoPath(initialPhoto)
        if initialPhoto and initialPath then break end
        LrTasks.sleep(0.1)
    end
    if not initialPhoto or not initialPath then
        local diagnosticRoot = LrPathUtils.child(
            LrPathUtils.getStandardFilePath("temp"), "LR360Viewer")
        LrFileUtils.createAllDirectories(diagnosticRoot)
        writeText(LrPathUtils.child(diagnosticRoot, "selection.log"),
            "Selection lookup failed\n" ..
            tostring(selectionDiagnostic or "no diagnostic") .. "\n" ..
            "photo=" .. tostring(initialPhoto) .. "\n" ..
            "path=" .. tostring(initialPath))
        return
    end
    if not LrFileUtils.exists(initialPath) then
        LrDialogs.message("LR 360 Viewer",
            "The active photo is unavailable on disk:\n\n" .. initialPath, "warning")
        return
    end

    -- Session state, optional Lightroom renders and launch files stay in system TEMP.
    local tempRoot = LrPathUtils.child(
        LrPathUtils.getStandardFilePath("temp"), "LR360Viewer")
    LrFileUtils.createAllDirectories(tempRoot)
    local sessionId = string.format("%.0f-%06d",
        LrDate.currentTime() * 1000, math.random(0, 999999))
    local sessionDir = LrPathUtils.child(tempRoot, "session-" .. sessionId)
    LrFileUtils.createAllDirectories(sessionDir)

    local sessionFile = LrPathUtils.child(sessionDir, "session.state")
    local aliveFile = sessionFile .. ".alive"
    local renderRequestFile = sessionFile .. ".render-request"
    local importRequestFile = sessionFile .. ".import"
    local runFile = LrPathUtils.child(sessionDir, "launch.cmd")

    local revision = 1
    local currentSourcePath = initialPath
    local currentDisplayPath = initialPath
    local currentDisplayKind = "source"
    local currentRendering = false
    local currentMessage = ""
    local renderedFiles = {}
    local photosByPath = { [initialPath] = initialPhoto }

    local function publishState(imageChanged)
        if imageChanged then revision = revision + 1 end
        return writeText(sessionFile, table.concat({
            tostring(revision),
            cleanLine(currentSourcePath),
            cleanLine(currentDisplayPath),
            cleanLine(currentDisplayKind),
            currentRendering and "1" or "0",
            cleanLine(currentMessage),
        }, "\n"))
    end

    local function switchToDirectSource(photo, path)
        photosByPath[path] = photo
        currentSourcePath = path
        currentDisplayPath = path
        currentDisplayKind = "source"
        currentRendering = false
        currentMessage = ""
        publishState(true)
    end

    publishState(false)

    local launcher = LrPathUtils.child(_PLUGIN.path, "viewer\\LR360Viewer.cmd")
    if not LrFileUtils.exists(launcher) then
        LrDialogs.message("LR 360 Viewer",
            "Missing viewer launcher:\n\n" .. launcher, "critical")
        return
    end

    local f = io.open(runFile, "w")
    if not f then
        LrDialogs.message("LR 360 Viewer",
            "Could not create temporary launcher.", "critical")
        return
    end
    f:write('@echo off\r\n')
    f:write('call "' .. launcher .. '" "' .. initialPath ..
        '" "--session" "' .. sessionFile .. '"\r\n')
    f:close()
    LrTasks.execute('cmd.exe /d /c ""' .. runFile .. '""')

    local function processImportRequest()
        if not LrFileUtils.exists(importRequestFile) then return end
        local rf = io.open(importRequestFile, "r")
        local sourcePath = rf and rf:read("*l") or nil
        local newPath = rf and rf:read("*l") or nil
        if rf then rf:close() end
        pcall(function() LrFileUtils.delete(importRequestFile) end)
        if not sourcePath or not newPath or sourcePath == "" or newPath == "" or
           not LrFileUtils.exists(newPath) then return end

        local stackPhoto = photosByPath[sourcePath] or
            catalog:findPhotoByPath(sourcePath)
        if not stackPhoto then return end
        local ok, err = catalog:withWriteAccessDo(
            "Import 360 Perspective",
            function() catalog:addPhoto(newPath, stackPhoto, "below") end)
        if not ok then
            LrDialogs.message("LR 360 Viewer",
                "The perspective was saved, but Lightroom could not add it to the stack:\n\n" ..
                tostring(err), "warning")
        end
    end

    local function processRenderRequest()
        if not LrFileUtils.exists(renderRequestFile) then return nil end
        pcall(function() LrFileUtils.delete(renderRequestFile) end)

        local photo = getActivePhoto(catalog)
        local sourcePath = getPhotoPath(photo)
        if not photo or not sourcePath then
            currentRendering = false
            currentMessage = "No active Lightroom photo is available to render."
            publishState(false)
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
        publishState(false)

        local renderedPath, renderError = renderWithLightroom(photo, sessionDir)
        currentRendering = false
        if renderedPath then renderedFiles[renderedPath] = true end

        local activeAfterRender = getActivePhoto(catalog)
        local activeAfterPath = getPhotoPath(activeAfterRender)
        if activeAfterRender and activeAfterPath then
            photosByPath[activeAfterPath] = activeAfterRender
        end
        if activeAfterPath and activeAfterPath ~= sourcePath then
            switchToDirectSource(activeAfterRender, activeAfterPath)
        elseif renderedPath then
            currentDisplayPath = renderedPath
            currentDisplayKind = "lightroom_render"
            currentMessage = ""
            publishState(true)
        else
            currentMessage = "Lightroom render failed: " .. tostring(renderError)
            publishState(false)
        end
        return activeAfterPath or sourcePath
    end

    local startedAt = LrDate.currentTime()
    local seenAlive = false
    local lastAliveValue = nil
    local lastAliveChangeAt = startedAt
    local observedPath = initialPath
    local pendingPath, pendingPhoto, pendingSince = nil, nil, 0

    while LrDate.currentTime() < startedAt + 21600 do
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
            seenAlive = true
        end
        if (seenAlive and now - lastAliveChangeAt >= 15) or
           (not seenAlive and now - startedAt > 45) then
            break
        end
        LrTasks.sleep(0.15)
    end

    processImportRequest()
    for path, _ in pairs(renderedFiles) do
        pcall(function() LrFileUtils.delete(path) end)
    end
    for _, path in ipairs({ renderRequestFile, importRequestFile,
            aliveFile, sessionFile, runFile }) do
        pcall(function()
            if LrFileUtils.exists(path) then LrFileUtils.delete(path) end
        end)
    end
    pcall(function() LrFileUtils.delete(sessionDir) end)
end)
