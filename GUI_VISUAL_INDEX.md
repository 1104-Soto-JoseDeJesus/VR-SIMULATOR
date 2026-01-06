# GUI Visual Structure Index & Review

## Overview
This document indexes all GUI visual components, styling, and assets in the VR Battle Simulator application. The GUI is built using **PyQt6** with a glassmorphism dark theme.

---

## Theme & Styling Files

### Primary Stylesheets
1. **`vr_game_sim/gui/modern_theme.qss`** (228 lines)
   - Main application theme
   - Glassmorphism dark theme with blue accents
   - Defines colors, borders, hover states for all widgets
   - Key colors:
     - Background: `#0b0e14` (dark blue-black)
     - Glass cards: `rgba(30, 35, 45, 200)`
     - Primary buttons: Golden (`rgba(255, 193, 7, 0.9)`)
     - Accent blue: `#1e88e5` / `#42a5f5`
     - Text: `#e0e0e0`

2. **`vr_game_sim/gui/styles.qss`** (131 lines)
   - Additional styles for arena stats widgets
   - Progress bar color variants (red/blue team, healed, kills, etc.)
   - Loaded dynamically by `arena_stats.py`

### Style Application
- Main theme loaded in `main()` function (line 13533-13546)
- Uses Qt "Fusion" style as base
- Additional inline stylesheets applied via `setStyleSheet()` throughout code

---

## Main Window Structure

### MainWindow Class (`gui_main.py`, line 7315)
- **Window Title**: "Battle Simulator"
- **Central Widget**: QTabWidget with 9 tabs

### Tabs (in order):
1. **Army Setup** (`setup_tab`)
2. **Report** (`report_tab`)
3. **Figures** (`figures_tab`)
4. **Skill Breakdowns** (`skill_breakdown_tab`)
5. **Battlefield** (`battlefield_tab`)
6. **Battlefield Reports** (`battlefield_report_tab`)
7. **Arena** (`arena_tab`)
8. **Arena Reports** (`arena_report_tab`)
9. **Arena Figures** (`arena_figures_tab`)

---

## Core Widget Classes

### 1. ArmyFrame (`gui_main.py`, line 2835)
- **Type**: QGroupBox
- **Purpose**: Main army configuration widget
- **Visual Elements**:
  - Hero selection combos (2 heroes)
  - Hero images with star overlays (`StarredImageLabel`)
  - Unit type selector with icon
  - Troop count/tier controls
  - Modifier sliders (ATK/DEF/HP)
  - Gear button
  - Plugin skill images
  - Jewel skills button
  - Mount skills button
  - Bonus stats button
  - Rally checkbox

### 2. StarredImageLabel (`gui_main.py`, line 824)
- **Type**: QLabel (custom)
- **Purpose**: Displays images with procedurally drawn star overlays
- **Features**:
  - Grey-out stars based on count
  - Supports hero portraits and skill images
  - Configurable via JSON metadata files
  - Star positioning ratios configurable

### 3. ArenaTab (`gui_main.py`, line 5701)
- **Type**: QWidget
- **Purpose**: Arena mode interface with 3×2 grid slots per team
- **Visual Elements**:
  - Battlefield background image (`BattlefieldBackground.png`)
  - 6 deployment slots per team (red/blue)
  - Army icons (`ArmyIcon` class)
  - Slot items (`SlotItem` - QGraphicsEllipseItem)
  - Control buttons (Run, Clear, etc.)

### 4. BattlefieldTab (`gui_main.py`, line 4403)
- **Type**: QWidget
- **Purpose**: Battlefield simulation interface
- **Visual Elements**:
  - Battlefield background image
  - Army positioning
  - Graphics scene/view

### 5. ArenaStats Components (`gui/arena_stats.py`)
- **HeroStatsHeader**: Column headers for stats
- **HeroStatsWidget**: Individual hero stat display with:
  - Portrait images (2 per hero)
  - Name label
  - Progress bars for: Remaining, Healed, Kills, Heavily Wounded, Heavily Wounded Dealt
  - Color-coded progress bars
- **ArenaStatsHeader**: Mirrored header layout
- **ArenaStatsRow**: Side-by-side hero comparison
- **SkillStatsRow**: Skill performance breakdown
- **HeroSkillDialog**: Modal dialog for detailed skill stats

---

## Dialog Classes

### Configuration Dialogs
1. **HeroEditDialog** (line 2449) - Hero configuration
2. **GearSelectionDialog** (line 2343) - Gear selection
3. **JewelSkillsDialog** (line 2153) - Jewel skill assignment
4. **MountSkillsDialog** (line 2224) - Mount skill assignment
5. **BonusStatsDialog** (line 1996) - Bonus stats configuration
6. **ArmySetupDialog** (line 4071) - Full army setup
7. **RallyConfigDialog** (line 2651) - Rally configuration

