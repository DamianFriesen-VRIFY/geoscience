#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Standalone Desurvey Script for VSCode
Desurveys drill holes without requiring QGIS
"""

import pandas as pd
import numpy as np
import math
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Dict
import geopandas as gpd
from shapely.geometry import LineString, Point


class Quaternion:
    """Quaternion class for 3D rotations"""
    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0):
        self.w = w
        self.x = x
        self.y = y
        self.z = z
    
    @classmethod
    def from_axis_angle(cls, axis, angle):
        """Create quaternion from axis and angle (in radians)"""
        half_angle = angle / 2.0
        sin_half = math.sin(half_angle)
        return cls(
            math.cos(half_angle),
            axis[0] * sin_half,
            axis[1] * sin_half,
            axis[2] * sin_half
        )
    
    def multiply(self, other):
        """Multiply two quaternions"""
        w = self.w * other.w - self.x * other.x - self.y * other.y - self.z * other.z
        x = self.w * other.x + self.x * other.w + self.y * other.z - self.z * other.y
        y = self.w * other.y - self.x * other.z + self.y * other.w + self.z * other.x
        z = self.w * other.z + self.x * other.y - self.y * other.x + self.z * other.w
        return Quaternion(w, x, y, z)
    
    def conjugate(self):
        """Return conjugate of quaternion"""
        return Quaternion(self.w, -self.x, -self.y, -self.z)
    
    def rotate_vector(self, vec):
        """Rotate a 3D vector using this quaternion"""
        vec_quat = Quaternion(0, vec[0], vec[1], vec[2])
        result = self.multiply(vec_quat).multiply(self.conjugate())
        return [result.x, result.y, result.z]


class DesurveyStandalone:
    """Standalone desurvey functionality"""
    
    def __init__(self, desurvey_length=1.0, down_dip_negative=True):
        """
        Initialize desurvey parameters
        
        Args:
            desurvey_length: Length of desurvey segments (default 1.0)
            down_dip_negative: True if down dip is negative (default True)
        """
        self.desurvey_length = desurvey_length
        self.down_dip_negative = down_dip_negative
    
    def load_collar_data(self, collar_file):
        """
        Load collar data from CSV file
        
        Args:
            collar_file: Path to collar CSV file
            
        Returns:
            DataFrame with collar data
        """
        df = pd.read_csv(collar_file)
        # Strip whitespace from column names
        df.columns = df.columns.str.strip()
        return df
    
    def load_survey_data(self, survey_file):
        """
        Load survey data from CSV file
        
        Args:
            survey_file: Path to survey CSV file
            
        Returns:
            DataFrame with survey data
        """
        df = pd.read_csv(survey_file)
        # Strip whitespace from column names
        df.columns = df.columns.str.strip()
        return df
    
    def desurvey_hole(self, collar, surveys):
        """
        Desurvey a single drill hole
        
        Args:
            collar: Dictionary with collar info (HoleID, East, North, RL, EOH, Az, Dip)
            surveys: List of survey dictionaries (Depth, Az, Dip)
            
        Returns:
            List of desurvey points with (Depth, East, North, Elevation)
        """
        import numpy as np
        
        hole_id = collar['HoleID']
        
        # Validate and handle NaN values in collar data
        try:
            east = float(collar['East']) if pd.notna(collar['East']) else 0.0
            north = float(collar['North']) if pd.notna(collar['North']) else 0.0
            elev = float(collar['RL']) if pd.notna(collar['RL']) else 0.0
            eoh = float(collar['EOH']) if pd.notna(collar['EOH']) else 0.0
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid collar data for hole {hole_id}: {str(e)}")
        
        if eoh <= 0:
            raise ValueError(f"Invalid EOH ({eoh}) for hole {hole_id}")
        
        # Start from collar
        current_east = east
        current_north = north
        current_elev = elev
        current_depth = 0.0
        
        # Initialize with collar azimuth and dip if no surveys
        if len(surveys) == 0:
            # For holes without survey data, use collar Az/Dip if available, otherwise default to vertical
            collar_az = collar.get('Az', 0.0)  # Default azimuth = 0 (North)
            collar_dip = collar.get('Dip', -90.0)  # Default dip = -90° (vertical down)
            surveys = [
                {'Depth': 0.0, 'Az': collar_az, 'Dip': collar_dip},
                {'Depth': eoh, 'Az': collar_az, 'Dip': collar_dip}
            ]
        
        # Ensure first survey is at depth 0
        if surveys[0]['Depth'] > 0:
            collar_az = collar.get('Az', surveys[0]['Az'])
            collar_dip = collar.get('Dip', surveys[0]['Dip'])
            surveys.insert(0, {'Depth': 0.0, 'Az': collar_az, 'Dip': collar_dip})
        
        # Add end-of-hole survey if needed
        if surveys[-1]['Depth'] < eoh:
            surveys.append({
                'Depth': eoh,
                'Az': surveys[-1]['Az'],
                'Dip': surveys[-1]['Dip']
            })
        
        desurvey_points = []
        desurvey_points.append({
            'HoleID': hole_id,
            'Depth': 0.0,
            'East': east,
            'North': north,
            'Elevation': elev
        })
        
        # Process each survey interval
        for i in range(len(surveys) - 1):
            survey_from = surveys[i]
            survey_to = surveys[i + 1]
            
            depth_from = survey_from['Depth']
            depth_to = survey_to['Depth']
            az_from = survey_from['Az']
            az_to = survey_to['Az']
            dip_from = survey_from['Dip']
            dip_to = survey_to['Dip']
            
            # Calculate number of segments
            interval_length = depth_to - depth_from
            if interval_length <= 0:
                continue
            
            num_segments = max(1, int(math.ceil(interval_length / self.desurvey_length)))
            segment_length = interval_length / num_segments
            
            # Interpolate along the survey interval
            for seg in range(num_segments):
                # Interpolation factor
                t = (seg + 1) / num_segments
                
                # Interpolate azimuth and dip
                az = az_from + t * (az_to - az_from)
                dip = dip_from + t * (dip_to - dip_from)
                
                # Convert to radians
                az_rad = math.radians(az)
                dip_rad = math.radians(dip)
                
                # Calculate displacement
                # Azimuth is measured clockwise from north
                # Dip is measured from horizontal
                # If down_dip_negative is True, negative dips mean drilling down
                # If down_dip_negative is False, positive dips mean drilling down
                # Standard convention: positive dip = up, negative dip = down
                # So if down_dip_negative is False, we need to negate to convert to standard
                if not self.down_dip_negative:
                    dip_rad = -dip_rad
                
                # Calculate vector components
                horizontal_dist = segment_length * math.cos(dip_rad)
                vertical_dist = segment_length * math.sin(dip_rad)
                
                delta_north = horizontal_dist * math.cos(az_rad)
                delta_east = horizontal_dist * math.sin(az_rad)
                delta_elev = vertical_dist
                
                # Update position
                current_east += delta_east
                current_north += delta_north
                current_elev += delta_elev
                current_depth = depth_from + (seg + 1) * segment_length
                
                desurvey_points.append({
                    'HoleID': hole_id,
                    'Depth': round(current_depth, 3),
                    'East': round(current_east, 3),
                    'North': round(current_north, 3),
                    'Elevation': round(current_elev, 3)
                })
        
        return desurvey_points
    
    def desurvey_all_holes(self, collar_df, survey_df):
        """
        Desurvey all drill holes
        
        Args:
            collar_df: DataFrame with collar data
            survey_df: DataFrame with survey data
            
        Returns:
            DataFrame with all desurvey points
        """
        # Strip whitespace from column names
        collar_df = collar_df.copy()
        collar_df.columns = collar_df.columns.str.strip()
        survey_df = survey_df.copy()
        survey_df.columns = survey_df.columns.str.strip()
        
        all_points = []
        
        # Validate collar data and skip holes with invalid data
        valid_holes = 0
        skipped_holes = []
        
        for _, collar_row in collar_df.iterrows():
            hole_id = collar_row['HoleID']
            
            # Check for NaN values in required collar fields
            if pd.isna(collar_row['East']) or pd.isna(collar_row['North']) or pd.isna(collar_row['RL']) or pd.isna(collar_row['EOH']):
                skipped_holes.append(hole_id)
                continue
            
            # Check for valid EOH
            if collar_row['EOH'] <= 0:
                skipped_holes.append(hole_id)
                continue
            
            # Get surveys for this hole
            hole_surveys = survey_df[survey_df['HoleID'] == hole_id].copy()
            
            # Convert to list of dictionaries, skipping rows with NaN values
            surveys = []
            for _, survey_row in hole_surveys.iterrows():
                # Skip surveys with NaN values in critical fields
                if pd.notna(survey_row['Depth']) and pd.notna(survey_row['Az']) and pd.notna(survey_row['Dip']):
                    surveys.append({
                        'Depth': float(survey_row['Depth']),
                        'Az': float(survey_row['Az']),
                        'Dip': float(survey_row['Dip'])
                    })
            
            # Sort by depth
            surveys.sort(key=lambda x: x['Depth'])
            
            # Desurvey this hole
            try:
                collar_dict = collar_row.to_dict()
                points = self.desurvey_hole(collar_dict, surveys)
                all_points.extend(points)
                valid_holes += 1
            except Exception as e:
                print(f"Warning: Could not desurvey hole {hole_id}: {str(e)}")
                skipped_holes.append(hole_id)
                continue
        
        if skipped_holes:
            print(f"\nSkipped {len(skipped_holes)} holes due to invalid data: {', '.join(map(str, skipped_holes[:10]))}")
            if len(skipped_holes) > 10:
                print(f"... and {len(skipped_holes) - 10} more")
        
        print(f"Successfully desurveyed {valid_holes} holes")
        
        # Convert to DataFrame
        desurvey_df = pd.DataFrame(all_points)
        return desurvey_df
    
    def create_trace_shapefile(self, desurvey_df, output_path, crs="EPSG:4326"):
        """
        Create a shapefile of drill traces from desurvey data
        
        Args:
            desurvey_df: DataFrame with desurvey points (HoleID, Depth, East, North, Elevation)
            output_path: Path for output shapefile
            crs: Coordinate reference system (default: EPSG:4326 for WGS84)
            
        Returns:
            GeoDataFrame with drill trace lines
        """
        # Group by HoleID to create one line per hole
        traces = []
        
        for hole_id in desurvey_df['HoleID'].unique():
            hole_data = desurvey_df[desurvey_df['HoleID'] == hole_id].sort_values('Depth')
            
            if len(hole_data) < 2:
                continue  # Need at least 2 points to make a line
            
            # Create 3D coordinates (X, Y, Z)
            coords = [(row['East'], row['North'], row['Elevation']) 
                     for _, row in hole_data.iterrows()]
            
            # Create LineString (3D)
            line = LineString(coords)
            
            # Get collar info (first point)
            first_point = hole_data.iloc[0]
            last_point = hole_data.iloc[-1]
            
            traces.append({
                'HoleID': hole_id,
                'CollarEast': first_point['East'],
                'CollarNorth': first_point['North'],
                'CollarElev': first_point['Elevation'],
                'EndEast': last_point['East'],
                'EndNorth': last_point['North'],
                'EndElev': last_point['Elevation'],
                'Depth': last_point['Depth'],
                'NumPoints': len(hole_data),
                'geometry': line
            })
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(traces, crs=crs)
        
        # Save to shapefile
        output_path = Path(output_path)
        gdf.to_file(output_path, driver='ESRI Shapefile')
        
        return gdf
    
    def create_interval_shapefile(self, desurvey_df, interval_data_df, output_path, 
                                  from_col='From', to_col='To', hole_id_col=None, 
                                  crs="EPSG:4326", include_fields=None):
        """
        Create a shapefile of downhole intervals as 3D lines
        
        Args:
            desurvey_df: DataFrame with desurvey points
            interval_data_df: DataFrame with interval data (HoleID, From, To, plus data fields)
            output_path: Path for output shapefile
            from_col: Name of 'from' depth column (default 'From')
            to_col: Name of 'to' depth column (default 'To')
            hole_id_col: Name of hole ID column (default None, auto-detect)
            crs: Coordinate reference system (default: EPSG:4326)
            include_fields: List of field names to include (None = all fields)
            
        Returns:
            GeoDataFrame with interval geometries
        """
        # Strip whitespace from column names
        interval_data_df = interval_data_df.copy()
        interval_data_df.columns = interval_data_df.columns.str.strip()
        
        # Auto-detect hole ID column if not specified
        if hole_id_col is None:
            for col in ['HoleID', 'HoleId', 'HOLEID', 'holeid', 'Hole_ID', 'hole_id']:
                if col in interval_data_df.columns:
                    hole_id_col = col
                    break
            if hole_id_col is None:
                raise ValueError("Could not find hole ID column in interval data")
        
        intervals = []
        
        for _, interval_row in interval_data_df.iterrows():
            hole_id = interval_row[hole_id_col]
            depth_from = interval_row[from_col]
            depth_to = interval_row[to_col]
            
            # Get desurvey data for this hole
            hole_desurvey = desurvey_df[desurvey_df['HoleID'] == hole_id].copy()
            hole_desurvey = hole_desurvey.sort_values('Depth')
            
            if len(hole_desurvey) < 2:
                continue
            
            # Find points that fall within or bracket the interval
            interval_points = []
            
            # Get all points between from and to depths (inclusive)
            within_interval = hole_desurvey[
                (hole_desurvey['Depth'] >= depth_from) & 
                (hole_desurvey['Depth'] <= depth_to)
            ]
            
            # Interpolate start point
            before_start = hole_desurvey[hole_desurvey['Depth'] <= depth_from]
            after_start = hole_desurvey[hole_desurvey['Depth'] >= depth_from]
            
            if len(before_start) > 0 and len(after_start) > 0:
                p1 = before_start.iloc[-1]
                p2 = after_start.iloc[0]
                
                if p1['Depth'] == depth_from:
                    start_point = (p1['East'], p1['North'], p1['Elevation'])
                elif p2['Depth'] == depth_from:
                    start_point = (p2['East'], p2['North'], p2['Elevation'])
                else:
                    # Linear interpolation
                    t = (depth_from - p1['Depth']) / (p2['Depth'] - p1['Depth'])
                    start_point = (
                        p1['East'] + t * (p2['East'] - p1['East']),
                        p1['North'] + t * (p2['North'] - p1['North']),
                        p1['Elevation'] + t * (p2['Elevation'] - p1['Elevation'])
                    )
                interval_points.append(start_point)
            elif len(after_start) > 0:
                p = after_start.iloc[0]
                interval_points.append((p['East'], p['North'], p['Elevation']))
            else:
                continue
            
            # Add intermediate points
            for _, pt in within_interval.iterrows():
                if pt['Depth'] > depth_from and pt['Depth'] < depth_to:
                    interval_points.append((pt['East'], pt['North'], pt['Elevation']))
            
            # Interpolate end point
            before_end = hole_desurvey[hole_desurvey['Depth'] <= depth_to]
            after_end = hole_desurvey[hole_desurvey['Depth'] >= depth_to]
            
            if len(before_end) > 0 and len(after_end) > 0:
                p1 = before_end.iloc[-1]
                p2 = after_end.iloc[0]
                
                if p1['Depth'] == depth_to:
                    end_point = (p1['East'], p1['North'], p1['Elevation'])
                elif p2['Depth'] == depth_to:
                    end_point = (p2['East'], p2['North'], p2['Elevation'])
                else:
                    # Linear interpolation
                    t = (depth_to - p1['Depth']) / (p2['Depth'] - p1['Depth'])
                    end_point = (
                        p1['East'] + t * (p2['East'] - p1['East']),
                        p1['North'] + t * (p2['North'] - p1['North']),
                        p1['Elevation'] + t * (p2['Elevation'] - p1['Elevation'])
                    )
                interval_points.append(end_point)
            elif len(before_end) > 0:
                p = before_end.iloc[-1]
                interval_points.append((p['East'], p['North'], p['Elevation']))
            else:
                continue
            
            # Create line geometry if we have at least 2 points
            if len(interval_points) < 2:
                continue
            
            line = LineString(interval_points)
            
            # Calculate mid-point of the interval
            depth_mid = (depth_from + depth_to) / 2.0
            
            # Interpolate mid-point coordinates
            before_mid = hole_desurvey[hole_desurvey['Depth'] <= depth_mid]
            after_mid = hole_desurvey[hole_desurvey['Depth'] >= depth_mid]
            
            if len(before_mid) > 0 and len(after_mid) > 0:
                p1 = before_mid.iloc[-1]
                p2 = after_mid.iloc[0]
                
                if p1['Depth'] == depth_mid:
                    mid_x, mid_y, mid_z = p1['East'], p1['North'], p1['Elevation']
                elif p2['Depth'] == depth_mid:
                    mid_x, mid_y, mid_z = p2['East'], p2['North'], p2['Elevation']
                else:
                    # Linear interpolation
                    t = (depth_mid - p1['Depth']) / (p2['Depth'] - p1['Depth'])
                    mid_x = p1['East'] + t * (p2['East'] - p1['East'])
                    mid_y = p1['North'] + t * (p2['North'] - p1['North'])
                    mid_z = p1['Elevation'] + t * (p2['Elevation'] - p1['Elevation'])
            elif len(after_mid) > 0:
                p = after_mid.iloc[0]
                mid_x, mid_y, mid_z = p['East'], p['North'], p['Elevation']
            elif len(before_mid) > 0:
                p = before_mid.iloc[-1]
                mid_x, mid_y, mid_z = p['East'], p['North'], p['Elevation']
            else:
                # Fallback to average of start and end
                mid_x = (interval_points[0][0] + interval_points[-1][0]) / 2.0
                mid_y = (interval_points[0][1] + interval_points[-1][1]) / 2.0
                mid_z = (interval_points[0][2] + interval_points[-1][2]) / 2.0
            
            # Prepare interval data
            interval_data = {'geometry': line}
            
            # Add selected fields or all fields
            if include_fields is None:
                for col in interval_data_df.columns:
                    if col not in [hole_id_col, from_col, to_col]:
                        interval_data[col] = interval_row[col]
            else:
                for field in include_fields:
                    if field in interval_data_df.columns:
                        interval_data[field] = interval_row[field]
            
            # Always include key fields
            interval_data['HoleID'] = hole_id
            interval_data['From'] = depth_from
            interval_data['To'] = depth_to
            interval_data['Length'] = depth_to - depth_from
            interval_data['MidX'] = round(mid_x, 3)
            interval_data['MidY'] = round(mid_y, 3)
            interval_data['MidZ'] = round(mid_z, 3)
            
            intervals.append(interval_data)
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(intervals, crs=crs)
        
        # Save to shapefile
        output_path = Path(output_path)
        gdf.to_file(output_path, driver='ESRI Shapefile')
        
        return gdf
    
    def create_interval_points_shapefile(self, desurvey_df, interval_data_df, output_path,
                                        from_col='From', to_col='To', hole_id_col=None,
                                        crs="EPSG:4326", include_fields=None):
        """
        Create a point shapefile from mid-points of downhole intervals
        
        Args:
            desurvey_df: DataFrame with desurvey points
            interval_data_df: DataFrame with interval data (HoleID, From, To, plus data fields)
            output_path: Path for output shapefile
            from_col: Name of 'from' depth column (default 'From')
            to_col: Name of 'to' depth column (default 'To')
            hole_id_col: Name of hole ID column (default None, auto-detect)
            crs: Coordinate reference system (default: EPSG:4326)
            include_fields: List of field names to include (None = all fields)
            
        Returns:
            GeoDataFrame with point geometries
        """
        # Strip whitespace from column names
        interval_data_df = interval_data_df.copy()
        interval_data_df.columns = interval_data_df.columns.str.strip()
        
        # Auto-detect hole ID column if not specified
        if hole_id_col is None:
            for col in ['HoleID', 'HoleId', 'HOLEID', 'holeid', 'Hole_ID', 'hole_id']:
                if col in interval_data_df.columns:
                    hole_id_col = col
                    break
            if hole_id_col is None:
                raise ValueError("Could not find hole ID column in interval data")
        
        points = []
        
        for _, interval_row in interval_data_df.iterrows():
            hole_id = interval_row[hole_id_col]
            depth_from = interval_row[from_col]
            depth_to = interval_row[to_col]
            depth_mid = (depth_from + depth_to) / 2.0
            
            # Get desurvey data for this hole
            hole_desurvey = desurvey_df[desurvey_df['HoleID'] == hole_id].copy()
            hole_desurvey = hole_desurvey.sort_values('Depth')
            
            if len(hole_desurvey) == 0:
                continue
            
            # Interpolate mid-point coordinates
            before_mid = hole_desurvey[hole_desurvey['Depth'] <= depth_mid]
            after_mid = hole_desurvey[hole_desurvey['Depth'] >= depth_mid]
            
            if len(before_mid) > 0 and len(after_mid) > 0:
                p1 = before_mid.iloc[-1]
                p2 = after_mid.iloc[0]
                
                if p1['Depth'] == depth_mid:
                    mid_x, mid_y, mid_z = p1['East'], p1['North'], p1['Elevation']
                elif p2['Depth'] == depth_mid:
                    mid_x, mid_y, mid_z = p2['East'], p2['North'], p2['Elevation']
                else:
                    # Linear interpolation
                    t = (depth_mid - p1['Depth']) / (p2['Depth'] - p1['Depth'])
                    mid_x = p1['East'] + t * (p2['East'] - p1['East'])
                    mid_y = p1['North'] + t * (p2['North'] - p1['North'])
                    mid_z = p1['Elevation'] + t * (p2['Elevation'] - p1['Elevation'])
            elif len(after_mid) > 0:
                p = after_mid.iloc[0]
                mid_x, mid_y, mid_z = p['East'], p['North'], p['Elevation']
            elif len(before_mid) > 0:
                p = before_mid.iloc[-1]
                mid_x, mid_y, mid_z = p['East'], p['North'], p['Elevation']
            else:
                continue
            
            # Create point geometry (3D)
            point = Point(mid_x, mid_y, mid_z)
            
            # Prepare point data
            point_data = {'geometry': point}
            
            # Add selected fields or all fields
            if include_fields is None:
                for col in interval_data_df.columns:
                    if col not in [hole_id_col, from_col, to_col]:
                        point_data[col] = interval_row[col]
            else:
                for field in include_fields:
                    if field in interval_data_df.columns:
                        point_data[field] = interval_row[field]
            
            # Always include key fields
            point_data['HoleID'] = hole_id
            point_data['From'] = depth_from
            point_data['To'] = depth_to
            point_data['MidDepth'] = depth_mid
            point_data['Length'] = depth_to - depth_from
            point_data['MidX'] = round(mid_x, 3)
            point_data['MidY'] = round(mid_y, 3)
            point_data['MidZ'] = round(mid_z, 3)
            
            points.append(point_data)
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(points, crs=crs)
        
        # Save to shapefile
        output_path = Path(output_path)
        gdf.to_file(output_path, driver='ESRI Shapefile')
        
        return gdf
    
    def create_collar_shapefile(self, collar_df, output_path, crs="EPSG:4326"):
        """
        Create a point shapefile from collar locations
        
        Args:
            collar_df: DataFrame with collar data (HoleID, East, North, RL, EOH, Az, Dip)
            output_path: Path for output shapefile
            crs: Coordinate reference system (default: EPSG:4326)
            
        Returns:
            GeoDataFrame with point geometries
        """
        # Strip whitespace from column names
        collar_df = collar_df.copy()
        collar_df.columns = collar_df.columns.str.strip()
        
        points = []
        
        for _, collar_row in collar_df.iterrows():
            # Create 3D point geometry
            point = Point(collar_row['East'], collar_row['North'], collar_row['RL'])
            
            # Prepare point data with all collar attributes
            point_data = {
                'HoleID': collar_row['HoleID'],
                'East': collar_row['East'],
                'North': collar_row['North'],
                'RL': collar_row['RL'],
                'EOH': collar_row['EOH'],
                'geometry': point
            }
            
            # Add Az and Dip if they exist
            if 'Az' in collar_df.columns and pd.notna(collar_row.get('Az')):
                point_data['Az'] = collar_row['Az']
            if 'Dip' in collar_df.columns and pd.notna(collar_row.get('Dip')):
                point_data['Dip'] = collar_row['Dip']
            
            points.append(point_data)
        
        # Create GeoDataFrame
        gdf = gpd.GeoDataFrame(points, crs=crs)
        
        # Save to shapefile
        output_path = Path(output_path)
        gdf.to_file(output_path, driver='ESRI Shapefile')
        
        return gdf
    
    def sample_desurvey_at_intervals(self, desurvey_df, interval_data_df, from_col='From', to_col='To', hole_id_col=None):
        """
        Sample desurvey data at specific intervals (e.g., assay intervals)
        
        Args:
            desurvey_df: DataFrame with desurvey points
            interval_data_df: DataFrame with interval data (must have HoleID, From, To columns)
            from_col: Name of 'from' depth column (default 'From')
            to_col: Name of 'to' depth column (default 'To')
            hole_id_col: Name of hole ID column (default None, auto-detect)
            
        Returns:
            DataFrame with interval data plus desurvey coordinates
        """
        # Strip whitespace from column names
        interval_data_df = interval_data_df.copy()
        interval_data_df.columns = interval_data_df.columns.str.strip()
        
        # Auto-detect hole ID column if not specified
        if hole_id_col is None:
            for col in ['HoleID', 'HoleId', 'HOLEID', 'holeid', 'Hole_ID', 'hole_id']:
                if col in interval_data_df.columns:
                    hole_id_col = col
                    break
            if hole_id_col is None:
                raise ValueError("Could not find hole ID column in interval data")
        
        result_rows = []
        
        for _, interval_row in interval_data_df.iterrows():
            hole_id = interval_row[hole_id_col]
            depth_from = interval_row[from_col]
            depth_to = interval_row[to_col]
            depth_mid = (depth_from + depth_to) / 2.0
            
            # Get desurvey data for this hole
            hole_desurvey = desurvey_df[desurvey_df['HoleID'] == hole_id].copy()
            hole_desurvey = hole_desurvey.sort_values('Depth')
            
            if len(hole_desurvey) == 0:
                continue
            
            # Interpolate position at from, mid, and to depths
            positions = {}
            for depth, suffix in [(depth_from, '_from'), (depth_mid, '_mid'), (depth_to, '_to')]:
                # Find surrounding points
                before = hole_desurvey[hole_desurvey['Depth'] <= depth]
                after = hole_desurvey[hole_desurvey['Depth'] >= depth]
                
                if len(before) == 0:
                    pos = after.iloc[0]
                    east, north, elev = pos['East'], pos['North'], pos['Elevation']
                elif len(after) == 0:
                    pos = before.iloc[-1]
                    east, north, elev = pos['East'], pos['North'], pos['Elevation']
                else:
                    p1 = before.iloc[-1]
                    p2 = after.iloc[0]
                    
                    if p1['Depth'] == p2['Depth']:
                        east, north, elev = p1['East'], p1['North'], p1['Elevation']
                    else:
                        # Linear interpolation
                        t = (depth - p1['Depth']) / (p2['Depth'] - p1['Depth'])
                        east = p1['East'] + t * (p2['East'] - p1['East'])
                        north = p1['North'] + t * (p2['North'] - p1['North'])
                        elev = p1['Elevation'] + t * (p2['Elevation'] - p1['Elevation'])
                
                positions[f'East{suffix}'] = east
                positions[f'North{suffix}'] = north
                positions[f'Elevation{suffix}'] = elev
            
            # Combine original data with positions
            result_row = interval_row.to_dict()
            result_row.update(positions)
            result_rows.append(result_row)
        
        return pd.DataFrame(result_rows)
    
    def create_qc_report(self, collar_df, survey_df, interval_df, desurvey_df, output_path, 
                        shapefile_paths=None):
        """
        Create an HTML QC report for data quality checking
        
        Args:
            collar_df: DataFrame with collar data
            survey_df: DataFrame with survey data (can be None)
            interval_df: DataFrame with interval data (can be None)
            desurvey_df: DataFrame with desurvey results
            output_path: Path for output HTML file
            shapefile_paths: Dict with paths to created shapefiles for 3D visualization
                           {'collar': path, 'traces': path, 'intervals': path, 'points': path}
            
        Returns:
            Dictionary with QC results
        """
        from datetime import datetime
        
        # Strip whitespace from column names
        collar_df = collar_df.copy()
        collar_df.columns = collar_df.columns.str.strip()
        if survey_df is not None:
            survey_df = survey_df.copy()
            survey_df.columns = survey_df.columns.str.strip()
        if interval_df is not None:
            interval_df = interval_df.copy()
            interval_df.columns = interval_df.columns.str.strip()
        
        qc_results = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'collar': {},
            'survey': {},
            'interval': {},
            'overall': {},
            'shapefile_paths': shapefile_paths or {}
        }
        
        # QC Collar Data
        qc_results['collar']['total_holes'] = len(collar_df)
        qc_results['collar']['duplicate_ids'] = collar_df['HoleID'].duplicated().sum()
        qc_results['collar']['missing_coordinates'] = collar_df[['East', 'North', 'RL']].isna().any(axis=1).sum()
        qc_results['collar']['missing_eoh'] = collar_df['EOH'].isna().sum()
        qc_results['collar']['zero_eoh'] = (collar_df['EOH'] <= 0).sum()
        qc_results['collar']['coord_range'] = {
            'East': {'min': float(collar_df['East'].min()), 'max': float(collar_df['East'].max())},
            'North': {'min': float(collar_df['North'].min()), 'max': float(collar_df['North'].max())},
            'RL': {'min': float(collar_df['RL'].min()), 'max': float(collar_df['RL'].max())},
            'EOH': {'min': float(collar_df['EOH'].min()), 'max': float(collar_df['EOH'].max())}
        }
        
        # QC Survey Data
        if survey_df is not None and len(survey_df) > 0:
            qc_results['survey']['total_surveys'] = len(survey_df)
            qc_results['survey']['holes_with_surveys'] = survey_df['HoleID'].nunique()
            qc_results['survey']['holes_without_surveys'] = len(collar_df) - survey_df['HoleID'].nunique()
            qc_results['survey']['invalid_depths'] = (survey_df['Depth'] < 0).sum()
            qc_results['survey']['invalid_azimuth'] = ((survey_df['Az'] < 0) | (survey_df['Az'] > 360)).sum()
            qc_results['survey']['invalid_dip'] = ((survey_df['Dip'] < -90) | (survey_df['Dip'] > 90)).sum()
            
            # Check for surveys beyond EOH
            beyond_eoh = []
            for hole_id in survey_df['HoleID'].unique():
                collar_row = collar_df[collar_df['HoleID'] == hole_id]
                if len(collar_row) > 0:
                    eoh = collar_row.iloc[0]['EOH']
                    hole_surveys = survey_df[survey_df['HoleID'] == hole_id]
                    if (hole_surveys['Depth'] > eoh).any():
                        beyond_eoh.append(hole_id)
            qc_results['survey']['surveys_beyond_eoh'] = len(beyond_eoh)
            qc_results['survey']['holes_beyond_eoh'] = beyond_eoh[:10]  # First 10
            
            # Check for non-monotonic depths
            non_monotonic = []
            for hole_id in survey_df['HoleID'].unique():
                hole_surveys = survey_df[survey_df['HoleID'] == hole_id].sort_values('Depth')
                depths = hole_surveys['Depth'].values
                if not all(depths[i] <= depths[i+1] for i in range(len(depths)-1)):
                    non_monotonic.append(hole_id)
            qc_results['survey']['non_monotonic_depths'] = len(non_monotonic)
            qc_results['survey']['holes_non_monotonic'] = non_monotonic[:10]
        else:
            qc_results['survey']['total_surveys'] = 0
            qc_results['survey']['holes_with_surveys'] = 0
            qc_results['survey']['holes_without_surveys'] = len(collar_df)
        
        # QC Interval Data
        if interval_df is not None and len(interval_df) > 0:
            # Detect hole ID column
            hole_id_col = None
            for col in ['HoleID', 'HoleId', 'HOLEID', 'holeid']:
                if col in interval_df.columns:
                    hole_id_col = col
                    break
            
            if hole_id_col:
                qc_results['interval']['total_intervals'] = len(interval_df)
                qc_results['interval']['holes_with_intervals'] = interval_df[hole_id_col].nunique()
                qc_results['interval']['invalid_depths'] = ((interval_df['From'] < 0) | (interval_df['To'] < 0)).sum()
                qc_results['interval']['inverted_intervals'] = (interval_df['From'] > interval_df['To']).sum()
                qc_results['interval']['zero_length'] = (interval_df['From'] == interval_df['To']).sum()
                qc_results['interval']['negative_length'] = (interval_df['From'] > interval_df['To']).sum()
                
                # Check for intervals beyond EOH
                beyond_eoh_int = []
                for hole_id in interval_df[hole_id_col].unique():
                    collar_row = collar_df[collar_df['HoleID'] == hole_id]
                    if len(collar_row) > 0:
                        eoh = collar_row.iloc[0]['EOH']
                        hole_intervals = interval_df[interval_df[hole_id_col] == hole_id]
                        if (hole_intervals['To'] > eoh).any():
                            beyond_eoh_int.append(hole_id)
                qc_results['interval']['intervals_beyond_eoh'] = len(beyond_eoh_int)
                qc_results['interval']['holes_beyond_eoh'] = beyond_eoh_int[:10]
                
                # Check for overlapping intervals
                overlaps = []
                for hole_id in interval_df[hole_id_col].unique():
                    hole_intervals = interval_df[interval_df[hole_id_col] == hole_id].sort_values('From')
                    for i in range(len(hole_intervals) - 1):
                        if hole_intervals.iloc[i]['To'] > hole_intervals.iloc[i+1]['From']:
                            overlaps.append(hole_id)
                            break
                qc_results['interval']['overlapping_intervals'] = len(overlaps)
                qc_results['interval']['holes_with_overlaps'] = overlaps[:10]
                
                # Check for gaps in intervals
                gaps = []
                for hole_id in interval_df[hole_id_col].unique():
                    hole_intervals = interval_df[interval_df[hole_id_col] == hole_id].sort_values('From')
                    for i in range(len(hole_intervals) - 1):
                        if hole_intervals.iloc[i]['To'] < hole_intervals.iloc[i+1]['From']:
                            gaps.append(hole_id)
                            break
                qc_results['interval']['gaps_in_intervals'] = len(gaps)
                qc_results['interval']['holes_with_gaps'] = gaps[:10]
        else:
            qc_results['interval']['total_intervals'] = 0
        
        # QC EOH Depth Variance
        qc_results['eoh_variance'] = {
            'mismatches': [],
            'survey_variances': [],
            'interval_variances': [],
            'count': 0,
            'tolerance': 0.1,  # meters - for detection
            'reporting_threshold': 15.0  # meters - for reporting
        }
        
        eoh_mismatches = []
        survey_variances = []
        interval_variances = []
        
        for _, collar_row in collar_df.iterrows():
            hole_id = collar_row['HoleID']
            collar_eoh = collar_row['EOH']
            issues = []
            
            # Check survey max depth
            if survey_df is not None and len(survey_df) > 0:
                hole_surveys = survey_df[survey_df['HoleID'] == hole_id]
                if len(hole_surveys) > 0:
                    max_survey_depth = hole_surveys['Depth'].max()
                    variance_survey = abs(collar_eoh - max_survey_depth)
                    if variance_survey > qc_results['eoh_variance']['tolerance']:
                        issues.append({
                            'type': 'Survey',
                            'collar_eoh': float(collar_eoh),
                            'max_depth': float(max_survey_depth),
                            'variance': float(variance_survey)
                        })
                        if variance_survey >= qc_results['eoh_variance']['reporting_threshold']:
                            survey_variances.append({
                                'hole_id': hole_id,
                                'collar_eoh': float(collar_eoh),
                                'max_depth': float(max_survey_depth),
                                'variance': float(variance_survey)
                            })
            
            # Check interval max depth
            if interval_df is not None and len(interval_df) > 0:
                hole_id_col = None
                for col in ['HoleID', 'HoleId', 'HOLEID', 'holeid']:
                    if col in interval_df.columns:
                        hole_id_col = col
                        break
                
                if hole_id_col:
                    hole_intervals = interval_df[interval_df[hole_id_col] == hole_id]
                    if len(hole_intervals) > 0:
                        max_interval_depth = hole_intervals['To'].max()
                        variance_interval = abs(collar_eoh - max_interval_depth)
                        if variance_interval > qc_results['eoh_variance']['tolerance']:
                            issues.append({
                                'type': 'Interval',
                                'collar_eoh': float(collar_eoh),
                                'max_depth': float(max_interval_depth),
                                'variance': float(variance_interval)
                            })
                            if variance_interval >= qc_results['eoh_variance']['reporting_threshold']:
                                interval_variances.append({
                                    'hole_id': hole_id,
                                    'collar_eoh': float(collar_eoh),
                                    'max_depth': float(max_interval_depth),
                                    'variance': float(variance_interval)
                                })
            
            if issues:
                eoh_mismatches.append({
                    'hole_id': hole_id,
                    'issues': issues
                })
        
        # Sort variances by magnitude (highest to lowest)
        survey_variances.sort(key=lambda x: x['variance'], reverse=True)
        interval_variances.sort(key=lambda x: x['variance'], reverse=True)
        
        qc_results['eoh_variance']['mismatches'] = eoh_mismatches
        qc_results['eoh_variance']['survey_variances'] = survey_variances
        qc_results['eoh_variance']['interval_variances'] = interval_variances
        qc_results['eoh_variance']['count'] = len(eoh_mismatches)
        
        # Overall Summary
        qc_results['overall']['total_holes'] = len(collar_df)
        qc_results['overall']['desurvey_points'] = len(desurvey_df)
        qc_results['overall']['avg_points_per_hole'] = len(desurvey_df) / len(collar_df) if len(collar_df) > 0 else 0
        
        # Generate HTML report
        try:
            html = self._generate_qc_html(qc_results, collar_df, desurvey_df, interval_df)
        except Exception as e:
            print(f"Error generating QC HTML: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
        
        # Save HTML file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"QC Report saved to: {output_path}")
        except Exception as e:
            print(f"Error writing QC report to {output_path}: {str(e)}")
            raise
        
        return qc_results
    
    def _generate_plotly_3d(self, collar_df, desurvey_df, interval_df=None):
        """
        Generate interactive 3D Plotly visualization of drill holes
        
        Args:
            collar_df: DataFrame with collar data
            desurvey_df: DataFrame with desurvey results
            interval_df: DataFrame with interval data (optional)
            
        Returns:
            HTML string with Plotly chart
        """
        try:
            import plotly.graph_objects as go
            
            fig = go.Figure()
            
            # Add collar points at surface (depth = 0)
            # Calculate depth below surface for each collar
            collar_depths = [0.0] * len(collar_df)  # Collars are at surface (depth 0)
            
            fig.add_trace(go.Scatter3d(
                x=collar_df['East'],
                y=collar_df['North'],
                z=collar_depths,
                mode='markers',
                name='Collars',
                marker=dict(
                    size=8,
                    color='red',
                    symbol='diamond',
                    line=dict(color='darkred', width=1)
                ),
                text=[f"HoleID: {hid}<br>East: {e:.2f}<br>North: {n:.2f}<br>RL: {rl:.2f}<br>Depth: 0.00m<br>EOH: {eoh:.2f}" 
                      for hid, e, n, rl, eoh in zip(collar_df['HoleID'], collar_df['East'], 
                                                      collar_df['North'], collar_df['RL'], collar_df['EOH'])],
                hovertemplate='<b>%{text}</b><extra></extra>'
            ))
            
            # Add drill traces (with visibility toggle)
            # Convert elevation to depth below surface for each hole
            for hole_id in desurvey_df['HoleID'].unique():
                hole_data = desurvey_df[desurvey_df['HoleID'] == hole_id].sort_values('Depth')
                
                # Get collar RL for this hole to calculate depth below surface
                collar_rl = collar_df[collar_df['HoleID'] == hole_id]['RL'].iloc[0]
                # Depth below surface = RL - Elevation
                depths_below_surface = collar_rl - hole_data['Elevation']
                
                fig.add_trace(go.Scatter3d(
                    x=hole_data['East'],
                    y=hole_data['North'],
                    z=depths_below_surface,
                    mode='lines',
                    name='Drill Traces',
                    legendgroup='traces',  # Group all traces together
                    line=dict(
                        color='blue',
                        width=3
                    ),
                    showlegend=(hole_id == desurvey_df['HoleID'].unique()[0]),  # Show legend only for first trace
                    text=[f"HoleID: {hole_id}<br>Depth: {d:.2f}m<br>East: {e:.2f}<br>North: {n:.2f}<br>Elev: {el:.2f}" 
                          for d, e, n, el in zip(hole_data['Depth'], hole_data['East'], 
                                                  hole_data['North'], hole_data['Elevation'])],
                    hovertemplate='<b>%{text}</b><extra></extra>'
                ))
            
            # Add interval mid-points if available (inverted Z-axis)
            if interval_df is not None and len(interval_df) > 0:
                # Calculate mid-points for intervals
                interval_points = []
                
                hole_id_col = None
                for col in ['HoleID', 'HoleId', 'HOLEID', 'holeid']:
                    if col in interval_df.columns:
                        hole_id_col = col
                        break
                
                if hole_id_col:
                    for _, interval_row in interval_df.iterrows():
                        hole_id = interval_row[hole_id_col]
                        depth_mid = (interval_row['From'] + interval_row['To']) / 2.0
                        
                        # Interpolate mid-point from desurvey
                        hole_desurvey = desurvey_df[desurvey_df['HoleID'] == hole_id].sort_values('Depth')
                        
                        if len(hole_desurvey) > 0:
                            before = hole_desurvey[hole_desurvey['Depth'] <= depth_mid]
                            after = hole_desurvey[hole_desurvey['Depth'] >= depth_mid]
                            
                            if len(before) > 0 and len(after) > 0:
                                p1 = before.iloc[-1]
                                p2 = after.iloc[0]
                                
                                if p1['Depth'] == p2['Depth']:
                                    mid_x, mid_y, mid_z = p1['East'], p1['North'], p1['Elevation']
                                else:
                                    t = (depth_mid - p1['Depth']) / (p2['Depth'] - p1['Depth'])
                                    mid_x = p1['East'] + t * (p2['East'] - p1['East'])
                                    mid_y = p1['North'] + t * (p2['North'] - p1['North'])
                                    mid_z = p1['Elevation'] + t * (p2['Elevation'] - p1['Elevation'])
                                    
                                interval_points.append({
                                    'x': mid_x,
                                    'y': mid_y,
                                    'z': mid_z,
                                    'hole_id': hole_id,
                                    'from': interval_row['From'],
                                    'to': interval_row['To']
                                })
                    
                    if interval_points:
                        # Convert interval elevations to depth below surface
                        interval_depths = []
                        for p in interval_points:
                            collar_rl = collar_df[collar_df['HoleID'] == p['hole_id']]['RL'].iloc[0]
                            depth_below_surface = collar_rl - p['z']
                            interval_depths.append(depth_below_surface)
                        
                        fig.add_trace(go.Scatter3d(
                            x=[p['x'] for p in interval_points],
                            y=[p['y'] for p in interval_points],
                            z=interval_depths,
                            mode='markers',
                            name='Interval Mid-Points',
                            marker=dict(
                                size=4,
                                color='green',
                                symbol='circle',
                                opacity=0.7
                            ),
                            text=[f"HoleID: {p['hole_id']}<br>From-To: {p['from']:.2f}-{p['to']:.2f}m" 
                                  for p in interval_points],
                            hovertemplate='<b>%{text}</b><extra></extra>'
                        ))
            
            # Update layout with depth axis (0 at top, positive values going down)
            fig.update_layout(
                title='3D Drill Hole Visualization',
                scene=dict(
                    xaxis_title='East (m)',
                    yaxis_title='North (m)',
                    zaxis_title='Depth Below Surface (m)',
                    zaxis=dict(autorange='reversed'),  # Reverse so depth increases downward
                    aspectmode='data'
                ),
                height=700,
                showlegend=True,
                legend=dict(
                    yanchor="top",
                    y=0.99,
                    xanchor="left",
                    x=0.01
                ),
                updatemenus=[
                    dict(
                        type="buttons",
                        direction="left",
                        buttons=[
                            dict(
                                args=[{"visible": [True] + [True] * len(desurvey_df['HoleID'].unique()) + 
                                      ([True] if interval_df is not None and len(interval_df) > 0 else [])}],
                                label="Show All",
                                method="update"
                            ),
                            dict(
                                args=[{"visible": [True] + [False] * len(desurvey_df['HoleID'].unique()) + 
                                      ([True] if interval_df is not None and len(interval_df) > 0 else [])}],
                                label="Hide Traces",
                                method="update"
                            ),
                            dict(
                                args=[{"visible": [True] + [True] * len(desurvey_df['HoleID'].unique()) + 
                                      ([False] if interval_df is not None and len(interval_df) > 0 else [])}],
                                label="Hide Intervals",
                                method="update"
                            )
                        ],
                        pad={"r": 10, "t": 10},
                        showactive=True,
                        x=0.11,
                        xanchor="left",
                        y=1.15,
                        yanchor="top"
                    )
                ]
            )
            
            # Convert to HTML div
            plotly_html = fig.to_html(full_html=False, include_plotlyjs='cdn')
            return plotly_html
            
        except Exception as e:
            return f'<div class="error-box"><strong>Could not generate 3D visualization:</strong> {str(e)}</div>'
    
    def _generate_qc_html(self, qc_results, collar_df=None, desurvey_df=None, interval_df=None):
        """Generate HTML content for QC report"""
        
        def status_icon(count):
            """Return status icon based on count (0 = pass)"""
            if count == 0:
                return '✓'
            elif count > 0:
                return '✗'
            return '−'
        
        def status_class(count):
            """Return CSS class based on count"""
            if count == 0:
                return 'status-pass'
            elif count > 0:
                return 'status-fail'
            return 'status-info'
        
        # Generate Plotly chart first (before the main HTML template)
        plotly_chart = ""
        if collar_df is not None and desurvey_df is not None:
            plotly_chart = self._generate_plotly_3d(collar_df, desurvey_df, interval_df)
        
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Drill Hole Desurvey - QC Report</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .summary-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .summary-card .value {{
            font-size: 32px;
            font-weight: bold;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .status-pass {{
            color: #4caf50;
            font-weight: bold;
            font-size: 18px;
        }}
        .status-fail {{
            color: #f44336;
            font-weight: bold;
            font-size: 18px;
        }}
        .status-info {{
            color: #757575;
            font-weight: bold;
            font-size: 18px;
        }}
        .section {{
            margin: 30px 0;
            padding: 20px;
            background-color: #f8f9fa;
            border-radius: 8px;
        }}
        .info-box {{
            background-color: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .warning-box {{
            background-color: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .error-box {{
            background-color: #ffebee;
            border-left: 4px solid #f44336;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .range-table {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin: 10px 0;
        }}
        .range-item {{
            background: white;
            padding: 10px;
            border-radius: 4px;
            border: 1px solid #e0e0e0;
        }}
        .timestamp {{
            color: #7f8c8d;
            font-size: 14px;
            margin-top: 20px;
            text-align: right;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-success {{ background-color: #4caf50; color: white; }}
        .badge-warning {{ background-color: #ff9800; color: white; }}
        .badge-error {{ background-color: #f44336; color: white; }}
        .badge-info {{ background-color: #2196f3; color: white; }}
        .legend {{
            background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 15px;
            margin: 20px 0;
        }}
        .legend-title {{
            font-weight: bold;
            margin-bottom: 10px;
            color: #495057;
        }}
        .legend-items {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 10px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-icon {{
            font-size: 18px;
            font-weight: bold;
        }}
        .subsection {{
            margin: 20px 0;
            padding: 15px;
            background-color: white;
            border-radius: 6px;
            border: 1px solid #e0e0e0;
        }}
        .subsection h4 {{
            color: #495057;
            margin-top: 0;
            margin-bottom: 15px;
            padding-bottom: 8px;
            border-bottom: 2px solid #dee2e6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🔍 Drill Hole Desurvey - Quality Control Report</h1>
        <p class="timestamp">Generated: {qc_results['timestamp']}</p>
        
        <div class="summary">
            <div class="summary-card">
                <h3>Total Drill Holes</h3>
                <div class="value">{qc_results['overall']['total_holes']}</div>
            </div>
            <div class="summary-card">
                <h3>Desurvey Points</h3>
                <div class="value">{qc_results['overall']['desurvey_points']:,}</div>
            </div>
            <div class="summary-card">
                <h3>Avg Points/Hole</h3>
                <div class="value">{qc_results['overall']['avg_points_per_hole']:.1f}</div>
            </div>
            <div class="summary-card">
                <h3>Survey Records</h3>
                <div class="value">{qc_results['survey']['total_surveys']}</div>
            </div>
        </div>
"""
        
        # Add 3D Plotly visualization if it was generated
        if plotly_chart:
            html += """
        <h2>🌍 3D Drill Hole Visualization</h2>
        <div class="section">
            <p>Interactive 3D view of drill hole locations, traces, and intervals. Click and drag to rotate, scroll to zoom.</p>
"""
            html += plotly_chart
            html += """
        </div>
"""
        
        # Add simple status legend at top
        html += """
        <div class="legend">
            <div class="legend-title">Status Legend</div>
            <div class="legend-items">
                <div class="legend-item">
                    <span class="status-pass">✓</span>
                    <span>Pass</span>
                </div>
                <div class="legend-item">
                    <span class="status-fail">✗</span>
                    <span>Fail</span>
                </div>
            </div>
        </div>
        
        <h2>📍 Collar Data Quality</h2>
        <div class="section">
            <p><strong>{qc_results['collar']['total_holes']}</strong> collar records loaded</p>
            <table>
                <tr>
                    <th>Check</th>
                    <th>Count</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>Duplicate Hole IDs</td>
                    <td>{qc_results['collar']['duplicate_ids']}</td>
                    <td><span class="{status_class(qc_results['collar']['duplicate_ids'])}">{status_icon(qc_results['collar']['duplicate_ids'])}</span></td>
                </tr>
                <tr>
                    <td>Missing Coordinates</td>
                    <td>{qc_results['collar']['missing_coordinates']}</td>
                    <td><span class="{status_class(qc_results['collar']['missing_coordinates'])}">{status_icon(qc_results['collar']['missing_coordinates'])}</span></td>
                </tr>
                <tr>
                    <td>Invalid EOH Depths</td>
                    <td>{qc_results['collar']['missing_eoh'] + qc_results['collar']['zero_eoh']}</td>
                    <td><span class="{status_class(qc_results['collar']['missing_eoh'] + qc_results['collar']['zero_eoh'])}">{status_icon(qc_results['collar']['missing_eoh'] + qc_results['collar']['zero_eoh'])}</span></td>
                </tr>
            </table>
            
            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; font-weight: bold; color: #3498db;">Coordinate Ranges ▼</summary>
                <div class="range-table" style="margin-top: 10px;">
                    <div class="range-item">
                        <strong>East:</strong> {qc_results['collar']['coord_range']['East']['min']:.2f} to {qc_results['collar']['coord_range']['East']['max']:.2f} m
                    </div>
                    <div class="range-item">
                        <strong>North:</strong> {qc_results['collar']['coord_range']['North']['min']:.2f} to {qc_results['collar']['coord_range']['North']['max']:.2f} m
                    </div>
                    <div class="range-item">
                        <strong>RL:</strong> {qc_results['collar']['coord_range']['RL']['min']:.2f} to {qc_results['collar']['coord_range']['RL']['max']:.2f} m
                    </div>
                    <div class="range-item">
                        <strong>EOH:</strong> {qc_results['collar']['coord_range']['EOH']['min']:.2f} to {qc_results['collar']['coord_range']['EOH']['max']:.2f} m
                    </div>
                </div>
            </details>
        </div>
"""
        
        # Survey Data QC
        if qc_results['survey']['total_surveys'] > 0:
            html += f"""
        <h2>📐 Survey Data Quality</h2>
        <div class="section">
            <p><strong>{qc_results['survey']['total_surveys']}</strong> survey records for <strong>{qc_results['survey']['holes_with_surveys']}</strong> holes</p>
            <table>
                <tr>
                    <th>Check</th>
                    <th>Count</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>Holes without Surveys</td>
                    <td>{qc_results['survey']['holes_without_surveys']}</td>
                    <td><span class="{status_class(qc_results['survey']['holes_without_surveys'])}">{status_icon(qc_results['survey']['holes_without_surveys'])}</span></td>
                </tr>
                <tr>
                    <td>Invalid Depths/Azimuth/Dip</td>
                    <td>{qc_results['survey']['invalid_depths'] + qc_results['survey']['invalid_azimuth'] + qc_results['survey']['invalid_dip']}</td>
                    <td><span class="{status_class(qc_results['survey']['invalid_depths'] + qc_results['survey']['invalid_azimuth'] + qc_results['survey']['invalid_dip'])}">{status_icon(qc_results['survey']['invalid_depths'] + qc_results['survey']['invalid_azimuth'] + qc_results['survey']['invalid_dip'])}</span></td>
                </tr>
                <tr>
                    <td>Surveys Beyond EOH</td>
                    <td>{qc_results['survey']['surveys_beyond_eoh']}</td>
                    <td><span class="{status_class(qc_results['survey']['surveys_beyond_eoh'])}">{status_icon(qc_results['survey']['surveys_beyond_eoh'])}</span></td>
                </tr>
                <tr>
                    <td>Non-Monotonic Depths</td>
                    <td>{qc_results['survey']['non_monotonic_depths']}</td>
                    <td><span class="{status_class(qc_results['survey']['non_monotonic_depths'])}">{status_icon(qc_results['survey']['non_monotonic_depths'])}</span></td>
                </tr>
            </table>
"""
            if qc_results['survey']['surveys_beyond_eoh'] > 0:
                html += f"""
            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; color: #ff9800;">⚠ {len(qc_results['survey']['holes_beyond_eoh'])} holes with surveys beyond EOH ▼</summary>
                <div style="margin-top: 10px; padding-left: 20px;">
                    {', '.join(str(h) for h in qc_results['survey']['holes_beyond_eoh'][:20])}
                    {' ... and more' if qc_results['survey']['surveys_beyond_eoh'] > 20 else ''}
                </div>
            </details>
"""
            if qc_results['survey']['non_monotonic_depths'] > 0:
                html += f"""
            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; color: #ff9800;">⚠ {len(qc_results['survey']['holes_non_monotonic'])} holes with non-monotonic depths ▼</summary>
                <div style="margin-top: 10px; padding-left: 20px;">
                    {', '.join(str(h) for h in qc_results['survey']['holes_non_monotonic'][:20])}
                    {' ... and more' if qc_results['survey']['non_monotonic_depths'] > 20 else ''}
                </div>
            </details>
"""
            html += "        </div>\n"
        else:
            html += """
        <h2>📐 Survey Data Quality</h2>
        <div class="info-box">
            <strong>ℹ No survey data provided.</strong> Collar azimuth and dip will be used for entire hole length.
        </div>
"""
        
        # Interval Data QC
        if qc_results['interval']['total_intervals'] > 0:
            html += f"""
        <h2>📊 Interval Data Quality</h2>
        <div class="section">
            <p><strong>{qc_results['interval']['total_intervals']}</strong> intervals for <strong>{qc_results['interval']['holes_with_intervals']}</strong> holes</p>
            <table>
                <tr>
                    <th>Check</th>
                    <th>Count</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>Invalid/Inverted Intervals</td>
                    <td>{qc_results['interval']['invalid_depths'] + qc_results['interval']['inverted_intervals']}</td>
                    <td><span class="{status_class(qc_results['interval']['invalid_depths'] + qc_results['interval']['inverted_intervals'])}">{status_icon(qc_results['interval']['invalid_depths'] + qc_results['interval']['inverted_intervals'])}</span></td>
                </tr>
                <tr>
                    <td>Intervals Beyond EOH</td>
                    <td>{qc_results['interval']['intervals_beyond_eoh']}</td>
                    <td><span class="{status_class(qc_results['interval']['intervals_beyond_eoh'])}">{status_icon(qc_results['interval']['intervals_beyond_eoh'])}</span></td>
                </tr>
                <tr>
                    <td>Overlapping Intervals</td>
                    <td>{qc_results['interval']['overlapping_intervals']}</td>
                    <td><span class="{status_class(qc_results['interval']['overlapping_intervals'])}">{status_icon(qc_results['interval']['overlapping_intervals'])}</span></td>
                </tr>
                <tr>
                    <td>Gaps in Intervals</td>
                    <td>{qc_results['interval']['gaps_in_intervals']}</td>
                    <td><span class="{status_class(qc_results['interval']['gaps_in_intervals'])}">{status_icon(qc_results['interval']['gaps_in_intervals'])}</span></td>
                </tr>
            </table>
"""
            if qc_results['interval']['intervals_beyond_eoh'] > 0:
                html += f"""
            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; color: #ff9800;">⚠ {len(qc_results['interval']['holes_beyond_eoh'])} holes with intervals beyond EOH ▼</summary>
                <div style="margin-top: 10px; padding-left: 20px;">
                    {', '.join(str(h) for h in qc_results['interval']['holes_beyond_eoh'][:20])}
                    {' ... and more' if qc_results['interval']['intervals_beyond_eoh'] > 20 else ''}
                </div>
            </details>
"""
            if qc_results['interval']['overlapping_intervals'] > 0:
                html += f"""
            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; color: #ff9800;">⚠ {len(qc_results['interval']['holes_with_overlaps'])} holes with overlapping intervals ▼</summary>
                <div style="margin-top: 10px; padding-left: 20px;">
                    {', '.join(str(h) for h in qc_results['interval']['holes_with_overlaps'][:20])}
                    {' ... and more' if qc_results['interval']['overlapping_intervals'] > 20 else ''}
                </div>
            </details>
"""
            html += "        </div>\n"
        else:
            html += """
        <h2>📊 Interval Data Quality</h2>
        <div class="info-box">
            <strong>ℹ No interval data provided.</strong>
        </div>
"""
        
        # EOH Depth Variance Section
        html += f"""
        <h2>📏 End of Hole Depth Variance</h2>
        <div class="section">
            <p>Checking consistency between Collar EOH and maximum depths in Survey/Interval data.</p>
            <p><em>Note: Only variances ≥{qc_results['eoh_variance']['reporting_threshold']} m are reported below.</em></p>
            
            <table>
                <tr>
                    <th>Check</th>
                    <th>Result</th>
                    <th>Status</th>
                </tr>
                <tr>
                    <td>Holes with EOH Mismatches (any variance)</td>
                    <td>{qc_results['eoh_variance']['count']}</td>
                    <td><span class="{status_class(qc_results['eoh_variance']['count'])}">{status_icon(qc_results['eoh_variance']['count'])}</span></td>
                </tr>
                <tr>
                    <td>Survey Variances ≥{qc_results['eoh_variance']['reporting_threshold']} m</td>
                    <td>{len(qc_results['eoh_variance']['survey_variances'])}</td>
                    <td><span class="{status_class(len(qc_results['eoh_variance']['survey_variances']))}">{status_icon(len(qc_results['eoh_variance']['survey_variances']))}</span></td>
                </tr>
                <tr>
                    <td>Interval Variances ≥{qc_results['eoh_variance']['reporting_threshold']} m</td>
                    <td>{len(qc_results['eoh_variance']['interval_variances'])}</td>
                    <td><span class="{status_class(len(qc_results['eoh_variance']['interval_variances']))}">{status_icon(len(qc_results['eoh_variance']['interval_variances']))}</span></td>
                </tr>
            </table>
"""
        
        # Survey Variance Subsection
        if len(qc_results['eoh_variance']['survey_variances']) > 0:
            html += f"""
            <div class="subsection">
                <h4>Survey Data Variances (Sorted by Magnitude)</h4>
                <p>Holes where maximum survey depth differs from collar EOH by ≥{qc_results['eoh_variance']['reporting_threshold']} m</p>
                <table>
                    <tr>
                        <th>Hole ID</th>
                        <th>Collar EOH</th>
                        <th>Max Survey Depth</th>
                        <th>Variance</th>
                    </tr>
"""
            for var in qc_results['eoh_variance']['survey_variances']:
                html += f"""
                    <tr>
                        <td><strong>{var['hole_id']}</strong></td>
                        <td>{var['collar_eoh']:.2f} m</td>
                        <td>{var['max_depth']:.2f} m</td>
                        <td>{var['variance']:.2f} m</td>
                    </tr>
"""
            html += """
                </table>
            </div>
"""
        
        # Interval Variance Subsection
        if len(qc_results['eoh_variance']['interval_variances']) > 0:
            html += f"""
            <div class="subsection">
                <h4>Interval Data Variances (Sorted by Magnitude)</h4>
                <p>Holes where maximum interval depth differs from collar EOH by ≥{qc_results['eoh_variance']['reporting_threshold']} m</p>
                <table>
                    <tr>
                        <th>Hole ID</th>
                        <th>Collar EOH</th>
                        <th>Max Interval Depth</th>
                        <th>Variance</th>
                    </tr>
"""
            for var in qc_results['eoh_variance']['interval_variances']:
                html += f"""
                    <tr>
                        <td><strong>{var['hole_id']}</strong></td>
                        <td>{var['collar_eoh']:.2f} m</td>
                        <td>{var['max_depth']:.2f} m</td>
                        <td>{var['variance']:.2f} m</td>
                    </tr>
"""
            html += """
                </table>
            </div>
"""
        
        # Warning or success message
        if qc_results['eoh_variance']['count'] > 0:
            html += """
            <div class="warning-box">
                <strong>⚠ EOH Depth Variance Detected</strong><br>
                The End of Hole depth in the collar file does not match the maximum depth in survey or interval data for some holes.
                This may indicate incomplete data or data entry errors. Please verify these holes.
            </div>
"""
        else:
            html += """
            <div class="info-box" style="border-left-color: #4caf50; background-color: #e8f5e9;">
                <strong style="color: #2e7d32;">✓ All EOH depths are consistent!</strong><br>
                Collar EOH depths match the maximum survey and interval depths within tolerance.
            </div>
"""
        
        html += "        </div>\n"
        
        # Summary
        html += """
        <h2>✅ Summary</h2>
        <div class="section">
"""
        
        # Calculate overall status
        issues_found = []
        if qc_results['collar']['duplicate_ids'] > 0:
            issues_found.append(f"<span class='badge badge-error'>{qc_results['collar']['duplicate_ids']} duplicate collar IDs</span>")
        if qc_results['collar']['missing_coordinates'] > 0:
            issues_found.append(f"<span class='badge badge-error'>{qc_results['collar']['missing_coordinates']} missing coordinates</span>")
        if qc_results['collar']['zero_eoh'] > 0:
            issues_found.append(f"<span class='badge badge-error'>{qc_results['collar']['zero_eoh']} invalid EOH depths</span>")
        
        if qc_results['survey']['total_surveys'] > 0:
            if qc_results['survey']['invalid_depths'] > 0:
                issues_found.append(f"<span class='badge badge-error'>{qc_results['survey']['invalid_depths']} invalid survey depths</span>")
            if qc_results['survey']['surveys_beyond_eoh'] > 0:
                issues_found.append(f"<span class='badge badge-warning'>{qc_results['survey']['surveys_beyond_eoh']} surveys beyond EOH</span>")
            if qc_results['survey']['non_monotonic_depths'] > 0:
                issues_found.append(f"<span class='badge badge-error'>{qc_results['survey']['non_monotonic_depths']} non-monotonic survey depths</span>")
        
        if qc_results['interval']['total_intervals'] > 0:
            if qc_results['interval']['inverted_intervals'] > 0:
                issues_found.append(f"<span class='badge badge-error'>{qc_results['interval']['inverted_intervals']} inverted intervals</span>")
            if qc_results['interval']['intervals_beyond_eoh'] > 0:
                issues_found.append(f"<span class='badge badge-warning'>{qc_results['interval']['intervals_beyond_eoh']} intervals beyond EOH</span>")
            if qc_results['interval']['overlapping_intervals'] > 0:
                issues_found.append(f"<span class='badge badge-warning'>{qc_results['interval']['overlapping_intervals']} overlapping intervals</span>")
        
        if qc_results['eoh_variance']['count'] > 0:
            issues_found.append(f"<span class='badge badge-warning'>{qc_results['eoh_variance']['count']} EOH depth mismatches</span>")
        
        if not issues_found:
            html += """
            <div class="info-box" style="border-left-color: #4caf50; background-color: #e8f5e9;">
                <strong style="color: #2e7d32;">✓ All Quality Checks Passed!</strong><br>
                No critical data quality issues were found. Data is ready for processing.
            </div>
"""
        else:
            html += f"""
            <div class="warning-box">
                <strong>⚠ Issues Found:</strong><br>
                {' '.join(issues_found)}
            </div>
            <p>Please review the detailed checks above and correct any critical issues before using this data for analysis.</p>
"""
        
        html += """
        </div>
        
        <div class="timestamp">
            <p><em>This report was automatically generated by the Drill Hole Desurvey Tool.</em></p>
        </div>
    </div>
</body>
</html>
"""
        
        return html


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
if __name__ == '__main__':
    import sys
    
    # Check if GUI mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == '--gui':
        run_gui()
    elif len(sys.argv) > 1 and sys.argv[1] == '--test':
        main()
    else:
        # Default to GUI
        run_gui()
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
        ttk.Button(frame, text="Load Files & Continue", command=self.load_files, 
                  style='Accent.TButton').grid(row=11, column=0, columnspan=2, pady=20)
    
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
        
        # Run section
        run_frame = ttk.LabelFrame(frame, text="Execute", padding=10)
        run_frame.pack(fill='x')
        
        ttk.Button(run_frame, text="Run Desurvey", command=self.run_desurvey,
                  style='Accent.TButton', width=20).pack(pady=10)
        
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
            
            # Save desurvey output
            output_path = Path(self.output_dir) / "Desurvey_Output.csv"
            desurvey_df.to_csv(output_path, index=False)
            self.results_text.insert(tk.END, f"✓ Saved: {output_path}\n")
            
            # Process interval data if exists
            if interval_data is not None:
                self.results_text.insert(tk.END, f"\nProcessing {len(interval_data)} intervals...\n")
                self.root.update()
                
                interval_with_coords = desurvey.sample_desurvey_at_intervals(
                    desurvey_df, 
                    interval_data,
                    from_col='From',
                    to_col='To',
                    hole_id_col='HoleID'
                )
                
                interval_output = Path(self.output_dir) / "Interval_With_Coordinates.csv"
                interval_with_coords.to_csv(interval_output, index=False)
                self.results_text.insert(tk.END, f"✓ Saved: {interval_output}\n")
            
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


