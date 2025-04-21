import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from strava_api import StravaAPI, get_access_token
import json
import time
from pytz import UTC
import os

def get_credentials(file_path='strava_id.txt'):
    """
    Read Strava API credentials from a file
    Returns: tuple of (client_id, client_secret)
    """
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()
            credentials = {}
            for line in lines:
                if '=' in line:
                    key, value = line.strip().split('=')
                    credentials[key.strip()] = value.strip()
            
            if 'client_id' not in credentials or 'client_secret' not in credentials:
                raise ValueError("Missing required credentials in file")
            
            return credentials['client_id'], credentials['client_secret']
    except FileNotFoundError:
        print(f"Error: Credentials file '{file_path}' not found.")
        print("Please create a file named 'strava_id.txt' with your credentials in the format:")
        print("client_id = your_client_id")
        print("client_secret = your_client_secret")
        exit(1)
    except Exception as e:
        print(f"Error reading credentials: {str(e)}")
        exit(1)

def analyze_training_data(strava_api, start_date=None, end_date=None):
    """
    Analyze training data and create insights for next season planning
    """
    print("Fetching activities from Strava...")
    # Get all activities
    all_activities = []
    page = 1
    
    # Convert dates to UTC if provided
    if start_date:
        start_date = pd.to_datetime(start_date).tz_localize(UTC)
    if end_date:
        end_date = pd.to_datetime(end_date).tz_localize(UTC)
    
    while True:
        print(f"Fetching page {page}...", end='\r')
        try:
            activities = strava_api.get_activities(per_page=100, page=page)
            
            if not activities:  # If no activities returned
                print("\nNo more activities found")
                break
                
            # Check if we've reached activities before our start date
            if start_date and activities:  # Only proceed if we have activities
                last_activity = activities[-1]  # Get the last activity
                if 'start_date' in last_activity:  # Check if start_date exists
                    last_activity_date = pd.to_datetime(last_activity['start_date'])
                    if last_activity_date < start_date:
                        # Only keep activities within our date range
                        filtered_activities = [a for a in activities 
                                            if 'start_date' in a and 
                                            pd.to_datetime(a['start_date']) >= start_date]
                        if filtered_activities:  # Only extend if we have activities in our date range
                            all_activities.extend(filtered_activities)
                        break
                
            all_activities.extend(activities)
            page += 1
            
            # Add a small delay to avoid rate limiting
            time.sleep(1)
            
        except Exception as e:
            print(f"\nError fetching activities: {str(e)}")
            break
    
    print(f"\nFetched {len(all_activities)} activities")
    
    if not all_activities:
        print("No activities found in the specified date range")
        return None, None

    # Convert to DataFrame
    print("Processing data...")
    try:
        df = pd.DataFrame(all_activities)
        
        # Check if we have the required columns
        required_columns = ['start_date', 'distance', 'moving_time', 'total_elevation_gain']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            print(f"Missing required columns: {missing_columns}")
            return None, None
        
        # Convert date strings to datetime (they're already UTC from Strava)
        df['start_date'] = pd.to_datetime(df['start_date'])
        
        # Filter by date range if provided
        if start_date:
            df = df[df['start_date'] >= start_date]
        if end_date:
            df = df[df['start_date'] <= end_date]
        
        if len(df) == 0:
            print("No activities found after filtering by date range")
            return None, None
        
        # Calculate additional metrics
        df['week'] = df['start_date'].dt.isocalendar().week
        df['month'] = df['start_date'].dt.month
        df['year'] = df['start_date'].dt.year
        
        # Group by week and calculate metrics
        print("Calculating weekly statistics...")
        weekly_stats = df.groupby(['year', 'week']).agg({
            'distance': 'sum',
            'moving_time': 'sum',
            'total_elevation_gain': 'sum',
            'id': 'count'
        }).reset_index()
        
        weekly_stats.columns = ['year', 'week', 'total_distance_km', 'total_time_minutes', 
                              'total_elevation_meters', 'number_of_activities']
        
        # Convert units
        weekly_stats['total_distance_km'] = weekly_stats['total_distance_km'] / 1000
        weekly_stats['total_time_hours'] = weekly_stats['total_time_minutes'] / 60
        
        # Calculate intensity (distance/time)
        weekly_stats['average_speed_kmh'] = weekly_stats['total_distance_km'] / weekly_stats['total_time_hours']
        
        # Save to CSV
        print("Saving results...")
        weekly_stats.to_csv('training_analysis.csv', index=False)
        
        # Generate summary statistics
        summary = {
            'total_weeks': len(weekly_stats),
            'average_weekly_distance': weekly_stats['total_distance_km'].mean(),
            'max_weekly_distance': weekly_stats['total_distance_km'].max(),
            'average_weekly_time': weekly_stats['total_time_hours'].mean(),
            'average_weekly_activities': weekly_stats['number_of_activities'].mean(),
            'total_elevation': weekly_stats['total_elevation_meters'].sum(),
            'average_speed': weekly_stats['average_speed_kmh'].mean()
        }
        
        # Save summary to JSON
        with open('training_summary.json', 'w') as f:
            json.dump(summary, f, indent=2)
        
        return weekly_stats, summary
        
    except Exception as e:
        print(f"Error processing data: {str(e)}")
        return None, None

