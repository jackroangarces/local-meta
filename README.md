# Local Meta

**Local Meta** is a full-stack web application that analyzes regional competitive *Super Smash Bros. Ultimate* metagames using real player data. It aggregates tournament data, player rankings, and matchup statistics to provide information about character viability and regional trends.

---

## Overview

Local Meta answers a relevant question for competetive smashers:

> *What does the competitive meta actually look like in a specific region, and how can players adapt to it?*

By combining live tournament data, ranking information, and matchup datasets, the app provides insights into player skill and character performance across different regions.

---

## Features

### Regional Meta Analysis
- Supports **multiple geographic regions**
- Tracks player populations and character distributions per region
- Enables region-specific insights rather than global generalizations

### Player & Ranking Data
- Displays **top players** in each region
- Integrates ranking data courtesy of SchuStats
- Stores historical ranking snapshots for future analysis

### Tournament Integration
- Uses the **start.gg API** to:
  - Fetch **upcoming tournaments**
  - Support location-based event discovery
  - Retrieve event-specific or player-specific data

### Character Insights

- **Most Mained Characters**  
  Identify the most popular characters in a region

- **Most Battled Characters**  
  See which characters appear most frequently in matches

- **Least Battled / Unused Characters**  
  Highlight underrepresented or niche picks

- **Best Coverage Characters**  
  Uses weighted matchup data to determine which characters perform best against the **actual regional meta**, not just universal tier lists

---

## Data Processing

- Web scraping pipelines collect and normalize player and ranking data  
- Matchup datasets (from Smashmate) are used for statistical calculations  
- Weighted algorithms factor in:
  - Character popularity
  - Matchup win rates
  - Regional player distribution

---

## Tech Stack

### Frontend
- React
- TypeScript

### Backend
- Python
- FastAPI

### Database
- PostgreSQL
