#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GUI Wrapper for Desurvey Standalone Script
Provides tkinter interface for field matching and output location selection
"""

import pandas as pd
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys

# Import the standalone desurvey module
# We'll import it dynamically
try:
    from desurvey_standalone import DesurveyStandalone
except ImportError:
    print("Error: Could not import desurvey_standalone module")
    print("Make sure desurvey_standalone.py is in the same directory")
    sys.exit(1)


class DesurveyGUI:
    """GUI for desurvey operations"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Drill Hole Desurvey Tool")
        self.root.geometry("900x700")
        
        # Data storage
        self.collar_file = None
        self.survey_file = None
        self.interval_file = None
        self.output_dir = None
        self.collar_df = None
        self.survey_df = None
        self.interval_df = None
        
        # Field mappings
        self.collar_mapping = {}
        self.survey_mapping = {}
        self.interval_mapping = {}
        
        # Desurvey parameters
        self.desurvey_length = tk.DoubleVar(value=1.0)
        self.down_dip_negative = tk.BooleanVar(value=True)
        self.output_crs = tk.StringVar(value="32750")
        self.create_shapefile = tk.BooleanVar(value=True)
        self.create_interval_shapefile = tk.BooleanVar(value=True)
        self.create_interval_points = tk.BooleanVar(value=True)
        self.create_collar_shapefile = tk.BooleanVar(value=True)
        self.create_qc_report = tk.BooleanVar(value=True)
        
        # Output filenames (without extension)
        self.trace_filename = tk.StringVar(value="Drill_Traces")
        self.interval_filename = tk.StringVar(value="Downhole_Intervals")
        self.interval_points_filename = tk.StringVar(value="Interval_MidPoints")
        self.collar_filename = tk.StringVar(value="Collar_Points")
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the user interface"""
        # Create notebook for tabs
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Tab 1: Input Files
        tab1 = ttk.Frame(notebook)
        notebook.add(tab1, text='1. Input Files')
        self.setup_input_tab(tab1)
        
        # Tab 2: Field Mapping
        tab2 = ttk.Frame(notebook)
        notebook.add(tab2, text='2. Field Mapping')
        self.setup_mapping_tab(tab2)
        
        # Tab 3: Parameters & Run
        tab3 = ttk.Frame(notebook)
        notebook.add(tab3, text='3. Parameters & Run')
        self.setup_run_tab(tab3)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def setup_input_tab(self, parent):
        """Setup input files tab"""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill='both', expand=True)
        
        # Collar file
        ttk.Label(frame, text="Collar Data File (Required):", font=('', 10, 'bold')).grid(row=0, column=0, sticky='w', pady=(0,5))
        self.collar_file_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.collar_file_var, width=60, state='readonly').grid(row=1, column=0, padx=(0,5))
        ttk.Button(frame, text="Browse...", command=self.browse_collar_file).grid(row=1, column=1)
        ttk.Label(frame, text="Required columns: HoleID, East, North, Elevation/RL, EOH/Depth", 
                 foreground='gray').grid(row=2, column=0, columnspan=2, sticky='w', pady=(0,15))
        
        # Survey file
        ttk.Label(frame, text="Survey Data File (Optional):", font=('', 10, 'bold')).grid(row=3, column=0, sticky='w', pady=(0,5))
        self.survey_file_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.survey_file_var, width=60, state='readonly').grid(row=4, column=0, padx=(0,5))
        ttk.Button(frame, text="Browse...", command=self.browse_survey_file).grid(row=4, column=1)
        ttk.Label(frame, text="Required columns: HoleID, Depth, Azimuth, Dip", 
                 foreground='gray').grid(row=5, column=0, columnspan=2, sticky='w', pady=(0,15))
        
        # Interval file
        ttk.Label(frame, text="Interval Data File (Optional - for assay, lithology, etc.):", 
                 font=('', 10, 'bold')).grid(row=6, column=0, sticky='w', pady=(0,5))
        self.interval_file_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.interval_file_var, width=60, state='readonly').grid(row=7, column=0, padx=(0,5))
        ttk.Button(frame, text="Browse...", command=self.browse_interval_file).grid(row=7, column=1)
        ttk.Label(frame, text="Required columns: HoleID, From, To, plus any data columns", 
                 foreground='gray').grid(row=8, column=0, columnspan=2, sticky='w', pady=(0,15))
        
        # Output directory
        ttk.Label(frame, text="Output Directory:", font=('', 10, 'bold')).grid(row=9, column=0, sticky='w', pady=(0,5))
        self.output_dir_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.output_dir_var, width=60, state='readonly').grid(row=10, column=0, padx=(0,5))
        ttk.Button(frame, text="Browse...", command=self.browse_output_dir).grid(row=10, column=1)
        
        # Load button
        ttk.Button(frame, text="Load Files & Continue", command=self.load_files).grid(row=11, column=0, columnspan=2, pady=20)
    
    def setup_mapping_tab(self, parent):
        """Setup field mapping tab"""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill='both', expand=True)
        
        # Create scrollable frame
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        self.mapping_frame = ttk.Frame(canvas)
        
        self.mapping_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.mapping_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Info label
        info_label = ttk.Label(self.mapping_frame, 
                              text="Map your CSV columns to the required fields. Load files first in Tab 1.",
                              font=('', 9, 'italic'), foreground='blue')
        info_label.grid(row=0, column=0, columnspan=3, pady=(0,10), sticky='w')
    
    def setup_run_tab(self, parent):
        """Setup parameters and run tab"""
        frame = ttk.Frame(parent, padding=10)
        frame.pack(fill='both', expand=True)
        
        # Parameters section
        param_frame = ttk.LabelFrame(frame, text="Desurvey Parameters", padding=10)
        param_frame.pack(fill='x', pady=(0,20))
        
        ttk.Label(param_frame, text="Desurvey Segment Length (meters):").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(param_frame, textvariable=self.desurvey_length, width=15).grid(row=0, column=1, sticky='w', padx=(10,0))
        ttk.Label(param_frame, text="Smaller = more accurate but slower", 
                 foreground='gray').grid(row=0, column=2, sticky='w', padx=(10,0))
        
        ttk.Checkbutton(param_frame, text="Down dip is negative (e.g., -90° = vertical down)", 
                       variable=self.down_dip_negative).grid(row=1, column=0, columnspan=3, sticky='w', pady=5)
        
        ttk.Label(param_frame, text="Input Coordinate System (EPSG code):").grid(row=2, column=0, sticky='w', pady=5)
        crs_frame = ttk.Frame(param_frame)
        crs_frame.grid(row=2, column=1, columnspan=2, sticky='w', padx=(10,0))
        ttk.Label(crs_frame, text="EPSG:", foreground='#666').pack(side='left')
        crs_entry = ttk.Entry(crs_frame, textvariable=self.output_crs, width=12)
        crs_entry.pack(side='left', padx=(2,10))
        ttk.Label(crs_frame, text="e.g., 32750 (UTM 50S), 32632 (UTM 32N) - Do NOT use lat/long", 
                 foreground='gray', font=('', 8)).pack(side='left')
        
        # Output options with filenames
        output_opts_frame = ttk.LabelFrame(param_frame, text="Output Options", padding=10)
        output_opts_frame.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(10,0))
        
        opt_row = 0
        ttk.Checkbutton(output_opts_frame, text="Create shapefile of collar points", 
                       variable=self.create_collar_shapefile).grid(row=opt_row, column=0, sticky='w', pady=2)
        ttk.Label(output_opts_frame, text="Filename:").grid(row=opt_row, column=1, sticky='e', padx=(10,5))
        ttk.Entry(output_opts_frame, textvariable=self.collar_filename, width=25).grid(row=opt_row, column=2, sticky='w', pady=2)
        ttk.Label(output_opts_frame, text=".shp", foreground='gray').grid(row=opt_row, column=3, sticky='w')
        
        opt_row += 1
        ttk.Checkbutton(output_opts_frame, text="Create shapefile of drill traces", 
                       variable=self.create_shapefile).grid(row=opt_row, column=0, sticky='w', pady=2)
        ttk.Label(output_opts_frame, text="Filename:").grid(row=opt_row, column=1, sticky='e', padx=(10,5))
        ttk.Entry(output_opts_frame, textvariable=self.trace_filename, width=25).grid(row=opt_row, column=2, sticky='w', pady=2)
        ttk.Label(output_opts_frame, text=".shp", foreground='gray').grid(row=opt_row, column=3, sticky='w')
        
        opt_row += 1
        ttk.Checkbutton(output_opts_frame, text="Create shapefile of downhole intervals (if interval data)", 
                       variable=self.create_interval_shapefile).grid(row=opt_row, column=0, sticky='w', pady=2)
        ttk.Label(output_opts_frame, text="Filename:").grid(row=opt_row, column=1, sticky='e', padx=(10,5))
        ttk.Entry(output_opts_frame, textvariable=self.interval_filename, width=25).grid(row=opt_row, column=2, sticky='w', pady=2)
        ttk.Label(output_opts_frame, text=".shp", foreground='gray').grid(row=opt_row, column=3, sticky='w')
        
        opt_row += 1
        ttk.Checkbutton(output_opts_frame, text="Create point shapefile of interval mid-points (if interval data)", 
                       variable=self.create_interval_points).grid(row=opt_row, column=0, sticky='w', pady=2)
        ttk.Label(output_opts_frame, text="Filename:").grid(row=opt_row, column=1, sticky='e', padx=(10,5))
        ttk.Entry(output_opts_frame, textvariable=self.interval_points_filename, width=25).grid(row=opt_row, column=2, sticky='w', pady=2)
        ttk.Label(output_opts_frame, text=".shp", foreground='gray').grid(row=opt_row, column=3, sticky='w')
        
        opt_row += 1
        ttk.Checkbutton(output_opts_frame, text="Generate HTML QC Report", 
                       variable=self.create_qc_report).grid(row=opt_row, column=0, columnspan=4, sticky='w', pady=2)
        
        # Run section
        run_frame = ttk.LabelFrame(frame, text="Execute", padding=10)
        run_frame.pack(fill='x')
        
        ttk.Button(run_frame, text="Run Desurvey", command=self.run_desurvey, width=20).pack(pady=10)
        
        # Results text
        ttk.Label(run_frame, text="Results:").pack(anchor='w')
        self.results_text = tk.Text(run_frame, height=20, width=80, state='disabled')
        self.results_text.pack(fill='both', expand=True, pady=(5,0))
        
        # Scrollbar for results
        results_scroll = ttk.Scrollbar(run_frame, command=self.results_text.yview)
        results_scroll.pack(side='right', fill='y')
        self.results_text.config(yscrollcommand=results_scroll.set)
    
    def browse_collar_file(self):
        """Browse for collar file"""
        filename = filedialog.askopenfilename(
            title="Select Collar Data File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.collar_file_var.set(filename)
            self.collar_file = filename
    
    def browse_survey_file(self):
        """Browse for survey file"""
        filename = filedialog.askopenfilename(
            title="Select Survey Data File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.survey_file_var.set(filename)
            self.survey_file = filename
    
    def browse_interval_file(self):
        """Browse for interval file"""
        filename = filedialog.askopenfilename(
            title="Select Interval Data File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.interval_file_var.set(filename)
            self.interval_file = filename
    
    def browse_output_dir(self):
        """Browse for output directory"""
        dirname = filedialog.askdirectory(title="Select Output Directory")
        if dirname:
            self.output_dir_var.set(dirname)
            self.output_dir = dirname
    
    def load_files(self):
        """Load and preview files"""
        if not self.collar_file:
            messagebox.showerror("Error", "Please select a collar data file")
            return
        
        if not self.output_dir:
            messagebox.showerror("Error", "Please select an output directory")
            return
        
        try:
            # Load collar file
            self.collar_df = pd.read_csv(self.collar_file)
            self.collar_df.columns = self.collar_df.columns.str.strip()
            
            # Load survey file if provided
            if self.survey_file:
                self.survey_df = pd.read_csv(self.survey_file)
                self.survey_df.columns = self.survey_df.columns.str.strip()
            else:
                self.survey_df = None
            
            # Load interval file if provided
            if self.interval_file:
                self.interval_df = pd.read_csv(self.interval_file)
                self.interval_df.columns = self.interval_df.columns.str.strip()
            else:
                self.interval_df = None
            
            # Setup field mappings
            self.setup_field_mappings()
            
            self.status_var.set("Files loaded successfully. Please map fields in Tab 2.")
            messagebox.showinfo("Success", "Files loaded successfully!\n\nPlease proceed to Tab 2 to map fields.")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error loading files:\n{str(e)}")
    
    def setup_field_mappings(self):
        """Setup field mapping UI"""
        # Clear existing mappings
        for widget in self.mapping_frame.winfo_children():
            if widget.grid_info().get('row', 0) > 0:  # Keep info label
                widget.destroy()
        
        row = 1
        
        # Collar mappings
        if self.collar_df is not None:
            ttk.Label(self.mapping_frame, text="Collar Data Fields:", 
                     font=('', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', pady=(10,5))
            row += 1
            
            collar_fields = {
                'HoleID': ['HoleID', 'HoleId', 'HOLEID', 'Hole_ID', 'BHID', 'ID'],
                'East': ['East', 'EAST', 'Easting', 'X', 'x'],
                'North': ['North', 'NORTH', 'Northing', 'Y', 'y'],
                'RL': ['RL', 'Elevation', 'Elev', 'ELEV', 'Z', 'z', 'Collar'],
                'EOH': ['EOH', 'E.O.H', 'Depth', 'TotalDepth', 'Length', 'MaxDepth'],
                'Az': ['Az', 'Azimuth', 'AZ', 'AZIMUTH', 'Bearing'],
                'Dip': ['Dip', 'DIP', 'Incl', 'Inclination', 'INCL']
            }
            
            self.collar_combos = {}
            for field, suggestions in collar_fields.items():
                required = field not in ['Az', 'Dip']
                label_text = f"{field}:" + (" *" if required else " (optional)")
                ttk.Label(self.mapping_frame, text=label_text).grid(row=row, column=0, sticky='w', padx=(20,10), pady=2)
                
                combo = ttk.Combobox(self.mapping_frame, values=[''] + list(self.collar_df.columns), width=30)
                combo.grid(row=row, column=1, sticky='w', pady=2)
                self.collar_combos[field] = combo
                
                # Auto-select if match found
                for col in self.collar_df.columns:
                    if col in suggestions:
                        combo.set(col)
                        break
                
                row += 1
        
        # Survey mappings
        if self.survey_df is not None:
            ttk.Label(self.mapping_frame, text="Survey Data Fields:", 
                     font=('', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', pady=(15,5))
            row += 1
            
            survey_fields = {
                'HoleID': ['HoleID', 'HoleId', 'HOLEID', 'Hole_ID', 'BHID', 'ID'],
                'Depth': ['Depth', 'DEPTH', 'At', 'AT'],
                'Az': ['Az', 'Azimuth', 'AZ', 'AZIMUTH', 'Bearing'],
                'Dip': ['Dip', 'DIP', 'Incl', 'Inclination', 'INCL']
            }
            
            self.survey_combos = {}
            for field, suggestions in survey_fields.items():
                ttk.Label(self.mapping_frame, text=f"{field}: *").grid(row=row, column=0, sticky='w', padx=(20,10), pady=2)
                
                combo = ttk.Combobox(self.mapping_frame, values=[''] + list(self.survey_df.columns), width=30)
                combo.grid(row=row, column=1, sticky='w', pady=2)
                self.survey_combos[field] = combo
                
                # Auto-select if match found
                for col in self.survey_df.columns:
                    if col in suggestions:
                        combo.set(col)
                        break
                
                row += 1
        
        # Interval mappings
        if self.interval_df is not None:
            ttk.Label(self.mapping_frame, text="Interval Data Fields:", 
                     font=('', 10, 'bold')).grid(row=row, column=0, columnspan=3, sticky='w', pady=(15,5))
            row += 1
            
            interval_fields = {
                'HoleID': ['HoleID', 'HoleId', 'HOLEID', 'Hole_ID', 'BHID', 'ID'],
                'From': ['From', 'FROM', 'Start', 'Depth_From', 'DepthFrom'],
                'To': ['To', 'TO', 'End', 'Depth_To', 'DepthTo']
            }
            
            self.interval_combos = {}
            for field, suggestions in interval_fields.items():
                ttk.Label(self.mapping_frame, text=f"{field}: *").grid(row=row, column=0, sticky='w', padx=(20,10), pady=2)
                
                combo = ttk.Combobox(self.mapping_frame, values=[''] + list(self.interval_df.columns), width=30)
                combo.grid(row=row, column=1, sticky='w', pady=2)
                self.interval_combos[field] = combo
                
                # Auto-select if match found
                for col in self.interval_df.columns:
                    if col in suggestions:
                        combo.set(col)
                        break
                
                row += 1
        
        ttk.Label(self.mapping_frame, text="* Required fields", 
                 foreground='red', font=('', 8)).grid(row=row, column=0, columnspan=3, sticky='w', pady=(10,0))
    
    def run_desurvey(self):
        """Run the desurvey process"""
        if self.collar_df is None:
            messagebox.showerror("Error", "Please load files first in Tab 1")
            return
        
        # Validate collar mappings
        try:
            collar_mapped = {}
            for field, combo in self.collar_combos.items():
                value = combo.get()
                if value:
                    collar_mapped[field] = value
                elif field not in ['Az', 'Dip']:
                    raise ValueError(f"Collar field '{field}' is required")
            
            # Rename columns
            collar_rename = {v: k for k, v in collar_mapped.items()}
            collar_data = self.collar_df.rename(columns=collar_rename)
            
            # Validate survey mappings if survey data exists
            survey_data = None
            if self.survey_df is not None:
                survey_mapped = {}
                for field, combo in self.survey_combos.items():
                    value = combo.get()
                    if value:
                        survey_mapped[field] = value
                    else:
                        raise ValueError(f"Survey field '{field}' is required")
                
                survey_rename = {v: k for k, v in survey_mapped.items()}
                survey_data = self.survey_df.rename(columns=survey_rename)
            
            # Validate interval mappings if interval data exists
            interval_data = None
            interval_mapped = {}
            if self.interval_df is not None:
                for field, combo in self.interval_combos.items():
                    value = combo.get()
                    if value:
                        interval_mapped[field] = value
                    else:
                        raise ValueError(f"Interval field '{field}' is required")
                
                interval_rename = {v: k for k, v in interval_mapped.items()}
                interval_data = self.interval_df.rename(columns=interval_rename)
            
        except ValueError as e:
            messagebox.showerror("Mapping Error", str(e))
            return
        except Exception as e:
            messagebox.showerror("Error", f"Error validating mappings:\n{str(e)}")
            return
        
        # Run desurvey
        try:
            self.status_var.set("Running desurvey...")
            self.results_text.config(state='normal')
            self.results_text.delete(1.0, tk.END)
            
            # Get CRS with EPSG prefix
            crs_code = self.output_crs.get().strip()
            if not crs_code.upper().startswith('EPSG:'):
                crs_code = f"EPSG:{crs_code}"
            
            # Initialize desurvey
            desurvey = DesurveyStandalone(
                desurvey_length=self.desurvey_length.get(),
                down_dip_negative=self.down_dip_negative.get()
            )
            
            # Process
            self.results_text.insert(tk.END, "Starting desurvey process...\n\n")
            self.results_text.insert(tk.END, f"Collar records: {len(collar_data)}\n")
            
            if survey_data is not None:
                self.results_text.insert(tk.END, f"Survey records: {len(survey_data)}\n")
                # Create empty dataframe if no surveys
                if len(survey_data) == 0:
                    survey_data = pd.DataFrame(columns=['HoleID', 'Depth', 'Az', 'Dip'])
            else:
                self.results_text.insert(tk.END, "No survey data - using collar Az/Dip\n")
                survey_data = pd.DataFrame(columns=['HoleID', 'Depth', 'Az', 'Dip'])
            
            self.results_text.insert(tk.END, "\nDesurveying holes...\n")
            self.root.update()
            
            # Desurvey all holes
            desurvey_df = desurvey.desurvey_all_holes(collar_data, survey_data)
            
            self.results_text.insert(tk.END, f"Generated {len(desurvey_df)} desurvey points\n\n")
            
            # Track created shapefiles for QC report
            shapefile_paths = {}
            
            # Create collar shapefile if requested
            if self.create_collar_shapefile.get():
                try:
                    self.results_text.insert(tk.END, "\nCreating shapefile of collar points...\n")
                    self.root.update()
                    
                    collar_shapefile_path = Path(self.output_dir) / f"{self.collar_filename.get()}.shp"
                    collar_gdf = desurvey.create_collar_shapefile(
                        collar_data,
                        collar_shapefile_path,
                        crs=crs_code
                    )
                    
                    self.results_text.insert(tk.END, f"✓ Saved Collar Shapefile: {collar_shapefile_path}\n")
                    self.results_text.insert(tk.END, f"  - Number of collars: {len(collar_gdf)}\n")
                    self.results_text.insert(tk.END, f"  - CRS: {crs_code}\n")
                    shapefile_paths['collar'] = str(collar_shapefile_path)
                except Exception as e:
                    self.results_text.insert(tk.END, f"⚠ Warning: Could not create collar shapefile: {str(e)}\n")
            
            # Create shapefile if requested
            if self.create_shapefile.get():
                try:
                    self.results_text.insert(tk.END, "\nCreating shapefile of drill traces...\n")
                    self.root.update()
                    
                    shapefile_path = Path(self.output_dir) / f"{self.trace_filename.get()}.shp"
                    gdf = desurvey.create_trace_shapefile(
                        desurvey_df, 
                        shapefile_path,
                        crs=crs_code
                    )
                    
                    self.results_text.insert(tk.END, f"✓ Saved Shapefile: {shapefile_path}\n")
                    self.results_text.insert(tk.END, f"  - Number of drill traces: {len(gdf)}\n")
                    self.results_text.insert(tk.END, f"  - CRS: {crs_code}\n")
                    shapefile_paths['traces'] = str(shapefile_path)
                except Exception as e:
                    self.results_text.insert(tk.END, f"⚠ Warning: Could not create shapefile: {str(e)}\n")
            
            # Process interval data if exists
            if interval_data is not None:
                self.results_text.insert(tk.END, f"\nProcessing {len(interval_data)} intervals...\n")
                self.root.update()
                
                # Create interval shapefile if requested
                if self.create_interval_shapefile.get():
                    try:
                        self.results_text.insert(tk.END, "Creating shapefile of downhole intervals...\n")
                        self.root.update()
                        
                        interval_shapefile = Path(self.output_dir) / f"{self.interval_filename.get()}.shp"
                        interval_gdf = desurvey.create_interval_shapefile(
                            desurvey_df,
                            interval_data,
                            interval_shapefile,
                            from_col='From',
                            to_col='To',
                            hole_id_col='HoleID',
                            crs=crs_code
                        )
                        
                        self.results_text.insert(tk.END, f"✓ Saved Interval Shapefile: {interval_shapefile}\n")
                        self.results_text.insert(tk.END, f"  - Number of intervals: {len(interval_gdf)}\n")
                        shapefile_paths['intervals'] = str(interval_shapefile)
                    except Exception as e:
                        self.results_text.insert(tk.END, f"⚠ Warning: Could not create interval shapefile: {str(e)}\n")
                
                # Create interval points shapefile if requested
                if self.create_interval_points.get():
                    try:
                        self.results_text.insert(tk.END, "Creating point shapefile of interval mid-points...\n")
                        self.root.update()
                        
                        points_shapefile = Path(self.output_dir) / f"{self.interval_points_filename.get()}.shp"
                        points_gdf = desurvey.create_interval_points_shapefile(
                            desurvey_df,
                            interval_data,
                            points_shapefile,
                            from_col='From',
                            to_col='To',
                            hole_id_col='HoleID',
                            crs=crs_code
                        )
                        
                        self.results_text.insert(tk.END, f"✓ Saved Interval Points Shapefile: {points_shapefile}\n")
                        self.results_text.insert(tk.END, f"  - Number of points: {len(points_gdf)}\n")
                        shapefile_paths['points'] = str(points_shapefile)
                    except Exception as e:
                        self.results_text.insert(tk.END, f"⚠ Warning: Could not create points shapefile: {str(e)}\n")
            
            # Generate QC Report if requested
            if self.create_qc_report.get():
                try:
                    self.results_text.insert(tk.END, "\nGenerating QC Report...\n")
                    self.root.update()
                    
                    qc_output = Path(self.output_dir) / "QC_Report.html"
                    self.results_text.insert(tk.END, f"  Output path: {qc_output}\n")
                    self.root.update()
                    
                    qc_results = desurvey.create_qc_report(
                        collar_data,
                        survey_data,
                        interval_data,
                        desurvey_df,
                        qc_output,
                        shapefile_paths=shapefile_paths
                    )
                    
                    self.results_text.insert(tk.END, f"✓ Saved QC Report: {qc_output}\n")
                    
                    # Display quick summary
                    issues = 0
                    if qc_results['collar']['duplicate_ids'] > 0:
                        issues += 1
                    if qc_results['collar']['missing_coordinates'] > 0:
                        issues += 1
                    if qc_results['survey'].get('invalid_depths', 0) > 0:
                        issues += 1
                    if qc_results['interval'].get('inverted_intervals', 0) > 0:
                        issues += 1
                    if qc_results.get('eoh_variance', {}).get('count', 0) > 0:
                        issues += 1
                        self.results_text.insert(tk.END, f"  ⚠ {qc_results['eoh_variance']['count']} holes with EOH depth variance\n")
                    
                    if issues == 0:
                        self.results_text.insert(tk.END, "  ✓ QC: All checks passed!\n")
                    else:
                        self.results_text.insert(tk.END, f"  ⚠ QC: {issues} issue type(s) found - see report for details\n")
                    
                except Exception as e:
                    self.results_text.insert(tk.END, f"⚠ ERROR creating QC report: {str(e)}\n")
                    import traceback
                    self.results_text.insert(tk.END, f"Traceback: {traceback.format_exc()}\n")
            
            self.results_text.insert(tk.END, "\n" + "="*60 + "\n")
            self.results_text.insert(tk.END, "DESURVEY COMPLETED SUCCESSFULLY!\n")
            self.results_text.insert(tk.END, "="*60 + "\n")
            
            self.status_var.set("Desurvey completed successfully!")
            messagebox.showinfo("Success", f"Desurvey completed!\n\nOutput saved to:\n{self.output_dir}")
            
        except Exception as e:
            self.results_text.insert(tk.END, f"\n\nERROR: {str(e)}\n")
            self.status_var.set("Error occurred")
            messagebox.showerror("Error", f"Error during desurvey:\n{str(e)}")
        
        finally:
            self.results_text.config(state='disabled')


def main():
    """Run the GUI application"""
    root = tk.Tk()
    app = DesurveyGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
