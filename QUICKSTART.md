# Desurvey Quick Start Guide

## For First-Time Users

### Step 1: Activate the Environment
```powershell
cd c:\Users\DamianFriesen\Documents\GitHub\geoscience
.\venv_desurvey\Scripts\Activate.ps1
```

### Step 2: Launch the GUI
```powershell
python desurvey_gui.py
```

### Step 3: In the GUI

**Tab 1 - Input Files:**
1. Click "Browse..." next to **Collar Data File** and select your collar CSV
2. Click "Browse..." next to **Survey Data File** (optional - skip if you don't have survey data)
3. Click "Browse..." next to **Interval Data File** (optional - for assay, lithology, etc.)
4. Click "Browse..." next to **Output Directory** and choose where to save results
5. Click "Load Files & Continue"

**Tab 2 - Field Mapping:**
- The GUI will auto-match common field names
- Review and adjust any mappings as needed
- Required fields are marked with *

**Tab 3 - Parameters & Run:**
1. Set **Desurvey Segment Length** (default: 1.0 meters)
   - Smaller = more accurate but slower
   - Larger = faster but less accurate
2. Check/uncheck **Down dip is negative** based on your data convention
3. Click "Run Desurvey"
4. Results will appear in the text box

### Step 4: Check Your Output Files

Navigate to your output directory to find:
- `Desurvey_Output.csv` - Desurvey drill hole traces
- `Interval_With_Coordinates.csv` - Interval data with 3D coordinates (if interval file was provided)

## Data Requirements

### Minimum Required Data (Collar File Only)
Your collar CSV must have these fields (names can vary):
- **HoleID** - Unique hole identifier
- **East** - Easting coordinate
- **North** - Northing coordinate  
- **RL/Elevation** - Elevation
- **EOH/Depth** - End of hole depth
- **Az** - Azimuth (optional if you have survey file)
- **Dip** - Dip angle (optional if you have survey file)

### Optional Survey File
If you have downhole surveys, your survey CSV should have:
- **HoleID** - Matching the collar file
- **Depth** - Depth of measurement
- **Az** - Azimuth at that depth
- **Dip** - Dip at that depth

### Optional Interval File
For assay or lithology data to be georeferenced:
- **HoleID** - Matching the collar file  
- **From** - Start depth
- **To** - End depth
- **[Data columns]** - Any other columns (Au, Cu, lithology, etc.)

## Example Workflow

```
1. Have your data files ready:
   - MyCollars.csv
   - MySurveys.csv (optional)
   - MyAssays.csv (optional)

2. Run GUI:
   python desurvey_gui.py

3. Load files and map fields

4. Run desurvey

5. Open output files in Excel, QGIS, or other software
```

## Tips

- **Field names don't match exactly?** The GUI will try to auto-match, but you can manually select the correct column from the dropdown
- **Don't have survey data?** No problem! Leave it blank and the tool will use collar Az/Dip
- **Want to script it?** See the command-line examples in the main README
- **Processing many holes?** Consider increasing desurvey length to 5.0 or 10.0 meters for faster processing

## Common Issues

**"Collar field 'X' is required"**  
→ Make sure you've mapped all required collar fields in Tab 2

**"Could not find hole ID column"**  
→ Make sure your interval file has a HoleID column that matches the collar file

**No output appears**  
→ Check that your CSV files are properly formatted and have matching HoleIDs between collar/survey/interval files

## Need Help?

See the full README: `DESURVEY_STANDALONE_README.md`
