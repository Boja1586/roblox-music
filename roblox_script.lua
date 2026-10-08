-- Roblox скрипт: подгрузка музыки с твоего сайта
-- Вставь в: executor (loadstring) или LocalScript в StarterPlayerScripts (своя игра)
-- ВАЖНО для своей игры: Game Settings -> Security -> Enable HttpService = ON

local API_URL = "https://ВАШ-ДОМЕН/api/songs" -- <-- ПОМЕНЯЙ

local HttpService = game:GetService("HttpService")

local function loadSongs()
    local ok, res = pcall(function()
        -- в executor game:HttpGet, в обычной игре HttpService:GetAsync
        if game:GetService("RunService"):IsStudio() or true then
            local f = (game.HttpGet or HttpService.GetAsync)
            -- пробуем оба варианта
            local body
            if game.HttpGet then
                body = game:HttpGet(API_URL)
            else
                body = HttpService:GetAsync(API_URL)
            end
            return HttpService:JSONDecode(body)
        end
    end)
    if not ok then
        warn("Не смог загрузить с сайта: " .. tostring(res))
        return {}
    end
    -- сервер отдаёт {songs = {...}}, /raw отдаёт просто текст
    if res.songs then return res.songs end
    if type(res) == "table" then return res end
    return {}
end

local songs = loadSongs()
print("Загружено треков: " .. #songs)
for i, s in ipairs(songs) do
    print(i, s.id, s.name)
end

-- Пример плеера: играет первый трек
local sound = Instance.new("Sound")
sound.Name = "WebMusic"
sound.Parent = workspace
if #songs > 0 then
    sound.SoundId = "rbxassetid://" .. tostring(songs[1].id)
    sound.Volume = 0.5
    sound:Play()
end

-- Простой переключатель в чат: !next / !skip
-- (для executor / своей игры с LocalScript)
local idx = 1
local function play(i)
    idx = ((i - 1) % #songs) + 1
    local s = songs[idx]
    if not s then return end
    sound.SoundId = "rbxassetid://" .. tostring(s.id)
    sound:Play()
    print("▶ " .. tostring(s.id) .. " — " .. tostring(s.name))
end

game.Players.LocalPlayer.Chatted:Connect(function(msg)
    if #songs == 0 then return end
    msg = string.lower(msg)
    if msg == "!next" or msg == "!skip" then play(idx + 1)
    elseif msg == "!prev" then play(idx - 1)
    elseif msg:match("^!play %d+") then
        local n = tonumber(msg:match("%d+"))
        if n then play(n) end
    end
end)
