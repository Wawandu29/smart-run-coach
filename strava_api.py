import requests
import json
from datetime import datetime
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse

class StravaAPI:
    def __init__(self, access_token=None):
        self.access_token = access_token
        self.base_url = "https://www.strava.com/api/v3"
        self.headers = {}
        if access_token:
            self.headers = {
                'Authorization': f'Bearer {self.access_token}'
            }

    def get_athlete(self):
        """Get the authenticated athlete's profile"""
        endpoint = f"{self.base_url}/athlete"
        response = requests.get(endpoint, headers=self.headers)
        return response.json()

    def get_activities(self, per_page=30, page=1):
        """Get the authenticated athlete's activities"""
        endpoint = f"{self.base_url}/athlete/activities"
        params = {
            'per_page': per_page,
            'page': page
        }
        response = requests.get(endpoint, headers=self.headers, params=params)
        return response.json()

    def get_activity(self, activity_id):
        """Get a specific activity by ID"""
        endpoint = f"{self.base_url}/activities/{activity_id}"
        response = requests.get(endpoint, headers=self.headers)
        return response.json()

class OAuthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        # Parse the query parameters
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'code' in params:
            code = params['code'][0]
            self.server.auth_code = code
            self.wfile.write(b"Authentication successful! You can close this window.")
        else:
            self.wfile.write(b"Authentication failed. Please try again.")

def get_access_token(client_id, client_secret):
    # Start a local server to receive the OAuth callback
    server = HTTPServer(('localhost', 8000), OAuthHandler)
    server.auth_code = None
    
    # Open the authorization URL in the default browser
    auth_url = f"http://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri=http://localhost:8000&approval_prompt=force&scope=activity:read_all"
    webbrowser.open(auth_url)
    
    # Wait for the authorization code
    server.handle_request()
    
    if server.auth_code:
        # Exchange the authorization code for an access token
        token_url = "https://www.strava.com/oauth/token"
        data = {
            'client_id': client_id,
            'client_secret': client_secret,
            'code': server.auth_code,
            'grant_type': 'authorization_code'
        }
        response = requests.post(token_url, data=data)
        return response.json()
    return None

# Example usage:
if __name__ == "__main__":
    # Replace these with your actual client ID and secret
    CLIENT_ID = "153827"
    CLIENT_SECRET = "e555d7e76a0de078a3d6eac98fd4e84705e76b0c"
    
    # Get a new access token
    token_data = get_access_token(CLIENT_ID, CLIENT_SECRET)
    if token_data:
        print("Access Token:", token_data['access_token'])
        print("Refresh Token:", token_data['refresh_token'])
        
        # Initialize the API with the new access token
        strava = StravaAPI(token_data['access_token'])
        
        # Get athlete profile
        try:
            athlete = strava.get_athlete()
            print("\nAthlete Profile:")
            print(json.dumps(athlete, indent=2))
        except Exception as e:
            print(f"Error getting athlete profile: {e}")
        
        # Get recent activities
        try:
            print(strava.base_url)
            activities = strava.get_activities(per_page=5)
            print("\nRecent Activities:")
            if isinstance(activities, list):
                for activity in activities:
                    if isinstance(activity, dict):
                        print(f"{activity.get('name', 'No name')} - {activity.get('distance', 0)/1000:.2f}km")
                    else:
                        print(f"Unexpected activity format: {type(activity)}")
            else:
                print(f"Unexpected response format: {type(activities)}")
        except Exception as e:
            print(f"Error getting activities: {e}")
    else:
        print("Failed to get access token") 