def run_gui():
    """Run the GUI application"""
    root = tk.Tk()
    app = DesurveyGUI(root)
    root.mainloop()


def main():
    """Main function for testing"""
    # Example usage
    script_dir = Path(__file__).parent
    testdata_dir = script_dir / 'testdata'
    
    # Initialize desurvey
    desurvey = DesurveyStandalone(desurvey_length=1.0, down_dip_negative=True)
    
    # Load data
    collar_df = desurvey.load_collar_data(testdata_dir / 'Collar.csv')
    survey_df = desurvey.load_survey_data(testdata_dir / 'Survey.csv')
    
    print("Collar Data:")
    print(collar_df)
    print("\nSurvey Data:")
    print(survey_df)
    
    # Desurvey all holes
    desurvey_df = desurvey.desurvey_all_holes(collar_df, survey_df)
    
    print("\nDesurvey Results:")
    print(desurvey_df)
    
    # Save to CSV
    output_file = testdata_dir / 'Desurvey_Output.csv'
    desurvey_df.to_csv(output_file, index=False)
    print(f"\nDesurvey results saved to: {output_file}")
    
    # If assay data exists, sample it
    assay_file = testdata_dir / 'Assay.csv'
    if assay_file.exists():
        assay_df = pd.read_csv(assay_file)
        assay_df.columns = assay_df.columns.str.strip()
        
        print("\nAssay Data:")
        print(assay_df.head())
        
        # Sample desurvey at assay intervals
        assay_with_coords = desurvey.sample_desurvey_at_intervals(
            desurvey_df, assay_df, from_col='From', to_col='To'
        )
        
        print("\nAssay Data with Coordinates:")
        print(assay_with_coords.head())
        
        # Save to CSV
        assay_output = testdata_dir / 'Assay_With_Coordinates.csv'
        assay_with_coords.to_csv(assay_output, index=False)
        print(f"\nAssay with coordinates saved to: {assay_output}")


if __name__ == '__main__':
    import sys
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--gui':
            # Launch GUI mode
            run_gui()
        elif sys.argv[1] == '--help' or sys.argv[1] == '-h':
            print("Drill Hole Desurvey Tool")
            print("\nUsage:")
            print("  python desurvey_standalone.py           # Run test with sample data")
            print("  python desurvey_standalone.py --gui     # Launch GUI interface")
            print("  python desurvey_standalone.py --help    # Show this help")
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        # Default: run test with sample data
        print("Running desurvey test with sample data...")
        print("(Use --gui to launch the graphical interface)\n")
        main()