### Utility Dialogs
8. **SeedOutcomeDialog** (line 494) - Seed target selection
9. **ArenaSeedDialog** (line 606) - Arena seed configuration
10. **CustomTargetingDialog** (line 694) - Targeting order
11. **DynamicUnrevivableDialog** (line 1570) - Dynamic unrevivable settings
12. **TroopScalarDialog** (line 1692) - Troop scalar multiplier
13. **PDFLayoutDialog** (line 1493) - PDF export layout
14. **StarOverlayDebugDialog** (line 1105) - Star overlay tuning

### Specialized Widgets
15. **SkillParamEditor** (line 1780) - Skill parameter editing
16. **ModSlider** (line 2820) - Custom slider for modifiers
17. **ThousandSepSpinBox** (line 473) - Number input with thousand separators

---

## Image Assets

### Icon Directory (`vr_game_sim/Icons/`)
- **Unit Icons**: `archers.png`, `infantry.png`, `pikemen.png`
- **Stat Icons**: 
  - `CastsICON.png`
  - `HealsICON.png`
  - `KillsICON.png`
  - `RemainingTroopsICON.png`
  - `HeavilyWoundedIcon.png`
  - `Shields.png`
  - `DamageReduction.png`
  - `Rage.png`
  - `RageReduction.png`
- **Jewel Icons**: 
  - `Frigg's Agate.png`
  - `Tyr's Emerald.png`
  - `Thor's Ruby.png`
  - `Freya's Amethyst.png`
  - `Odin's Amber.png`
  - `Heimdall's Sapphire.png`
- **Background Images**:
  - `BattlefieldBackground.png`
  - `ArenaSummaryBackground.png`
- **Misc**: `VS.png`

### Hero Images (`vr_game_sim/Hero Images/`)
- Individual hero portrait PNG files
- Named by capitalized hero name (e.g., `Odin.png`)
- May include JSON metadata files for star configuration

### Gear Icons (`vr_game_sim/Gear Icons/`)
- 60+ gear item PNG files
- Named by gear name (e.g., `Abundance-Hat.png`)
- Includes rarity indicators (Common, Uncommon, Rare, Epic, Legendary)

### Skill Images
- **Plugin Skill Images** (`vr_game_sim/Plugin Skill Images/`)
- **PluginSkillsSmallIcons** (`vr_game_sim/PluginSkillsSmallIcons/`)
- **MountSkillsIcons** (`vr_game_sim/MountSkillsIcons/`)

---

## Color Scheme Reference

### Background Colors
- **Main Window**: `#0b0e14` (dark blue-black)
- **Glass Cards**: `rgba(30, 35, 45, 200)`
- **Text Areas**: `rgba(20, 25, 35, 200)`

### Accent Colors
- **Primary Blue**: `#1e88e5`
- **Hover Blue**: `#42a5f5`
- **Primary Button (Golden)**: `rgba(255, 193, 7, 0.9)`
- **Primary Button Hover**: `rgba(255, 213, 79, 1.0)`

### Progress Bar Colors
- **Red Team**: `rgba(229, 57, 53, 0.9)`
- **Blue Team**: `rgba(30, 136, 229, 0.9)`
- **Healed**: `rgba(82, 201, 166, 0.9)` / `#52c9a6`
- **Kills**: `rgba(255, 107, 107, 0.9)` / `#ff6b6b`
- **Remaining**: `rgba(255, 169, 77, 0.9)`
- **Shielded**: `rgba(90, 158, 255, 0.9)`
- **Rage**: `rgba(157, 78, 221, 0.9)`
- **Damage Reduced**: `rgba(255, 169, 77, 0.9)`
- **Rage Reduced**: `rgba(255, 107, 157, 0.9)`
- **Heavily Wounded**: `#DC143C` (Crimson)
- **Heavily Wounded Dealt**: `#800080` (Purple)

### Text Colors
- **Primary Text**: `#e0e0e0`
- **Secondary Text**: `#b0b0b0`
- **White Text**: `#ffffff`

---

## Styling Patterns

### Border Radius
- **Cards**: `15px`
- **Buttons**: `8px`
- **Primary Buttons**: `10px`
- **Input Fields**: `8px`
- **Tabs**: `10px` (top corners)

### Borders
- **Default**: `1px solid rgba(255, 255, 255, 0.1)`
- **Hover**: `1px solid #1e88e5` or `#42a5f5`
- **Primary Button**: `2px solid rgba(255, 235, 59, 0.8)`

### Padding
- **Buttons**: `8px 16px`
- **Primary Buttons**: `12px 24px`
- **Input Fields**: `6px 12px`
- **Text Areas**: `8px`

