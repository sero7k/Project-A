# Project-A - Private Servers

Welcome to **Project-A - Private Servers**.

This repository focuses on research and preservation work around the early **July 2021 alpha build** of *Valorant* (internally known as "Project A"). Compared to modern versions, this build contains fewer integrity checks, lighter encryption, and a simpler networking structure, making it more accessible for reverse engineering and protocol research.

Our goal is to recreate the original gameplay experience and provide a foundation for running community-hosted servers for educational and archival purposes.

---

## Requirements

Before using this project, make sure you have:

- Python 3.12+
- PostgreSQL
- A PostgreSQL user named `projecta`
- A PostgreSQL password set to `projecta`

Recommended local database details:

- Database name: `projecta`
- Username: `projecta`
- Password: `projecta`

---

## Installation

Installation is simple:

1. Download or extract the files from this repository.
2. Open your **Project A / game folder root**.
3. Move or extract all files directly into that root folder.
4. Allow Windows to merge folders and replace files if prompted.

After that, the project files should sit alongside the main game files in the root directory.

---

## Setup

1. Install Python 3.12 or newer.
2. Install PostgreSQL.
3. Create or configure a PostgreSQL user with the password `projecta`.
4. Extract this project into the root of your game folder.
5. Run `install_requirements.bat` from the game root.
6. Run `launch.bat` from the game root.

If your PostgreSQL setup uses the default local configuration for this project, the typical login values are:

- Username: `projecta`
- Password: `projecta`
- Database: `projecta`

The current launcher flow is set up to run without administrator privileges.

---

## Goals

- Recreate the original 2021 alpha experience
- Research and document the game's networking and systems
- Develop custom/private server infrastructure
- Share progress, tools, and discoveries with the community

---

## Current Status

> This project is still in **early development**.  
> Many systems are incomplete or unstable, and compatibility may change frequently.

---

## Features

- Custom server implementation
- Early protocol research
- Packet and asset analysis
- Experimental matchmaking and session handling
- Community-driven development

---

## Contributing

Contributions, research notes, and technical findings are welcome.

If you want to help:
- Open an issue
- Submit a pull request
- Share research findings

---

## Disclaimer

This project is intended for **research, educational, and preservation purposes only**.

All rights to *Valorant* and related assets belong to Riot Games.

