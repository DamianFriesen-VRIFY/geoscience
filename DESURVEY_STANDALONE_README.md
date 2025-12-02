# Desurvey Standalone Script

A standalone Python script for desurveying drill holes without requiring QGIS. This script can be run directly in VSCode or any Python environment with both **GUI** and **command-line** interfaces.

## Features

- **Interactive GUI** with field mapping and file browser
- **Desurvey drill holes** from collar and survey data
- **Sample intervals** at specific depths (e.g., assay intervals, lithology)
- **Export results** to CSV for further analysis
- **No QGIS dependency** - runs with just Python, pandas, and numpy
- **Automatic field matching** - suggests common field names
- **Custom output location** - choose where to save results

## Installation

### 1. Create and activate virtual environment

```powershell
# Create virtual environment
python -m venv venv_desurvey

# Activate (PowerShell)
.\venv_desurvey\Scripts\Activate.ps1

# Activate (Command Prompt)
.\venv_desurvey\Scripts\activate.bat

# Activate (bash/Linux/Mac)
source venv_desurvey/bin/activate
```

### 2. Install dependencies

```powershell
## Usage

### GUI Mode (Recommended for New Users)

Launch the graphical interface for easy file selection and field mapping:

```powershell
# Activate virtual environment first
.\venv_desurvey\Scripts\Activate.ps1

# Run the GUI
python desurvey_gui.py
```

**GUI Features:**
1. **Tab 1 - Input Files**: Browse and select collar, survey, and interval data files, plus output directory
2. **Tab 2 - Field Mapping**: Automatically matches common field names or manually map your CSV columns
3. **Tab 3 - Parameters & Run**: Set desurvey parameters and execute

The GUI will:
- Auto-detect and suggest field mappings
- Validate required fields before running
- Display progress and results
- Save output files to your chosen directory

### Command-Line Mode (For Scripts & Automation)

For programmatic usage or batch processing:
## Usage

### Basic Example

```python
from desurvey_standalone import DesurveyStandalone

# Initialize desurvey
desurvey = DesurveyStandalone(
    desurvey_length=1.0,      # Length of desurvey segments (meters)
    down_dip_negative=True     # True if down dip is negative
)

# Load collar and survey data
collar_df = desurvey.load_collar_data('testdata/Collar.csv')
survey_df = desurvey.load_survey_data('testdata/Survey.csv')

# Desurvey all holes
desurvey_df = desurvey.desurvey_all_holes(collar_df, survey_df)

### Test with Sample Data

```powershell
# Activate virtual environment first
.\venv_desurvey\Scripts\Activate.ps1

# Run the test script with sample data
python desurvey_standalone.py
```

This will process the test data in the `testdata/` folder and create output files.

## File Structure

```
geoscience/
├── desurvey_standalone.py      # Core desurvey library
├── desurvey_gui.py              # GUI wrapper application
├── requirements_standalone.txt  # Python dependencies
├── venv_desurvey/              # Virtual environment
├── testdata/                    # Sample data for testing
│   ├── Collar.csv
│   ├── Survey.csv
│   └── Assay.csv
└── DESURVEY_STANDALONE_README.md
```

## Input Data Formatsv('testdata/Assay.csv')
assay_df.columns = assay_df.columns.str.strip()

# Sample desurvey at assay intervals
assay_with_coords = desurvey.sample_desurvey_at_intervals(
    desurvey_df, 
    assay_df, 
    from_col='From',  # Column name for start depth
    to_col='To'       # Column name for end depth
)

# Save results
assay_with_coords.to_csv('Assay_With_Coordinates.csv', index=False)
```

### Run Test Script

```powershell
# Activate virtual environment first
.\venv_desurvey\Scripts\Activate.ps1

# Run the test script
python desurvey_standalone.py
```

## Input Data Format

### Collar Data (CSV)
Required columns:
- `HoleID` - Unique hole identifier
- `East` - Easting coordinate
- `North` - Northing coordinate
- `RL` - Elevation/RL
- `EOH` - End of hole depth
- `Az` - Azimuth (optional, if no survey data)
- `Dip` - Dip (optional, if no survey data)

Example:
```csv
HoleID,East,North,RL,EOH,Az,Dip
DDH90,500000,2000000,3970,100,0,-90
DDH01,500060,2000000,3970,100,10,0
```

### Survey Data (CSV)
Required columns:
- `HoleID` - Unique hole identifier (matches collar)
- `Depth` - Depth of survey measurement
- `Az` - Azimuth
- `Dip` - Dip angle

Example:
```csv
HoleID,Depth,Az,Dip
DDH01,0,10,0
DDH01,50,350,0
```

### Interval Data (CSV)
Required columns:
- `HoleID` or `HoleId` - Unique hole identifier
- `From` - Start depth of interval
- `To` - End depth of interval
- Additional columns with interval attributes

Example:
```csv
HoleId,From,To,Val
DDH01,0,25,10
DDH01,40,80,40
```

## Output Data

### Desurvey Output
Contains the 3D path of each drill hole:
- `HoleID` - Hole identifier
- `Depth` - Depth along hole
- `East` - Easting coordinate
- `North` - Northing coordinate
- `Elevation` - Elevation/RL

### Interval Output with Coordinates
Original interval data plus coordinates at start, middle, and end of each interval:
- `East_from`, `North_from`, `Elevation_from` - Coordinates at start of interval
- `East_mid`, `North_mid`, `Elevation_mid` - Coordinates at middle of interval
- `East_to`, `North_to`, `Elevation_to` - Coordinates at end of interval

## Parameters

### DesurveyStandalone Class

- `desurvey_length` (float): Length of desurvey segments in meters (default: 1.0)
  - Smaller values = more points, more accurate but slower
  - Larger values = fewer points, faster but less accurate

- `down_dip_negative` (bool): Convention for dip direction (default: True)
  - True: Down dip is negative (e.g., -90° = vertical down)
  - False: Down dip is positive (e.g., +90° = vertical down)

## Troubleshooting

### GUI doesn't open
```
ModuleNotFoundError: No module named 'tkinter'
```
**Solution**: Tkinter should be included with Python. If missing, reinstall Python with tkinter support or use command-line mode.

### Import Errorsured clockwise from north (0° = north, 90° = east)
- The script automatically handles holes with or without survey data
- If no surveys exist for a hole, collar azimuth and dip are used
- Linear interpolation is used between survey points
- Column name matching is case-insensitive for hole ID columns

## Comparison with QGIS Plugin

This standalone script provides the core desurvey functionality of the QGIS plugin but:
- ✅ Runs without QGIS
- ✅ Easier to integrate into automated workflows
- ✅ Can be used in Jupyter notebooks or scripts
- ❌ No 3D visualization (use output CSV in other software)
- ❌ No interactive UI (use programmatically)

## Troubleshooting

### Import Error
```
ModuleNotFoundError: No module named 'pandas'
```
**Solution**: Make sure you activated the virtual environment and installed dependencies:
```powershell
.\venv_desurvey\Scripts\Activate.ps1
pip install -r requirements_standalone.txt
```

### Column Name Error
```
KeyError: 'HoleID'
```
**Solution**: Check your CSV column names. The script auto-detects common variations but you can specify manually:
```python
assay_with_coords = desurvey.sample_desurvey_at_intervals(
    desurvey_df, assay_df, 
    from_col='From', 
    to_col='To',
    hole_id_col='YourColumnName'  # Specify exact column name
)
```

## License

Same license as the main Geoscience QGIS plugin.