def plot_training_data(weekly_stats):
    """
    Create visualization of training data
    """
    print("Creating visualizations...")
    plt.figure(figsize=(15, 10))
    
    # Create a proper x-axis label combining year and week
    x_labels = [f"{row['year']}-W{row['week']}" for _, row in weekly_stats.iterrows()]
    
    # Plot 1: Weekly Distance
    plt.subplot(2, 2, 1)
    plt.bar(x_labels, weekly_stats['total_distance_km'], color='skyblue')
    plt.title('Weekly Distance (km)')
    plt.xlabel('Week')
    plt.ylabel('Distance (km)')
    plt.xticks(rotation=45)
    
    # Plot 2: Weekly Time
    plt.subplot(2, 2, 2)
    plt.bar(x_labels, weekly_stats['total_time_hours'], color='lightgreen')
    plt.title('Weekly Training Time (hours)')
    plt.xlabel('Week')
    plt.ylabel('Time (hours)')
    plt.xticks(rotation=45)
    
    # Plot 3: Number of Activities
    plt.subplot(2, 2, 3)
    plt.bar(x_labels, weekly_stats['number_of_activities'], color='salmon')
    plt.title('Number of Activities per Week')
    plt.xlabel('Week')
    plt.ylabel('Number of Activities')
    plt.xticks(rotation=45)
    
    # Plot 4: Average Speed
    plt.subplot(2, 2, 4)
    plt.bar(x_labels, weekly_stats['average_speed_kmh'], color='gold')
    plt.title('Average Speed (km/h)')
    plt.xlabel('Week')
    plt.ylabel('Speed (km/h)')
    plt.xticks(rotation=45)
    
    plt.tight_layout()
    plt.savefig('training_analysis.png')

def get_date_input(prompt):
    while True:
        try:
            date_str = input(prompt)
            # Try to parse the date
            date = datetime.strptime(date_str, '%Y-%m-%d')
            return date_str
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD format (e.g., 2024-01-01)")

if __name__ == "__main__":
    print("Starting training analysis...")
    
    # Get credentials from file
    client_id, client_secret = get_credentials()
    
    # Get access token using OAuth
    print("\nGetting access token...")
    token_data = get_access_token(client_id, client_secret)
    
    if token_data and 'access_token' in token_data:
        # Initialize Strava API with the new access token
        strava = StravaAPI(token_data['access_token'])
        
        # Get date range from user
        # print("\nEnter the date range for analysis (format: YYYY-MM-DD)")
        # end_date = get_date_input("Enter end date (e.g., 2024-06-02): ")
        # start_date = get_date_input("Enter start date (e.g., 2023-06-02): ")

        end_date = "2025-04-21"
        start_date = "2024-09-01"
        
        print(f"\nAnalyzing data from {start_date} to {end_date}")
        
        # Analyze training data
        weekly_stats, summary = analyze_training_data(strava, start_date, end_date)
        
        if weekly_stats is not None:
            plt.close()
            # Create visualizations
            plot_training_data(weekly_stats)
            
            
            print("\nTraining Analysis Summary:")
            print(f"Total weeks analyzed: {summary['total_weeks']}")
            print(f"Average weekly distance: {summary['average_weekly_distance']:.2f} km")
            print(f"Maximum weekly distance: {summary['max_weekly_distance']:.2f} km")
            print(f"Average weekly training time: {summary['average_weekly_time']:.2f} hours")
            print(f"Average number of activities per week: {summary['average_weekly_activities']:.2f}")
            print(f"Total elevation gain: {summary['total_elevation']:.2f} meters")
            print(f"Average speed: {summary['average_speed']:.2f} km/h")
            
            print("\nData has been saved to:")
            print("- training_analysis.csv (detailed weekly data)")
            print("- training_summary.json (summary statistics)")
            print("- training_analysis.png (visualizations)")
        else:
            print("No data was analyzed. Please check your access token and date range.")
    else:
        print("Failed to get access token. Please check your client ID and secret.") 