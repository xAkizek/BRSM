import discord, pyautogui, pyperclip, psutil, asyncio, json, os, re, cv2, mss
import pygetwindow as gw
import numpy as np
from PIL import ImageGrab
from PIL import Image
from io import BytesIO
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('YOUR_BOT_TOKEN')

pyautogui.FAILSAFE = False

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

bot.auto_message_task = None
bot.in_progress = False

@bot.event
async def on_ready():
    print(f'✅ - Logged in as {bot.user}')
    await bot.tree.sync()

    clear_chat_logs()

    bot.loop.create_task(monitor_game_log())
    bot.loop.create_task(setup_auto_restart())

    commands_list = [f'/{command.name}' for command in bot.tree.get_commands()]
    print(f'📜 - Commands: {", ".join(commands_list)}')
    
    activity = discord.Activity(type=discord.ActivityType.listening, name="/help | BRSM v0.2.0")
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print(f'🤖 - BRSM v0.2.0 | Support server: https://discord.gg/Wnm5UEZHxR')

# ====[ CONFIG ]================================================================================================================
default_config = {
    "roles_id": [],
    "blacklist": False,
    "blacklist_logs": None,
    "blacklist_objects": [],
    "ban_duration": "infinite",
    "ban_message": "You have been banned by BRSM v0.2.0 | https://discord.gg/Wnm5UEZHxR",
    "max_warnings": 2,
    "warning_message": "{player_name}, you are using a blacklisted vehicle. Please stop using it, otherwise you will be banned.",
    "auto_restart": False
}

config_path = f"C:\\Users\\{os.getlogin()}\\AppData\\Local\\BrickRigs\\SavedRemastered\\Config\\WindowsNoEditor\\Game.ini"

def load_config():
    global config
    try:
        with open("config.json", "r", encoding="utf-8") as file:
            config = json.load(file)
        if any(key not in config for key in default_config):
            raise ValueError
    except (FileNotFoundError, json.JSONDecodeError, ValueError):
        print("🔧 - Config not found or invalid. Creating a new one with default values.")
        config = default_config.copy()
        save_config()

def save_config():
    global config
    with open("config.json", "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)

load_config()

# ====[ CHECK ROLES ]================================================================================================================
async def check_roles(interaction, bot):
    required_roles = config.get("roles_id", None)

    if not required_roles:
        embed = discord.Embed(description="**⚠️・Allowed roles have not been set. To set them, go to: /settings > Allowed Roles.**", color=0xffc633)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return False

    user_roles = [role.id for role in interaction.user.roles]

    if any(role_id in user_roles for role_id in required_roles):
        return True

    embed = discord.Embed(description="**⛔・You don't have the required role to use this command.**", color=0xd94930)
    await interaction.response.send_message(embed=embed, ephemeral=True)
    return False

# ====[ CLOSE BRICK RIGS ]================================================================================================================
async def close_brick_rigs(interaction: discord.Interaction):
    closed = False
    for process in psutil.process_iter(['name']):
        if process.info['name'] == 'BrickRigs-Win64-Shipping.exe':
            process.terminate()
            process.wait(timeout=10)
            closed = True

    if not closed:
        embed = discord.Embed(description="**⚠️・Brick Rigs was not active or could not be closed.**", color=0xffc633)
        await interaction.followup.send(embed=embed, ephemeral=True)
        return False
    return True

# ====[ CLEAR CHAT LOGS ]================================================================================================================
def clear_chat_logs():
    with open(config_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    lines_to_keep = [line for line in lines if not line.startswith("ChatMessageLog")]

    with open(config_path, "w", encoding="utf-8") as file:
        file.writelines(lines_to_keep)

# ====[ ACTIVE WINDOW ]================================================================================================================
def active_window():
    window = gw.getWindowsWithTitle('Brick Rigs')
    return window and window[0].isActive if window else False

# ====[ PRESS KEYS ]================================================================================================================
async def press_keys(keys, delay=0.2):
    for key in keys:
        pyautogui.press(key)
        await asyncio.sleep(delay)

# ====[ HELP ]================================================================================================================
@bot.tree.command(name="help", description="Bot info and more.")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="Brick Rigs Server Management v0.2.0", color=0xff971a)

    embed.add_field(
        name="🔧・Commands:",
        value="```/settings, /game, /configuration, /banned-list, /ban, /unban, /restart, /send-message, /auto-message, /blacklist```",
        inline=False
    )

    view = discord.ui.View(timeout=None)
    support_button = discord.ui.Button(label="Support Server", style=discord.ButtonStyle.link, url="https://discord.gg/Wnm5UEZHxR")
    view.add_item(support_button)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ====[ SETTINGS ]================================================================================================================
@bot.tree.command(name="settings", description="Bot configuration and more.") 
async def settings(interaction: discord.Interaction):
    required_roles = config.get("roles_id", [])

    user_roles = [role.id for role in interaction.user.roles]

    if required_roles and not any(role_id in user_roles for role_id in required_roles):
        embed = discord.Embed(description="**⛔・You don't have the required role to use this command.**", color=0xd94930)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if not required_roles and not interaction.user.guild_permissions.administrator:
        embed = discord.Embed(description="**⛔・You don't have Administrator permissions to use this command.**", color=0xd94930)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="Settings",
        description="**Select an option from the menu below.**",
        color=0xff971a
    )

    settings_select = discord.ui.Select(
        placeholder="Select an option...",
        options=[
            discord.SelectOption(label="Allowed Roles", value="allowed_roles", description="Select roles that will allow you to use commands."),
            discord.SelectOption(label="Toggle Blacklist", value="toggle_blacklist", description="Enable or disable the blacklist feature."),
            discord.SelectOption(label="Toggle Auto Restart", value="toggle_auto_restart", description="Enable or disable auto restart after 100 rounds."),
            discord.SelectOption(label="Stop Auto Message", value="stop_auto_message", description="Disable current auto message operation.")
        ]
    )

    async def settings_select_callback(interaction: discord.Interaction):
        if settings_select.values[0] == "allowed_roles":
            await allowed_roles(interaction)
        elif settings_select.values[0] == "toggle_blacklist":
            await toggle_blacklist(interaction)
        elif settings_select.values[0] == "toggle_auto_restart":
            await toggle_auto_restart(interaction)
        elif settings_select.values[0] == "stop_auto_message":
            await stop_auto_message(interaction)

    settings_select.callback = settings_select_callback

    view = discord.ui.View(timeout=None)
    view.add_item(settings_select)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ====[ SETTINGS ALLOWED ROLES ]================================================================================================================