### Font Sizes
- **Default**: `12px`
- **Primary Buttons**: `14px`
- **Group Box Titles**: `13px`
- **Headers**: `14px` (bold)

---

## Custom Styling Locations

### Inline Stylesheets (in `gui_main.py`)
- Line 1743: Status label color
- Line 7265-7297: Various label styles
- Line 7712-7772: Output tree/text styles
- Line 7792-7944: Scroll areas and backgrounds
- Line 8513-8711: Skill breakdown table styles
- Line 13533-13546: Fallback theme (if QSS file missing)

### Inline Stylesheets (in `gui/arena_stats.py`)
- Line 40, 156, 376, 399: Transparent backgrounds
- Line 185: Missing image placeholder
- Line 235, 243: Progress bar chunk colors
- Line 545-551: Gradient progress bars

---

## Visual Component Hierarchy

```
MainWindow
├── QTabWidget
    ├── Army Setup Tab
    │   ├── Control Buttons (Run, Save, Load, Swap, etc.)
    │   └── ArmyFrame (x2) - Red/Blue teams
    │       ├── Hero Selection (ComboBox + StarredImageLabel)
    │       ├── Unit Type (ComboBox + Icon)
    │       ├── Troop Controls (SpinBox)
    │       ├── Modifier Sliders (ModSlider)
    │       ├── Gear Button
    │       ├── Plugin Skill Images
    │       ├── Jewel Skills Button
    │       ├── Mount Skills Button
    │       └── Bonus Stats Button
    ├── Report Tab
    │   ├── Output Tree (QTreeWidget)
    │   └── Output Text (QTextEdit)
    ├── Figures Tab
    │   └── Matplotlib Figures (ScrollArea)
    ├── Skill Breakdowns Tab
    │   ├── Background Image (ArenaSummaryBackground.png)
    │   └── Skill Statistics Grid
    ├── Battlefield Tab
    │   ├── Graphics Scene
    │   └── Battlefield Background
    ├── Battlefield Reports Tab
    ├── Arena Tab
    │   ├── Battlefield Background
    │   ├── Slot Grid (3×2 per team)
    │   └── Control Buttons
    ├── Arena Reports Tab
    │   └── ArenaStatsHeader + ArenaStatsRow widgets
    └── Arena Figures Tab
```

---

## Key Visual Features

1. **Glassmorphism Theme**: Translucent cards with blur effects
2. **Dark Mode**: Deep blue-black background with light text
3. **Color-Coded Teams**: Red vs Blue throughout
4. **Progress Bars**: Multiple color variants for different stat types
5. **Star Overlays**: Procedurally drawn on hero/skill images
6. **Background Images**: Used in arena and skill breakdown tabs
7. **Icon System**: Extensive use of PNG icons for units, stats, jewels
8. **Responsive Layouts**: Grid layouts with stretch factors
9. **Hover Effects**: Blue glow on interactive elements
10. **Primary Action Highlighting**: Golden buttons for main actions

---

## Files Summary

### Python Files
- **`vr_game_sim/gui_main.py`** (13,557 lines) - Main GUI implementation
- **`vr_game_sim/gui/arena_stats.py`** (709 lines) - Arena statistics widgets

### Stylesheet Files
- **`vr_game_sim/gui/modern_theme.qss`** (228 lines) - Main theme
- **`vr_game_sim/gui/styles.qss`** (131 lines) - Arena stats styles

### Asset Directories
- `vr_game_sim/Icons/` - 20 icon files
- `vr_game_sim/Hero Images/` - Hero portraits + JSON metadata
- `vr_game_sim/Gear Icons/` - 60+ gear item images
- `vr_game_sim/Plugin Skill Images/` - Plugin skill artwork
- `vr_game_sim/PluginSkillsSmallIcons/` - Small plugin icons
- `vr_game_sim/MountSkillsIcons/` - Mount skill icons
- `vr_game_sim/Unit Icons/` - Unit type icons
- `vr_game_sim/Stat Icons/` - Stat indicator icons

---

## Notes for Visual Overhaul

1. **Theme Files**: Both QSS files control the overall look
2. **Inline Styles**: Many widgets have inline styles that override theme
3. **Image Assets**: Large collection of PNG assets that may need updating
4. **Color Constants**: Colors are hardcoded in multiple places
5. **Custom Widgets**: Several custom widgets (StarredImageLabel, ModSlider) have their own styling
6. **Progress Bars**: Extensive color customization for different stat types
7. **Background Images**: Two background images used for visual appeal
8. **Icon System**: Icons loaded dynamically based on hero/unit names

---

*This index was generated for planning GUI visual overhaul. All file paths are relative to the workspace root.*


