# 🎫 Support Ticket Bot (Production-Ready)
> **Modern, High-Performance Discord Support Ticket Bot written in Python 3.12+ and discord.py 2.5+**
> 
> *សៀវភៅណែនាំជាភាសាខ្មែរ និងភាសាអង់គ្លេស (Bilingual Guide in Khmer and English)*

---

## 📑 តារាងមាតិកា / Table of Contents
1. [English Guide](#-english-guide)
   - [Features](#features)
   - [Prerequisites](#prerequisites)
   - [Step 1: Discord Developer Setup & Intents](#step-1-discord-developer-setup--intents)
   - [Step 2: Bot Installation & Dependencies](#step-2-bot-installation--dependencies)
   - [Step 3: Configuration (.env)](#step-3-configuration-env)
   - [Step 4: Launching the Bot](#step-4-launching-the-bot)
   - [Step 5: In-Discord Setup & Panel Creation](#step-5-in-discord-setup--panel-creation)
   - [Command Reference](#command-reference)
   - [Optional Web Admin Dashboard](#optional-web-admin-dashboard)
   - [Troubleshooting](#troubleshooting)
2. [សៀវភៅណែនាំជាភាសាខ្មែរ (Khmer Guide)](#-សៀវភៅណែនាំជាភាសាខ្មែរ-khmer-guide)
   - [លក្ខណៈពិសេសចម្បង](#លក្ខណៈពិសេសចម្បង)
   - [តម្រូវការដំបូង](#តម្រូវការដំបូង)
   - [ជំហានទី១: បង្កើត Discord Application & បើក Intents](#ជំហានទី១-បង្កើត-discord-application--បើក-intents)
   - [ជំហានទី២: ដំឡើង Dependencies](#ជំហានទី២-ដំឡើង-dependencies)
   - [ជំហានទី៣: កំណត់រចនាសម្ព័ន្ធ .env](#ជំហានទី៣-កំណត់រចនាសម្ព័ន្ធ-env)
   - [ជំហានទី៤: បើកដំណើរការ Bot](#ជំហានទី៤-បើកដំណើរការ-bot)
   - [ជំហានទី៥: បង្កើត Ticket Panel ក្នុង Discord](#ជំហានទី៥-បង្កើត-ticket-panel-ក្នុង-discord)
   - [បញ្ជីពាក្យបញ្ជា (Commands)](#បញ្ជីពាក្យបញ្ជា-commands)
   - [ការដោះស្រាយបញ្ហា (Troubleshooting)](#ការដោះស្រាយបញ្ហា-troubleshooting)

---

# 🇬🇧 English Guide

## Features
- **100% Persistent Interactive UI**: Panel buttons, in-channel ticket controls, and modals remain functional across bot reboots.
- **Automated Lifecycle**: 1-click private ticket channel generation, permission isolation (@everyone blocked), user addition/removal.
- **Single-Staff Claim Engine**: Staff can claim tickets; prevents overlapping staff interference unless released.
- **HTML & Plain Text Transcripts**: Generates standalone Discord Dark theme transcripts with avatars, timestamps, and attachment previews, dispatched to log channels and user DMs.
- **Smart Greetings & Keyword Auto-Responder**: Category-specific automated welcomes and keyword answers (e.g., "pay", "order", "refund").
- **Admin Suite & Analytics**: Interactive Discord select menu `/ticket-config`, stats dashboard (`/ticket-stats`), and ticket directory.
- **Optional FastAPI Dashboard**: Real-time browser web portal for monitoring metrics, ticket activity, and staff leaderboards.
- **Unified Database**: SQLite by default (zero configuration) with optional PostgreSQL / Supabase connectivity.

---

## Prerequisites
- **Python**: Version 3.12 or newer.
- **Operating System**: Windows 10/11, Linux (Ubuntu/Debian), or macOS / VPS.
- **Discord Account**: With administrator rights on your target Discord server.

---

## Step 1: Discord Developer Setup & Intents

1. Navigate to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application**, name your application (e.g., `Support Ticket Bot`), and click **Create**.
3. Under the **Bot** tab on the left menu:
   - Click **Reset Token** and copy the generated token (this is your `DISCORD_TOKEN`).
   - Scroll down to **Privileged Gateway Intents** and enable ALL three:
     - ✅ **Presence Intent**
     - ✅ **Server Members Intent**
     - ✅ **Message Content Intent**
   - Click **Save Changes**.
4. Under the **OAuth2** -> **URL Generator** tab:
   - Under **Scopes**, select: `bot` and `applications.commands`.
   - Under **Bot Permissions**, select: `Administrator` (or explicitly: `Manage Channels`, `Manage Roles`, `View Channels`, `Send Messages`, `Embed Links`, `Attach Files`, `Read Message History`).
   - Copy the generated URL at the bottom, paste it into your browser, and authorize the bot to your server.

---

## Step 2: Bot Installation & Dependencies

Open PowerShell, Command Prompt, or your Linux terminal inside the project directory:

### Windows (PowerShell / CMD)
```powershell
# 1. Create a virtual environment
python -m venv venv

# 2. Activate the virtual environment
venv\Scripts\activate

# 3. Upgrade pip and install requirements
pip install --upgrade pip
pip install -r requirements.txt
```

### Linux / macOS
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 3: Configuration (.env)

Copy the `.env.example` file to create your active `.env`:

```powershell
# Windows
copy .env.example .env

# Linux / Mac
cp .env.example .env
```

Open `.env` in any text editor and fill in your details:
```env
# Required: Paste your Discord Bot Token
DISCORD_TOKEN=your_actual_bot_token_here

# Recommended for instant slash command synchronization:
# Right click your Discord server icon -> Copy Server ID
GUILD_ID=123456789012345678

# Database URL (Default SQLite runs locally without any setup)
DATABASE_URL=sqlite:///tickets.db

# Ticket settings
MAX_OPEN_TICKETS=1
TICKET_NAME_FORMAT=ticket-{id:06d}
AUTOREPLY_ENABLED=true

# Optional Web Admin Dashboard
ENABLE_DASHBOARD=false
DASHBOARD_PORT=8080
DASHBOARD_ADMIN_USER=admin
DASHBOARD_ADMIN_PASSWORD=your_secure_password
```

---

## Step 4: Launching the Bot

Make sure your virtual environment is active:
```powershell
python bot.py
```

Expected output:
```text
[2026-09-24 05:00:00] [INFO   ] ticketbot.database: Connected to SQLite database at: tickets.db
[2026-09-24 05:00:00] [INFO   ] ticketbot.migrations: Database schema initialized and verified successfully.
[2026-09-24 05:00:01] [INFO   ] ticketbot.events: Logged in as Support Ticket Bot (123456789)
[2026-09-24 05:00:01] [INFO   ] ticketbot.events: Registered persistent views: TicketPanelView, TicketControlView
[2026-09-24 05:00:02] [INFO   ] ticketbot.events: Synced 18 slash commands directly to Guild ID.
```

---

## Step 5: In-Discord Setup & Panel Creation

1. **Configure System Settings**:
   Run `/ticket-config` in your Discord server.
   Use the interactive menus to select:
   - **Support Role**: The role given to your support agents.
   - **Audit Log Channel**: The channel where ticket events will be audited.
   - **Transcript Channel**: The channel where HTML/TXT transcripts are uploaded.
2. **Post the Ticket Panel**:
   In your designated support channel (e.g., `#open-ticket`), run:
   ```
   /ticket-panel
   ```
   The bot will post the professional embed with interactive buttons (`🎫 Create Ticket`, `💳 Payment Support`, `🛒 Purchase Support`, `🐛 Report Problem`, `📞 Contact Staff`).

---

## Command Reference

### Admin & Configuration
| Command | Description |
|---|---|
| `/ticket-panel [channel]` | Deploys the interactive ticket panel embed |
| `/ticket-config` | Opens interactive dropdown UI to configure roles, channels, and limits |
| `/ticket-settings` | Configure settings via direct slash parameters |
| `/ticket-stats` | Displays all-time analytics and staff claim leaderboards |
| `/ticket-list [status]` | Lists recent tickets filtered by status (open/closed) |

### In-Ticket Staff Commands
| Command | Description |
|---|---|
| `/ticket-claim` | Claims the active ticket channel for the caller |
| `/ticket-unclaim` | Releases staff claim on the ticket |
| `/ticket-close [reason]` | Closes the ticket, locks permissions, and generates transcripts |
| `/ticket-reopen` | Restores user messaging permissions and reopens ticket |
| `/ticket-delete [reason]` | Deletes channel after saving final transcript |
| `/ticket-add <user>` | Grants a member access to the ticket |
| `/ticket-remove <user>` | Revokes a member's access from the ticket |
| `/ticket-transcript` | Generates and exports HTML transcript immediately |

### Member Registration Commands (Citizen System)
| Command | Description |
|---|---|
| `/register` | Opens interactive registration modal for character/citizen profile |
| `/register-panel [channel]` | Deploys the persistent Member Registration Panel with button |
| `/register-status [member]` | Checks verification status and registration details |
| `/register-user <member> <name> <phone_or_id>` | Admin manually registers/verifies a member |
| `/unregister-user <member>` | Admin revokes registration from a member |
| `/register-settings` | Configures registration requirement, role, and log channel |
| `/register-list [page]` | Lists verified members directory with pagination |

### Auto-Reply & Keyword Engine
| Command | Description |
|---|---|
| `/autoreply list` | Lists all category welcome messages |
| `/autoreply set <cat> <msg>` | Sets custom welcome message for a category |
| `/autoreply enable <cat>` | Enables greeting for a category |
| `/autoreply disable <cat>` | Disables greeting for a category |
| `/autoreply reset <cat>` | Resets category greeting to default |
| `/keyword list` | Lists all active keyword triggers |
| `/keyword add <key> <res>` | Registers an automatic keyword response inside tickets |
| `/keyword remove <key>` | Deletes a keyword trigger |

---

## Optional Web Admin Dashboard
If `ENABLE_DASHBOARD=true` in `.env`, the bot automatically launches a web dashboard at:
```
http://localhost:8080/dashboard
```
- **Login**: Use `DASHBOARD_ADMIN_USER` and `DASHBOARD_ADMIN_PASSWORD`.
- **Features**: Real-time stats widgets, staff claim leaderboards, and settings manager.

---

## Troubleshooting
- **Slash commands not showing up?**
  Set `GUILD_ID=your_server_id` in `.env` for instant registration. Global registration across Discord takes up to 60 minutes.
- **Bot cannot create ticket channels?**
  Verify the bot has `Administrator` or `Manage Channels` permissions in Discord, and that its role is higher in the hierarchy than the channels it creates.
- **"Privileged Intents" Error?**
  Go to Discord Developer Portal -> Bot -> Scroll to **Privileged Gateway Intents** -> Enable **Message Content Intent**, **Server Members Intent**, and **Presence Intent**.

---
---

# 🇰🇭 សៀវភៅណែនាំជាភាសាខ្មែរ (Khmer Guide)

## លក្ខណៈពិសេសចម្បង
- **UI ដែលមិនបាត់បង់មុខងារ (Persistent Views)**: ប៊ូតុង និងម៉ឺនុយទាំងអស់នៅតែដំណើរការធម្មតា ទោះបីជា Bot ត្រូវបាន Restart ឬបិទបើកឡើងវិញក៏ដោយ។
- **ការគ្រប់គ្រងសំបុត្រស្វ័យប្រវត្តិ (Automated Lifecycle)**: ចុចតែ ១ ក្លីក បង្កើត Channel ឯកជនភ្លាមៗ បិទសិទ្ធិ @everyone មិនឲ្យមើលឃើញ និងផ្ដល់សិទ្ធិត្រឹមត្រូវជូនម្ចាស់សំបុត្រ និងក្រុម Support។
- **ប្រព័ន្ធ Staff Claim**: បុគ្គលិកជំនួយអាចចុច Claim ដើម្បីទទួលខុសត្រូវរៀងៗខ្លួន។
- **Transcript ជា HTML យ៉ាងស្រស់ស្អាត**: បង្កើតកំណត់ត្រាការសន្ទនា (HTML & TXT) ដែលមានរូបភាព Profile, ពេលវេលា, និង File ភ្ជាប់ រួចផ្ញើចូលទៅ Channel Log និង DM ជូនអ្នកបង្កើតសំបុត្រ។
- **ប្រព័ន្ធឆ្លើយតបស្វ័យប្រវត្តិ (Auto-Reply & Keywords)**: ឆ្លើយតបស្វាគមន៍តាមប្រភេទបញ្ហា និងឆ្លើយតបស្វ័យប្រវត្តិតាមពាក្យគន្លឹះដូចជា "pay", "order", "refund"។
- **ផ្ទាំងគ្រប់គ្រង Web Dashboard (FastAPI)**: អាចមើលស្ថិតិសរុប ចំនួនសំបុត្របើក/បិទ និងតារាងបុគ្គលិកឆ្នើមតាម Browser។

---

## តម្រូវការដំបូង
1. **Python**: កំណែ 3.12 ឬខ្ពស់ជាងនេះ។
2. **ប្រព័ន្ធប្រតិបត្តិការ**: Windows, Linux, ឬ VPS។
3. **គណនី Discord**: ដែលមានសិទ្ធិ Administrator លើ Discord Server របស់អ្នក។

---

## ជំហានទី១: បង្កើត Discord Application & បើក Intents

1. ចូលទៅកាន់ [Discord Developer Portal](https://discord.com/developers/applications)។
2. ចុច **New Application** ដាក់ឈ្មោះ Bot (ឧទាហរណ៍ `Support Ticket Bot`) រួចចុច **Create**។
3. ចូលទៅកាន់ Menu **Bot** នៅខាងឆ្វេង៖
   - ចុច **Reset Token** រួច Copy Token ទុក (នេះជា `DISCORD_TOKEN`)។
   - អូសចុះមកក្រោមត្រង់ **Privileged Gateway Intents** ហើយបើកទាំង ៣ នេះ៖
     - ✅ **Presence Intent**
     - ✅ **Server Members Intent**
     - ✅ **Message Content Intent**
   - ចុច **Save Changes**។
4. ចូលទៅកាន់ Menu **OAuth2** -> **URL Generator**៖
   - ត្រង់ **Scopes** ជ្រើសរើស: `bot` និង `applications.commands`។
   - ត្រង់ **Bot Permissions** ជ្រើសរើស: `Administrator`។
   - Copy Link នៅខាងក្រោមយកទៅបើកលើ Browser ដើម្បី Invite Bot ចូលទៅក្នុង Server របស់អ្នក។

---

## ជំហានទី២: ដំឡើង Dependencies

បើក PowerShell ឬ Command Prompt នៅក្នុង Folder របស់ Bot៖

```powershell
# ១. បង្កើត Virtual Environment
python -m venv venv

# ២. បើកដំណើរការ Virtual Environment (Windows)
venv\Scripts\activate

# ៣. ដំឡើងបណ្ណាល័យដែលត្រូវការ
pip install --upgrade pip
pip install -r requirements.txt
```

---

## ជំហានទី៣: កំណត់រចនាសម្ព័ន្ធ .env

ចម្លង File `.env.example` ទៅជា `.env`៖
```powershell
copy .env.example .env
```

បើក File `.env` រួចបំពេញព័ត៌មាន៖
```env
DISCORD_TOKEN=ដាក់_TOKEN_របស់_BOT_នៅទីនេះ
GUILD_ID=ដាក់_SERVER_ID_របស់អ្នក_ដើម្បីឲ្យចេញ_SLASH_COMMAND_ភ្លាមៗ
DATABASE_URL=sqlite:///tickets.db
MAX_OPEN_TICKETS=1
TICKET_NAME_FORMAT=ticket-{id:06d}
AUTOREPLY_ENABLED=true
```

---

## ជំហានទី៤: បើកដំណើរការ Bot

ដំណើរការ Bot ដោយប្រើពាក្យបញ្ជា៖
```powershell
python bot.py
```
នៅពេល Bot ដំណើរការជោគជ័យ អ្នកនឹងឃើញសារថា `Logged in as Support Ticket Bot` និង `Synced slash commands`។

---

## ជំហានទី៥: បង្កើត Ticket Panel ក្នុង Discord

1. **កំណត់ Role និង Channel**:
   វាយពាក្យបញ្ជា `/ticket-config` ក្នុង Discord Server របស់អ្នក។ វានឹងបង្ហាញផ្ទាំង Menu ឲ្យអ្នកជ្រើសរើស Support Role, Audit Log Channel, និង Transcript Channel ដោយងាយស្រួល។
2. **ដាក់ផ្ទាំងបង្កើតសំបុត្រ (Ticket Panel)**:
   ចូលទៅកាន់ Channel ជំនួយរបស់អ្នក (ឧទាហរណ៍ `#support`) រួចវាយ៖
   ```
   /ticket-panel
   ```
   Bot នឹងផ្ញើផ្ទាំង Embed ដែលមានប៊ូតុងចុចបង្កើតសំបុត្រ (`🎫 Create Ticket`, `💳 Payment Support`, `🛒 Purchase Support`, `🐛 Report Problem`, `📞 Contact Staff`)។

---

## បញ្ជីពាក្យបញ្ជា (Commands)

### ការគ្រប់គ្រងទូទៅ
- `/ticket-panel`: បង្ហាញផ្ទាំងចុចបើកសំបុត្រ
- `/ticket-config`: បើកផ្ទាំងកំណត់រចនាសម្ព័ន្ធ Server
- `/ticket-settings`: កំណត់តាមរយៈ Slash Parameters ផ្ទាល់
- `/ticket-stats`: មើលស្ថិតិសរុប និងបុគ្គលិកដែលបានជួយច្រើនជាងគេ
- `/ticket-list`: មើលបញ្ជីសំបុត្រទាំងអស់

### សម្រាប់បុគ្គលិកក្នុង Channel សំបុត្រ
- `/ticket-claim`: ទទួលយកសំបុត្រនេះមកដោះស្រាយ
- `/ticket-unclaim`: លែងសិទ្ធិទទួលខុសត្រូវសំបុត្រ
- `/ticket-close`: បិទសំបុត្រ និងទាញយក Transcript
- `/ticket-reopen`: បើកសំបុត្រឡើងវិញ
- `/ticket-delete`: លុប Channel សំបុត្រចោលជាស្ថាពរ
- `/ticket-add <user>`: បន្ថែមសមាជិកចូលក្នុងសំបុត្រ
- `/ticket-remove <user>`: ដកសមាជិកចេញពីសំបុត្រ
- `/ticket-transcript`: ទាញយក File កំណត់ត្រាការសន្ទនា (HTML)

### ប្រព័ន្ធចុះឈ្មោះសមាជិក (Registration System)
- `/register`: បើកផ្ទាំងចុះឈ្មោះសម្រាប់អ្នកប្រើប្រាស់
- `/register-panel [channel]`: ដាក់ផ្ទាំងចុះឈ្មោះសមាជិកដែលមានប៊ូតុងចុច
- `/register-status [member]`: ពិនិត្យមើលព័ត៌មាន និងស្ថានភាពចុះឈ្មោះ
- `/register-user`: Admin ចុះឈ្មោះឲ្យសមាជិកផ្ទាល់
- `/unregister-user`: Admin ដកហូតការចុះឈ្មោះ
- `/register-settings`: កំណត់លក្ខខណ្ឌចុះឈ្មោះ និង Role
- `/register-list`: មើលបញ្ជីសមាជិកដែលបានចុះឈ្មោះ


---

## ការដោះស្រាយបញ្ហា (Troubleshooting)

1. **រកមិនឃើញ Slash Commands ក្នុង Discord?**
   - សូមប្រាកដថាអ្នកបានដាក់ `GUILD_ID` ក្នុង File `.env` ដើម្បីឲ្យ Commands Sync ភ្លាមៗ។ ប្រសិនបើទុកចោល វាអាចចំណាយពេលរហូតដល់ ១ ម៉ោងដើម្បី Sync ទូទាំងពិភពលោក។
2. **Bot មិនអាចបង្កើត Channel បាន?**
   - សូមពិនិត្យមើលសិទ្ធិរបស់ Bot ក្នុង Server។ Bot ត្រូវការសិទ្ធិ `Manage Channels` និង `Manage Roles`។
3. **កំហុស "Privileged Intents"?**
   - សូមចូលទៅកាន់ Discord Developer Portal -> Bot -> ត្រង់ **Privileged Gateway Intents** សូមបើក **Message Content Intent** និង **Server Members Intent**។

---

## 🚀 ការដាក់ដំណើរការលើ Render (Hosting on Render)

### ភាសាខ្មែរ (Khmer):
1. បង្កើត Account លើ [Render.com](https://render.com) ហើយភ្ជាប់ជាមួយ GitHub Account របស់អ្នក។
2. ចុច **New +** -> ជ្រើសរើស **Web Service** (Free) ឬ **Background Worker**។
3. ជ្រើសរើស GitHub Repository: `LeeXinGaming/NMG-TICKET-BOT`។
4. កំណត់ Settings:
   - **Name**: `nmg-ticket-bot`
   - **Language / Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
5. ចូលទៅកាន់ **Environment Variables** ហើយបន្ថែមដូចខាងក្រោម:
   - `DISCORD_TOKEN` = `your_bot_token_from_developer_portal`
   - `GUILD_ID` = `1549490376195309661`
   - `SUPPORT_ROLE_ID` = `1549492423326179458`
   - `TICKET_CATEGORY_ID` = `1549540319958147155`
   - `LOG_CHANNEL_ID` = `1553102113268047874`
   - `TRANSCRIPT_CHANNEL_ID` = `1553102113268047874`
   - `ENABLE_DASHBOARD` = `true`
6. ចុច **Deploy Web Service** ជាការស្រេច!

### English:
1. Log in to [Render.com](https://render.com) and link your GitHub.
2. Click **New +** -> Select **Web Service**.
3. Connect your repository: `LeeXinGaming/NMG-TICKET-BOT`.
4. Configure:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
5. Under **Environment Variables**, paste the keys from `.env.example` along with your secret values.
6. Click **Deploy Web Service**.