async def allowed_roles(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Allowed Roles",
        description="**Select roles from the menu below to use commands.**",
        color=0xff971a
    )

    selected_roles = config.get("roles_id", [])

    role_options = [
        discord.SelectOption(label=role.name, value=str(role.id), default=str(role.id) in map(str, selected_roles))
        for role in interaction.guild.roles if role.name != "@everyone"
    ][::-1][:25]

    if not role_options:
        embed.description = "**🚧・No roles available. Please add roles to the server.**"
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    role_select = discord.ui.Select(placeholder="Select roles...", options=role_options, min_values=0, max_values=25)

    async def role_select_callback(interaction: discord.Interaction):
        selected_role_id = [int(role_id) for role_id in role_select.values]

        if selected_role_id:
            config["roles_id"] = selected_role_id
            save_config()

            added_roles = ", ".join([f"<@&{role_id}>" for role_id in selected_role_id])
            success_embed = discord.Embed(description=f"**✅・Successfully added roles: {added_roles}.**", color=0x77ab00)

            await interaction.response.send_message(embed=success_embed, ephemeral=True)

        else:
            config["roles_id"] = []
            save_config()

            success_embed = discord.Embed(description="**✅・Successfully removed all roles.**", color=0x77ab00)
            await interaction.response.send_message(embed=success_embed, ephemeral=True)

    role_select.callback = role_select_callback

    view = discord.ui.View(timeout=None)
    view.add_item(role_select)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ====[ SETTINGS TOGGLE BLACKLIST ]================================================================================================================
