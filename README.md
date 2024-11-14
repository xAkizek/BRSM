# BRSM (Brick Rigs Server Management)
**BRSM** is a tool for remote management of your Brick Rigs server. With it, you can send custom automated messages, ban and unban players, configure a fully customizable blacklist, and much more.
## How to Use
1. Install [Python 3.13.0 or higher](https://www.python.org/downloads/) and [VS Code](https://code.visualstudio.com) or any other code editor you prefer.
2. Open a terminal and run the following command to install the required libraries:
```
pip install discord.py pyautogui pyperclip psutil python-dotenv pygetwindow pillow opencv-python numpy audioop-lts
```
3. Open the `.env` file and paste your bot token from [Discord Developer Portal](https://discord.com/developers/applications). If you don't know how to do it, [click here](https://www.upwork.com/resources/how-to-make-discord-bot).
```
DISCORD_TOKEN=your_bot_token_here
```
5. Run the `main.py` file to start the program, then **restart Discord** to see all commands.
> [!IMPORTANT]
If you are using the blacklist feature, run the tool before launching the game. Also, make sure the game is in windowed mode, as full-screen mode may prevent some features from working properly.
## Need Help?
If you have any problems, questions or suggestions, join us:
- [Support Discord Server](https://discord.gg/Wnm5UEZHxR)
