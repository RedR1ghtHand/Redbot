

<a id="readme-top"></a>
<h1 align="center">
    RedVoice
</h1>

![image_2025-11-01_124138462](https://github.com/user-attachments/assets/0f0c494a-34b6-4946-a2c9-79e9dd866f3e)

<p align="center">
    Discord temporary channel bot
    <br />
    <a href="https://redmarket.click">Visit Site</a>
    &middot;
    <a href="https://github.com/RedR1ghtHand/RedVoice/issues/new?labels=bug&template=bug-report.md">Report Bug</a>
    &middot;
    <a href="https://github.com/RedR1ghtHand/RedVoice//issues/new?labels=enhancement&template=feature-request.md">Request Feature</a>
</p>

&nbsp;<br/>&nbsp;<br/>&nbsp;<br/>&nbsp;

## About
RedVoice is a discord bot written with python which allows guild users to create a temporary voice channels via entering a specific 🔊 room, with some cool extra features.

## Features
- fully asynchronous
- channel control panel with renaming and member limit adjustment
<img width="417" height="342" alt="image" src="https://github.com/user-attachments/assets/1f950490-30d7-4867-bdd6-0da6b2612f44" />

- all voice sessions stored in database(mongodb) as session, saving context as timestamps, owner, duration, etc
- `/top {1-10}` command to show top sessions sorted by duration
<img width="322" height="435" alt="image" src="https://github.com/user-attachments/assets/3d30915f-8a85-4b40-b4db-976eda154634" />

- `/clean_up_short_sessions` {treshhold in secconds: min 600}(admin only) command to clean up those thouthands of one-minute sessions in database
<img width="425" height="136" alt="image" src="https://github.com/user-attachments/assets/cc39b73e-b5ca-4de8-aab7-bf0aa7c9fb82" />

- names pool: The bot owner can set a list of default names for temporary channels, and the bot will randomly pick one when creating a new channel.

- adjustable messages: The bot owner can customize any button label, icon, or message to better fit their community’s tone or language simply in `messages.yaml` file

## Setup and Startup

### Discord bot
- Create an application on [official discord developer portal](https://discord.com/developers/applications)
- Go to the Bot tab → Add Bot → copy your Token (you’ll need it soon).
- Under OAuth2 → URL Generator, select:
    1. `bot` and `applications.commands` **scopes**
    2. in **Bot Permissions**, tick:
        - *View Channels*
        - *Connect / Speak*
        - *Manage Channels*
        - *Send Messages*
        - *Embed Links*
        - *Use Slash Commands*
    3. Copy the generated URL, paste it in your browser, and invite the bot to your server.

### .env Setup
Copy poject from git
   ```bash
   git clone https://github.com/RedR1ghtHand/RedVoice.git
   ```
Create a `.env` file in the project root with the following variables:

```env
# ==========================
# Discord Bot Configuration
# ==========================
# Your Discord bot token.
BOT_TOKEN=your_discord_bot_token_here

# ==========================
# Guild Configuration
# ==========================
# Comma-separated list of allowed guild (server) IDs.
# To get a guild ID: right-click on the server name -> "Copy Server ID" (Developer Mode must be enabled in Discord settings).
ALLOWED_GUILDS=123456789012345678

# Channel IDs that the bot monitors to create temporary voice channels.
# To get a channel ID: right-click on the channel -> "Copy Channel ID" (Developer Mode must be enabled).
CREATE_CHANNEL_IDS=1424808645812114636,1424808645111111116

# Default channel names the bot will use when creating new temporary channels.
# A random name from this list will be chosen each time.
DEFAULT_CHANNEL_NAMES=Sanctuary,Bunker,Under stairs nook,Kitchen,Garage

# ==========================
# MongoDB Configuration
# ==========================
# MongoDB connection string.
# For Docker setups, use 'mongo' as the hostname (matches the Docker service name).
# For local MongoDB, use 'localhost', or use a MongoDB Atlas connection string (https://cloud.mongodb.com/).
MONGO_URI=mongodb://mongo:27017/redbot
MONGO_DB=redbot

# ==========================
# Logging Configuration
# ==========================
# Available levels: DEBUG, INFO, WARNING, ERROR
LOG_LEVEL=INFO
```

### Docker Setup (Recommended)

The easiest way to run the bot - Docker handles everything:

> [!IMPORTANT] 
> - The `.env` file is automatically loaded by Docker Compose
> - After modifying `.env`, restart containers: `docker-compose restart bot`


1. **Prerequisites**: 
    - [Docker](https://www.docker.com/), [Docker Compose](https://docs.docker.com/compose/install/) installed
    - The repository cloned and `.env` file configured

2. **Build and start the app**:
   ```bash
   docker-compose up -d
   ```

3. **Wait for the containers to start, then enjoy the functionality!**

### Local Development Setup

If you prefer running locally without Docker:
1. **Prerequisites**: 
   - [Python3](https://www.python.org/)
   - The repository cloned and `.env` file configured

2. **Run MongoDB locally** 
   or use [MongoDB Atlas](https://cloud.mongodb.com/) connection string in `.env`:
   

3. **Run**:
   ```bash
   pip install poetry
   ```   
   ```bash
   poetry install 
   ```   
4. **Run the bot**:
   ```bash
   poetry run python -m main
   ```

5. **Wait for the bot to start, then enjoy the functionality!**