async def toggle_blacklist(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return

    embed = discord.Embed(
        title="Toggle Blacklist",
        description="**Select an option from the menu below to enable or disable the blacklist.**",
        color=0xff971a
    )

    view = discord.ui.View(timeout=None)

    async def dropdown_callback(interaction: discord.Interaction):
        config["blacklist"] = True if dropdown.values[0] == "enable" else False
        save_config()
        
        await interaction.response.send_message(embed=discord.Embed(description=f"**✅・Blacklist has been {'enabled' if config['blacklist'] else 'disabled'}.**", color=0x77ab00), ephemeral=True)

    dropdown = discord.ui.Select(
        placeholder="Select an option...",
        options=[
            discord.SelectOption(label="Enable", value="enable"),
            discord.SelectOption(label="Disable", value="disable")
        ]
    )

    dropdown.callback = dropdown_callback
    view.add_item(dropdown)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ====[ SETTINGS TOGGLE AUTO RESTART ]================================================================================================================
async def toggle_auto_restart(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return

    embed = discord.Embed(
        title="Toggle Auto Restart",
        description="**Select an option from the menu below to enable or disable auto restart after 100 rounds.**",
        color=0xff971a
    )

    view = discord.ui.View(timeout=None)

    async def dropdown_callback(interaction: discord.Interaction):
        config["auto_restart"] = True if dropdown.values[0] == "enable" else False
        save_config()
        
        bot.auto_restart = config["auto_restart"]
        
        if bot.auto_restart:
            bot.loop.create_task(scan_and_click())
        
        await interaction.response.send_message(embed=discord.Embed(description=f"**✅・Auto restart has been {'enabled' if bot.auto_restart else 'disabled'}.**", color=0x77ab00),ephemeral=True)

    dropdown = discord.ui.Select(
        placeholder="Select an option...",
        options=[
            discord.SelectOption(label="Enable", value="enable"),
            discord.SelectOption(label="Disable", value="disable")
        ]
    )

    dropdown.callback = dropdown_callback
    view.add_item(dropdown)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ====[ SETTINGS TOGGLE AUTO RESTART SYSTEM ]====================================================================
image_folder = "./imgs"
threshold = 0.8

async def setup_auto_restart():
    bot.auto_restart = config.get("auto_restart", False)
    if bot.auto_restart:
        bot.loop.create_task(scan_and_click())

def grab_screenshot():
    screenshot = ImageGrab.grab()
    screenshot_np = np.array(screenshot)
    return cv2.cvtColor(screenshot_np, cv2.COLOR_RGB2BGR)

def find_c_image(c_image, screenshot):
    result = cv2.matchTemplate(screenshot, c_image, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    if max_val >= threshold:
        return max_loc, c_image.shape[1], c_image.shape[0], max_val
    return None, None, None, None

def click_on_location(x, y, w, h):
    center_x = x + w // 2
    center_y = y + h // 2
    pyautogui.moveTo(center_x, center_y)
    pyautogui.click()

async def scan_and_click():
    while config.get("auto_restart", False):
        screenshot = grab_screenshot()
        
        for filename in os.listdir(image_folder):
            if filename.endswith(".png"):
                image_path = os.path.join(image_folder, filename)
                c_image = cv2.imread(image_path, cv2.IMREAD_COLOR)
                
                loc, w, h, similarity = find_c_image(c_image, screenshot)
                if loc:
                    click_on_location(loc[0], loc[1], w, h)
                    break

        await asyncio.sleep(4)

# ====[ SETTINGS STOP AUTO MESSAGES ]================================================================================================================
async def stop_auto_message(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return

    if hasattr(bot, 'auto_message_task') and bot.auto_message_task:
        bot.auto_message_task.cancel()
        bot.auto_message_task = None
        embed = discord.Embed(description="**✅・Auto message has been stopped.**", color=0x77ab00)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        embed = discord.Embed(description="**❌・No active auto message operation found.**", color=0xd94930)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ====[ GAME ]================================================================================================================
@bot.tree.command(name="game", description="Turn the game and server on or off.")
async def game(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return
    
    async def stop_auto_message():
        if hasattr(bot, 'auto_message_task') and bot.auto_message_task:
            bot.auto_message_task.cancel()
            bot.auto_message_task = None

    game_embed = discord.Embed(
        title="Game",
        description="**Select option from the menu below.**",
        color=0xff971a
    )

    class GameModeDropdown(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="On", description="Turns the game and server on.", value="on"),
                discord.SelectOption(label="Off", description="Turns the game and server off.", value="off")
            ]
            super().__init__(placeholder="Select an option...", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            selected_option = self.values[0]

            if selected_option == "on":
                pyautogui.hotkey('win', 'r')
                await asyncio.sleep(0.5)
                pyautogui.typewrite('steam://rungameid/552100')
                await asyncio.sleep(0.5)
                pyautogui.press('enter')
                await asyncio.sleep(20)
                await press_keys(['enter', 'tab', 'enter'])

                embed = discord.Embed(description="**✅・Game turned on successfully.**", color=0x77ab00)
                await interaction.followup.send(embed=embed, ephemeral=True)

            elif selected_option == "off":
                pyautogui.press('esc')
                closed_successfully = await close_brick_rigs(interaction)
                if not closed_successfully:
                    return

                await asyncio.sleep(0.2)
                brick_rigs_windows = [win for win in gw.getWindowsWithTitle('Brick Rigs')]
                if brick_rigs_windows:
                    brick_rigs_windows[0].activate()
                    await asyncio.sleep(1)

                await stop_auto_message()

                clear_chat_logs()

                embed = discord.Embed(description="**✅・Game turned off successfully.**", color=0x77ab00)
                await interaction.followup.send(embed=embed, ephemeral=True)

    dropdown_view = discord.ui.View()
    dropdown_view.add_item(GameModeDropdown())

    await interaction.response.send_message(embed=game_embed, view=dropdown_view, ephemeral=True)

# ====[ CONFIGURATION ]================================================================================================================
@bot.tree.command(name="configuration", description="Allows you to manage all server settings, and much more if you figure it out.")
async def configuration(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return
    
    embed = discord.Embed(description="**🚧・Important! If you are currently using the auto message/auto restart/blacklist feature, it is recommended to disable it.**", color=0xffc633)
    button_view = ConfigurationView()
    
    await interaction.response.send_message(embed=embed, view=button_view, ephemeral=True)

class ConfigurationView(discord.ui.View):
    def __init__(self):
        super().__init__()

        proceed_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.secondary)
        proceed_button.callback = self.proceed_button_callback
        self.add_item(proceed_button)

    async def proceed_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True, ephemeral=True)

        try:
            screenshot_view = ScreenshotView()
            screenshot = screenshot_view.get_screenshot_from_window("Brick Rigs")

            if screenshot:
                with BytesIO() as img_bytes:
                    screenshot.save(img_bytes, format="PNG")
                    img_bytes.seek(0)
                    await interaction.followup.send(file=discord.File(fp=img_bytes, filename="screenshot.png"), view=screenshot_view, ephemeral=True)
            else:
                embed = discord.Embed(description="**❌・Failed to take a screenshot.**", color=0xd94930)
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(description=f"**❌・An error occurred:** \n```{str(e)}```", color=0xd94930)
            await interaction.followup.send(embed=embed, ephemeral=True)

# ====[ CONFIGURATION SYSTEM ]================================================================================================================
class TextInputModal(discord.ui.Modal, title="Text"):
    text_input = discord.ui.TextInput(
        label="Enter text:",
        style=discord.TextStyle.long,
        required=False
    )

    empty_input = discord.ui.TextInput(
        label="Info:",
        default="If you want to remove all the text from the field just don't type anything and click submit button.\n\nAbout the character limit:\n- Server Password: 16\n- Server Name: 64\n- Server Description: 2048",
        style=discord.TextStyle.long,
        required=False
    )

    def __init__(self, callback):
        super().__init__()
        self.callback_func = callback

    async def on_submit(self, interaction: discord.Interaction):
        text_to_paste = self.text_input.value

        if not text_to_paste.strip():
            pyautogui.hotkey("ctrl", "a")
            pyautogui.hotkey("ctrl", "c")
            
            copied_text = pyperclip.paste()

            embed = discord.Embed(description=f"**✅・Field has been cleared successfully:** \n```{copied_text}```", color=0x77ab00)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            pyautogui.press("backspace")  
            return
        
        pyperclip.copy(text_to_paste)
        pyautogui.hotkey("ctrl", "v")
        await self.callback_func(interaction, text_to_paste)

class ScreenshotView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.message = None

        self.add_item(discord.ui.Button(label="ㅤ", style=discord.ButtonStyle.secondary, custom_id="empty_button", row=0))
        self.add_item(discord.ui.Button(label="↑", style=discord.ButtonStyle.primary, custom_id="move_up", row=0))
        self.add_item(discord.ui.Button(label="ㅤ", style=discord.ButtonStyle.secondary, custom_id="empty_button2", row=0))

        self.add_item(discord.ui.Button(label="←", style=discord.ButtonStyle.primary, custom_id="move_left", row=1))
        self.add_item(discord.ui.Button(label="↓", style=discord.ButtonStyle.primary, custom_id="move_down", row=1))
        self.add_item(discord.ui.Button(label="→", style=discord.ButtonStyle.primary, custom_id="move_right", row=1))

        self.add_item(discord.ui.Button(label="Esc", style=discord.ButtonStyle.danger, custom_id="press_esc", row=2))
        self.add_item(discord.ui.Button(label="Tab", style=discord.ButtonStyle.secondary, custom_id="press_tab", row=2))
        self.add_item(discord.ui.Button(label="Enter", style=discord.ButtonStyle.success, custom_id="press_enter", row=2))
        self.add_item(discord.ui.Button(label="Enter Text", style=discord.ButtonStyle.primary, custom_id="enter_text", row=2))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.data["custom_id"] in ["empty_button", "empty_button2"]:
            return False

        actions = {
            "move_up": "up",
            "move_down": "down",
            "move_left": "left",
            "move_right": "right",
            "press_esc": "esc",
            "press_tab": "tab",
            "press_enter": "enter"
        }

        if interaction.data["custom_id"] in actions:
            pyautogui.press(actions[interaction.data["custom_id"]])
        elif interaction.data["custom_id"] == "enter_text":
            modal = TextInputModal(self.on_modal_submit)
            await interaction.response.send_modal(modal)
            return True

        await self.send_screenshot(interaction)
        return True

    async def on_modal_submit(self, interaction: discord.Interaction, text: str):
        embed = discord.Embed(description=f"**✅・Text successfully pasted:** ```\n{text}```", color=0x77ab00)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        await self.send_screenshot(interaction, defer=False)

    def get_screenshot_from_window(self, window_title: str):
        windows = gw.getWindowsWithTitle(window_title)
        if not windows:
            raise Exception(f"Could not find a {window_title} window.")

        window = windows[0]
        window.activate()

        with mss.mss() as sct:
            monitor = {
                "top": window.top,
                "left": window.left,
                "width": window.width,
                "height": window.height
            }
            screenshot = sct.grab(monitor)
            return Image.frombytes("RGB", screenshot.size, screenshot.rgb)

    async def send_screenshot(self, interaction: discord.Interaction, defer=True):
        try:
            if defer:
                await interaction.response.defer()
            screenshot = self.get_screenshot_from_window("Brick Rigs")

            if screenshot:
                with BytesIO() as img_bytes:
                    screenshot.save(img_bytes, format="PNG")
                    img_bytes.seek(0)
                    await interaction.followup.send(file=discord.File(fp=img_bytes, filename="screenshot.png"), view=self, ephemeral=True)
            else:
                embed = discord.Embed(description="**❌・Failed to take a screenshot.**", color=0xd94930)
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            embed = discord.Embed(description=f"**❌・An error occurred:** \n```{str(e)}```", color=0xd94930)
            await interaction.followup.send(embed=embed, ephemeral=True)

# ====[ BANNED LIST ]================================================================================================================
@bot.tree.command(name="banned-list", description="Shows the list of banned players.")
async def banned_list(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return
    
    await interaction.response.defer(ephemeral=True)

    view = BannedListView(interaction, config_path)

    if view.error_embed:
        await interaction.followup.send(embed=view.error_embed, ephemeral=True)
    elif view.banned_pages:
        embed = discord.Embed(
            title="Banned Players List",
            description=view.banned_pages[0],
            color=0xff971a
        ).set_footer(text=f"Page 1/{len(view.banned_pages)}")

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    else:
        await interaction.followup.send(embed=discord.Embed(description="**🚧・Banned players not found.**", color=0xffc633), ephemeral=True)

# ====[ BANNED LIST SYSTEM ]================================================================================================================
class BannedListView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, config_path: str):
        super().__init__(timeout=None)
        self.config_path = config_path
        self.interaction = interaction
        self.current_page = 0

        self.previous_button = discord.ui.Button(label="<", style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label=">", style=discord.ButtonStyle.secondary)

        self.previous_button.callback = self.previous_page
        self.next_button.callback = self.next_page

        self.add_item(self.previous_button)
        self.add_item(self.next_button)

        self.banned_pages, self.error_embed = self.load_banned_pages()

    def load_banned_pages(self):
        banned_pages = []
        current_page = ""

        try:
            with open(self.config_path, "r", encoding="utf-8") as file:
                lines = file.readlines()

            banned_entries = [re.sub(r'^KickedPlayers=', '', line.strip()) for line in lines if line.startswith("KickedPlayers=")]
            pattern = re.compile(
                r'PlayerId=(?P<id>\d*),PlayerName="(?P<name>[^"]*)",KickTime=(?P<time>[\d\-.]*),KickDuration=(?P<duration>[\d+.:]*),KickReason="(?P<reason>[^"]*)"'
            )

            for entry in banned_entries:
                match = pattern.search(entry)
                if match:
                    player_name = match.group('name')
                    player_id = match.group('id')
                    kick_reason = match.group('reason') or "N/A"
                    kick_duration = match.group('duration')
                    kick_time = match.group('time')

                    formatted_entry = (
                        f"Player: {player_name}\n"
                        f"Steam ID: {player_id}\n"
                        f"Reason: {kick_reason}\n"
                        f"Duration: {kick_duration}\n"
                        f"Time: {kick_time}\n"
                    )

                    line = f"```\n{formatted_entry}```"

                    if len(current_page) + len(line) > 4096:
                        banned_pages.append(current_page.strip())
                        current_page = line
                    else:
                        current_page += line

            if current_page:
                banned_pages.append(current_page.strip())

            return banned_pages, None

        except FileNotFoundError:
            error_embed = discord.Embed(description="**❌・Game.ini file not found.**", color=0xd94930)
            return [], error_embed

    async def previous_page(self, interaction: discord.Interaction):
        self.current_page = (self.current_page - 1) % len(self.banned_pages)
        await self.update_embed(interaction)

    async def next_page(self, interaction: discord.Interaction):
        self.current_page = (self.current_page + 1) % len(self.banned_pages)
        await self.update_embed(interaction)

    async def update_embed(self, interaction: discord.Interaction):
        if self.error_embed:
            await interaction.response.edit_message(embed=self.error_embed, view=None)
        else:
            embed = discord.Embed(
                title="Banned Players List",
                description=self.banned_pages[self.current_page],
                color=0xff971a
            )
            embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.banned_pages)}")
            await interaction.response.edit_message(embed=embed, view=self)

# ====[ BAN ]================================================================================================================
@bot.tree.command(name="ban", description="Ban a selected player based on his Steam ID.")
async def ban(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return
    
    if not active_window():
        embed = discord.Embed(description="**🚧・Brick Rigs window must be active to use this command.**", color=0xffc633)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    modal = BanModal()
    await interaction.response.send_modal(modal)

# ====[ BAN SYSTEM ]================================================================================================================
class BanModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Ban Player")

        self.steam_id_input = discord.ui.TextInput(
            label="Player Steam ID:",
            placeholder="76561197960287930",
            max_length=17,
            required=True
        )
        
        self.reason_input = discord.ui.TextInput(
            label="Reason:",
            max_length=100,
            style=discord.TextStyle.long,
            required=True
        )

        self.add_item(self.steam_id_input)
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        steam_id = self.steam_id_input.value
        reason = self.reason_input.value

        view = BanDurationSelectView(steam_id, reason)
        embed = discord.Embed(
            title="Ban Duration",
            description=f"**Select the ban duration for the player with Steam ID [{steam_id}](https://steamcommunity.com/profiles/{steam_id}) from the menu below.**",
            color=0xff971a
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class BanDurationSelectView(discord.ui.View):
    def __init__(self, steam_id, reason):
        super().__init__(timeout=None)
        self.steam_id = steam_id
        self.reason = reason

        self.duration_select = discord.ui.Select(
            placeholder="Select ban duration...",
            options=[
                discord.SelectOption(label="10 minutes", value="10min"),
                discord.SelectOption(label="Infinite", value="infinite")
            ]
        )
        self.duration_select.callback = self.on_duration_select
        self.add_item(self.duration_select)

    async def on_duration_select(self, interaction: discord.Interaction):
        selected_duration = self.duration_select.values[0]
        await perform_ban_action(self.steam_id, self.reason, interaction, selected_duration)

async def perform_ban_action(steam_id, reason, interaction, duration):
    bot.in_progress = True
    await interaction.response.defer()

    await press_keys(['esc', 'tab', 'tab', 'tab', 'enter', 'tab', 'tab', 'enter', 'tab', 'enter'])

    pyperclip.copy(steam_id)
    pyautogui.hotkey("ctrl", "v")

    await press_keys(['tab', 'tab', 'tab', 'tab', 'enter'])

    pyperclip.copy(reason)
    pyautogui.hotkey("ctrl", "v")

    if duration == "10min":
        await press_keys(['tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'enter', 'esc', 'esc'])
    elif duration == "infinite":
        await press_keys(['tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'enter', 'tab', 'enter', 'esc', 'esc'])

    success_embed = discord.Embed(description=f"**✅・Successfully banned a player with Steam ID [{steam_id}](https://steamcommunity.com/profiles/{steam_id}).**", color=0x77ab00)
    await interaction.followup.send(embed=success_embed, ephemeral=True)

    bot.in_progress = False

# ====[ UNBAN ]================================================================================================================
@bot.tree.command(name="unban", description="Unban a selected player based on his Steam ID.")
async def unban(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return
    
    if not active_window():
        embed = discord.Embed(description="**🚧・Brick Rigs window must be active to use this command.**", color=0xffc633)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    modal = UnbanModal()
    await interaction.response.send_modal(modal)

# ====[ UNBAN SYSTEM ]================================================================================================================
class UnbanModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Unban Player")

        self.steam_id_input = discord.ui.TextInput(
            label="Player Steam ID:",
            placeholder="76561197960287930",
            max_length=17,
            required=True
        )

        self.add_item(self.steam_id_input)

    async def on_submit(self, interaction: discord.Interaction):
        steam_id = self.steam_id_input.value

        await perform_unban_action(steam_id, interaction)

async def perform_unban_action(steam_id, interaction):
    bot.in_progress = True
    await interaction.response.defer()

    await press_keys(['esc', 'tab', 'tab', 'tab', 'enter', 'tab', 'tab', 'enter', 'tab', 'enter'])

    pyperclip.copy(steam_id)
    pyautogui.hotkey("ctrl", "v")
    await asyncio.sleep(0.1)

    await press_keys(['tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'enter'])
    pyautogui.press('1')
    await press_keys(['tab', 'tab', 'tab', 'enter', 'esc', 'esc'])

    success_embed = discord.Embed(description=f"**✅・Successfully unbanned a player with Steam ID [{steam_id}](https://steamcommunity.com/profiles/{steam_id}).**", color=0x77ab00)
    await interaction.followup.send(embed=success_embed, ephemeral=True)

    bot.in_progress = False

# ====[ RESTART ]================================================================================================================
@bot.tree.command(name="restart", description="Allows restarting the server in 3 different ways.")
async def restart(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return
    
    if not active_window():
        embed = discord.Embed(description="**🚧・Brick Rigs window must be active to use this command.**", color=0xffc633)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    restart_options = [
        discord.SelectOption(label="Match", value="match_restart", description="Quickly restarts the match."),
        discord.SelectOption(label="Server", value="server_restart", description="Shuts down and restarts the server."),
        discord.SelectOption(label="Game", value="game_restart", description="Restarts the game by shutting it down.")
    ]

    view = discord.ui.View(timeout=None)
    restart_select = discord.ui.Select(placeholder="Select restart type...", options=restart_options)

    async def press_keys(keys, delay=0.2):
        for key in keys:
            pyautogui.press(key)
            await asyncio.sleep(delay)

    async def restart_select_callback(interaction: discord.Interaction):
        bot.in_progress = True
        if not active_window():
            embed = discord.Embed(description="**🚧・Brick Rigs window must be active to perform this operation.**", color=0xffc633)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            bot.in_progress = False
            return

        selected_restart = restart_select.values[0]
        await interaction.response.defer()

        if selected_restart == "match_restart":
            await press_keys(['esc', 'tab', 'tab', 'tab', 'tab', 'enter', 'tab', 'enter', 'enter'])
            embed = discord.Embed(description="**✅・Match restarted successfully.**", color=0x77ab00)
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif selected_restart == "server_restart":
            await press_keys(['esc', 'tab', 'tab', 'tab', 'tab', 'tab', 'enter', 'enter', 'left', 'enter', 'tab', 'enter'])
            embed = discord.Embed(description="**✅・Server restarted successfully.**", color=0x77ab00)
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif selected_restart == "game_restart":
            closed_successfully = await close_brick_rigs(interaction)
            if not closed_successfully:
                return

            await asyncio.sleep(0.2)
            brick_rigs_windows = [win for win in gw.getWindowsWithTitle('Brick Rigs')]
            if brick_rigs_windows:
                brick_rigs_windows[0].activate()
                await asyncio.sleep(1)

            clear_chat_logs()

            pyautogui.hotkey('win', 'r')
            await asyncio.sleep(1)
            pyautogui.typewrite('steam://rungameid/552100')
            await asyncio.sleep(1)
            pyautogui.press('enter')
            await asyncio.sleep(20)
            await press_keys(['enter', 'tab', 'enter'])

            embed = discord.Embed(description="**✅・Game restarted successfully.**", color=0x77ab00)
            await interaction.followup.send(embed=embed, ephemeral=True)

        bot.in_progress = False

    restart_select.callback = restart_select_callback
    view.add_item(restart_select)

    embed = discord.Embed(
        title="Restart Selection",
        description="**Select the type of restart from the menu below.**",
        color=0xff971a
    )

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ====[ SEND MESSAGE ]================================================================================================================
@bot.tree.command(name="send-message", description="Send a single message to the server.")
async def send_message(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return

    if not active_window():
        embed = discord.Embed(description="**🚧・The Brick Rigs window must be active to use this command.**", color=0xffc633)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    modal = SendMessageModal()
    await interaction.response.send_modal(modal)

# ====[ SEND MESSAGE SYSTEM ]================================================================================================================
class SendMessageModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Send Message")

        self.message_input = discord.ui.TextInput(
            label="Message:",
            max_length=150,
            style=discord.TextStyle.long,
            required=True
        )

        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        bot.in_progress = True
        text = self.message_input.value

        if not active_window():
            embed = discord.Embed(description="**🚧・The Brick Rigs window must be active to use this command.**", color=0xffc633)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            bot.in_progress = False
            return

        pyperclip.copy(text)
        pyautogui.press("j")
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")

        embed = discord.Embed(description=f"**✅・Message successfully sent to the server:**```\n{text}```", color=0x77ab00)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        bot.in_progress = False

# ====[ AUTO MESSAGE ]================================================================================================================
@bot.tree.command(name="auto-message", description="Send auto messages to the server.")
async def auto_message(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return
    
    if not active_window():
        embed = discord.Embed(description=f"**🚧・Brick Rigs window must be active to use this command.**", color=0xffc633)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    if hasattr(bot, 'auto_message_task') and bot.auto_message_task and not bot.auto_message_task.done():
        embed = discord.Embed(description="**⚠️・An auto message operation is already in progress. If you're facing issues, use: /settings > Stop Auto Message.**", color=0xffc633)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    modal = AutoMessageModal()
    await interaction.response.send_modal(modal)

async def send_messages(channel, text, delay, interaction):
    was_active = True

    while True:
        if bot.in_progress:
            await asyncio.sleep(1)
            continue

        if not active_window():
            if was_active:
                embed = discord.Embed(description="**🚧・Brick Rigs window is inactive, please return to it to resume the auto message operation.**", color=0xffc633)
                await interaction.followup.send(embed=embed, ephemeral=True)
                was_active = False
            await asyncio.sleep(1)
            continue
        else:
            if not was_active:
                embed = discord.Embed(description="**✅・Operation resumed!**", color=0x77ab00)
                await interaction.followup.send(embed=embed, ephemeral=True)
                was_active = True

        pyperclip.copy(text)
        pyautogui.press("j")
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        await asyncio.sleep(delay)

async def send_feedback(interaction, message, color=0xff971a):
    embed = discord.Embed(description=message, color=color)
    await interaction.followup.send(embed=embed, ephemeral=True)

# ====[ AUTO MESSAGE SYSTEM ]================================================================================================================
class AutoMessageModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Auto Message")

        self.message_input = discord.ui.TextInput(
            label="Message:",
            max_length=150,
            style=discord.TextStyle.long,
            required=True
        )
        
        self.delay_input = discord.ui.TextInput(
            label="Delay (in seconds):",
            placeholder="5 min = 300 seconds",
            style=discord.TextStyle.short,
            required=True
        )

        self.add_item(self.message_input)
        self.add_item(self.delay_input)

    async def on_submit(self, interaction: discord.Interaction):
        text = self.message_input.value

        try:
            delay = int(self.delay_input.value)
            if delay <= 0:
                raise ValueError
        except ValueError:
            embed = discord.Embed(description=f"**⚠️・Incorrect value in the delay field. Please enter a number greater than 0.**```\n{text}```", color=0xffc633)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        auto_message_embed = discord.Embed(
            title="Auto Message",
            color=0xff971a
        )

        auto_message_embed.add_field(
            name="✏️・Message:",
            value=f"```\n{text}```",
            inline=False
        )

        auto_message_embed.add_field(
            name="⏰・Delay:",
            value=f"```\n{delay} seconds```",
            inline=False
        )

        auto_message_embed.set_footer(text="If this message disappears or there is another issue, use: /settings > Stop Auto Message.")

        view = discord.ui.View(timeout=None)
        stop_button = discord.ui.Button(label="Stop", style=discord.ButtonStyle.danger)

        async def stop_auto_message(interaction: discord.Interaction):
            if hasattr(bot, 'auto_message_task') and bot.auto_message_task:
                bot.auto_message_task.cancel()
                bot.auto_message_task = None
                stop_embed = discord.Embed(description="**✅・Auto message has been stopped.**", color=0x77ab00)
                await interaction.response.edit_message(embed=stop_embed, view=None)

        stop_button.callback = stop_auto_message
        view.add_item(stop_button)

        await interaction.response.send_message(embed=auto_message_embed, view=view, ephemeral=True)

        bot.auto_message_task = bot.loop.create_task(send_messages(interaction.channel, text, delay, interaction))

# ====[ BLACKLIST ] ================================================================================================================
@bot.tree.command(name="blacklist", description="Add objects to the blacklist, modify them, and more.")
async def blacklist(interaction: discord.Interaction):
    if not await check_roles(interaction, bot):
        return

    blacklist_status = config.get("blacklist")

    if not blacklist_status:
        embed = discord.Embed(description="**⚠️・Blacklist is disabled. Enable it in: /settings > Toggle Blacklist.**", color=0xffc633)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    embed = discord.Embed(
        title="Blacklist",
        description="**Select the button below that interests you.**",
        color=0xff971a
    )

    view = discord.ui.View(timeout=None)

    add_button = discord.ui.Button(label="Add", style=discord.ButtonStyle.success, emoji="📥")
    modify_button = discord.ui.Button(label="Modify", style=discord.ButtonStyle.primary, emoji="✏️")
    config_button = discord.ui.Button(label="Config", style=discord.ButtonStyle.secondary, emoji="🔧")

    async def add_callback(interaction: discord.Interaction):
        modal = BlacklistAddModal()
        await interaction.response.send_modal(modal)

    add_button.callback = add_callback
    modify_button.callback = modify_callback
    config_button.callback = config_callback

    view.add_item(add_button)
    view.add_item(modify_button)
    view.add_item(config_button)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ====[ BLACKLIST SYSTEM ]================================================================================================================
def extract_steam_id(line):
    match = re.search(r'PlayerId=(\d+)', line)
    if match:
        return match.group(1)
    return None

def extract_player_name(line):
    match = re.search(r'PlayerName="([^"]+)"', line)
    if match:
        return match.group(1)
    return None

def send_warning_message(player_name):
    warning_message = config["warning_message"].replace("{player_name}", player_name)
    pyperclip.copy(warning_message)

    pyautogui.press("j")
    pyautogui.hotkey("ctrl", "v")
    pyautogui.press("enter")

async def perform_action_after_max_warnings(steam_id, ban_message):
    bot.in_progress = True

    brick_rigs_windows = [win for win in gw.getWindowsWithTitle('Brick Rigs')]
    if brick_rigs_windows:
        brick_rigs_windows[0].activate()

    await asyncio.sleep(0.1)

    await press_keys(['esc', 'tab', 'tab', 'tab', 'enter', 'tab', 'tab', 'enter', 'tab', 'enter'])

    pyperclip.copy(steam_id)
    pyautogui.hotkey("ctrl", "v")
    await asyncio.sleep(0.2)

    await press_keys(['tab', 'tab', 'tab', 'tab', 'enter'])

    pyperclip.copy(ban_message)
    pyautogui.hotkey("ctrl", "v")
    await asyncio.sleep(0.2)

    ban_duration = config.get("ban_duration", None)
    if ban_duration == "10min":
        await press_keys(['tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'enter', 'esc', 'esc'])
    elif ban_duration == "infinite":
        await press_keys(['tab', 'tab', 'tab', 'tab', 'tab', 'tab', 'enter', 'tab', 'enter', 'esc', 'esc'])

    bot.in_progress = False

async def send_log_message(channel_id, description, color):
    channel = bot.get_channel(channel_id)
    if channel:
        embed = discord.Embed(description=description, color=color)
        await channel.send(embed=embed)
    else:
        error_embed = discord.Embed(description="**❌・Log channel not found.**", color=0xd94930)
        await bot.get_channel(channel_id).send(embed=error_embed)

async def monitor_game_log():
    last_mtime = 0
    blacklist_objects = config.get("blacklist_objects", [])
    warning_count = {}
    log_channel_id = config.get("blacklist_logs", None)

    def clean_vehicle_name(vehicle_name):
        return vehicle_name.replace('\\"', '"')

    while True:
        blacklist_status = config.get("blacklist")

        if not blacklist_status:
            await asyncio.sleep(5)
            continue

        try:
            obj = os.stat(config_path)
            current_mtime = obj.st_mtime
        except FileNotFoundError:
            await asyncio.sleep(1)
            continue

        if current_mtime != last_mtime:
            last_mtime = current_mtime
            blacklist_objects = config.get("blacklist_objects", [])

            with open(config_path, "r", encoding="utf-8") as file:
                lines = file.readlines()
                chat_lines = [line for line in lines if line.startswith("ChatMessageLog")]
                
                if not chat_lines:
                    continue

                last_chat_line = chat_lines[-1]

                player_name = extract_player_name(last_chat_line)
                steam_id = extract_steam_id(last_chat_line)
                if not player_name or not steam_id:
                    continue

                cleaned_last_chat_line = clean_vehicle_name(last_chat_line)

                for item in blacklist_objects:
                    cleaned_item = clean_vehicle_name(item)

                    if f'TextOption=INVTEXT("{cleaned_item}")' in cleaned_last_chat_line:
                        if player_name not in warning_count:
                            warning_count[player_name] = {}

                        if cleaned_item not in warning_count[player_name]:
                            warning_count[player_name][cleaned_item] = 1
                        else:
                            warning_count[player_name][cleaned_item] += 1

                        max_warnings = config.get("max_warnings")
                        log_channel_id = config.get("blacklist_logs")
                        blacklist_objects = config.get("blacklist_objects")

                        if warning_count[player_name][cleaned_item] > max_warnings:
                            ban_message = config["ban_message"]
                            await perform_action_after_max_warnings(steam_id, ban_message)

                            if log_channel_id:
                                description = f"**🔨・Player [{player_name}](https://steamcommunity.com/profiles/{steam_id}) has been banned for using the blacklisted object {cleaned_item}.**"
                                await send_log_message(log_channel_id, description, color=0xd94930)

                            del warning_count[player_name]
                        else:
                            send_warning_message(player_name)

                            if log_channel_id:
                                description = f"**📝・Player [{player_name}](https://steamcommunity.com/profiles/{steam_id}) has been warned for using the blacklisted object {cleaned_item}. Warning #{warning_count[player_name][cleaned_item]}.**"
                                await send_log_message(log_channel_id, description, color=0xffcc4d)

        await asyncio.sleep(1)

# ====[ BLACKLIST ADD BUTTON ]================================================================================================================
class BlacklistAddModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Add Banned Objects")

        self.vehicles_input = discord.ui.TextInput(
            style=discord.TextStyle.long,
            label="Enter Banned Objects:",
            placeholder="Vehicle 1, Vehicle 2...",
            max_length=1024,
            required=True
        )

        self.add_item(self.vehicles_input)

    async def on_submit(self, interaction: discord.Interaction):
        vehicles = {v.strip() for v in self.vehicles_input.value.split(',') if v.strip()}

        existing_blacklist = config.get("blacklist_objects", [])

        new_vehicles = []
        duplicates = []

        for v in vehicles:
            if len(v) > 47:
                v = v[:47] + "..."
            if v not in existing_blacklist:
                new_vehicles.append(v)
            else:
                duplicates.append(v)

        existing_blacklist.extend(new_vehicles)
        config["blacklist_objects"] = existing_blacklist
        save_config()

        embeds = []

        if new_vehicles:
            success_embed = discord.Embed(description=f"**✅・Successfully added vehicles to the blacklist:**```\n{chr(10).join(new_vehicles)}```", color=0x77ab00)
            embeds.append(success_embed)
        if duplicates:
            duplicate_embed = discord.Embed(description=f"**⚠️・The following vehicles are already in the blacklist:**```\n{chr(10).join(duplicates)}```", color=0xffc633)
            embeds.append(duplicate_embed)
        if embeds:
            await interaction.response.send_message(embeds=embeds, ephemeral=True)

# ====[ BLACKLIST MODIFY BUTTON ]=================================================================================
async def modify_callback(interaction: discord.Interaction):
    blacklist_objects = config.get("blacklist_objects", [])
    objects_per_page = 25

    if not blacklist_objects:
        empty_embed = discord.Embed(description="**⚠️・The blacklist is empty. To add objects, use: /blacklist > Add.**", color=0xffc633)
        await interaction.response.send_message(embed=empty_embed, ephemeral=True)
    else:
        view = BlacklistModificationView(interaction, blacklist_objects, objects_per_page)
        await view.show_page(interaction)

class BlacklistModificationView(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, blacklist_objects: list, objects_per_page: int):
        super().__init__(timeout=None)
        self.interaction = interaction
        self.blacklist_objects = blacklist_objects
        self.objects_per_page = objects_per_page
        self.current_page = 0
        self.total_pages = (len(blacklist_objects) + objects_per_page - 1) // objects_per_page

        self.previous_button = discord.ui.Button(label="<", style=discord.ButtonStyle.secondary)
        self.next_button = discord.ui.Button(label=">", style=discord.ButtonStyle.secondary)
        self.remove_all_button = discord.ui.Button(label="Remove All", style=discord.ButtonStyle.danger)

        self.previous_button.callback = self.previous_page
        self.next_button.callback = self.next_page
        self.remove_all_button.callback = self.remove_all

        self.add_item(self.previous_button)
        self.add_item(self.next_button)
        self.add_item(self.remove_all_button)

        self.list_message = None

    async def show_page(self, interaction: discord.Interaction):
        if not self.blacklist_objects:
            cleared_embed = discord.Embed(description="**✅・Successfully cleared the entire blacklist.**", color=0x77ab00)

            empty_view = discord.ui.View()

            if interaction.response.is_done():
                await interaction.followup.send(embed=cleared_embed, view=empty_view, ephemeral=True)
            else:
                await interaction.response.edit_message(embed=cleared_embed, view=empty_view)

            self.list_message = None
            return

        self.total_pages = (len(self.blacklist_objects) + self.objects_per_page - 1) // self.objects_per_page
        if self.current_page >= self.total_pages:
            self.current_page = self.total_pages - 1

        start_idx = self.current_page * self.objects_per_page
        end_idx = start_idx + self.objects_per_page
        page_objects = self.blacklist_objects[start_idx:end_idx]

        formatted_objects = "\n".join(f"- {obj}" for obj in page_objects)
        page_embed = discord.Embed(
            title="Blacklist Modification",
            description=f"{formatted_objects}",
            color=0xff971a
        )
        page_embed.set_footer(text=f"Page {self.current_page + 1}/{self.total_pages}")

        dropdown = BlacklistDropdown(page_objects, start_idx, self) if page_objects else None
        new_view = discord.ui.View()

        if dropdown:
            new_view.add_item(dropdown)
        new_view.add_item(self.previous_button)
        new_view.add_item(self.next_button)
        new_view.add_item(self.remove_all_button)

        if self.list_message:
            await self.list_message.edit(embed=page_embed, view=new_view)
        else:
            if interaction.response.is_done():
                await interaction.followup.send(embed=page_embed, view=new_view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=page_embed, view=new_view, ephemeral=True)
            self.list_message = await interaction.original_response()

    async def previous_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_page = (self.current_page - 1) % self.total_pages
        await self.show_page(interaction)

    async def next_page(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.current_page = (self.current_page + 1) % self.total_pages
        await self.show_page(interaction)

    async def remove_all(self, interaction: discord.Interaction):
        confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.secondary)

        async def confirm_callback(interaction: discord.Interaction):
            await interaction.response.defer()

            config["blacklist_objects"] = []
            save_config()

            success_embed = discord.Embed(description="**✅・Successfully cleared the entire blacklist.**", color=0x77ab00)
            await interaction.followup.send(embed=success_embed, ephemeral=True)

            self.blacklist_objects = []
            self.total_pages = 1
            self.current_page = 0

        confirm_button.callback = confirm_callback

        confirm_view = discord.ui.View()
        confirm_view.add_item(confirm_button)

        confirmation_embed = discord.Embed(description="**📄・Are you sure you want to remove all objects from the blacklist? This action cannot be undone.**", color=0xff971a)

        await interaction.response.send_message(embed=confirmation_embed, view=confirm_view, ephemeral=True)

class BlacklistDropdown(discord.ui.Select):
    def __init__(self, page_objects: list, start_idx: int, parent_view: BlacklistModificationView):
        options = [
            discord.SelectOption(label=obj, value=str(start_idx + idx)) 
            for idx, obj in enumerate(page_objects)
        ]
        super().__init__(placeholder="Select an object to remove...", options=options)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        current_blacklist_objects = config.get("blacklist_objects", [])
        selected_index = int(self.values[0])

        if selected_index < len(current_blacklist_objects):
            selected_object = current_blacklist_objects[selected_index]
            current_blacklist_objects.remove(selected_object)
            config["blacklist_objects"] = current_blacklist_objects
            save_config()

            await self.parent_view.show_page(interaction)

# ====[ BLACKLIST CONFIG BUTTON ]================================================================================================================
async def config_callback(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Blacklist Configuration",
        description="**Select the button below that interests you.**",
        color=0xff971a
    )

    view = discord.ui.View(timeout=None)

    ban_message_button = discord.ui.Button(label="Ban Message", style=discord.ButtonStyle.secondary, emoji="⛔")
    ban_duration_button = discord.ui.Button(label="Ban Duration", style=discord.ButtonStyle.secondary, emoji="⏲")
    warning_button = discord.ui.Button(label="Warning Message", style=discord.ButtonStyle.secondary, emoji="⚠️")
    max_warnings_button = discord.ui.Button(label="Number of Warnings", style=discord.ButtonStyle.secondary, emoji="📄")
    logs_channel_button = discord.ui.Button(label="Logs Channel", style=discord.ButtonStyle.secondary, emoji="📝")

    async def ban_message_callback(interaction: discord.Interaction):
        modal = BanMessageModal()
        await interaction.response.send_modal(modal)

    async def warning_message_callback(interaction: discord.Interaction):
        modal = WarningMessageModal()
        await interaction.response.send_modal(modal)

    async def max_warnings_callback(interaction: discord.Interaction):
        modal = MaxWarningsModal()
        await interaction.response.send_modal(modal)

    ban_message_button.callback = ban_message_callback
    ban_duration_button.callback = ban_duration_callback
    warning_button.callback = warning_message_callback
    max_warnings_button.callback = max_warnings_callback
    logs_channel_button.callback = logs_channel_callback

    view.add_item(ban_message_button)
    view.add_item(ban_duration_button)
    view.add_item(warning_button)
    view.add_item(max_warnings_button)
    view.add_item(logs_channel_button)

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ====[ BLACKLIST BAN MESSAGE ] ==============================================================================================================
class BanMessageModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Ban Message")

        self.ban_message_input = discord.ui.TextInput(
            style=discord.TextStyle.long,
            label="Message:",
            max_length=100,
            default=config.get("ban_message", "You have been banned by BRSM v0.2.0 | https://discord.gg/Wnm5UEZHxR"),
            required=True
        )

        self.add_item(self.ban_message_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_ban_message = self.ban_message_input.value.strip()

        config["ban_message"] = new_ban_message
        save_config()

        embed = discord.Embed(description=f"**✅ Successfully updated the ban message:**\n```{new_ban_message}```", color=0x77ab00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ====[ BLACKLIST BAN DURATION ]=========================================================================================================
async def ban_duration_callback(interaction: discord.Interaction):
    duration_embed = discord.Embed(
        title="Ban Duration",
        description="**Select the ban duration from the menu below.**",
        color=0xff971a
    )

    class BanDurationDropdown(discord.ui.Select):
        def __init__(self):
            options = [
                discord.SelectOption(label="10 minutes", description="Set ban duration to 10 minutes", value="10min"),
                discord.SelectOption(label="Infinite", description="Set ban duration to infinite", value="infinite")
            ]
            super().__init__(placeholder="Select ban duration...", min_values=1, max_values=1, options=options)

        async def callback(self, interaction: discord.Interaction):
            selected_option = self.values[0]

            config["ban_duration"] = selected_option
            save_config()

            embed = discord.Embed(description=f"**✅・Successfully set ban duration to {self.value(selected_option)}.**", color=0x77ab00)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        def value(self, value: str):
            if value == "10min":
                return "10 minutes"
            elif value == "infinite":
                return "infinite"
            return value

    dropdown_view = discord.ui.View()
    dropdown_view.add_item(BanDurationDropdown())

    await interaction.response.send_message(embed=duration_embed, view=dropdown_view, ephemeral=True)

# ====[ BLACKLIST WARNING MESSAGE ]================================================================================================================
class WarningMessageModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Warning Message")

        self.warning_message_input = discord.ui.TextInput(
            style=discord.TextStyle.long,
            label="Message:",
            placeholder="{player_name} – shows the player's name",
            max_length=150,
            default=config.get("warning_message", "{player_name}, you are using a blacklisted vehicle. Please stop using it, otherwise you will be banned."),
            required=True
        )

        self.add_item(self.warning_message_input)

    async def on_submit(self, interaction: discord.Interaction):
        new_warning_message = self.warning_message_input.value.strip()

        config["warning_message"] = new_warning_message
        save_config()

        embed = discord.Embed(description=f"**✅ Successfully updated the warning message:**\n```{new_warning_message}```", color=0x77ab00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ====[ BLACKLIST MAX WARNINGS ] ==============================================================================================================
class MaxWarningsModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Max Warnings")

        self.max_warnings_input = discord.ui.TextInput(
            style=discord.TextStyle.short,
            label="Value:",
            placeholder="0 - instant ban",
            default=config.get("max_warnings", None),
            max_length=3,
            required=True
        )

        self.add_item(self.max_warnings_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            max_warnings = int(self.max_warnings_input.value.strip())

            if max_warnings < 0:
                raise ValueError

            config["max_warnings"] = max_warnings
            save_config()

            embed = discord.Embed(description=f"**✅ Successfully updated the max warnings value to:**\n```{max_warnings}```", color=0x77ab00)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except ValueError as e:
            embed = discord.Embed(description=f"**⚠️・Incorrect value in the delay field. Please enter a number.**", color=0xffc633)
            await interaction.response.send_message(embed=embed, ephemeral=True)

# ====[ BLACKLIST LOGS CHANNEL ] ==============================================================================================================
async def logs_channel_callback(interaction: discord.Interaction):
    channels = interaction.guild.text_channels  
    options = [discord.SelectOption(label=channel.name, value=str(channel.id)) for channel in channels]
    
    select_menu = discord.ui.Select(
        placeholder="Select logs channel...",
        options=options
    )
    
    async def select_callback(interaction: discord.Interaction):
        selected_channel_id = select_menu.values[0]

        with open('config.json', 'r+') as config_file:
            config = json.load(config_file)
            config["blacklist_logs"] = int(selected_channel_id)
            config_file.seek(0)
            json.dump(config, config_file, indent=4)
            config_file.truncate()

        load_config()

        embed = discord.Embed(description=f"**✅・Successfully set the log channel to <#{selected_channel_id}>.**", color=0x77ab00)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    select_menu.callback = select_callback
    
    view = discord.ui.View()
    view.add_item(select_menu)
    
    embed = discord.Embed(title="Logs Channel", description="**Select a logs channel from the menu below.**", color=0xff971a)
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

bot.run(TOKEN)